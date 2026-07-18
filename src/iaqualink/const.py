from __future__ import annotations

AQUALINK_API_KEY = "EOOEMOW4YR6QNB07"
AQUALINK_API_SIGNING_KEY = "cj7iYKjiKxOqiLcN65PffA"

AQUALINK_LOGIN_URL = "https://prod.zodiac-io.com/users/v1/login"
AQUALINK_REFRESH_URL = "https://prod.zodiac-io.com/users/v1/refresh"
AQUALINK_DEVICES_URL = "https://r-api.iaqualink.net/v2/devices.json"

# Shared Zodiac WebSocket endpoint (robot cleaners, tcx). The https:// scheme is
# upgraded to wss:// by httpx-ws.
AQUALINK_WS_URL = "https://prod-socket.zodiac-io.com/devices"

KEEPALIVE_EXPIRY = 30
DEFAULT_REQUEST_TIMEOUT = 10.0
WS_ACK_TIMEOUT = 2.0
