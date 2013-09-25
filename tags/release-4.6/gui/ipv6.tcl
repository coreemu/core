#
# Copyright 2005-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

#
# Copyright 2005-2008 University of Zagreb, Croatia.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# This work was supported in part by Croatian Ministry of Science
# and Technology through the research contract #IP-2003-143.
#

#****h* imunes/ipv6.tcl
# NAME
#   ipv6.tcl -- file for handeling IPv6
#****

#****f* ipv6.tcl/findFreeIPv6Net
# NAME
#   findFreeIPv6Net -- find free IPv6 network
# SYNOPSIS
#   set ipnet [findFreeIPv4Net $mask]
# FUNCTION
#   Finds a free IPv6 network. Network is concidered to be free
#   if there are no simulated nodes attached to it. 
# INPUTS
#   * mask -- this parameter is left unused for now
# RESULT
#   * ipnet -- returns the free IPv6 network address in the form "a $i". 
#****
 
proc findFreeIPv6Net { mask } {
    global g_prefs node_list

    set ipnets {}
    foreach node $node_list {
	foreach ifc [ifcList $node] {
	    set ipparts [split [getIfcIPv6addr $node $ifc] :]
	    set endidx [expr {[lsearch $ipparts {}] - 1}]
	    if {$endidx < 0 } { set endidx end }
	    set ipnet [lrange $ipparts 0 $endidx]
	    if {[lsearch $ipnets $ipnet] == -1} {
		lappend ipnets $ipnet
	    }
	}
    }
    # include mobility newlinks in search
    foreach newlink [.c find withtag "newlink"] {
        set ipnet [lrange [split [lindex [.c gettags $newlink] 5] :] 0 3]
	lappend ipnets $ipnet
    }
    if {![info exists g_prefs(gui_ipv6_addr)]} { setDefaultAddrs ipv6 }
    set newnet [split $g_prefs(gui_ipv6_addr) :]
    set endidx [expr {[lsearch $newnet {}] - 1}]
    if {$endidx < 0 } { set endidx end }
    set newnet [lrange $newnet 0 $endidx]
    
    for { set i 0 } { $i <= 9999 } { incr i } {
	if {[lsearch $ipnets "$newnet $i"] == -1} {
	    set newnetcolon [join $newnet :]
	    set ipnet "$newnetcolon:$i"
	    return $ipnet
	}
    }
}

#****f* ipv6.tcl/autoIPv6addr 
# NAME
#   autoIPv6addr -- automaticaly assign an IPv6 address
# SYNOPSIS
#   autoIPv6addr $node_id $iface 
# FUNCTION
#   automaticaly assignes an IPv6 address to the interface $iface of 
#   of the node $node.
# INPUTS
#   * node_id -- the node containing the interface to witch a new 
#     IPv6 address should be assigned
#   * iface -- the interface to witch a new, automatilacy generated, IPv6  
#     address will be assigned
#****

proc autoIPv6addr { node iface } {
    set peer_ip6addrs {}
    set netmaskbits 64 ;# default
    setIfcIPv6addr $node $iface ""

    set peer_node [logicalPeerByIfc $node $iface]
    # find addresses of NETWORK layer peer nodes
    if { [[typemodel $peer_node].layer] == "LINK" } {
	foreach l2node [listLANnodes $peer_node {}] {
	    foreach ifc [ifcList $l2node] {
		set peer [logicalPeerByIfc $l2node $ifc]
		set peer_if [ifcByLogicalPeer $peer $l2node]
		set peer_ip6addr [getIfcIPv6addr $peer $peer_if]
		if { $peer_ip6addr != "" } {
		    lappend peer_ip6addrs [lindex [split $peer_ip6addr /] 0]
		    set netmaskbits [lindex [split $peer_ip6addr /] 1]
		}
	    }
	}
    # point-to-point link with another NETWORK layer peer
    } else {
	set peer_if [ifcByLogicalPeer $peer_node $node]
	set peer_ip6addr [getIfcIPv6addr $peer_node $peer_if]
	set peer_ip6addrs [lindex [split $peer_ip6addr /] 0]
	if { $peer_ip6addr != "" } {
	    set netmaskbits [lindex [split $peer_ip6addr /] 1]
	}
    }
    # Boeing: first node connected to wlan should use wlan prefix
    if { [nodeType $peer_node] == "wlan" && 
    	 [llength $peer_ip6addrs] == 0 } {
	# use the special "wireless" pseudo-interface
	set peer_ip6addr [getIfcIPv6addr $peer_node wireless]
	set peer_ip6addrs [lindex [split $peer_ip6addr /] 0]
	set netmaskbits [lindex [split $peer_ip6addr /] 1]
    }
    set nodetype [nodeType $node]
    if { $nodetype == "router" } { set nodetype [getNodeModel $node] }
    switch -exact -- $nodetype {
	router {
	    set targetbyte 1
	}
	host {
	    set targetbyte 10
	}
	PC -
	pc {
	    set targetbyte 20
	}
	default {
	    set targetbyte 1
	}
    }
    # peer has an IPv6 address, allocate a new address on the same network
    if { $peer_ip6addrs != "" } {
	set net [ipv6ToNet [lindex $peer_ip6addrs 0] 64]
	set ipaddr $net\::$targetbyte
	while { [lsearch $peer_ip6addrs $ipaddr] >= 0 } {
	    incr targetbyte
	    set ipaddr $net\::$targetbyte
	}
	setIfcIPv6addr $node $iface "$ipaddr/$netmaskbits"
    } else {
	set ipnet [findFreeIPv6Net 64]
	setIfcIPv6addr $node $iface "${ipnet}::$targetbyte/$netmaskbits"
    }
}

