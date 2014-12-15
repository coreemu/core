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


#****h* imunes/nodecfg.tcl
# NAME
#  nodecfg.tcl -- file used for manipultaion with nodes in IMUNES
# FUNCTION
#  This module is used to define all the actions used for configuring 
#  nodes in IMUNES. The definition of nodes is presented in NOTES
#  section.
#
# NOTES
#  The IMUNES configuration file contains declarations of IMUNES objects.
#  Each object declaration contains exactly the following three fields:
#
#     object_class object_id class_specific_config_string
#
#  Currently only two object classes are supported: node and link. In the
#  future we plan to implement a canvas object, which should allow placing
#  other objects into multiple visual maps.
#
#  "node" objects are further divided by their type, which can be one of
#  the following:
#  * router
#  * host
#  * pc
#  * lanswitch
#  * hub
#  * rj45
#  * pseudo
#
#  The following node types are to be implemented in the future:
#  * text
#  * image
#
#
# Routines for manipulation of per-node network configuration files
# IMUNES keeps per-node network configuration in an IOS / Zebra / Quagga
# style format.
#
# Network configuration is embedded in each node's config section via the
# "network-config" statement. The following functions can be used to
# manipulate the per-node network config:
#
# netconfFetchSection { node_id sectionhead }
#	Returns a section of a config file starting with the $sectionhead
#	line, and ending with the first occurence of the "!" sign.
#
# netconfClearSection { node_id sectionhead }
#	Removes the appropriate section from the config.
#
# netconfInsertSection { node_id section }
#	Inserts a section in the config file. Sections beginning with the
#	"interface" keyword are inserted at the head of the config, and
#	all other sequences are simply appended to the config tail.
#
# getIfcOperState { node_id ifc }
#	Returns "up" or "down".
#
# setIfcOperState { node_id ifc state }
#	Sets the new interface state. Implicit default is "up".
#
#Boeing:
# getIfcDumpState { node_id ifc }
#	Returns "tcpdump on" or "tcpdump off".
#
#Boeing:
# setIfcDumpState { node_id ifc state }
#	Sets the tcpdump state for the interface
#
# getIfcQDisc { node_id ifc }
# getIfcQDisc { node_id ifc }
#	Returns "FIFO", "WFQ" or "DRR".
#
# setIfcQDisc { node_id ifc qdisc }
#	Sets the new queuing discipline. Implicit default is FIFO.
#
# getIfcQDrop { node_id ifc }
#	Returns "drop-tail" or "drop-head".
#
# setIfcQDrop { node_id ifc qdrop }
#	Sets the new queuing discipline. Implicit default is "drop-tail".
#
# getIfcQLen { node_id ifc }
#	Returns the queue length limit in packets.
#
# setIfcQLen { node_id ifc len }
#	Sets the new queue length limit.
#
# getIfcMTU { node_id ifc }
#	Returns the configured MTU, or an empty string if default MTU is used.
#
# setIfcMTU { node_id ifc mtu }
#	Sets the new MTU. Zero MTU value denotes the default MTU.
#
# getIfcIPv4addr { node_id ifc }
#	Returns a list of all IPv4 addresses assigned to an interface.
#
# setIfcIPv4addr { node_id ifc addr }
#	Sets a new IPv4 address(es) on an interface. The correctness of the
#	IP address format is not checked / enforced.
#
# getIfcIPv6addr { node_id ifc }
#	Returns a list of all IPv6 addresses assigned to an interface.
#
# setIfcIPv6addr { node_id ifc addr }
#	Sets a new IPv6 address(es) on an interface. The correctness of the
#	IP address format is not checked / enforced.
#
# getStatIPv4routes { node_id }
#	Returns a list of all static IPv4 routes as a list of
#	{destination gateway {metric}} pairs.
#
# setStatIPv4routes { node_id route_list }
#	Replace all current static route entries with a new one, in form of
#	a list, as described above.
#
# getStatIPv6routes { node_id }
#	Returns a list of all static IPv6 routes as a list of
#	{destination gateway {metric}} pairs.
#
# setStatIPv6routes { node_id route_list }
#	Replace all current static route entries with a new one, in form of
#	a list, as described above.
#
# getNodeName { node_id }
#	Returns node's logical name.
#
# setNodeName { node_id name }
#	Sets a new node's logical name.
#
# nodeType { node_id }
#	Returns node's type.
#
# getNodeModel { node_id }
#	Returns node's optional model identifier.
#
# setNodeModel { node_id model }
#	Sets the node's optional model identifier.
#
# getNodeCanvas { node_id }
#	Returns node's canvas affinity.
#
# setNodeCanvas { node_id canvas_id }
#	Sets the node's canvas affinity.
#
# getNodeCoords { node_id }
#	Return icon coords.
#
# setNodeCoords { node_id coords }
#	Sets the coordinates.
#
# getNodeLabelCoords { node_id }
#	Return node label coordinates.
#
# setNodeLabelCoords { node_id coords }
#	Sets the label coordinates.
#
# getNodeCPUConf { node_id }
#	Returns node's CPU scheduling parameters { minp maxp weight }.
#
# setNodeCPUConf { node_id param_list }
#	Sets the node's CPU scheduling parameters.
#
# ifcList { node_id }
#	Returns a list of all interfaces present in a node.
#
# peerByIfc { node_id ifc }
#	Returns id of the node on the other side of the interface
#
# logicalPeerByIfc { node_id ifc }
#	Returns id of the logical node on the other side of the interface.
#
# ifcByPeer { local_node_id peer_node_id }
#	Returns the name of the interface connected to the specified peer 
#       if the peer is on the same canvas, otherwise returns an empty string.
#
# ifcByLogicalPeer { local_node_id peer_node_id }
#	Returns the name of the interface connected to the specified peer.
#	Returns the right interface even if the peer node is on the other
#	canvas.
#
# hasIPv4Addr { node_id }
# hasIPv6Addr { node_id }
#	Returns true if at least one interface has an IPv{4|6} address
#	configured, otherwise returns false.
#
# removeNode { node_id }
#	Removes the specified node as well as all the links that bind 
#       that node to any other node.
#
# newIfc { ifc_type node_id }
#	Returns the first available name for a new interface of the 
#       specified type.
#
# All of the above functions are independent to any Tk objects. This means
# they can be used for implementing tasks external to GUI, so inside the
# GUI any updating of related Tk objects (such as text labels etc.) will
# have to be implemented by additional Tk code.
#
# Additionally, an alternative configuration can be specified in 
# "custom-config" section.
#
# getCustomConfig { node_id }
#
# setCustomConfig { node_id cfg }
#
# getCustomEnabled { node_id }
#
# setCustomEnabled { node_id state }
#****

#****f* nodecfg.tcl/typemodel
# NAME
#   typemodel -- find node's type and routing model 
# SYNOPSIS
#   set typemod [typemodel $node_id]
# FUNCTION
#   For input node this procedure returns the node's  
#   type and routing model (if exists) 
# INPUTS
#   * node_id -- node id
# RESULT
#   * typemod -- returns node's type and routing model in form type.model
#****

proc typemodel { node } {
    return [nodeType $node]
}

