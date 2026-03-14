#!/bin/sh
set -eu

WG_IFACE="${WG_CLIENT_INTERFACE:-wg-egress}"
WG_CONF="/etc/wireguard/${WG_IFACE}.conf"
WG_RUNTIME_DIR="/run/wireguard"
WG_RUNTIME_CONF="${WG_RUNTIME_DIR}/${WG_IFACE}.conf"
# WG users subnet coming from container #1
WG_USERS_SUBNET="${WG_SERVER_SUBNET:-10.66.0.0/24}"

apk add --no-cache wireguard-tools iptables iproute2

if [ ! -f "$WG_CONF" ]; then
  echo "Missing $WG_CONF (place external WG client config there)" >&2
  exit 1
fi

mkdir -p "$WG_RUNTIME_DIR"

# Build runtime config to avoid common container issues:
# 1) remove DNS= lines (wg-quick tries resolvconf/systemd and fails in minimal containers)
# 2) enforce Table=off (prevents wg-quick from trying sysctl src_valid_mark on read-only /proc/sys)
awk '
  BEGIN {in_if=0; saw_table=0}
  /^[[:space:]]*\[Interface\][[:space:]]*$/ {in_if=1; print; next}
  /^[[:space:]]*\[/ {if (in_if && !saw_table) print "Table = off"; in_if=0}
  {
    if (in_if && $1=="Table") saw_table=1
    if (in_if && $1=="DNS") next
    print
  }
  END {if (in_if && !saw_table) print "Table = off"}
' "$WG_CONF" > "$WG_RUNTIME_CONF"

chmod 600 "$WG_RUNTIME_CONF"

wg-quick up "$WG_RUNTIME_CONF"

# Policy-route only traffic from WG users subnet to the external WG interface.
ip route replace default dev "$WG_IFACE" table 51820
ip rule add from "$WG_USERS_SUBNET" lookup 51820 priority 100 2>/dev/null || true

# NAT traffic from container #1 / WG users into the external WG tunnel.
iptables -t nat -A POSTROUTING -o "$WG_IFACE" -j MASQUERADE
iptables -A FORWARD -i eth0 -o "$WG_IFACE" -j ACCEPT
iptables -A FORWARD -i "$WG_IFACE" -o eth0 -m state --state RELATED,ESTABLISHED -j ACCEPT

echo "WG egress configured: ${WG_USERS_SUBNET} -> ${WG_IFACE} (Table=51820)" >&2

exec tail -f /dev/null
