#!/bin/bash
# scut-webhook.sh — Called by rsyslog omprog when a SCUT notification arrives.
# Install on TKD01SVR: copy to /usr/local/bin/scut-webhook.sh ; chmod +x
#
# Usage (called by rsyslog): scut-webhook.sh <InstanceName>
# Reads syslog lines from stdin (omprog protocol) and fires HTTP POSTs to the
# target instance's SCUT listener.
#
# Endpoint map MUST match skills/scut/endpoints.json. If /etc/scut/endpoints.json
# exists, it is used as the source of truth; otherwise the embedded map below is
# used. Keep them in sync.

INSTANCE="$1"

# --- Resolve endpoint: prefer deployed endpoints.json, else embedded map ---
ENDPOINTS_JSON="${SCUT_ENDPOINTS:-/etc/scut/endpoints.json}"
ENDPOINT=""

if [ -f "$ENDPOINTS_JSON" ] && command -v python3 >/dev/null 2>&1; then
    ENDPOINT=$(python3 - "$ENDPOINTS_JSON" "$INSTANCE" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    ep = d.get("instances", {}).get(sys.argv[2])
    if ep:
        print(f"{ep['host']}:{ep['port']}")
except Exception:
    pass
PY
)
fi

if [ -z "$ENDPOINT" ]; then
    # Embedded fallback — keep in sync with endpoints.json
    declare -A ENDPOINTS
    ENDPOINTS[Bob]="TKD14PC:8514"
    ENDPOINTS[Spock]="TKD01AI:8514"
    ENDPOINTS[Watson]="TKD12PC:8514"
    ENDPOINTS[Deckard]="TKD15PC:8514"
    ENDPOINTS[Leon]="TKD02AI:8514"
    ENDPOINTS[Bill]="tkd01vm:8514"
    ENDPOINTS[Milo]="tkd04ai:8514"
    ENDPOINT="${ENDPOINTS[$INSTANCE]}"
fi

if [ -z "$ENDPOINT" ]; then
    echo "$(date -Iseconds) Unknown instance: $INSTANCE" >> /var/log/scut-errors.log
    exit 0
fi

# omprog feeds lines via stdin — read and process each
while IFS= read -r line; do
    # Syslog format: "... scut: SCUT:<target> from=<sender> type=<type> [nonce=.. scope=.. replyto=..]"
    SENDER=$(echo "$line"  | grep -oP 'from=\K[^ ]+'    || echo "unknown")
    TYPE=$(echo "$line"    | grep -oP 'type=\K[^ ]+'    || echo "notify")
    NONCE=$(echo "$line"   | grep -oP 'nonce=\K[^ ]+'   || echo "")
    SCOPE=$(echo "$line"   | grep -oP 'scope=\K[^ ]+'   || echo "")
    REPLYTO=$(echo "$line" | grep -oP 'replyto=\K[^ ]+' || echo "$SENDER")

    PAYLOAD="{\"from\":\"$SENDER\",\"type\":\"$TYPE\",\"source\":\"syslog\""
    [ -n "$NONCE" ]   && PAYLOAD="$PAYLOAD,\"nonce\":\"$NONCE\""
    [ -n "$SCOPE" ]   && PAYLOAD="$PAYLOAD,\"scope\":\"$SCOPE\""
    [ -n "$REPLYTO" ] && PAYLOAD="$PAYLOAD,\"replyto\":\"$REPLYTO\""
    PAYLOAD="$PAYLOAD}"

    curl -s -X POST "http://$ENDPOINT/notify" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        --connect-timeout 3 \
        --max-time 5 \
        >> /var/log/scut-webhook.log 2>&1 || true

    echo "$(date -Iseconds) Webhook fired: $INSTANCE ($ENDPOINT) from=$SENDER type=$TYPE scope=$SCOPE nonce=$NONCE" >> /var/log/scut-webhook.log
done