#****f* nodecfg.tcl/getNodeLocation
# NAME
#   getNodeLocation -- get location of the node
# SYNOPSIS
#   set location [getNodeLocation $node_id]
# FUNCTION
#   For input node this procedure returns the name of the CORE box 
#   controlling the node.
# INPUTS
#   * node_id -- node id
# RESULT
#   * location -- returns the location of the node
#****

proc getNodeLocation { node } {
    global $node

    set loc_tmp [lindex [lsearch -inline [set $node] "location *"] 1]
    return $loc_tmp
}



#****f* nodecfg.tcl/setNodeLocation
# NAME
#   setNodeLocation -- set location of the node
# SYNOPSIS
#   setNodeLocation $node_id $location
# FUNCTION
#   For input node this procedure sets the name of the CORE box 
#   controlling the node.
# INPUTS
#   * node_id -- node id
#   * location -- the name of the CORE box controlling the node
#****

proc setNodeLocation { node location } {
    global $node

    set i [lsearch [set $node] "location *"]
    if { $i >= 0 } {
        set $node [lreplace [set $node] $i $i]
    }

    if { $location == "" } { return }
    
    lappend $node [list location $location]

    return
}

# returns true if any connected peer has the specified location
proc nodePeerHasLocation { node location } {
    foreach ifc [ifcList $node] {
	set peer [peerByIfc $node $ifc]
	if { [getNodeLocation $peer] == $location } {
	    return 1
	}
    }
    return 0
}


#****f* nodecfg.tcl/setConfig
# NAME
#   setConfig -- add an element to the *-config
#		structure
# SYNOPSIS
#   setConfig $strlist $str
# FUNCTION
#   Procedure returns requested element that belongs
#	to *-config structure. 
# INPUTS
#    * strlist -- *-config structure
#    * cfg -- current *-config that will be extended
#	with new elements
#    * str -- new element
# RESULT
#    * strlist -- new *-config sructure
#****

proc setConfig { strlist cfg str } {

    set i [lsearch $strlist "$str *"]

    if { $i < 0 } {
	if { $cfg != {} } {
	    set newcfg [list $str $cfg]
	    lappend strlist $newcfg
	}
    } else {
	set oldval [lindex [lsearch -inline $strlist "$str *"] 1]
	if { $oldval != $cfg } {
	    set strlist [lreplace $strlist $i $i [list $str $cfg]]
	}
    }

    return $strlist
}


#****f* nodecfg.tcl/getConfig
# NAME
#   getConfig -- get an element of the *-config
# SYNOPSIS
#   getConfig $strlist $str
# FUNCTION
#	Procedure returns requested element that belongs
#		to *-config structure. 
# INPUTS
#   * strlist -- *-config structure
#	* str -- an element of the *-config structure
#****

proc getConfig { strlist str } {

    return [lindex [lsearch -inline $strlist "$str *"] 1]
}


#****f* nodecfg.tcl/getCustomEnabled
# NAME
#   getCustomEnabled -- get custom configuration enabled state 
# SYNOPSIS
#   set enabled [getCustomEnabled $node_id]
# FUNCTION
#   For input node this procedure returns true if custom configuration
#   is enabled for the specified node. 
# INPUTS
#   * node_id -- node id
# RESULT
#   * enabled -- returns true if custom configuration is enabled 
#****

proc getCustomEnabled { node } {
    global $node

    if { [lindex [lsearch -inline [set $node] "custom-enabled *"] 1] == true } {
	return true
    } else {
	return false
    }
}

#****f* nodecfg.tcl/setCustomEnabled
# NAME
#   setCustomEnabled -- set custom configuration enabled state 
# SYNOPSIS
#   setCustomEnabled $node_id $enabled
# FUNCTION
#   For input node this procedure enables or disables custom configuration.
# INPUTS
#   * node_id -- node id
#   * enabled -- true if enabling custom configuration, false if disabling 
#****

proc setCustomEnabled { node enabled } {
    global $node

    set i [lsearch [set $node] "custom-enabled *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i]
    }
    if { $enabled == true } {
	lappend $node [list custom-enabled $enabled]
    }
}

#****f* nodecfg.tcl/getCustomCmd
# NAME
#   getCustomCmd -- get custom configuration command 
# SYNOPSIS
#   set command [getCustomCmd $node_id]
# FUNCTION
#   For input node this procedure returns custom command.
# INPUTS
#   * node_id -- node id
# RESULT
#   * command -- custom configuration command 
#****

proc getCustomCmd { node } {
    global $node

    return [lindex [lsearch -inline [set $node] "custom-command *"] 1]
}

#****f* nodecfg.tcl/setCustomCmd
# NAME
#   setCustomEnabled -- set custom configuration command 
# SYNOPSIS
#   setCustomCmd $node_id $command
# FUNCTION
#   For input node this procedure sets custom command.
# INPUTS
#   * node_id -- node id
#   * command -- custom configuration command 
#****

proc setCustomCmd { node cmd } {
    global $node

    set i [lsearch [set $node] "custom-command *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i]
    }
	
    lappend $node [list custom-command $cmd]
}

#****f* nodecfg.tcl/getCustomConfig
# NAME
#   getCustomConfig -- get custom configuration section 
# SYNOPSIS
#   set cfg [getCustomConfig $node_id]
# FUNCTION
#   For input node this procedure returns custom configuration section.
# INPUTS
#   * node_id -- node id
# RESULT
#   * cfg -- returns custom configuration section 
#****

proc getCustomConfig { node } {
    global $node
    set customCfgList {}
	
    set customcmd ""
    set customcfg ""
    set customcmd [lsearch -inline [set $node] "custom-command *"]
    set customcmdval [lindex $customcmd 1]
    set customcfg [lsearch -inline [set $node] "custom-config *"]
    set customcfgval [lindex $customcfg 1]
    if { $customcmd != "" } {
	set customid [list custom-config-id generic]
	set customcmd [list custom-command $customcmdval]
	set customcfg [list config $customcfgval]
	set customCfgList [list [list $customid $customcmd $customcfg]]
    } else {
	set values [lsearch -all -inline [set $node] "custom-config *"]
	foreach val $values {
	    lappend customCfgList [lindex $val 1]
    	}
    }

    return $customCfgList
}


proc getCustomConfigByID { node id } {
    set customCfgList [getCustomConfig $node]
    foreach element $customCfgList {
	if { $id == [getConfig $element "custom-config-id"] } {
	    return [getConfig $element "config"]
	}
    }
    return ""
}

#****f* nodecfg.tcl/setCustomConfig
# NAME
#   setCustomConfig -- set custom configuration command 
# SYNOPSIS
#   setCustomConfig $node_id $cfg
# FUNCTION
#   For input node this procedure sets custom configuration section.
# INPUTS
#   * node_id -- node id
#   * id -- custom-config id
#   * cmd -- custom command
#   * cfg -- custom configuration section 
#   * delete -- if delete is set to 1, setCustomConfig is invoked
#	to delete custom-config with custom-config-id $id
#   * 
#****

