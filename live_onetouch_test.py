import sys
import os

# Add the project's src directory to sys.path
# This ensures that the 'iaqualink' module can be found when running the script directly,
# especially if the editable install isn't adding it to sys.path as expected.
_project_root = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.join(_project_root, "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

import asyncio
import logging

from iaqualink import AqualinkClient
from iaqualink.systems.iaqua.system import IaquaSystem # To ensure isinstance check works
from iaqualink.exception import AqualinkServiceException

# --- Configuration ---
# !!! IMPORTANT: Fill these in with your actual credentials and serial number !!!
USERNAME = "YOUR_EMAIL_HERE"
PASSWORD = "YOUR_PASSWORD_HERE"
TARGET_SERIAL = "YOUR_SYSTEM_SERIAL_HERE"
ONETOUCH_INDEX_TO_TEST = 6

# --- Logging Setup ---
# You can adjust the logging level if needed (e.g., logging.DEBUG for more detail)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting OneTouch live test script.")

    if USERNAME == "YOUR_EMAIL_HERE" or PASSWORD == "YOUR_PASSWORD_HERE" or TARGET_SERIAL == "YOUR_SYSTEM_SERIAL_HERE":
        logger.error("Please update USERNAME, PASSWORD, and TARGET_SERIAL in the script before running.")
        return

    # client = AqualinkClient(username=USERNAME, password=PASSWORD)
    # Using async context manager for client session handling
    async with AqualinkClient(username=USERNAME, password=PASSWORD) as client:
        try:
            logger.info(f"Attempting to log in as {USERNAME}...")
            # Login is handled by __aenter__ when using async context manager
            # await client.login() 
            if not client.logged:
                 # This should not happen if __aenter__ succeeds without raising an exception
                logger.error("Client did not log in successfully through context manager.")
                return
            logger.info("Login successful.")

            logger.info("Fetching all available systems...")
            systems = await client.get_systems()
            
            if not systems:
                logger.warning("No systems found for this account.")
                return

            logger.info(f"Found {len(systems)} system(s): {list(systems.keys())}")

            target_system = None
            for serial, system_obj in systems.items():
                if serial == TARGET_SERIAL:
                    if isinstance(system_obj, IaquaSystem):
                        target_system = system_obj
                        logger.info(f"Found target iAqualink system: {TARGET_SERIAL}")
                        break
                    else:
                        logger.warning(f"System {TARGET_SERIAL} found, but it's not an IaquaSystem (type: {type(system_obj).__name__}). Skipping OneTouch tests.")
                        return
            
            if not target_system:
                logger.error(f"Target system with serial {TARGET_SERIAL} not found in the account.")
                return

            logger.info(f"--- Testing OneTouch for system: {target_system.name} ({target_system.serial}) ---")

            logger.info(f"Fetching initial OneTouch state for index {ONETOUCH_INDEX_TO_TEST} (and others)...")
            initial_onetouch_state = await target_system.get_onetouch()
            logger.info(f"Initial OneTouch states: {initial_onetouch_state}")
            
            initial_switch = next((s for s in initial_onetouch_state if s.get("index") == ONETOUCH_INDEX_TO_TEST), None)
            if initial_switch:
                logger.info(f"Initial state of OneTouch {ONETOUCH_INDEX_TO_TEST} ('{initial_switch.get('label')}'): State={initial_switch.get('state')}, Status={initial_switch.get('status')}")
            else:
                logger.warning(f"OneTouch index {ONETOUCH_INDEX_TO_TEST} not found in initial state.")

            logger.info(f"Attempting to toggle OneTouch index {ONETOUCH_INDEX_TO_TEST}...")
            try:
                updated_onetouch_state_after_set = await target_system.set_onetouch(ONETOUCH_INDEX_TO_TEST)
                logger.info(f"Successfully called set_onetouch({ONETOUCH_INDEX_TO_TEST}).")
                logger.info(f"OneTouch states after toggle: {updated_onetouch_state_after_set}")

                final_switch = next((s for s in updated_onetouch_state_after_set if s.get("index") == ONETOUCH_INDEX_TO_TEST), None)
                if final_switch:
                    logger.info(f"New state of OneTouch {ONETOUCH_INDEX_TO_TEST} ('{final_switch.get('label')}'): State={final_switch.get('state')}, Status={final_switch.get('status')}")
                else:
                    logger.warning(f"OneTouch index {ONETOUCH_INDEX_TO_TEST} not found in state after toggle.")

            except AqualinkServiceException as e_toggle:
                logger.error(f"Error toggling OneTouch index {ONETOUCH_INDEX_TO_TEST}: {e_toggle}")
            except Exception as e_toggle_unexpected:
                logger.error(f"An unexpected error occurred while toggling OneTouch: {e_toggle_unexpected}", exc_info=True)

        except AqualinkServiceException as e_service:
            logger.error(f"An AqualinkServiceException occurred: {e_service}")
        except Exception as e_general:
            logger.error(f"An unexpected error occurred: {e_general}", exc_info=True)
    # No finally needed here as the async context manager handles client.close()
    logger.info("Live test script finished.")

if __name__ == "__main__":
    logger.warning("This script is for live testing and contains placeholder credentials.")
    logger.warning("Ensure you fill them in and DO NOT commit this file with real credentials.")
    asyncio.run(main()) 