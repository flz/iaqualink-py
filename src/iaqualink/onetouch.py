from typing import Any, Dict, List

def parse_onetouch_response(data: dict[str, Any]) -> List[dict[str, Any]]:
    """Parse the onetouch_screen response into a list of switches with label, state, and status."""
    switches = []
    for item in data.get("onetouch_screen", []):
        # Each item is a dict with a key like 'onetouch_1', 'onetouch_2', etc.
        key = next(iter(item.keys()), None)
        if key and key.startswith("onetouch_"):
            # Each value is a list of dicts with 'status', 'state', 'label'
            switch_info = {d_k: d_v for d in item[key] for d_k, d_v in d.items()}
            switch_info["index"] = int(key.split("_")[-1])
            switches.append(switch_info)
    return switches