proc setCustomConfig { node id cmd cfg delete } {
    global viewcustomid
    global $node

    # removes first occurrence of custom-command and custom-config
    set i [lsearch [set $node] "custom-command *"]
    if { $i != "-1" } {
	# remove custom-command
	set $node [lreplace [set $node] $i $i]
	# remove custom-config
	set j [lsearch [set $node] "custom-config *"]
	set $node [lreplace [set $node] $j $j]
    }
	
    # removes existing custom-config if custom-config-id matches
    set cnt 0
    set indices [lsearch -all [set $node] "custom-config *"]
    foreach i $indices {
	set tmp [lindex [set $node] $i]
	set customCfg [lindex $tmp 1]
	set cid [lindex [lsearch -inline $customCfg "custom-config-id *"] 1]

	if { $cid == $id } {
	    set $node [lreplace [set $node] $i $i]
	}
    }
	
    # adds the new config specified in the dialog box
    if { $delete == 0 } {
	if { $cfg != {} && $cmd != {} && $id != {} } {
	    set newid [list custom-config-id $id]
	    set viewcustomid [lindex $newid 1]
	    set newcmd [list custom-command $cmd]
	    set newcfg [list config $cfg]
	    # Boeing: insert the new custom config so it's the first (active) 
	    # custom config in the list, or just add it to the end
	    set first [lindex $indices 0]
	    if { $first < 0 } {
	        set first end
	    }
	    set $node [linsert [set $node] $first \
	    		[ list custom-config [list $newid $newcmd $newcfg] ]]
	    #lappend $node [ list custom-config [list $newid $newcmd $newcfg] ]
	}
    }
}

#****f* nodecfg.tcl/netconfFetchSection
# NAME
#   netconfFetchSection -- fetch the network configuration section 
# SYNOPSIS
#   set section [netconfFetchSection $node_id $sectionhead]
# FUNCTION
#   Returns a section of a network part of a configuration file starting with the $sectionhead
#   line, and ending with the first occurrence of the "!" sign.
# INPUTS
#   * node_id     -- node id
#   * sectionhead -- represents the first line of the section in network-config part of
#     the configuration file
# RESULT
#   * section -- returns a part of the configuration file between sectionhead and "!"
#****

proc netconfFetchSection { node sectionhead } {
    global $node

    set cfgmode global
    set section {}
    # Boeing: read custom config if enabled
    if { [lindex [lsearch -inline [set $node] "custom-enabled *"] 1] == true } {
        # this will match the first custom-config encountered
        set netconf [lindex [lsearch -inline [set $node] "custom-config *"] 1]
	set tmp [lindex [lsearch -inline $netconf "config *"] 1]
	if {$tmp != "" } { set netconf $tmp }
    } else {
        set netconf [lindex [lsearch -inline [set $node] "network-config *"] 1]
    }
    # if 'nocustom' keyword is passed in sectionhead, don't use custom-config
    if { [lsearch $sectionhead "nocustom"] > -1 } {
        # remove "nocustom" from sectionhead
        set sectionhead [lsearch -all -inline -not $sectionhead "nocustom"]
        # do not read custom config
        set netconf [lindex [lsearch -inline [set $node] "network-config *"] 1]
    }
    # end Boeing
    foreach line $netconf {
        if { $cfgmode == "section" } {
            if { "$line" == "!" } {
                return $section
            }
            lappend section "$line"
            continue
        }
        if { "$line" == "$sectionhead" } {
            set cfgmode section
        # Boeing: search the first part of $line for $sectionhead
        } elseif { "router bgp" == "$sectionhead" } { 
            if { [string first $sectionhead $line 0] == 0 } {
                set cfgmode section
                lappend section "$line"
            }
        }
    }
}

#****f* nodecfg.tcl/netconfClearSection
# NAME
#   netconfClearSection -- clear the section from a network-config part
# SYNOPSIS
#   netconfClearSection $node_id $sectionhead
# FUNCTION
#   Removes the appropriate section from the network part of the configuration.
# INPUTS
#   * node_id     -- node id
#   * sectionhead -- represents the first line of the section that is to be removed from network-config 
#     part of the configuration.
#****

proc netconfClearSection { node sectionhead } {
    global $node

    set i [lsearch [set $node] "network-config *"]
    set netconf [lindex [lindex [set $node] $i] 1]
    set lnum_beg -1
    set lnum_end 0
    foreach line $netconf {
	if { $lnum_beg == -1 && "$line" == "$sectionhead" } {
	    set lnum_beg $lnum_end
	}
	if { $lnum_beg > -1 && "$line" == "!" } {
	    set netconf [lreplace $netconf $lnum_beg $lnum_end]
	    set $node [lreplace [set $node] $i $i \
		[list network-config $netconf]]
	    return
	}
	incr lnum_end
    }
}

#****f* nodecfg.tcl/netconfInsertSection
# NAME
#   netconfInsertSection -- Insert the section to a network-config part of configuration
# SYNOPSIS
#   netconfInsertSection $node_id $section
# FUNCTION
#   Inserts a section in the configuration. Sections beginning with the
#   "interface" keyword are inserted at the head of the configuration, and
#   all other sequences are simply appended to the configuration tail.
# INPUTS
#   * node_id -- the node id of the node whose config section is inserted
#   * section -- represents the section that is being inserted. If there
#     was a section in network config with the same section head, it is lost.
#****

proc netconfInsertSection { node section } {
    global $node

    set sectionhead [lindex $section 0]
    netconfClearSection $node $sectionhead
    set i [lsearch [set $node] "network-config *"]
    set netconf [lindex [lindex [set $node] $i] 1]
    set lnum_beg end
    if { "[lindex $sectionhead 0]" == "interface" } {
	set lnum [lsearch $netconf "hostname *"]
	if { $lnum >= 0 } {
	    set lnum_beg [expr $lnum + 2]
	}
    } elseif { "[lindex $sectionhead 0]" == "hostname" } {
	set lnum_beg 0
    }
    if { "[lindex $section end]" != "!" } {
	lappend section "!"
    }
    foreach line $section {
	set netconf [linsert $netconf $lnum_beg $line]
	if { $lnum_beg != "end" } {
	    incr lnum_beg
	}
    }
    set $node [lreplace [set $node] $i $i [list network-config $netconf]]
}


#Boeing: proc to find out whether tcpdump should be on for an interface
proc getIfcDumpState { node ifc } {
    foreach line [netconfFetchSection $node "nocustom interface $ifc"] {
	if { [lindex $line 0] == "tcpdump" } {
	    return "tcpdump on"
	}
    }
    return "tcpdump off"
}

#Boeing: proc to set tcpdump for an interface
proc setIfcDumpState { node ifc state } {
    set ifcfg [list "interface $ifc"]
    if { $state == "tcpdump on" } {
	lappend ifcfg " tcpdump"
    }
    foreach line [netconfFetchSection $node "interface $ifc"] {
        if { [lindex $line 0] != "tcpdump" && \
	    [lrange $line 0 1] != "no tcpdump" } {
            lappend ifcfg $line
        }
    }
    netconfInsertSection $node $ifcfg
}


#****f* nodecfg.tcl/getIfcOperState
# NAME
#   getIfcOperState -- get interface operating state
# SYNOPSIS
#   set state [getIfcOperState $node_id $ifc]
# FUNCTION
#   Returns the operating state of the specified interface. It can be "up" or "down".
# INPUTS
#   * node_id -- node id
#   * ifc     -- The interface that is up or down
# RESULT
#   * state -- the operating state of the interface, can either "up" or "down".
#****

proc getIfcOperState { node ifc } {
    foreach line [netconfFetchSection $node "nocustom interface $ifc"] {
	if { [lindex $line 0] == "shutdown" } {
	    return "down"
	}
    }
    return "up"
}

