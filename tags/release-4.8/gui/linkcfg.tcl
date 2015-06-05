#
# Copyright 2005-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

#
# Copyright 2004-2008 University of Zagreb, Croatia.
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

#****h* imunes/linkcfg.tcl
# NAME
#  linkcfg.tcl -- file used for manipultaion with links in IMUNES
# FUNCTION
#  This module is used to define all the actions used for configuring 
#  links in IMUNES. 
#
# NOTES
# 
# linkPeers { link_id }
#	Returns node_ids of link endpoints
#
# linkByPeers { node1_id node2_id }
#	Returns link_id whose peers are node1 and node2
#
# removeLink { link_id }
#	Removes the link and related entries in peering node's configs
#
# getLinkBandwidth { link_id }
#	... in bits per second
#
# getLinkBandwidthString { link_id }
#	... as string 
#
# getLinkDelay { link_id }
#	... in microseconds
#
# getLinkDelayString { link_id }
#	... as sting
#
# setLinkBandwidth { link_id bandwidth }
#	... in bits per second
#
# setLinkDelay { link_id delay }
#	... in microseconds
#
# All of the above functions are independent to any Tk objects. This means
# they can be used for implementing tasks external to GUI, yet inside the
# GUI any updating of related Tk objects (such as text labels etc.) will
# have to be implemented by additional Tk code.
#****

#****f* linkcfg.tcl/linkPeers
# NAME
#   linkPeers -- get link's peer nodes
# SYNOPSIS
#   set link_peers [linkPeers $link_id]
# FUNCTION
#   Returns node_ids of link endpoints.
# INPUTS
#   * link_id -- link id
# RESULT
#   * link_peers -- returns nodes_ids of a link endpoints 
#     in a list {node1_id node2_id}
#****

proc linkPeers { link } {
    global $link

    set entry [lsearch -inline [set $link] "nodes {*}"]
    return [lindex $entry 1]
}

#****f* linkcfg.tcl/linkByPeers
# NAME
#   linkByPeers -- get link id from peer nodes
# SYNOPSIS
#   set link_id [linkByPeers $node1_id $node2_id]
# FUNCTION
#   Returns link_id whose peers are node1 and node2. 
#   The order of input nodes is irrelevant.
# INPUTS
#   * node1_id -- node id of the first node
#   * node2_id -- node id of the second node
# RESULT
#   * link_id -- returns id of a link connecting endpoints 
#     node1_id node2_id. 
#****

proc linkByPeers { node1 node2 } {
    global link_list

    foreach link $link_list {
	set peers [linkPeers $link]
	if { $peers == "$node1 $node2" || $peers == "$node2 $node1" } {
	    return $link
	}
    }
}

# same as linkByPeers but for links split across canvases
proc linkByPeersMirror { node1 node2 } {
    foreach ifc [ifcList $node1] {
	set link [lindex [linkByIfc $node1 $ifc] 0]
	set mirror [getLinkMirror $link]
	if { $mirror != "" } {
	    set peers [linkPeers $mirror]
	    # link node 1 is real node, link node 2 is always pseudo-node
	    if { [lindex $peers 0] == $node2 } {
		return $link
	    }
	}
    }
    return ""
}

#****f* linkcfg.tcl/removeLink
# NAME
#   removeLink -- removes a link.
# SYNOPSIS
#   removeLink $link_id
# FUNCTION
#   Removes the link and related entries in peering node's configs.
#   Updates the default route for peer nodes. 
# INPUTS
#   * link_id -- link id
#****

proc removeLink { link } {
    global link_list $link

    set pnodes [linkPeers $link]
    foreach node $pnodes {
	global $node
	set i [lsearch $pnodes $node]
	set peer [lreplace $pnodes $i $i]
	set ifc [ifcByPeer $node $peer]
	netconfClearSection $node "interface $ifc"
	set i [lsearch [set $node] "interface-peer {$ifc $peer}"]
	set $node [lreplace [set $node] $i $i]
    }
    set i [lsearch -exact $link_list $link]
    set link_list [lreplace $link_list $i $i]
}

