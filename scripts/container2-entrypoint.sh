#!/bin/sh
set -eu

WG_IFACE="${WG_CLIENT_INTERFACE:-wg-egress}"
WG_CONF="/etc/wireguard/${WG_IFACE}.conf"

apk add --no-cache wireguard-tools iptables iproute2

if [ ! -f "$WG_CONF" ]; then
  echo "Missing $WG_CONF (place external WG client config there)" >&2
  exit 1
fi

wg-quick up "$WG_IFACE"

# NAT traffic from container #1 / WG users into the external WG tunnel.
iptables -t nat -A POSTROUTING -o "$WG_IFACE" -j MASQUERADE
iptables -A FORWARD -i eth0 -o "$WG_IFACE" -j ACCEPT
iptables -A FORWARD -i "$WG_IFACE" -o eth0 -m state --state RELATED,ESTABLISHED -j ACCEPT

exec tail -f /dev/null