#****f* nodecfg.tcl/setIfcOperState
# NAME
#   setIfcOperState -- set interface operating state
# SYNOPSIS
#   setIfcOperState $node_id $ifc
# FUNCTION
#   Sets the operating state of the specified interface. It can be set to "up" or "down".
# INPUTS
#   * node_id  -- node id
#   * ifc      -- interface
#   * state    -- new operating state of the interface, can be either "up" or "down"
#****

proc setIfcOperState { node ifc state } {
    set ifcfg [list "interface $ifc"]
    if { $state == "down" } {
	lappend ifcfg " shutdown"
    }
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lindex $line 0] != "shutdown" && \
	    [lrange $line 0 1] != "no shutdown" } {
	    lappend ifcfg $line
	}
    }
    netconfInsertSection $node $ifcfg
}

#****f* nodecfg.tcl/getIfcQDisc
# NAME
#   getIfcQDisc -- get interface queuing discipline
# SYNOPSIS
#   set qdisc [getIfcQDisc $node_id $ifc]
# FUNCTION
#   Returns one of the supported queuing discipline ("FIFO", "WFQ" or "DRR") that is activ
#   for the specified interface.
# INPUTS
#   * node_id -- represents the node id of the node whose interface's queuing discipline is checked.
#   * ifc     -- The interface name.
# RESULT
#   * qdisc -- returns queuing discipline of the interface, can be "FIFO", "WFQ" or "DRR".
#****

proc getIfcQDisc { node ifc } {
    foreach line [netconfFetchSection $node "nocustom interface $ifc"] {
	if { [lindex $line 0] == "fair-queue" } {
	    return WFQ
	}
	if { [lindex $line 0] == "drr-queue" } {
	    return DRR
	}
    }
    return FIFO
}

#****f* nodecfg.tcl/setIfcQDisc
# NAME
#   setIfcQDisc -- set interface queueing discipline
# SYNOPSIS
#   setIfcQDisc $node_id $ifc $qdisc
# FUNCTION
#	Sets the new queuing discipline for the interface. Implicit default is FIFO.
# INPUTS
#   * node_id  -- represents the node id of the node whose interface's queuing discipline is set.
#   * ifc      -- interface name.
#   * qdisc    -- queuing discipline of the interface, can be "FIFO", "WFQ" or "DRR".
#****

proc setIfcQDisc { node ifc qdisc } {
    set ifcfg [list "interface $ifc"]
    if { $qdisc == "WFQ" } {
	lappend ifcfg " fair-queue"
    }
    if { $qdisc == "DRR" } {
	lappend ifcfg " drr-queue"
    }
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lindex $line 0] != "fair-queue" && \
	    [lindex $line 0] != "drr-queue" } {
	    lappend ifcfg $line
	}
    }
    netconfInsertSection $node $ifcfg
}

#****f* nodecfg.tcl/getIfcQDrop
# NAME
#   getIfcQDrop -- get interface queue dropping policy
# SYNOPSIS
#   set qdrop [getIfcQDrop $node_id $ifc]
# FUNCTION
#   Returns one of the supported queue dropping policies ("drop-tail" or "drop-head") that is active
#   for the specified interface.
# INPUTS
#   * node_id -- represents the node id of the node whose interface's queue dropping policy is checked.
#   * ifc     -- The interface name.
# RESULT
#   * qdrop -- returns queue dropping policy of the interface, can be "drop-tail" or "drop-head".
#****

proc getIfcQDrop { node ifc } {
    foreach line [netconfFetchSection $node "nocustom interface $ifc"] {
	if { [lindex $line 0] == "drop-head" } {
	    return drop-head
	}
    }
    return drop-tail
}

#****f* nodecfg.tcl/setIfcQDrop
# NAME
#   setIfcQDrop -- set interface queue dropping policy

# SYNOPSIS
#   setIfcQDrop $node_id $ifc $qdrop
# FUNCTION
#   Sets the new queuing discipline. Implicit default is "drop-tail".
# INPUTS
#   * node_id -- represents the node id of the node whose interface's queue droping policie is set.
#   * ifc     -- interface name.
#   * qdrop   -- new queue dropping policy of the interface, can be "drop-tail" or "drop-head".
#****

proc setIfcQDrop { node ifc qdrop } {
    set ifcfg [list "interface $ifc"]
    if { $qdrop == "drop-head" } {
	lappend ifcfg " drop-head"

    }
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lindex $line 0] != "drop-head" && \
	    [lindex $line 0] != "drop-tail" } {
	    lappend ifcfg $line
	}
    }
    netconfInsertSection $node $ifcfg
}

#****f* nodecfg.tcl/getIfcQLen
# NAME
#   getIfcQLen -- get interface queue length
# SYNOPSIS
#   set qlen [getIfcQLen $node_id $ifc]
# FUNCTION
#   Returns the queue length limit in number of packets.
# INPUTS
#   * node_id -- represents the node id of the node whose interface's queue length is checked.
#   * ifc     -- interface name.
# RESULT
#   * qlen -- queue length limit represented in number of packets.
#****

proc getIfcQLen { node ifc } {
    foreach line [netconfFetchSection $node "nocustom interface $ifc"] {
	if { [lindex $line 0] == "queue-len" } {
	    return [lindex $line 1]
	}
    }
    return 50
}

#****f* nodecfg.tcl/setIfcQLen
# NAME
#   setIfcQLen -- set interface queue length
# SYNOPSIS
#   setIfcQLen $node_id $ifc $len
# FUNCTION
#   Sets the queue length limit.
# INPUTS
#   * node_id -- represents the node id of the node whose interface's queue length is set.
#   * ifc     -- interface name.
#   * qlen    -- queue length limit represented in number of packets.
#****

proc setIfcQLen { node ifc len } {
    set ifcfg [list "interface $ifc"]
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lindex $line 0] != "queue-len" } {
	    lappend ifcfg $line
	}
    }
    if { $len > 5 && $len != 50 } {
	lappend ifcfg " queue-len $len"
    }
    netconfInsertSection $node $ifcfg
}

#****f* nodecfg.tcl/getIfcMTU
# NAME
#   getIfcMTU -- get interface MTU size.
# SYNOPSIS
#   set mtu [getIfcMTU $node_id $ifc]
# FUNCTION
#   Returns the configured MTU, or a default MTU.
# INPUTS
#   * node_id -- represents the node id of the node whose interface's MTU is checked.
#   * ifc     -- interface name.
# RESULT
#   * mtu -- maximum transmission unit of the packet, represented in bytes.
#****

proc getIfcMTU { node ifc } {
    foreach line [netconfFetchSection $node "nocustom interface $ifc"] {
	if { [lindex $line 0] == "mtu" } {
	    return [lindex $line 1]
	}
    }
    # Return defaults
    switch -exact [string range $ifc 0 2] {
	eth { return 1500 }
	ser { return 2044 }
    }
}

#****f* nodecfg.tcl/setIfcMTU
# NAME
#   setIfcMTU -- set interface MTU size.
# SYNOPSIS
#   setIfcMTU $node_id $ifc $mtu
# FUNCTION
#   Sets the new MTU. Zero MTU value denotes the default MTU.
# INPUTS
#   * node_id -- represents the node id of the node whose interface's MTU is set.
#   * ifc     -- interface name.
#   * mtu     -- maximum transmission unit of a packet, represented in bytes.
#****

