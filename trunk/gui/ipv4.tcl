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

#****h* imunes/ipv4.tcl
# NAME
#   ipv4.tcl -- file for handeling IPv4
#****

#****f* ipv4.tcl/findFreeIPv4Net
# NAME
#   findFreeIPv4Net -- find free IPv4 network
# SYNOPSIS
#   set ipnet [findFreeIPv4Net $mask]
# FUNCTION
#   Finds a free IPv4 network. Network is concidered to be free
#   if there are no simulated nodes attached to it. 
# INPUTS
#   * mask -- this parameter is left unused for now
# RESULT
#   * ipnet -- returns the free IPv4 network address in the form 10.a.b 
#****
 
proc findFreeIPv4Net { mask } {
    global g_prefs node_list

    set ipnets {}
    foreach node $node_list {
	foreach ifc [ifcList $node] {
	    set ipnet [lrange [split [getIfcIPv4addr $node $ifc] .] 0 2]
	    if {[lsearch $ipnets $ipnet] == -1} {
		lappend ipnets $ipnet
	    }
	}
    }
    # include mobility newlinks in search
    foreach newlink [.c find withtag "newlink"] {
        set ipnet [lrange [split [lindex [.c gettags $newlink] 4] .] 0 2]
	lappend ipnets $ipnet
    }
    if {![info exists g_prefs(gui_ipv4_addr)]} { setDefaultAddrs ipv4 }
    set abc [split $g_prefs(gui_ipv4_addr) .]
    set a [lindex $abc 0]
    set b [lindex $abc 1]
    set c [lindex $abc 2]

    for { set i $b } { $i <= 255 } { incr i } {
	for { set j $c } { $j <= 255 } { incr j } {
	    if {[lsearch $ipnets "$a $i $j"] == -1} {
		set ipnet "$a.$i.$j"
		return $ipnet
	    }
	}
    }
}

#****f* ipv4.tcl/autoIPv4addr 
# NAME
#   autoIPv4addr -- automaticaly assign an IPv4 address
# SYNOPSIS
#   autoIPv4addr $node $iface 
# FUNCTION
#   automaticaly assignes an IPv4 address to the interface $iface of 
#   of the node $node  
# INPUTS
#   * node -- the node containing the interface to which a new 
#     IPv4 address should be assigned
#   * iface -- the interface to witch a new, automatilacy generated, IPv4  
#     address will be assigned
#****

