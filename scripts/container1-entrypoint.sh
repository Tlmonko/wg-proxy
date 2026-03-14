#!/bin/sh
set -eu

WG_IFACE="${WG_SERVER_INTERFACE:-wg0}"
WG_PORT="${WG_SERVER_PORT:-51820}"
WG_ADDR="${WG_SERVER_ADDRESS:-10.66.0.1/24}"
WG_PRIVKEY="${WG_SERVER_PRIVATE_KEY:-}"
WG_SUBNET="${WG_SERVER_SUBNET:-10.66.0.0/24}"
WG_CLIENT_GATEWAY_IP="${WG_CLIENT_GATEWAY_IP:-172.30.0.2}"
WG_CLIENT_EGRESS_IFACE="${WG_CLIENT_EGRESS_IFACE:-eth0}"

if ! command -v wg >/dev/null 2>&1 || ! command -v iptables >/dev/null 2>&1; then
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache wireguard-tools iptables iproute2
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update && apt-get install -y --no-install-recommends wireguard-tools iptables iproute2
  else
    echo "Cannot install wireguard/iptables tools automatically" >&2
    exit 1
  fi
fi

mkdir -p /etc/wireguard
chmod 700 /etc/wireguard

if [ -n "$WG_PRIVKEY" ] && [ ! -f "/etc/wireguard/${WG_IFACE}.conf" ]; then
  cat > "/etc/wireguard/${WG_IFACE}.conf" <<EOF
[Interface]
Address = ${WG_ADDR}
ListenPort = ${WG_PORT}
PrivateKey = ${WG_PRIVKEY}
SaveConfig = true
EOF
fi

if [ ! -f "/etc/wireguard/${WG_IFACE}.conf" ]; then
  echo "Missing /etc/wireguard/${WG_IFACE}.conf (mount it or set WG_SERVER_PRIVATE_KEY)" >&2
  exit 1
fi

wg-quick up "$WG_IFACE"

# Route all user traffic from WG server subnet to container #2.
ip route replace "$WG_SUBNET" dev "$WG_IFACE" || true
ip route replace default via "$WG_CLIENT_GATEWAY_IP" dev "$WG_CLIENT_EGRESS_IFACE" table 51820
ip rule add from "$WG_SUBNET" lookup 51820 priority 100 || true

# Explicit forward rules: wg users -> container #2 and back.
iptables -A FORWARD -i "$WG_IFACE" -o "$WG_CLIENT_EGRESS_IFACE" -j ACCEPT
iptables -A FORWARD -i "$WG_CLIENT_EGRESS_IFACE" -o "$WG_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT

# Start bot process from image defaults if available.
if [ -x /docker-entrypoint.sh ]; then
  exec /docker-entrypoint.sh
elif [ -f /app/main.py ]; then
  exec python3 /app/main.py
else
  # Keep container alive for debugging if bot entrypoint is unknown.
  exec tail -f /dev/null
fi
