#!/bin/bash
set -euo pipefail

WG_IFACE="${WG_SERVER_INTERFACE:-wg0}"
WG_PORT="${WG_SERVER_PORT:-51820}"
WG_ADDR="${WG_SERVER_ADDRESS:-10.66.0.1/24}"
WG_PRIVKEY="${WG_SERVER_PRIVATE_KEY:-}"
WG_SUBNET="${WG_SERVER_SUBNET:-10.66.0.0/24}"
WG_CLIENT_GATEWAY_IP="${WG_CLIENT_GATEWAY_IP:-172.30.0.2}"
WG_CLIENT_EGRESS_IFACE="${WG_CLIENT_EGRESS_IFACE:-eth0}"

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

# Route traffic from bot-created peers to egress container (#2).
ip route replace "$WG_SUBNET" dev "$WG_IFACE" || true
ip route replace default via "$WG_CLIENT_GATEWAY_IP" dev "$WG_CLIENT_EGRESS_IFACE" table 51820
ip rule add from "$WG_SUBNET" lookup 51820 priority 100 2>/dev/null || true

iptables -A FORWARD -i "$WG_IFACE" -o "$WG_CLIENT_EGRESS_IFACE" -j ACCEPT
iptables -A FORWARD -i "$WG_CLIENT_EGRESS_IFACE" -o "$WG_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT

cd /app

if [[ -x /docker-entrypoint.sh ]]; then
  exec /docker-entrypoint.sh
fi

if [[ -f main.py ]]; then
  exec python main.py
fi

if [[ -f bot.py ]]; then
  exec python bot.py
fi

if compgen -G "*.py" >/dev/null; then
  first_py=$(ls -1 *.py | head -n1)
  exec python "$first_py"
fi

echo "Cannot find bot стартовый файл in /app (expected main.py/bot.py)" >&2
exec tail -f /dev/null