proc setIfcMTU { node ifc mtu } {
    set ifcfg [list "interface $ifc"]
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lindex $line 0] != "mtu" } {
	    lappend ifcfg $line
	}
    }
    switch -exact [string range $ifc 0 2] {
	eth { set limit 1500 }
	ser { set limit 2044 }
    }
    if { $mtu >= 256 && $mtu < $limit } {
	lappend ifcfg " mtu $mtu"
    }
    netconfInsertSection $node $ifcfg
}

#****f* nodecfg.tcl/getIfcIPv4addr
# NAME
#   getIfcIPv4addr -- get interface IPv4 address.
# SYNOPSIS
#   set addr [getIfcIPv4addr $node_id $ifc]
# FUNCTION
#   Returns the list of IPv4 addresses assigned to the specified interface.
# INPUTS
#   * node_id -- node id
#   * ifc  -- interface name.
# RESULT
#   * addr -- A list of all the IPv4 addresses assigned to the specified interface.
#****

proc getIfcIPv4addr { node ifc } {
    set addrlist {}
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lrange $line 0 1] == "ip address" } {
	    lappend addrlist [lindex $line 2]
	}
    }
    # XXX remove this extra check if special OpenVZ case is removed
    # this forces a search of network-config when no IP address has been found
    if { [llength $addrlist] == 0 } {
	foreach line [netconfFetchSection $node "nocustom interface $ifc"] {
	    if { [lrange $line 0 1] == "ip address" } {
		lappend addrlist [lindex $line 2]
	    }
	}
    }
    return $addrlist
}

#****f* nodecfg.tcl/setIfcIPv4addr
# NAME
#   setIfcIPv4addr -- set interface IPv4 address.
# SYNOPSIS
#   setIfcIPv4addr $node_id $ifc $addr
# FUNCTION
#   Sets a new IPv4 address(es) on an interface. The correctness of the
#   IP address format is not checked / enforced.
# INPUTS
#   * node_id -- the node id of the node whose interface's IPv4 address is set.
#   * ifc     -- interface name.
#   * addr    -- new IPv4 address.
#****

proc setIfcIPv4addr { node ifc addr } {
    set ifcfg [list "interface $ifc"]
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lrange $line 0 1] != "ip address" } {
	    lappend ifcfg $line
	}
    }
    if { $addr != "" } {
	lappend ifcfg " ip address $addr"
    }
    netconfInsertSection $node $ifcfg
    return
}

#****f* nodecfg.tcl/getIfcIPv6addr
# NAME
#   getIfcIPv6addr -- get interface IPv6 address.
# SYNOPSIS
#   set addr [getIfcIPv6addr $node_id $ifc]
# FUNCTION
#   Returns the list of IPv6 addresses assigned to the specified interface.
# INPUTS
#   * node_id -- the node id of the node whose interface's IPv6 addresses are returned.
#   * ifc     -- interface name.
# RESULT
#   * addr -- A list of all the IPv6 addresses assigned to the specified interface.
#****

proc getIfcIPv6addr { node ifc } {
    set addrlist {}
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lrange $line 0 1] == "ipv6 address" } {
	    lappend addrlist [lindex $line 2]
	}
    }
    return $addrlist
}

#****f* nodecfg.tcl/setIfcIPv6addr
# NAME
#   setIfcIPv6addr -- set interface IPv6 address.
# SYNOPSIS
#   setIfcIPv6addr $node_id $ifc $addr
# FUNCTION
#   Sets a new IPv6 address(es) on an interface. The correctness of the
#   IP address format is not checked / enforced.
# INPUTS
#   * node_id -- the node id of the node whose interface's IPv4 address is set.
#   * ifc     -- interface name.
#   * addr    -- new IPv6 address.
#****

proc setIfcIPv6addr { node ifc addr } {
    set ifcfg [list "interface $ifc"]
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lrange $line 0 1] != "ipv6 address" } {
	    lappend ifcfg $line
	}
    }
    if { $addr != "" } {
	lappend ifcfg " ipv6 address $addr"
    }
    netconfInsertSection $node $ifcfg
}

proc getIfcMacaddr { node ifc } {
    set addrlist {}
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lrange $line 0 1] == "mac address" } {
 	    lappend addrlist [lindex $line 2]
 	}
    }
    return $addrlist
}

proc setIfcMacaddr { node ifc macaddr} {
    set ifcfg [list "interface $ifc"]
    foreach line [netconfFetchSection $node "interface $ifc"] {
	if { [lrange $line 0 1] != "mac address" } {
	    lappend ifcfg $line
	}
    }
    if { $macaddr != "" } {
	lappend ifcfg " mac address $macaddr"
    }
    netconfInsertSection $node $ifcfg
}

#****f* nodecfg.tcl/getStatIPv4routes
# NAME
#   getStatIPv4routes -- get static IPv4 routes.
# SYNOPSIS
#   set routes [getStatIPv4routes $node_id]
# FUNCTION
#   Returns a list of all static IPv4 routes as a list of
#   {destination gateway {metric}} pairs.
# INPUTS
#   * node_id -- node id
# RESULT
#   * routes -- the list of all static routes defined for the specified node
#****

proc getStatIPv4routes { node } {
    global $node

    set routes {}
    set netconf [lindex [lsearch -inline [set $node] "network-config *"] 1]
    foreach entry [lsearch -all -inline $netconf "ip route *"] {
	lappend routes [lrange $entry 2 end]
    }
    return $routes
}

#****f* nodecfg.tcl/setStatIPv4routes
# NAME
#   setStatIPv4routes -- set static IPv4 routes.
# SYNOPSIS
#   setStatIPv4routes $node_id $routes
# FUNCTION
#   Replace all current static route entries with a new one, in form of
#   a list of {destination gateway {metric}} pairs.
# INPUTS
#   * node_id -- the node id of the node whose static routes are set.
#   * routes  -- the list of all static routes defined for the specified node
#****

proc setStatIPv4routes { node routes } {
    netconfClearSection $node "ip route [lindex [getStatIPv4routes $node] 0]"
    set section {}
    foreach route $routes {
	lappend section "ip route $route"
    }
    netconfInsertSection $node $section
}

#****f* nodecfg.tcl/getStatIPv6routes
# NAME
#   getStatIPv6routes -- get static IPv6 routes.
# SYNOPSIS
#   set routes [getStatIPv6routes $node_id]
# FUNCTION
#   Returns a list of all static IPv6 routes as a list of
#   {destination gateway {metric}} pairs.
# INPUTS
#   * node_id -- node id
# RESULT
#   * routes -- the list of all static routes defined for the specified node
#****

proc getStatIPv6routes { node } {
    global $node

    set routes {}
    set netconf [lindex [lsearch -inline [set $node] "network-config *"] 1]
    foreach entry [lsearch -all -inline $netconf "ipv6 route *"] {
	lappend routes [lrange $entry 2 end]
    }
    return $routes
}

