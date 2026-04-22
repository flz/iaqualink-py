from __future__ import annotations

AQUALINK_API_KEY = "EOOEMOW4YR6QNB07"

AQUALINK_LOGIN_URL = "https://prod.zodiac-io.com/users/v1/login"
AQUALINK_REFRESH_URL = "https://prod.zodiac-io.com/users/v1/refresh"
AQUALINK_DEVICES_URL = "https://r-api.iaqualink.net/devices.json"

KEEPALIVE_EXPIRY = 30
DEFAULT_REQUEST_TIMEOUT = 10.0

RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0
RETRY_AFTER_MAX_DELAY = 60.0