#****f* linkcfg.tcl/getLinkBandwidth
# NAME
#   getLinkBandwidth -- get link bandwidth
# SYNOPSIS
#   set bandwidth [getLinkBandwidth $link_id]
# FUNCTION
#   Returns the link bandwidth expressed in bits per second.
# INPUTS
#   * link_id -- link id
# RESULT
#   * bandwidth -- The value of link bandwidth in bits per second.
#****

proc getLinkBandwidth { link {dir "down"} } {
    global $link

    set entry [lsearch -inline [set $link] "bandwidth *"]
    set val [lindex $entry 1] ;# one or more values
    if { $dir == "up" } { return [lindex $val 1] }
    return [lindex $val 0]
}

#****f* linkcfg.tcl/getLinkBandwidthString
# NAME
#   getLinkBandwidthString -- get link bandwidth string
# SYNOPSIS
#   set bandwidth_str [getLinkBandwidthString $link_id]
# FUNCTION
#   Returns the link bandwidth in form of a number an a mesure unit.
#   Measure unit is automaticaly asigned depending on the value of bandwidth.
# INPUTS
#   * link_id -- link id
# RESULT
#   * bandwidth_str -- The value of link bandwidth formated in a sting 
#     containing a measure unit.
#****

proc getLinkBandwidthString { link } {
    global $link
    set bandstr ""
    set sep ""
    set bandwidth [getLinkBandwidth $link]
    set bandwidthup [getLinkBandwidth $link up]
    if { $bandwidthup > 0 } {
	set bandwidth [list $bandwidth $bandwidthup]
	set sep " / "
    }
    foreach bw $bandwidth {
	if { $bandstr != "" } { set bandstr "$bandstr$sep" }
	set bandstr "$bandstr[getSIStringValue $bw "bps"]"
    }
    return $bandstr
}

proc getSIStringValue { val suffix } {
    if { $val <= 0 } {
	return ""
    }
    if { $val >= 660000000 } {
	return "[format %.2f [expr {$val / 1000000000.0}]] G$suffix"
    } elseif { $val >= 99000000 } {
	return "[format %d [expr {$val / 1000000}]] M$suffix"
    } elseif { $val >= 9900000 } {
	return "[format %.2f [expr {$val / 1000000.0}]] M$suffix"
    } elseif { $val >= 990000 } {
	return "[format %d [expr {$val / 1000}]] K$suffix"
    } elseif { $val >= 9900 } {
	return "[format %.2f [expr {$val / 1000.0}]] K$suffix"
    } else {
	return "$val $suffix"
    }
}

#****f* linkcfg.tcl/setLinkBandwidth
# NAME
#   setLinkBandwidth -- set link bandwidth
# SYNOPSIS
#   setLinkBandwidth $link_id $value
# FUNCTION
#   Sets the link bandwidth in a bits per second.
# INPUTS
#   * link_id -- link id
#   * value -- link bandwidth in bits per second.
#****

proc setLinkBandwidth { link value } {
    global $link

    set i [lsearch [set $link] "bandwidth *"]
    if { $value <= 0 } {
	set $link [lreplace [set $link] $i $i]
    } else {
	if { [llength $value] > 1 } { set value "{$value}" }
	set $link [lreplace [set $link] $i $i "bandwidth $value"]
    }
}

proc getLinkColor { link } {
    global $link defLinkColor

    set entry [lsearch -inline [set $link] "color *"]
    if { $entry == "" } {
	return $defLinkColor
    } else {
	return [lindex $entry 1]
    }
}

proc setLinkColor { link value } {
    global $link

    set i [lsearch [set $link] "color *"]
    set $link [lreplace [set $link] $i $i "color $value"]
}

proc getLinkWidth { link } {
    global $link defLinkWidth

    set entry [lsearch -inline [set $link] "width *"]
    if { $entry == "" } {
	return $defLinkWidth
    } else {
	return [lindex $entry 1]
    }
}

proc setLinkWidth { link value } {
    global $link

    set i [lsearch [set $link] "width *"]
    set $link [lreplace [set $link] $i $i "width $value"]
}

#****f* linkcfg.tcl/getLinkDelay
# NAME
#   getLinkDelay -- get link delay
# SYNOPSIS
#   set delay [getLinkDelay $link_id]
# FUNCTION
#   Returns the link delay expressed in microseconds.
# INPUTS
#   * link_id -- link id
# RESULT
#   * delay -- The value of link delay in microseconds.
#****