#****f* nodecfg.tcl/setStatIPv6routes
# NAME
#   setStatIPv4routes -- set static IPv6 routes.
# SYNOPSIS
#   setStatIPv6routes $node_id $routes
# FUNCTION
#   Replace all current static route entries with a new one, in form of
#   a list of {destination gateway {metric}} pairs.
# INPUTS
#   * node_id -- node id
#   * routes  -- the list of all static routes defined for the specified node
#****

proc setStatIPv6routes { node routes } {
    netconfClearSection $node "ipv6 route [lindex [getStatIPv6routes $node] 0]"
    set section {}
    foreach route $routes {
	lappend section "ipv6 route $route"

    }
    netconfInsertSection $node $section
}

#****f* nodecfg.tcl/getNodeName
# NAME
#   getNodeName -- get node name.
# SYNOPSIS
#   set name [getNodeName $node_id]
# FUNCTION
#   Returns node's logical name.
# INPUTS
#   * node_id -- node id
# RESULT
#   * name -- logical name of the node
#****

proc getNodeName { node } {
    global $node

    set netconf [lindex [lsearch -inline [set $node] "network-config *"] 1]
    return [lrange [lsearch -inline $netconf "hostname *"] 1 end]
}

#****f* nodecfg.tcl/setNodeName
# NAME
#   setNodeName -- set node name.
# SYNOPSIS
#   setNodeName $node_id $name
# FUNCTION
#   Sets node's logical name.
# INPUTS
#   * node_id -- node id
#   * name    -- logical name of the node
#****

proc setNodeName { node name } {
    netconfClearSection $node "hostname [getNodeName $node]"
    netconfInsertSection $node [list "hostname $name"]
}

#****f* nodecfg.tcl/getNodeType
# NAME
#   getNodeType -- get node type.
# SYNOPSIS
#   set type [getNodeType $node_id]
# FUNCTION
#   Returns node's type.
# INPUTS
#   * node_id -- node id
# RESULT
#   * type -- type of the node
#****

proc nodeType { node } {
    global $node

    return [lindex [lsearch -inline [set $node] "type *"] 1]
}

#****f* nodecfg.tcl/getNodeModel
# NAME
#   getNodeModel -- get node routing model.
# SYNOPSIS
#   set model [getNodeModel $node_id]
# FUNCTION
#
# INPUTS
#   * node_id -- node id
# RESULT
#   * model -- routing model of the specified node
#****

proc getNodeModel { node } {
    global $node

    return [lindex [lsearch -inline [set $node] "model *"] 1]
}

#****f* nodecfg.tcl/setNodeModel
# NAME
#   setNodeModel -- set node routing model.
# SYNOPSIS
#   setNodeModel $node_id $model
# FUNCTION
#
# INPUTS
#   * node_id -- node id
#   * model   -- routing model of the specified node
#****

proc setNodeModel { node model } {
    global $node

    set i [lsearch [set $node] "model *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i "model $model"]
    } else {
	set $node [linsert [set $node] 1 "model $model"]
    }
}

#****f* nodecfg.tcl/getNodeCoords
# NAME
#   getNodeCoords -- get node icon coordinates.
# SYNOPSIS
#   set coords [getNodeCoords $node_id]
# FUNCTION
#   Returns node's icon coordinates.
# INPUTS
#   * node_id -- node id
# RESULT
#   * coords -- coordinates of the node's icon a list in form of {Xcoord Ycoord}
#****

proc getNodeCoords { node } {
    global $node

    return [lindex [lsearch -inline [set $node] "iconcoords *"] 1]
}

#****f* nodecfg.tcl/setNodeCoords
# NAME
#   setNodeCoords -- set node's icon coordinates.
# SYNOPSIS

#   setNodeCoords $node_id $coords
# FUNCTION
#   Sets node's icon coordinates.
# INPUTS
#   * node_id -- node id
#   * coords  -- coordinates of the node's icon in form of Xcoord Ycoord
#****

proc setNodeCoords { node coords } {
    global $node

    set i [lsearch [set $node] "iconcoords *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i "iconcoords {$coords}"]
    } else {
	set $node [linsert [set $node] end "iconcoords {$coords}"]
    }
    writeNodeCoords $node $coords
}

# this saves each node's current X,Y position to a /tmp/pycore.nnnnn/nX.xy
proc writeNodeCoords { node coords } {
    global oper_mode g_current_session

    if { [info exists oper_mode] && $oper_mode != "exec" } { return }
    if { $g_current_session == 0 } { return }
    if { [nodeType $node] != "router" } { return }

    set fn "/tmp/pycore.$g_current_session/$node.xy"
    catch { 
	set f [open $fn w]
	puts $f $coords
	close $f
    }
}

# cleanup the /tmp/pycore.nnnnn/nX.xy file
proc deleteNodeCoords { node } {
    global g_current_session

    if { $g_current_session == 0 } { return }
    if { [nodeType $node] != "router" } { return }

    set fn "/tmp/pycore.$g_current_session/$node.xy"
    if { [file exists $fn] } { file delete $fn }
}

#****f* nodecfg.tcl/getNodeLabelCoords
# NAME
#   getNodeLabelCoords -- get node's label coordinates.
# SYNOPSIS
#   set coords [getNodeLabelCoords $node_id]
# FUNCTION
#   Returns node's label coordinates.
# INPUTS
#   * node_id -- node id
# RESULT
#   * coords -- coordinates of the node's label a list in form of {Xcoord Ycoord}
#****

proc getNodeLabelCoords { node } {
    global $node

    return [lindex [lsearch -inline [set $node] "labelcoords *"] 1]
}

#****f* nodecfg.tcl/setNodeLabelCoords
# NAME
#   setNodeLabelCoords -- set node's label coordinates.
# SYNOPSIS
#   setNodeLabelCoords $node_id $coords
# FUNCTION
#   Sets node's label coordinates.
# INPUTS
#   * node_id -- node id
#   * coords  -- coordinates of the node's label in form of Xcoord Ycoord
#****

proc setNodeLabelCoords { node coords } {
    global $node

    set i [lsearch [set $node] "labelcoords *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i "labelcoords {$coords}"]
    } else {
	set $node [linsert [set $node] end "labelcoords {$coords}"]
    }
}

# return [dx, dy] offset for a node label, which may depend on its type
proc getDefaultLabelOffsets { nodetype } {
    set dx 0
    set dy 32
    if { [lsearch {hub lanswitch} $nodetype] >= 0 } {
	set dy 24
    }
    return [list $dx $dy]
}

#****f* nodecfg.tcl/ifcList
# NAME
#   ifcList -- get list of all interfaces
# SYNOPSIS
#   set ifcs [ifcList $node_id]
# FUNCTION
#   Returns a list of all interfaces present in a node.
# INPUTS
#   * node_id -- node id
# RESULT
#   * ifcs -- list of all node's interfaces.
#****

proc ifcList { node } {
    global $node
    if { ![info exists $node] } { return "" }
    set interfaces ""
    foreach entry [lsearch -all -inline [set $node] "interface-peer *"] {
	lappend interfaces [lindex [lindex $entry 1] 0]
    }
    return $interfaces
}

#****f* nodecfg.tcl/peerByIfc
# NAME
#   peerByIfc -- get node's peer by interface.
# SYNOPSIS
#   set peer [peerByIfc $node_id $ifc]
# FUNCTION
#   Returns id of the node on the other side of the interface. If the node 
#   on the other side of the interface is situated on the other canvas or connected
#   via split link, this function returns a pseudo node.
# INPUTS
#   * node_id -- node id
#   * ifc     -- interface name
# RESULT
#   * peer -- node id of the node on the other side of the interface
#****