#****f* ipv6.tcl/autoIPv6defaultroute 
# NAME
#   autoIPv6defaultroute -- automaticaly assign a default route 
# SYNOPSIS
#   autoIPv6defaultroute $node_id $iface 
# FUNCTION
#   searches the interface of the node for a router, if a router is found
#   then it is a new default gateway. 
# INPUTS
#   * node_id -- default gateway is provided for this node 
#   * iface -- the interface on witch we search for a new default gateway
#****

proc autoIPv6defaultroute { node iface } {
    if { [[typemodel $node].layer] != "NETWORK" } {
	#
	# Shouldn't get called at all for link-layer nodes
	#
	puts "autoIPv6defaultroute called for [[typemodel $node].layer] node"
	return
    }

    set peer_node [logicalPeerByIfc $node $iface]

    if { [[typemodel $peer_node].layer] == "LINK" } {
	foreach l2node [listLANnodes $peer_node {}] {
	    foreach ifc [ifcList $l2node] {
		set peer [logicalPeerByIfc $l2node $ifc]
		if { [nodeType $peer] != "router" && 
		     [nodeType $peer] != "ine" } {
		    continue
		}
		set peer_if [ifcByLogicalPeer $peer $l2node]
		set peer_ip6addr [getIfcIPv6addr $peer $peer_if]
		if { $peer_ip6addr != "" } {
		    set gw [lindex [split $peer_ip6addr /] 0]
		    setStatIPv6routes $node [list "::/0 $gw"]
		    return
		}
	    }
	}
    } else {
	if { [nodeType $peer_node] != "router" && 
	     [nodeType $peer_node] != "ine" } {
	    return
	}
	set peer_if [ifcByLogicalPeer $peer_node $node]
	set peer_ip6addr [getIfcIPv6addr $peer_node $peer_if]
	if { $peer_ip6addr != "" } {
	    set gw [lindex [split $peer_ip6addr /] 0]
	    setStatIPv6routes $node [list "::/0 $gw"]
	    return
	}
    }
}

#****f* ipv6.tcl/checkIPv6Addr 
# NAME
#   checkIPv6Addr -- check the IPv6 address 
# SYNOPSIS
#   set valid [checkIPv6Addr $str]
# FUNCTION
#   Checks if the provided string is a valid IPv6 address. 
# INPUTS
#   * str -- string to be evaluated.
# RESULT
#   * valid -- function returns 0 if the input string is not in the form
#     of a valid IP address, 1 otherwise
#****

proc checkIPv6Addr { str } {
    set doublec false
    set wordlist [split $str :]
    set wordcnt [expr [llength $wordlist] - 1]
    if { $wordcnt < 2 || $wordcnt > 7 } {
	return 0
    }
    if { [lindex $wordlist 0] == "" } {
	set wordlist [lreplace $wordlist 0 0 0]
    }
    if { [lindex $wordlist $wordcnt] == "" } {
	set wordlist [lreplace $wordlist $wordcnt $wordcnt 0]
    }
    for { set i 0 } { $i <= $wordcnt } { incr i } {
	set word [lindex $wordlist $i]
	if { $word == "" } {
	    if { $doublec == "true" } {
		return 0
	    }
	    set doublec true
	}
	if { [string length $word] > 4 } {
	    if { $i == $wordcnt } {
		return [checkIPv4Addr $word]
	    } else {
		return 0
	    }
	}
	if { [string is xdigit $word] == 0 } {
	    return 0
	}
    }
    return 1
}

#****f* ipv6.tcl/checkIPv6Net 
# NAME
#   checkIPv6Net -- check the IPv6 network 
# SYNOPSIS
#   set valid [checkIPv6Net $str]
# FUNCTION
#   Checks if the provided string is a valid IPv6 network. 
# INPUTS
#   * str -- string to be evaluated. Valid string is in form ipv6addr/m 
# RESULT
#   * valid -- function returns 0 if the input string is not in the form
#     of a valid IP address, 1 otherwise.
#****

proc checkIPv6Net { str } {
    if { $str == "" } {
	return 1
    }
    if { ![checkIPv6Addr [lindex [split $str /] 0]]} {
	return 0
    }
    set net [string trim [lindex [split $str /] 1]]
    if { [string length $net] == 0 } {
	return 0
    }
    return [checkIntRange $net 0 128]
}


#
# Boeing
# ***** ipv6.tcl/ipv6ToString
# NAME
#  ipv6ToString -- convert 128-bit number to colon notation
# ****