proc getLinkDelay { link {dir "down"} } {
    global $link

    set entry [lsearch -inline [set $link] "delay *"]
    set val [lindex $entry 1] ;# one or more values
    if { $dir == "up" } { return [lindex $val 1] }
    return [lindex $val 0]
}

#****f* linkcfg.tcl/getLinkDelayString
# NAME
#   getLinkDelayString -- get link delay string
# SYNOPSIS
#   set delay [getLinkDelayString $link_id]
# FUNCTION
#   Returns the link delay as a string with avalue and measure unit.
#   Measure unit is automaticaly asigned depending on the value of delay.
# INPUTS
#   * link_id -- link id
# RESULT
#   * delay -- The value of link delay formated in a string 
#     containing a measure unit.
#****

proc getLinkDelayString { link } {
    global $link
    set plusminus "\261"
    set delaystr ""
    set sep ""
    set delay [getLinkDelay $link]
    set delayup [getLinkDelay $link up]
    set jitter [getLinkJitter $link]
    set jitterup [getLinkJitter $link up]
    if { $jitter > 0 && $delay == "" } { set delay 0 }
    if { $jitterup > 0 && $delayup == "" } { set delayup 0 }
    if { $delayup > 0 || $jitterup > 0 } {
	set delay [list $delay $delayup]
	set jitter [list $jitter $jitterup]
	set sep " / "
    }
    set i 0
    foreach d $delay {
	if { $delaystr != "" } { set delaystr "$delaystr$sep" }
	if { [lindex $jitter $i] != "" } {
	    set jstr " ($plusminus"
	    set jstr "$jstr[getSIMicrosecondValue [lindex $jitter $i]])"
	} else {
	    set jstr ""
	}
	#set dstr "[getSIMicrosecondValue $d]"
	#if { $dstr == "" && $jstr != "" } { set dstr "0 us" }
	#set delaystr "$delaystr$dstr$jstr"
	set delaystr "$delaystr[getSIMicrosecondValue $d]$jstr"
	incr i
    }
    return $delaystr
}

proc getSIMicrosecondValue { val } {
    if { $val == "" } {
	return ""
    }
    if { $val >= 10000 } {
	return "[expr {$val / 1000}] ms"
    } elseif { $val >= 1000 } {
	return "[expr {$val * .001}] ms"
    } else {
	return "$val us"
    }
}

#****f* linkcfg.tcl/setLinkDelay
# NAME
#   setLinkDelay -- set link delay
# SYNOPSIS
#   setLinkDelay $link_id $value
# FUNCTION
#   Sets the link delay in microseconds.
# INPUTS
#   * link_id -- link id
#   * value -- link delay value in microseconds.
#****

proc setLinkDelay { link value } {
    global $link

    set i [lsearch [set $link] "delay *"]
    if { [checkEmptyZeroValues $value] } {
	set $link [lreplace [set $link] $i $i]
    } else {
	if { [llength $value] > 1 } { set value "{$value}" }
	set $link [lreplace [set $link] $i $i "delay $value"]
    }
}

#****f* linkcfg.tcl/getLinkBER
# NAME
#   getLinkBER -- get link BER
# SYNOPSIS
#   set BER [getLinkBER $link_id]
# FUNCTION
#   Returns 1/BER value of the link.
# INPUTS
#   * link_id -- link id
# RESULT
#   * BER -- The value of 1/BER of the link.
#****

proc getLinkBER { link {dir "down"} } {
    global $link

    set entry [lsearch -inline [set $link] "ber *"]
    set val [lindex $entry 1] ;# one or more values
    if { $dir == "up" } { return [lindex $val 1] }
    return [lindex $val 0]
}

proc getLinkBERString { link } {
    set ber [getLinkBER $link]
    set berup [getLinkBER $link up]
    if { $ber == "" && $berup == "" } { return "" }
    set berstr "loss="
    if { $ber != "" } {
	set berstr "$berstr$ber%"
    }
    if { $berup != "" } { 
	set berstr "$berstr / $berup%"
    }
    return $berstr
}

#****f* linkcfg.tcl/setLinkBER
# NAME
#   setLinkBER -- set link BER
# SYNOPSIS
#   setLinkBER $link_id value
# FUNCTION
#   Sets the BER value of the link.
# INPUTS
#   * link_id -- link id
#   * value -- The value of 1/BER of the link.
#****