proc peerByIfc { node ifc } {
    global $node

    set entry [lsearch -inline [set $node] "interface-peer {$ifc *}"]
    return [lindex [lindex $entry 1] 1]
}

#****f* nodecfg.tcl/logicalPeerByIfc
# NAME
#   logicalPeerByIfc -- get node's peer by interface.
# SYNOPSIS
#   set peer [logicalPeerByIfc $node_id $ifc]
# FUNCTION
#   Returns id of the node on the other side of the interface. If the node on the other
#   side of the interface is connected via normal link (not split) this function acts the same
#   as the function peerByIfc, but if the nodes are connected via split links or situated on different
#   canvases this function returns the logical peer node.
# INPUTS
#   * node_id -- node id
#   * ifc     -- interface name
# RESULT
#   * peer -- node id of the node on the other side of the interface
#****

proc logicalPeerByIfc { node ifc } {
    global $node

    set peer [peerByIfc $node $ifc]
    if { $peer == "" } { return "" }; # Boeing
    if { [nodeType $peer] != "pseudo" } {
	return $peer

    } else {
	set mirror_node [getNodeMirror $peer]
	set mirror_ifc [ifcList $mirror_node]
	return [peerByIfc $mirror_node $mirror_ifc]
    }
}

#****f* nodecfg.tcl/ifcByPeer
# NAME
#   ifcByPeer -- get node interface by peer.
# SYNOPSIS
#   set ifc [peerByIfc $node_id $peer_id]
# FUNCTION
#   Returns the name of the interface connected to the specified peer.
#   If the peer node is on different canvas or connected via split link
#   to the specified node this function returns an empty string.
# INPUTS
#   * node_id -- node id
#   * peer_id -- id of the peer node
# RESULT
#   * ifc -- interface name
#****

proc ifcByPeer { node peer } {
    global $node

    set entry [lsearch -inline [set $node] "interface-peer {* $peer}"]
    return [lindex [lindex $entry 1] 0]
}

#****f* nodecfg.tcl/ifcByLogicalPeer
# NAME
#   ifcByPeer -- get node interface by peer.
# SYNOPSIS
#   set ifc [peerByIfc $node_id $peer_id]
# FUNCTION
#   Returns the name of the interface connected to the specified peer.
#   Returns the right interface even if the peer node is on the other
#   canvas or connected via split link.
# INPUTS
#   * node_id -- node id
#   * peer_id -- id of the peer node
# RESULT
#   * ifc -- interface name
#****

proc ifcByLogicalPeer { node peer } {
    global $node

    set ifc [ifcByPeer $node $peer]
    if { $ifc == "" } {
	#
	# Must search through pseudo peers
	#
	foreach ifc [ifcList $node] {
	    set t_peer [peerByIfc $node $ifc]
	    if { [nodeType $t_peer] == "pseudo" } {
		set mirror [getNodeMirror $t_peer]
		if { [peerByIfc $mirror [ifcList $mirror]] == $peer } {
		    return $ifc
		}
	    }
	}
	return ""
    } else {
	return $ifc    
    }
}

#****f* nodecfg.tcl/hasIPv4Addr
# NAME
#   hasIPv4Addr -- has IPv4 address.
# SYNOPSIS
#   set check [hasIPv4Addr $node_id]
# FUNCTION
#   Returns true if at least one interface has an IPv4 address
#   configured, otherwise returns false.
# INPUTS
#   * node_id -- node id
# RESULT
#   * check -- true if at least one interface has IPv4 address, otherwise false.
#****

proc hasIPv4Addr { node } {
    foreach ifc [ifcList $node] {
	if { [getIfcIPv4addr $node $ifc] != "" } {
	    return true
	}
    }
    return false
}

#****f* nodecfg.tcl/hasIPv6Addr
# NAME
#   hasIPv4Addr -- has IPv6 address.
# SYNOPSIS
#   set check [hasIPv6Addr $node_id]
# FUNCTION
#   Retruns true if at least one interface has an IPv6 address
#   configured, otherwise returns false.
# INPUTS
#   * node_id -- node id
# RESULT
#   * check -- true if at least one interface has IPv6 address, otherwise false.
#****

proc hasIPv6Addr { node } {
    foreach ifc [ifcList $node] {
	if { [getIfcIPv6addr $node $ifc] != "" } {
	    return true
	}
    }
    return false
}

#****f* nodecfg.tcl/removeNode
# NAME
#   removeNode -- removes the node
# SYNOPSIS
#   removeNode $node_id
# FUNCTION
#   Removes the specified node as well as all the links binding that node to 
#   the other nodes.
# INPUTS
#   * node_id -- node id
#****

proc removeNode { node } {
    global node_list $node

    foreach ifc [ifcList $node] {
	set peer [peerByIfc $node $ifc]
	set link [linkByPeers $node $peer]
	removeLink $link
    }
    set i [lsearch -exact $node_list $node]
    set node_list [lreplace $node_list $i $i]
}

#****f* nodecfg.tcl/getNodeCanvas
# NAME
#   getNodeCanvas -- get node canvas id
# SYNOPSIS
#   set canvas [getNodeCanvas $node_id]
# FUNCTION
#   Returns node's canvas affinity.
# INPUTS
#   * node_id -- node id
# RESULT
#   * canvas -- canvas id
#****

proc getNodeCanvas { node } {
    global $node

    return [lindex [lsearch -inline [set $node] "canvas *"] 1]
}

#****f* nodecfg.tcl/setNodeCanvas
# NAME
#   setNodeCanvas -- set node canvas
# SYNOPSIS
#   setNodeCanvas $node_id $canvas
# FUNCTION
#   Sets node's canvas affinity.
# INPUTS
#   * node_id -- node id
#   * canvas -- canvas id
#****

proc setNodeCanvas { node canvas } {
    global $node

    set i [lsearch [set $node] "canvas *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i "canvas $canvas"]
    } else {
	set $node [linsert [set $node] end "canvas $canvas"]
    }
}

proc getNodeHidden { node } {
    global $node

    set h [lindex [lsearch -inline [set $node] "hidden *"] 1]
    if { $h == "" } { return 0 }
    return $h
}

proc setNodeHidden { node value } {
    global $node

    set i [lsearch [set $node] "hidden *"]
    if { $value == 0 } {
	if { $i >= 0 } {
	    set $node [lreplace [set $node] $i $i]
	}
	return
    }
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i "hidden $value"]
    } else {
	set $node [linsert [set $node] end "hidden $value"]
    }
}

#****f* nodecfg.tcl/newIfc
# NAME
#   newIfc -- new interface
# SYNOPSIS
#   set ifc [newIfc $type $node_id]
# FUNCTION
#   Returns the first available name for a new interface of the specified type.
# INPUTS
#   * node_id -- node id
#   * type    -- type
# RESULT
#   * ifc -- the first available name for a interface of the specified type
#****

proc newIfc { type node } {
    set interfaces [ifcList $node]
    set firstinterface 0
    for { set id $firstinterface } { [lsearch -exact $interfaces $type$id] >= 0 } {incr id} {}
    return $type$id
}

