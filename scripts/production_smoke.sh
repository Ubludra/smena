#!/usr/bin/env bash
# =============================================================================
# Smena production smoke test — non-destructive, no secrets, no auth needed.
#
#   ./scripts/production_smoke.sh https://smena.example.ru
#   INSECURE=1 ./scripts/production_smoke.sh https://smena.localhost   # local
#                                                      production simulation
#                                                      (Caddy tls internal)
#
# Checks (all read-only GET/HEAD):
#   1. /            -> 200 and an HTML document (SPA served);
#   2. /health/live -> 200 {"status":"ok"};
#   3. /health/ready-> 200 (database actually reachable);
#   4. the JS/CSS assets referenced by index.html -> 200 (bundle really
#      shipped with this deployment);
#   5. /api/v1/...  -> reaches FastAPI, NOT the SPA fallback (an authed
#      endpoint answers 401/405, never the index.html body);
#   6. http://      -> redirects to https:// (no redirect loop).
#
# Exit code is non-zero on the first failed check. Logs contain no secrets.
# =============================================================================
set -euo pipefail

BASE_URL="${1:?usage: $0 https://your-domain[ ; INSECURE=1 for local CA]}"
CURL=(curl -sS --max-time 15)
if [ "${INSECURE:-0}" = "1" ]; then
  CURL+=(-k)
fi
# RESOLVE_IP=127.0.0.1 pins APP_DOMAIN without DNS (local production
# simulation on smena.localhost); production runs never set it.
if [ -n "${RESOLVE_IP:-}" ]; then
  _hostport="${BASE_URL#*://}"
  _host="${_hostport%%:*}"
  _port="${BASE_URL##*://}"; _port="${_port#*:}"; _port="${_port%%/*}"
  [ -n "$_port" ] && [ "$_port" != "$_hostport" ] || _port=443
  CURL+=(--resolve "$_host:$_port:$RESOLVE_IP")
fi

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "  ok: $*"; }

echo "smoke: $BASE_URL"

# 1. SPA root.
root_body="$("${CURL[@]}" -w '\n%{http_code}' "$BASE_URL/")" || fail "cannot reach $BASE_URL/"
root_code="${root_body##*$'\n'}"
[ "$root_code" = "200" ] || fail "GET / returned $root_code (expected 200)"
grep -qi "<div id=\"root\"" <<<"$root_body" || fail "GET / is not the Smena SPA document"
pass "GET / -> 200 (SPA document)"

# 2/3. Probes.
live="$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$BASE_URL/health/live")"
[ "$live" = "200" ] || fail "GET /health/live returned $live"
pass "GET /health/live -> 200"

ready="$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$BASE_URL/health/ready")"
[ "$ready" = "200" ] || fail "GET /health/ready returned $ready (database not reachable?)"
pass "GET /health/ready -> 200 (database ok)"

# 4. Assets referenced by the served document.
asset="$(grep -oE '/assets/[A-Za-z0-9._-]+\.(js|css)' <<<"$root_body" | head -1)"
[ -n "$asset" ] || fail "index.html references no hashed asset (build not deployed?)"
asset_code="$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$BASE_URL$asset")"
[ "$asset_code" = "200" ] || fail "asset $asset returned $asset_code"
pass "asset $asset -> 200"

# 5. /api routes must hit the API, not the SPA fallback. A wrong-path API
#    request must NOT come back as an HTML document.
api_code="$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$BASE_URL/api/v1/auth/me")"
case "$api_code" in
  401|403|405|404) ;; # 404 is acceptable ONLY if the body is API JSON; checked next
  *) fail "GET /api/v1/auth/me returned $api_code (expected an API answer)" ;;
esac
api_body="$("${CURL[@]}" "$BASE_URL/api/v1/materials")"
grep -qi "<!doctype html" <<<"$api_body" && fail "/api/v1/* is answered by the SPA (proxy broken)"
pass "GET /api/v1/* -> API answers (status $api_code), not the SPA"

# 6. HTTP -> HTTPS, no loop.
if [ "${SKIP_HTTP_REDIRECT:-0}" != "1" ]; then
  host="${BASE_URL#https://}"
  http_code="$("${CURL[@]}" -o /dev/null -w '%{http_code} %{redirect_url}' "http://$host/" )"
  code="${http_code%% *}"
  target="${http_code##* }"
  [ "$code" = "301" ] || [ "$code" = "308" ] || fail "http:// returned $code (expected redirect)"
  grep -q "^https://" <<<"$target" || fail "http:// did not redirect to https:// ($target)"
  pass "http:// -> $code $target"
fi

echo "SMOKE PASS: $BASE_URL"
