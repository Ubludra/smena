"""Container healthcheck script.

Array-form Dockerfile/compose HEALTHCHECK commands are safer as a file than
as an inline `python -c "..."`: shell word-splitting (Podman's compose
emulation in particular) can mangle `-c` one-liners — a real failure we hit
on this host, which made a healthy service report unhealthy.
"""

import sys
import urllib.request

URL = "http://127.0.0.1:8000/health/live"

try:
    with urllib.request.urlopen(URL, timeout=3) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