proc setLinkBER { link value } {
    global $link

    set i [lsearch [set $link] "ber *"]
    if { [llength $value] > 1 && [lindex $value 0] <= 0 && \
	 [lindex $value 1] <= 0 } {
	set $link [lreplace [set $link] $i $i]
    } elseif { $value <= 0 } {
	set $link [lreplace [set $link] $i $i]
    } else {
	if { [llength $value] > 1 } { set value "{$value}" }
	set $link [lreplace [set $link] $i $i "ber $value"]
    }
}

#****f* linkcfg.tcl/getLinkDup
# NAME
#   getLinkDup -- get link packet duplicate value 
# SYNOPSIS
#   set duplicate [getLinkDup $link_id]
# FUNCTION
#   Returns the value of the link duplicate percentage.
# INPUTS
#   * link_id -- link id
# RESULT
#   * duplicate -- The percentage of the link packet duplicate value.
#****

proc getLinkDup { link {dir "down"} } {
    global $link

    set entry [lsearch -inline [set $link] "duplicate *"]
    set val [lindex $entry 1] ;# one or more values
    if { $dir == "up" } { return [lindex $val 1] }
    return [lindex $val 0]
}

proc getLinkDupString { link } {
    set dup [getLinkDup $link]
    set dupup [getLinkDup $link up]
    if { $dup == "" && $dupup == "" } { return "" }
    set dupstr "dup="
    if { $dup != "" } {
	set dupstr "$dupstr$dup%"
    }
    if { $dupup != "" } {
	set dupstr "$dupstr / $dupup%"
    }
    return $dupstr
}

#****f* linkcfg.tcl/setLinkDup
# NAME
#   setLinkDup -- set link packet duplicate value 
# SYNOPSIS
#   setLinkDup $link_id $value
# FUNCTION
#   Set link packet duplicate percentage.
# INPUTS
#   * link_id -- link id
#   * value -- The percentage of the link packet duplicate value.
#****

proc setLinkDup { link value } {
    global $link

    set i [lsearch [set $link] "duplicate *"]
    if { [checkEmptyZeroValues $value] } {
	set $link [lreplace [set $link] $i $i]
    } else {
	if { [llength $value] > 1 } { set value "{$value}" }
	set $link [lreplace [set $link] $i $i "duplicate $value"]
    }
}

# Returns true if link has unidirectional link effects, where
# upstream values may differ from downstream.
proc isLinkUni { link } {
    set bw [getLinkBandwidth $link up]
    set dl [getLinkDelay $link up]
    set jt [getLinkJitter $link up]
    set ber [getLinkBER $link up]
    set dup [getLinkDup $link up]
    if { $bw > 0 || $dl > 0 || $jt > 0 || $ber > 0 || $dup > 0 } {
	return true
    } else {
	return false
    }
}

#****f* linkcfg.tcl/getLinkMirror
# NAME
#   getLinkMirror -- get link's mirror link 
# SYNOPSIS
#   set mirror_link_id [getLinkMirror $link_id]
# FUNCTION
#   Returns the value of the link's mirror link. Mirror link is the other
#   part of the link connecting node to a pseudo node. Two mirror links
#   present only one physical link.
# INPUTS
#   * link_id -- link id
# RESULT
#   * mirror_link_id -- Mirror link id
#****

proc getLinkMirror { link } {
    global $link

    set entry [lsearch -inline [set $link] "mirror *"]
    return [lindex $entry 1]
}

#****f* linkcfg.tcl/setLinkMirror
# NAME
#   setLinkMirror -- set link's mirror link 
# SYNOPSIS
#   setLinkMirror $link_id $mirror_link_id
# FUNCTION
#   Sets the value of the link's mirror link. Mirror link is the other
#   part of the link connecting node to a pseudo node. Two mirror links
#   present only one physical link.
# INPUTS
#   * link_id -- link id
# RESULT
#   * mirror_link_id -- Mirror link id
#****

proc setLinkMirror { link value } {
    global $link

    set i [lsearch [set $link] "mirror *"]
    if { $value == "" } {
	set $link [lreplace [set $link] $i $i]
    } else {
	set $link [lreplace [set $link] $i $i "mirror $value"]
    }
}

