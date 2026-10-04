#!/bin/sh
set -eu
# Analyst UID 1000 can only reach the loopback proxy; its direct TCP/UDP is denied.
iptables -P INPUT DROP
iptables -P OUTPUT DROP
iptables -P FORWARD DROP
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -i lo -p tcp --dport 3128 -j ACCEPT
iptables -A OUTPUT -m owner --uid-owner 1000 -d 127.0.0.1 -p tcp --dport 3128 -j ACCEPT
iptables -A OUTPUT -m owner --uid-owner 1001 -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -m owner --uid-owner 1001 -d "$DNS_SERVER" -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -m owner --uid-owner 1001 -d "$DNS_SERVER" -p tcp --dport 53 -j ACCEPT
# Drop setup capabilities irreversibly before processing any untrusted CONNECT request.
exec setpriv --reuid=1001 --regid=1001 --clear-groups --bounding-set=-all \
    --inh-caps=-all --ambient-caps=-all --no-new-privs python3 /opt/proxy.py