proc autoIPv4addr { node iface } {
    set peer_ip4addrs {}
    set netmaskbits 24 ;# default

    if { [[typemodel $node].layer] != "NETWORK" } {
	#
	# Shouldn't get called at all for link-layer nodes
	#
	puts "autoIPv4 called for a [[typemodel $node].layer] layer node"
	return
    }
    setIfcIPv4addr $node $iface ""

    set peer_node [logicalPeerByIfc $node $iface]
    # find addresses of NETWORK layer peer nodes
    if { [[typemodel $peer_node].layer] == "LINK" } {
	foreach l2node [listLANnodes $peer_node {}] {
	    foreach ifc [ifcList $l2node] {
		set peer [logicalPeerByIfc $l2node $ifc]
		set peer_if [ifcByLogicalPeer $peer $l2node]
		set peer_ip4addr [getIfcIPv4addr $peer $peer_if]
		if { $peer_ip4addr != "" } {
		    lappend peer_ip4addrs [lindex [split $peer_ip4addr /] 0]
		    set netmaskbits [lindex [split $peer_ip4addr /] 1]
		}
	    }
	}
    # point-to-point link with another NETWORK layer peer
    } else {
	set peer_if [ifcByLogicalPeer $peer_node $node]
	set peer_ip4addr [getIfcIPv4addr $peer_node $peer_if]
	set peer_ip4addrs [lindex [split $peer_ip4addr /] 0]
	if { $peer_ip4addr != "" } {
	    set netmaskbits [lindex [split $peer_ip4addr /] 1]
	}
    }
    # first node connected to wlan should use wlan prefix
    if { [nodeType $peer_node] == "wlan" && 
    	 [llength $peer_ip4addrs] == 0 } {
	# use the special "wireless" pseudo-interface
	set peer_ip4addr [getIfcIPv4addr $peer_node wireless]
	set peer_ip4addrs [lindex [split $peer_ip4addr /] 0]
	set netmaskbits [lindex [split $peer_ip4addr /] 1]
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
    # peer has an IPv4 address, allocate a new address on the same network
    if { $peer_ip4addrs != "" } {
	set ipnums [split [lindex $peer_ip4addrs 0] .]
	set net "[lindex $ipnums 0].[lindex $ipnums 1].[lindex $ipnums 2]"
	set ipaddr $net.$targetbyte
	while { [lsearch $peer_ip4addrs $ipaddr] >= 0 } {
	    incr targetbyte
	    set ipaddr $net.$targetbyte
	}
	setIfcIPv4addr $node $iface "$ipaddr/$netmaskbits"
    } else {
	set ipnet [findFreeIPv4Net 24]
	setIfcIPv4addr $node $iface "$ipnet.$targetbyte/$netmaskbits"
    }
}


#****f* ipv4.tcl/autoIPv4defaultroute 
# NAME
#   autoIPvdefaultroute -- automaticaly assign a default route 
# SYNOPSIS
#   autoIPv4defaultroute $node $iface 
# FUNCTION
#   searches the interface of the node for a router, if a router is found
#   then it is a new default gateway. 
# INPUTS
#   * node  -- default gateway is provided for this node 
#   * iface -- the interface on witch we search for a new default gateway
#****

proc autoIPv4defaultroute { node iface } {
    if { [[typemodel $node].layer] != "NETWORK" } {
	#
	# Shouldn't get called at all for link-layer nodes
	#
	puts "autoIPv4defaultroute called for [[typemodel $node].layer] node"
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
		set peer_ip4addr [getIfcIPv4addr $peer $peer_if]
		if { $peer_ip4addr != "" } {
		    set gw [lindex [split $peer_ip4addr /] 0]
		    setStatIPv4routes $node [list "0.0.0.0/0 $gw"]
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
	set peer_ip4addr [getIfcIPv4addr $peer_node $peer_if]
	if { $peer_ip4addr != "" } {
	    set gw [lindex [split $peer_ip4addr /] 0]
	    setStatIPv4routes $node [list "0.0.0.0/0 $gw"]
	    return
	}
    }
}


#****f* ipv4.tcl/checkIPv4Addr 
# NAME
#   checkIPv4Addr -- check the IPv4 address 
# SYNOPSIS
#   set valid [checkIPv4Addr $str]
# FUNCTION
#   Checks if the provided string is a valid IPv4 address. 
# INPUTS
#   * str -- string to be evaluated. Valid IPv4 address is writen in form
#     a.b.c.d 
# RESULT
#   * valid -- function returns 0 if the input string is not in the form
#     of a valid IP address, 1 otherwise
#****

proc checkIPv4Addr { str } {
    set n 0
    if { $str == "" } {
	return 1
    }
    while { $n < 4 } {
	if { $n < 3 } {
	    set i [string first . $str]
	} else {
	    set i [string length $str]
	}
	if { $i < 1 } {
	    return 0
	}
	set part [string range $str 0 [expr $i - 1]]
	if { [string length [string trim $part]] != $i } {
	    return 0
	}
	if { ![string is integer $part] } {
	    return 0
	}
	if { $part < 0 || $part > 255 } {
	    return 0
	}
	set str [string range $str [expr $i + 1] end]
	incr n
    }
    return 1
}


#****f* ipv4.tcl/checkIPv4Net 
# NAME
#   checkIPv4Net -- check the IPv4 network 
# SYNOPSIS
#   set valid [checkIPv4Net $str]
# FUNCTION
#   Checks if the provided string is a valid IPv4 network. 
# INPUTS
#   * str -- string to be evaluated. Valid string is in form a.b.c.d/m 
# RESULT
#   * valid -- function returns 0 if the input string is not in the form
#     of a valid IP address, 1 otherwise
#****

proc checkIPv4Net { str } {
    if { $str == "" } {
	return 1
    }
    if { ![checkIPv4Addr [lindex [split $str /] 0]]} {
	return 0
    }
    set net [string trim [lindex [split $str /] 1]]
    if { [string length $net] == 0 } {
	return 0
    }
    return [checkIntRange $net 0 32]
}

#
# Boeing
# ***** ipv4.tcl/ipv4ToString
# NAME
#  ipv4ToString -- convert 32-bit integer to dotted decimal notation
# ****

proc ipv4ToString { ip } {
	return "[expr ($ip >> 24) & 0xFF].[expr ($ip >> 16) & 0xFF].[expr ($ip >> 8) & 0xFF].[expr $ip & 0xFF]"
}

#
# Boeing
# ***** ipv4.tcl/stringToIPv4
# NAME
#  stringToIPv4 -- convert dotted decimal string to 32-bit integer 
proc stringToIPv4 { ip } {
    set parts [split $ip .]
    set a [lindex $parts 0]; set b [lindex $parts 1];
    set c [lindex $parts 2]; set d [lindex $parts 3];
    return [expr {(($a << 24) + ($b << 16) + ($c << 8) + $d ) & 0xFFFFFFFF}]
}


proc ipv4ToNet { ip prefixlen } {
    set ipn [stringToIPv4 $ip]
    set ones [string repeat 1 $prefixlen]
    set zeroes [string repeat 0 [expr {32 - $prefixlen}]]
    binary scan [binary format B32 $ones$zeroes] H8 mask
    set netn [expr {$ipn & "0x$mask"}]
    return [ipv4ToString $netn]
}

proc getDefaultIPv4Addrs { } {
    global g_prefs
    return [list "10.0.0.0" "192.168.0.0" "172.16.0.0"]
}

proc isMulticast { str } {
    set i [string first . $str]
    if { $i < 1 } { return false }
    set part [string range $str 0 [expr {$i - 1}]]
    if { ![string is integer $part] } { return false }
    if { $part < 224 || $part > 239 } { return false }
    return true
}

proc ipv4List { node wantmask } {
    set r ""
    foreach ifc [ifcList $node] {
	foreach ip [getIfcIPv4addr $node $ifc] {
	    if { $wantmask } {
		lappend r $ip
	    } else {
		lappend r [lindex [split $ip /] 0]
	    }
	}
    }
    return $r
}


# this can be called with node_list to get a list of all subnets
proc ipv4SubnetList { nodes } {
    set r ""
    foreach node $nodes {
	foreach ipnet [ipv4List $node 1] {
	    set ip [lindex [split $ipnet /] 0]
	    set pl [lindex [split $ipnet /] 1]
	    set net "[ipv4ToNet $ip $pl]/$pl"
	    if { [lsearch $r $net] < 0 } {
		lappend r $net
	    }
	}
    }
    return $r
}