#****f* linkcfg.tcl/splitLink
# NAME
#   splitLink -- slit the link
# SYNOPSIS
#   set nodes [splitLink  $link_id $nodetype]
# FUNCTION
#   Splits the link in two parts. Each part of the split link is one 
#   pseudo link.
# INPUTS
#   * link_id -- link id
#   * nodetype -- type of the new nodes connecting slit links.
#     Usual value is pseudo.
# RESULT
#   * nodes -- list of node ids of new nodes.
#****

proc splitLink { link nodetype } {
    global link_list $link

    set orig_nodes [linkPeers $link]
    set orig_node1 [lindex $orig_nodes 0]
    set orig_node2 [lindex $orig_nodes 1]
    set new_node1 [newNode $nodetype]
    set new_node2 [newNode $nodetype]
    set new_link1 [newObjectId link]
    lappend link_list $new_link1
    set new_link2 [newObjectId link]
    lappend link_list $new_link2
    set ifc1 [ifcByPeer $orig_node1 $orig_node2]
    set ifc2 [ifcByPeer $orig_node2 $orig_node1]

    global $orig_node1 $orig_node2 $new_node1 $new_node2
    global $new_link1 $new_link2
    set $new_link1 {}
    set $new_link2 {}

    set i [lsearch [set $orig_node1] "interface-peer {* $orig_node2}"]
    set $orig_node1 [lreplace [set $orig_node1] $i $i \
			"interface-peer {$ifc1 $new_node1}"]
    set i [lsearch [set $orig_node2] "interface-peer {* $orig_node1}"]
    set $orig_node2 [lreplace [set $orig_node2] $i $i \
			"interface-peer {$ifc2 $new_node2}"]

    lappend $new_link1 "nodes {$orig_node1 $new_node1}"
    lappend $new_link2 "nodes {$orig_node2 $new_node2}"

    setNodeCanvas $new_node1 [getNodeCanvas $orig_node1]
    setNodeCanvas $new_node2 [getNodeCanvas $orig_node2]
    setNodeCoords $new_node1 [getNodeCoords $orig_node2]
    setNodeCoords $new_node2 [getNodeCoords $orig_node1]
    if { $nodetype != "pseudo" } {
	setNodeLabelCoords $new_node1 [getNodeLabelCoords $orig_node2]
	setNodeLabelCoords $new_node2 [getNodeLabelCoords $orig_node1]
    } else {
	setNodeLabelCoords $new_node1 [getNodeCoords $orig_node2]
	setNodeLabelCoords $new_node2 [getNodeCoords $orig_node1]
    }
    lappend $new_node1 "interface-peer {0 $orig_node1}"
    lappend $new_node2 "interface-peer {0 $orig_node2}"

    setLinkBandwidth $new_link1 [getLinkBandwidth $link]
    setLinkBandwidth $new_link2 [getLinkBandwidth $link]
    setLinkDelay $new_link1 [getLinkDelay $link]
    setLinkDelay $new_link2 [getLinkDelay $link]
    setLinkBER $new_link1 [getLinkBER $link]
    setLinkBER $new_link2 [getLinkBER $link]
    setLinkDup $new_link1 [getLinkDup $link]
    setLinkDup $new_link2 [getLinkDup $link]

    set i [lsearch -exact $link_list $link]
    set link_list [lreplace $link_list $i $i]

    return "$new_node1 $new_node2"
}

#****f* linkcfg.tcl/mergeLink
# NAME
#   mergeLink -- merge the link
# SYNOPSIS
#   set new_link_id [mergeLink  $link_id]
# FUNCTION
#   Rebuilts a link from two pseudo link. 
# INPUTS
#   * link_id -- pseudo link id
# RESULT
#   * new_link_id -- rebuilt link id.
#****