proc ipv6ToString { ip } {
    set ipv6nums {}
    #binary format c16 H16
    set prevbyte ""
    set prevword ""
    set have_double_colon 0
    foreach byte $ip {
	# group bytes into two-byte hex words
	set hexbyte [format "%x" [expr $byte & 0xFF]]
	if { $prevbyte == "" } {
	    set prevbyte $hexbyte
	} else {
	    if { $prevbyte == 0 } { ;# compress zeroes
		set prevbyte ""
		set hexbyte [format "%x" 0x$hexbyte]
	    } else {
		set hexbyte [format "%02x" 0x$hexbyte]
	    }
	    set twobytes "$prevbyte$hexbyte"
	    set prevbyte ""

	    # compress subsequent zeroes into ::, but only once
	    if { $twobytes == 0 } {
	        if { !$have_double_colon && $prevword == 0} {
		    # replace last 0 with :
		    set ipv6nums [lreplace $ipv6nums end end ""] 
		    set have_double_colon 1
		    set prevword ":"
		    continue ;# don't add current 0 word to list
		} elseif { $prevword == ":" } {
		    continue ;# another zero word, skip it
		}
	    }
	    set prevword $twobytes
    	    lappend ipv6nums $twobytes
	}
    }
    return [join $ipv6nums :]
}

#
# Boeing
# ***** ipv6.tcl/stringToIPv6
# NAME
#  stringToIPv6 -- convert colon notation to 128-bits of binary data
# ****

proc stringToIPv6 { ip } {
    set ip [expandIPv6 $ip]; # remove any double-colon notation
    set parts [split $ip :]

    if { [llength $parts] != 8 } { return "" }; # sanity check
    set bin ""

    foreach part $parts {
	scan $part "%x" num; # convert hex to number
	set binpart [binary format i $num]
	set bin ${bin}${binpart}
    }

    return $bin
}

# expand from double-colon shorthand notation to include all zeros
proc expandIPv6 { ip } {
    set parts [split $ip :]
    set partnum 0
    set expand {}
    set num_zeros 0
    while { [llength $parts] > 0 } {
	set part [lindex $parts 0]; 	# pop off first element
	set parts [lreplace $parts 0 0]

	if {$part == ""} { ; # this is the :: part of the address
	    set num_parts_remain [llength $parts]
	    if { $num_zeros > 0 } { ; # another empty element, another zero
		lappend expand 0
		continue
	    }
	    set num_zeros [expr { 8 - ($partnum + $num_parts_remain) }]
	    for { set i 0 } { $i < $num_zeros } { incr i } {
		lappend expand 0
	    }
	    continue;
	}
	lappend expand $part
	incr partnum
    }
    return [join $expand :]
}

#
# Boeing
# ***** ipv6.tcl/ipv6ToNet
# NAME
#  ipv6ToNet -- convert IPv6 address a.b.c.d to a.b.c 
# ****

proc ipv6ToNet { ip mask } {
	set ipv6nums [split $ip :] 
	# last remove last to nums of :: num
	set ipv6parts [lrange $ipv6nums 0 [expr [llength $ipv6nums] - 3]]
    	return [join $ipv6parts :]
}

# 
# Boeing
# ***** ipv6.tcl/autoIPv6wlanaddr
# NAME
#  autoIPv6wlanaddr -- part of autoIPv6addr to determine
#  address for node connected to the wlan
# ****
proc autoIPv6wlanaddr { node } {

	# search wlan node for peers, collect IP address into list
	set peer_ip6addrs ""
        foreach ifc [ifcList $node] {
		set peer [logicalPeerByIfc $node $ifc]
		set peer_if [ifcByLogicalPeer $peer $node]
		set peer_ip6addr [getIfcIPv6addr $peer $peer_if]
		if { $peer_ip6addr != "" } {
		    lappend peer_ip6addrs [lindex [split $peer_ip6addr /] 0]
		}
	}
	if { $peer_ip6addrs != "" } {
            set ipnums [split [lindex $peer_ip6addrs 0] :]
            set net "[lindex $ipnums 0]:[lindex $ipnums 1]"
	    set targetbyte 1
            set ipaddr $net\::$targetbyte
            while { [lsearch $peer_ip6addrs $ipaddr] >= 0 } {
                incr targetbyte
                set ipaddr $net\::$targetbyte
            }
	} else {
	    set ipnums [split [getIfcIPv6addr $node wireless] :]
            set net "[lindex $ipnums 0]:[lindex $ipnums 1]"
	    set ipaddr $net\::1
	}
        return "$ipaddr/64"
}

proc getDefaultIPv6Addrs { } {
    global g_prefs
    return [list "2001::" "2002::" "a::"]
}

proc ipv6List { node wantmask } {
    set r ""
    foreach ifc [ifcList $node] {
	foreach ip [getIfcIPv6addr $node $ifc] {
	    if { $wantmask } {
		lappend r $ip
	    } else {
		lappend r [lindex [split $ip /] 0]
	    }
	}
    }
    return $r
}

