#!/bin/bash
set -euo pipefail

WG_IFACE="${WG_SERVER_INTERFACE:-wg0}"
WG_PORT="${WG_SERVER_PORT:-51820}"
WG_ADDR="${WG_SERVER_ADDRESS:-10.66.0.1/24}"
WG_PRIVKEY="${WG_SERVER_PRIVATE_KEY:-}"
WG_SUBNET="${WG_SERVER_SUBNET:-10.66.0.0/24}"
WG_CLIENT_GATEWAY_IP="${WG_CLIENT_GATEWAY_IP:-172.30.0.2}"
# optional override; if empty script auto-detects iface to gateway
WG_CLIENT_EGRESS_IFACE="${WG_CLIENT_EGRESS_IFACE:-}"
BOT_HTTP_PORT="${BOT_HTTP_PORT:-8081}"
PROXY_BIND_IP="${PROXY_BIND_IP:-172.31.0.10}"

mkdir -p /etc/wireguard
chmod 700 /etc/wireguard

if [[ -n "$WG_PRIVKEY" && ! -f "/etc/wireguard/${WG_IFACE}.conf" ]]; then
  cat > "/etc/wireguard/${WG_IFACE}.conf" <<EOF
[Interface]
Address = ${WG_ADDR}
ListenPort = ${WG_PORT}
PrivateKey = ${WG_PRIVKEY}
SaveConfig = true
EOF
fi

if [[ ! -f "/etc/wireguard/${WG_IFACE}.conf" ]]; then
  echo "Missing /etc/wireguard/${WG_IFACE}.conf (mount it or set WG_SERVER_PRIVATE_KEY)" >&2
  exit 1
fi

wg-quick up "$WG_IFACE"

if [[ -z "$WG_CLIENT_EGRESS_IFACE" ]]; then
  # On container startup docker routes may appear slightly later.
  for _ in $(seq 1 30); do
    WG_CLIENT_EGRESS_IFACE="$(ip -4 route get "$WG_CLIENT_GATEWAY_IP" 2>/dev/null | awk '/dev/ {for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}')"
    [[ -n "$WG_CLIENT_EGRESS_IFACE" ]] && break
    sleep 1
  done
fi

if [[ -z "$WG_CLIENT_EGRESS_IFACE" ]]; then
  echo "Cannot detect egress interface for gateway $WG_CLIENT_GATEWAY_IP" >&2
  ip -4 route show >&2 || true
  exit 1
fi

# Route traffic from bot-created peers to egress container (#2).
ip route replace "$WG_SUBNET" dev "$WG_IFACE" || true
# Avoid intermittent "Nexthop has invalid gateway" by letting kernel resolve the
# proper L2 path first; fall back to explicit dev when needed.
ip route replace default via "$WG_CLIENT_GATEWAY_IP" table 51820 \
  || ip route replace default via "$WG_CLIENT_GATEWAY_IP" dev "$WG_CLIENT_EGRESS_IFACE" table 51820
ip rule add from "$WG_SUBNET" lookup 51820 priority 100 2>/dev/null || true

iptables -A FORWARD -i "$WG_IFACE" -o "$WG_CLIENT_EGRESS_IFACE" -j ACCEPT
iptables -A FORWARD -i "$WG_CLIENT_EGRESS_IFACE" -o "$WG_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT

echo "WG routing configured: ${WG_SUBNET} -> via ${WG_CLIENT_GATEWAY_IP} dev ${WG_CLIENT_EGRESS_IFACE}" >&2

cd /app

BOT_CMD=()
if [[ -x /docker-entrypoint.sh ]]; then
  BOT_CMD=(/docker-entrypoint.sh)
elif [[ -f main.py ]]; then
  BOT_CMD=(python main.py)
elif [[ -f bot.py ]]; then
  BOT_CMD=(python bot.py)
elif compgen -G "*.py" >/dev/null; then
  first_py=$(ls -1 *.py | head -n1)
  BOT_CMD=(python "$first_py")
else
  echo "Cannot find bot стартовый файл in /app (expected main.py/bot.py)" >&2
  exec tail -f /dev/null
fi

# Some bot versions bind webhook server to 127.0.0.1 only.
# Expose that loopback listener on proxy network IP so Traefik can reach it.
if command -v socat >/dev/null 2>&1; then
  socat "TCP-LISTEN:${BOT_HTTP_PORT},bind=${PROXY_BIND_IP},fork,reuseaddr" "TCP:127.0.0.1:${BOT_HTTP_PORT}" >/tmp/socat-webhook.log 2>&1 &
  echo "Webhook bridge enabled: ${PROXY_BIND_IP}:${BOT_HTTP_PORT} -> 127.0.0.1:${BOT_HTTP_PORT}" >&2
fi

exec "${BOT_CMD[@]}"