proc mergeLink { link } {
    global link_list node_list

    set mirror_link [getLinkMirror $link]
    if { $mirror_link == "" } {
	puts "error: mergeLink called for non-pseudo link"
	return
    }
    set link1_peers [linkPeers $link]
    set link2_peers [linkPeers $mirror_link]
    set orig_node1 [lindex $link1_peers 0]
    set orig_node2 [lindex $link2_peers 0]
    set pseudo_node1 [lindex $link1_peers 1]
    set pseudo_node2 [lindex $link2_peers 1]
    set new_link [newObjectId link]
    global $orig_node1 $orig_node2
    global $new_link

    set ifc1 [ifcByPeer $orig_node1 $pseudo_node1]
    set ifc2 [ifcByPeer $orig_node2 $pseudo_node2]
    set i [lsearch [set $orig_node1] "interface-peer {* $pseudo_node1}"]
    set $orig_node1 [lreplace [set $orig_node1] $i $i \
			"interface-peer {$ifc1 $orig_node2}"]
    set i [lsearch [set $orig_node2] "interface-peer {* $pseudo_node2}"]
    set $orig_node2 [lreplace [set $orig_node2] $i $i \
			"interface-peer {$ifc2 $orig_node1}"]

    set $new_link {}
    lappend $new_link "nodes {$orig_node1 $orig_node2}"

    setLinkBandwidth $new_link [getLinkBandwidth $link]
    setLinkDelay $new_link [getLinkDelay $link]
    setLinkBER $new_link [getLinkBER $link]
    setLinkDup $new_link [getLinkDup $link]

    set i [lsearch -exact $link_list $link]
    set link_list [lreplace $link_list $i $i]
    set i [lsearch -exact $link_list $mirror_link]
    set link_list [lreplace $link_list $i $i]
    lappend link_list $new_link

    set i [lsearch -exact $node_list $pseudo_node1]
    set node_list [lreplace $node_list $i $i]
    set i [lsearch -exact $node_list $pseudo_node2]
    set node_list [lreplace $node_list $i $i]

    return $new_link
}

#****f* linkcfg.tcl/newLink
# NAME
#   newLink -- create new link
# SYNOPSIS
#   set new_link_id [newLink  $node1_id $node2_id]
# FUNCTION
#   Creates a new link between nodes node1_id and node2_id. The order of
#   nodes is irrelevant.
# INPUTS
#   * node1_id -- node id of the peer node
#   * node2_id -- node id of the second peer node
# RESULT
#   * new_link_id -- new link id.
#****

