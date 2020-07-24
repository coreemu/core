# -------- CUSTOMIZATION REQUIRED --------
#
# Below are sample iptables firewall rules that you can uncomment and edit.
# You can also use ip6tables rules for IPv6.
#

# start by flushing all firewall rules (so this script may be re-run)
#iptables -F

# allow traffic related to established connections
#iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# allow TCP packets from any source destined for 192.168.1.1
#iptables -A INPUT -s 0/0 -i eth0 -d 192.168.1.1  -p TCP -j ACCEPT

# allow OpenVPN server traffic from eth0
#iptables -A INPUT -p udp --dport 1194 -j ACCEPT
#iptables -A INPUT -i eth0 -j DROP
#iptables -A OUTPUT -p udp --sport 1194 -j ACCEPT
#iptables -A OUTPUT -o eth0 -j DROP

# allow ICMP ping traffic
#iptables -A OUTPUT -p icmp --icmp-type echo-request -j ACCEPT
#iptables -A INPUT  -p icmp --icmp-type echo-reply   -j ACCEPT

# allow SSH traffic
#iptables -A -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT

# drop all other traffic coming in eth0
#iptables -A INPUT -i eth0 -j DROP