#****f* nodecfg.tcl/newNode
# NAME
#   newNode -- new node
# SYNOPSIS
#   set node_id [newNode $type]
# FUNCTION
#   Returns the node id of a new node of the specified type.
# INPUTS
#   * type -- node type
# RESULT
#   * node_id -- node id of a new node of the specified type
#****

proc newNode { type } {
    global node_list def_router_model
    global viewid
    catch {unset viewid}

    # overload the passed in parameter - allow specifing new node num
    if { [llength $type] > 1 } {
    	set node [lindex $type 1]
	set type [lindex $type 0]
    } else {
    set node [newObjectId node]
    }
	
    global $node
    set $node {}
    lappend $node "type $type"
    if { $type == "router" } {
	lappend $node "model $def_router_model"
	set nconfig [list \
		"hostname $node" \
		! ]
    # tunnel
    } elseif {$type == "rj45" || $type == "tunnel" || $type == "ktunnel" } {
	set nconfig [list \
		"hostname UNASSIGNED" \
		! ]
    # set wlan default parameters upon creation
    } elseif { $type == "wlan" } {
	global DEFAULT_WLAN_MODEL DEFAULT_WLAN_MODEL_TYPES 
	global DEFAULT_WLAN_MODEL_VALS
	set nconfig [list \
		"hostname $type[string range $node 1 end]" \
		! \
		"mobmodel" \
		"coreapi" \
		"$DEFAULT_WLAN_MODEL" \
		! ]
	lappend $node "network-config [list $nconfig]"
	setCustomConfig $node $DEFAULT_WLAN_MODEL $DEFAULT_WLAN_MODEL_TYPES \
			$DEFAULT_WLAN_MODEL_VALS 0
    } else {
		set nconfig [list \
		"hostname $node" \
		! ]
    }

    # wlan has already changed node global above
    if { $type != "wlan" } {
    lappend $node "network-config [list $nconfig]"
    }
    lappend node_list $node
    return $node
}

#****f* nodecfg.tcl/getNodeMirror
# NAME
#   getNodeMirror -- get node mirror
# SYNOPSIS
#   set mirror_node_id [getNodeMirror $node_id]
# FUNCTION
#   Returns the node id of a mirror pseudo node of the node. Mirror node is the
#   corresponding pseudo node. The pair of pseudo nodes, node and his mirror node, are 
#   introduced to form a split in a link. This split can be used for avoiding crossed 
#   links or for displaying a link between the nodes on a different canvas.
# INPUTS
#   * node_id -- node id
# RESULT
#   * mirror_node_id -- node id of a mirror node
#****

proc getNodeMirror { node } {
    global $node

    return [lindex [lsearch -inline [set $node] "mirror *"] 1]
}

#****f* nodecfg.tcl/setNodeMirror
# NAME
#   setNodeMirror -- set node mirror
# SYNOPSIS
#   setNodeMirror $node_id $mirror_node_id
# FUNCTION
#   Sets the node id of a mirror pseudo node of the specified node. Mirror node is the
#   corresponding pseudo node. The pair of pseudo nodes, node and his mirror node, are 
#   introduced to form a split in a link. This split can be used for avoiding crossed 
#   links or for displaying a link between the nodes on a different canvas.
# INPUTS
#   * node_id -- node id
#   * mirror_node_id -- node id of a mirror node
#****

proc setNodeMirror { node value } {
    global $node

    set i [lsearch [set $node] "mirror *"]
    if { $value == "" } {
	set $node [lreplace [set $node] $i $i]
    } else {
	set $node [linsert [set $node] end "mirror $value"]
    }
}


#****f* nodecfg.tcl/setType
# NAME
#   setType -- set node's type.
# SYNOPSIS
#   setType $node_id $type
# FUNCTION
#   Sets node's type.
# INPUTS
#   * node_id -- node id
#   * type  -- type of node
#****

proc setType { node type } {
    global $node

    set i [lsearch [set $node] "type *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i "type $type"]
    } else {
	set $node [linsert [set $node] 1 "type $type"]
    }
}

# begin Boeing: node commands specific to wlan
proc getNodeRange { node } {
    global $node

    return [lindex [lsearch -inline [set $node] "range *"] 1]
}

proc setNodeRange { node value } {
    global $node
    set i [lsearch [set $node] "range *"]
    if { $value == "" } {
	if { $i > 0 } {
	    set $node [lreplace [set $node] $i $i]
	}
	return
    }
    if { $i > 0 } {
	set $node [lreplace [set $node] $i $i "range $value"]
    } else {
        set $node [linsert [set $node] end "range $value"]
    }
    return
}
# end Boeing

# Boeing - custom post config commands
proc getCustomPostConfigCommands { node } {
    global $node
    return [lindex [lsearch -inline [set $node] "custom-post-config-commands *"] 1]
}

#Boeing custom pre config commands
proc getCustomPreConfigCommands { node } {
    global $node
    return [lindex [lsearch -inline [set $node] "custom-pre-config-commands *"] 1]
}

#Boeing custom post config commands
proc setCustomPostConfigCommands { node cfg } {
    global $node

    set i [lsearch [set $node] "custom-post-config-commands *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i]
    }
    if { $cfg != {} } {
	lappend $node [list custom-post-config-commands $cfg]
    }
    return
}

# get the services saved for this node; if want_defaults is true and no services
# have been configured, return the default services for this node type
proc getNodeServices { node want_defaults } {
    global $node

    set i [lsearch [set $node] "services *"]
    set s [lindex [lindex [set $node] $i] 1] 
    if { $want_defaults && $i < 0 } {
	set s [getNodeTypeServices [getNodeModel $node]]
    }
    return $s
}

# save the list of services configured for this node
proc setNodeServices { node services } {
    global $node

    set i [lsearch [set $node] "services *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i "services {$services}"]
    } else {
	set $node [linsert [set $node] end "services {$services}"]
    }
}

# Boeing - custom image
proc getCustomImage { node } {
	global $node
	return [lindex [lsearch -inline [set $node] "custom-image *"] 1]
}

# Boeing - custom image
proc setCustomImage { node image } {
    global $node

    set i [lsearch [set $node] "custom-image *"]
    if { $i >= 0 } {
	set $node [lreplace [set $node] $i $i]
    }
    if { $image != "" } {
	lappend $node [list custom-image $image]
    }
    return
}

# if cmd=save save all node positions, otherwise reset them with cmd=reset
proc resetAllNodeCoords { cmd } {
    global node_list g_saved_node_coords zoom

    # save the node coordinates to a global array
    if { $cmd == "save" } {
	array unset g_saved_node_coords
    	foreach node $node_list {
	    set coords [getNodeCoords $node]
	    if { $coords == "" } { continue }
	    array set g_saved_node_coords [list $node $coords]
	}
    # restore the node coordinates from the global array
    } elseif { $cmd == "reset" } {
	if { ![array exists g_saved_node_coords] } { return }
    	foreach node $node_list {
	    if { ![info exists g_saved_node_coords($node)] } { continue }
	    set coords $g_saved_node_coords($node)
	    if { [llength $coords] != 2 } { continue }
	    set x [expr {$zoom * [lindex $coords 0]}]
	    set y [expr {$zoom * [lindex $coords 1]}]
	    moveNodeAbs .c $node $x $y
	}
    }

}