proc newLink { lnode1 lnode2 } {
    global link_list
    global $lnode1 $lnode2
    global defEthBandwidth defSerBandwidth defSerDelay
    global defLinkColor defLinkWidth
    global curcanvas
    global systype

    if { [nodeType $lnode1] == "lanswitch" && \
	[nodeType $lnode2] != "router" && \
	[nodeType $lnode2] != "lanswitch" } { set regular no }
    if { [nodeType $lnode2] == "lanswitch" && \
	[nodeType $lnode1] != "router" && \
	[nodeType $lnode1] != "lanswitch" } { set regular no }
    if { [nodeType $lnode1] == "hub" && \
	[nodeType $lnode2] == "hub" } { set regular no }
    # Boeing: added tunnel, ktunnel types to behave as rj45
    if { [nodeType $lnode1] == "rj45" || [nodeType $lnode2] == "rj45" || \
	 [nodeType $lnode1] == "tunnel" || [nodeType $lnode2] == "tunnel" || \
	 [nodeType $lnode1] == "ktunnel" || [nodeType $lnode2] == "ktunnel"  } {
	if { [nodeType $lnode1] == "rj45" || [nodeType $lnode1] == "tunnel" || \
	     [nodeType $lnode1] == "ktunnel" } {
	    set rj45node $lnode1
	    set othernode $lnode2
	} else {
	    set rj45node $lnode2
	    set othernode $lnode1
	}
	# only allowed to link with certain types
	if { [lsearch {router lanswitch hub pc host wlan} \
	    [nodeType $othernode]] < 0} {
	    return
	}
	# check if already linked to something else
	if { [lsearch [set $rj45node] "interface-peer *"] > 0 } {
	    return
	}
    }
    # Boeing: wlan node is always first of the two nodes
    if { [nodeType $lnode2] == "wlan" } {
	set tmp $lnode1
	set lnode1 $lnode2
	set lnode2 $tmp
    }
    # end Boeing

    set link [newObjectId link]
    global $link
    set $link {}

    # pick new interface names or use names from global hint
    set do_auto_addressing 1
    global g_newLink_ifhints
    if { [info exists g_newLink_ifhints] && $g_newLink_ifhints != "" } {
	set ifname1 [lindex $g_newLink_ifhints 0]
	set ifname2 [lindex $g_newLink_ifhints 1]
	set do_auto_addressing 0
	set g_newLink_ifhints ""
    } else {
        set ifname1 [newIfc [chooseIfName $lnode1 $lnode2] $lnode1]
        set ifname2 [newIfc [chooseIfName $lnode2 $lnode1] $lnode2]
    }
    lappend $lnode1 "interface-peer {$ifname1 $lnode2}"
    lappend $lnode2 "interface-peer {$ifname2 $lnode1}"
    # check for existing interface config (supported by API)
    # this allows for interfaces/addresses to be configured before the link
    # is created
    set ipv4_addr1 [getIfcIPv4addr $lnode1 $ifname1]
    set ipv6_addr1 [getIfcIPv6addr $lnode1 $ifname1]
    set ipv4_addr2 [getIfcIPv4addr $lnode2 $ifname2]
    set ipv6_addr2 [getIfcIPv6addr $lnode2 $ifname2]

    lappend $link "nodes {$lnode1 $lnode2}"
    # parameters for links to wlan are based on wlan parameters
    if { [nodeType $lnode1] == "wlan" } {
    	set bandwidth [getLinkBandwidth $lnode1]
	set delay [getLinkDelay $lnode1]
	set model [netconfFetchSection $lnode1 "mobmodel"]
	if { $bandwidth != "" } {
	    lappend $link "bandwidth [getLinkBandwidth $lnode1]"
	}
	set ipv4_addr1 [getIfcIPv4addr $lnode1 wireless]
	if { $ipv4_addr1 == "" } { ;# allocate WLAN address now
	    setIfcIPv4addr $lnode1 wireless "[findFreeIPv4Net 32].0/32"
	}
	set ipv6_addr1 [getIfcIPv6addr $lnode1 wireless]
	if { $ipv6_addr1 == "" } {
	    setIfcIPv6addr $lnode1 wireless "[findFreeIPv6Net 128]::0/128"
	}
	if { [string range $model 0 6] == "coreapi" } {
	    set delay 0; # delay controlled by wireless module
	} elseif {$delay != ""} {
	    if { [lindex $systype 0] == "FreeBSD" } {
		lappend $link "delay [expr $delay/2]"
	    } else {
		lappend $link "delay $delay"
	    }
	}
	if { [[typemodel $lnode2].layer] == "NETWORK" } {
	    if { $ipv4_addr2 == "" } { autoIPv4addr $lnode2 $ifname2 }
	    if { $ipv6_addr2 == "" } { autoIPv6addr $lnode2 $ifname2 }
	}
    # tunnels also excluded from link settings
    } elseif { ([nodeType $lnode1] == "lanswitch" || \
	[nodeType $lnode2] == "lanswitch" || \
	[string first eth "$ifname1 $ifname2"] != -1) && \
	[nodeType $lnode1] != "rj45" && [nodeType $lnode2] != "rj45" && \
	[nodeType $lnode1] != "tunnel" && [nodeType $lnode2] != "tunnel" && \
	[nodeType $lnode1] != "ktunnel" && [nodeType $lnode2] != "ktunnel" } {
	lappend $link "bandwidth $defEthBandwidth"
    } elseif { [string first ser "$ifname1 $ifname2"] != -1 } {
	lappend $link "bandwidth $defSerBandwidth"
	lappend $link "delay $defSerDelay"
    }

    lappend link_list $link

    if { [nodeType $lnode2] != "pseudo" &&
	 [nodeType $lnode1] != "wlan" &&
	[[typemodel $lnode1].layer] == "NETWORK" } {
	if { $ipv4_addr1 == "" && $do_auto_addressing } {
	    autoIPv4addr $lnode1 $ifname1
	}
	if { $ipv6_addr1 == "" && $do_auto_addressing } {
	    autoIPv6addr $lnode1 $ifname1
	}
    }
    # assume wlan is always lnode1
    if { [nodeType $lnode1] != "pseudo" &&
	 [nodeType $lnode1] != "wlan" &&
	[[typemodel $lnode2].layer] == "NETWORK" } {
	if { $ipv4_addr2 == "" && $do_auto_addressing } {
	    autoIPv4addr $lnode2 $ifname2 
	}
	if { $ipv6_addr2 == "" && $do_auto_addressing } {
	    autoIPv6addr $lnode2 $ifname2
	}
    }

    # tunnel address based on its name 
    if { [nodeType $lnode1] == "tunnel" } {
	set ipaddr "[getNodeName $lnode1]/24"
	setIfcIPv4addr $lnode1 e0 $ipaddr
    }
    if { [nodeType $lnode2] == "tunnel" } {
	set ipaddr "[getNodeName $lnode2]/24"
	setIfcIPv4addr $lnode2 e0 $ipaddr
    }

    return $link
}

#****f* linkcfg.tcl/linkByIfc
# NAME
#   linkByIfg -- get link by interface
# SYNOPSIS
#   set link_id [linkByIfc  $node_id $fc]
# FUNCTION
#   Returns the link id of the link connecting the node's interface
# INPUTS
#   * node_id -- node id 
#   * ifc -- interface
# RESULT
#   * link_id -- link id.
#****

proc linkByIfc { node ifc } {
    global link_list

    set peer [peerByIfc $node $ifc]
    set dir ""
    foreach link $link_list {
	set endpoints [linkPeers $link]
	if { $endpoints == "$node $peer" } {
	    set dir downstream
	    break
	}
	if { $endpoints == "$peer $node" } {
	    set dir upstream
	    break
	}
    }
    if { $dir == "" } {
	puts "*** linkByIfc error: node=$node ifc=$ifc"
    }

    return [list $link $dir]
}

proc getLinkJitter { link {dir "down"} } {
    global $link

    set entry [lsearch -inline [set $link] "jitter *"]
    set val [lindex $entry 1] ;# one or more values
    if { $dir == "up" } { return [lindex $val 1] }
    return [lindex $val 0]
}

proc setLinkJitter { link value } {
    global $link

    set i [lsearch [set $link] "jitter *"]
    if { [llength $value] <= 1 && $value <= 0 } {
	set $link [lreplace [set $link] $i $i]
    } elseif { [llength $value] > 1 && [lindex $value 0] <= 0 && \
	[lindex $value 1] <= 0 } {
	set $link [lreplace [set $link] $i $i]
    } else {
	if { [llength $value] > 1 } { set value "{$value}" }
	set $link [lreplace [set $link] $i $i "jitter $value"]
    }
}

# Check for empty or zero values in value.
# Value may be a single value or list where the first two values will be
# inspected; returns true for empty or zero values, false otherwise.
proc checkEmptyZeroValues { value } {
    set isempty true
    foreach v $value {
	if { $v == "" } { continue } ;# this catches common case "{} {}"
	if { $v > 0 } { set isempty false }
    }
    return $isempty
}

# get any type of link attribute
proc getLinkOpaque { link key } {
    global $link

    set entry [lsearch -inline [set $link] "$key *"]
    return [lindex $entry 1]
}

# set any type of link attribute
#   passing in a value <= 0 or "" will delete this key
proc setLinkOpaque { link key value } {
    global $link

    set i [lsearch [set $link] "$key *"]
    if { $value <= 0 } {
	set $link [lreplace [set $link] $i $i]
    } else {
	set $link [lreplace [set $link] $i $i "$key $value"]
    }
}

#
# change GUI attributes for a link (width, color, dash)
#
proc updateLinkGuiAttr { link attr } {
    global defLinkColor defLinkWidth

    if { $attr == "" } { return }

    foreach a $attr {
	set kv [split $a =]
	set key [lindex $kv 0]
	set value [lindex $kv 1]

	switch -exact -- $key {
	    width {
		if { $value == "" } { set value $defLinkWidth }
		setLinkWidth $link $value
		.c itemconfigure "link && $link" -width [getLinkWidth $link]
	    }
	    color {
		setLinkColor $link $value
		.c itemconfigure "link && $link" -fill [getLinkColor $link] 
	    }
	    dash {
		.c itemconfigure "link && $link" -dash $value
	    }
	    default {
		puts "warning: unsupported GUI link attribute: $key"
	    }
	} ;# end switch
    } ;# end foreach attr
}

