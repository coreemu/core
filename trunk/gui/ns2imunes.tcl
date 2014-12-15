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

#
#****h* imunes/ns2imunes.tcl
# NAME
#  ns2imunes.tcl -- file used for converting from ns2 scripts to IMUNES conf
#  file
# FUNCTION
#  This module implements functionality for converting ns2 scripts into 
#  IMUNES conf file. Now, only basic ns2 functionalities are implemented, those
#  that can't be written in IMUNES config file or those that are not implemented
#  yet are ignored.
#****

#****f* ns2imunes.tcl/ns2im
# NAME
#   ns2im -- converts ns2 script into IMUNES and draws topology 
# SYNOPSIS
#   ns2im $ns2script
# FUNCTION
#   Implements basic logic for converting between formats. 
# INPUTS
#   * srcfile -- ns2 scripy
#****

proc ns2im { srcfile } {
    global node_list
    global link_list
    global canvas_list
    global curcanvas
    global cfg
    set cfg {}
    set node_list {}
    set link_list {}
    set canvas_list {}
    source $srcfile
    foreach node $node_list {
	setNodeCanvas $node $curcanvas
    }
    changeNodeType    
    setDefaultRoutes 
    arrangeNodes
    dumpCfg string cfg
    loadCfg $cfg
    redrawAll
    if { [file exists out.nam] == 1 } {
	file delete out.nam
    }
}

#****f* ns2imunes.tcl/new
# NAME
#   new -- basic/main ns2 function, invoked in ns2 script 
# SYNOPSIS
#   set ns [new Simulator]
# FUNCTION
#   Points to our main function: root-func.
# INPUTS
#   * object -- can be Simulator, Agent, Application. 
#****

proc new {object} {
    set arg [split $object "/"]
    set typepc "TCP UDP RTP RTCP"
    set typehost "TCPSink Null"
    if {$object == "Simulator"} {
    	return root-func
    } elseif {[lindex $arg 0] == "Agent"} {
	return nullfunc
    } elseif {[lindex $arg 0] == "Application"} {
    	return nullfunc
    } else {
    	return nullfunc
    }
} 

#****f* ns2imunes.tcl/nullfunc
# NAME
#   nullfunc -- does nothing; needed for avoiding errors. 
# SYNOPSIS
#   nullfunc args
# INPUTS
#   * can be any number of inputs
#****
proc nullfunc {args} {
}


#****f* ns2imunes.tcl/root-func
# NAME
#   root-func -- calls other functions 
# SYNOPSIS
#   root-func ns_command $args
# FUNCTION
#   For input node this procedure enables or disables custom configuration.
# INPUTS
#   * ns_command -- first arg is always name of the function
#   * args -- argument for function; there can be any number of arguments 
# RESULT
#   Returns result of function $ns_command
#****
proc root-func {ns_command args} {
    catch {
    	if {$args == ""} {
	    set x [$ns_command]
	    return $x
	} else {
	    set y [$ns_command $args]
	    return $y
	}
    } value
    return $value
}


#****f* ns2imunes.tcl/node
# NAME
#   node -- creates new node, ns_command invoked from root-func 
# SYNOPSIS
#   set node [node]
# RESULT
#   * node_id -- node id of a new node of type router
#****
proc node {} {
    set default "router"
    return [newNode $default]
}


#not implemented yet in IMUNES
proc simplex-link { linkdata } {
}


#****f* ns2imunes.tcl/duplex-link
# NAME
#   duplex-link -- creates new link, ns_command invoked from root-func
# SYNOPSIS
#   duplex-link $linkdata_list
# INPUTS
#   * linkdata -- list that describes link
#  RESULT
#   * new_link_id -- new link id.
#****
proc duplex-link { linkdata } {
    set node1 [lindex $linkdata 0]
    set node2 [lindex $linkdata 1]
    set bw [lindex $linkdata 2]
    set dly [lindex $linkdata 3]
    set type [lindex $linkdata 4]
    set link [newLink $node1 $node2]
    
    set bandwidth [getBandwidth $bw]
    setLinkBandwidth $link $bandwidth
    
    set delay [getDelay $dly]
    setLinkDelay $link $delay

    set queueingDiscipline [getQueingDiscipline $type]
}

    
#****f* ns2imunes.tcl/changeNodeType
# NAME
#   changeNodeType -- passes through list node_list and changes type of node.
# SYNOPSIS
#   changeNodeType
# FUNCTION
#   Passes through list node_list and calls procedures for changing type of
#   node if node has more than one neighbour.
#****
proc changeNodeType {} {
    global node_list
    foreach node $node_list {
	set ifc [ifcList $node]
	set ifcnum [llength $ifc]
	if { $ifcnum == 1 } {
	    setNodeModel $node "PC"
	}
    }
}


#****f* ns2imunes.tcl/setDefaultRoutes
# NAME
#   setDefaultRoutes -- sets default routes for non router nodes 
# SYNOPSIS
#   setDefaultRoutes
#****
proc setDefaultRoutes {} {
    global node_list
    foreach node $node_list {
	set type [nodeType $node] 
	if { $type == "pc" || $type == "host" } {
	    set interfaces [ifcList $node]
	    foreach ifc $interfaces {
  		autoIPv4defaultroute $node $ifc
		autoIPv6defaultroute $node $ifc
	    }
	}
    }
}


#****f* ns2imunes.tcl/getBandwidth
# NAME
#   getBandwith -- returns bandwidth value in bits 
# SYNOPSIS
#   getBandwith $bandwith
# FUNCTION
#   Detects input unit, and returns bandwidth value in bits.
# INPUTS
#   * bw -- bandwidth
#****
proc getBandwidth { bw } {
    regexp {[0-9]+} $bw value
    regexp {[A-Za-z]+} $bw unit
    switch $unit {
    	"Kb"	"return [expr $value*1000]"
	"Mb"	"return [expr $value*1000000]"
	"Gb"	"return [expr $value*1000000000]"
    }
}

#****f* ns2imunes.tcl/getDelay
# NAME
#   getDelay -- returns delay value in microseconds 
# SYNOPSIS
#   getDelay $dly
# FUNCTION
#   Detects input unit, and returns delay value in microseconds.
# INPUTS
#   * dly -- delay
#****
proc getDelay { dly } {
    regexp {[0-9]+} $dly value
    regexp {[a-z]+} $dly unit
    switch $unit {
    	"ms"	" return [expr $value*1000] "
	"us"	" return $value "
    }
}

#****f* ns2imunes.tcl/getQueingDiscipline
# NAME
#   getQueingDiscipline -- returns queing discipline 
# SYNOPSIS
#   getQueingDiscipline $type
# INPUTS
#   * type -- type of queing discipline written in ns2 format
#****
proc getQueingDiscipline { type } {
    if {[string match "DropTail" $type]} {
    	return "droptail"
    } elseif {[string match "CBQ" $type]  ||\
    	[string match "WFQ" $type]} {
	return "fair-queue"
    } elseif {[string match "DRR" $type]} {
    	return "drr-queue"
    }   
}


#****f* ns2imunes.tcl/arrangeNodes
# NAME
#   arrangeNodes -- calculates coordinates for nodes
# SYNOPSIS
#   arrangeNodes
# FUNCTION
#   Calculates and writes coordinates for every node in global variable
#   node_list.
#****
proc arrangeNodes {} {
    global node_list
    global activetool
#with next foreach loop we divide nodes on layer3/router
#nodes and edge (pc, host) nodes
    set routers {}
    set edgeNodes {}
    foreach node $node_list {
	set type [nodeType $node]
	if { $type == "router" } {
	    lappend routers $node
	} else {
	    lappend edgeNodes $node
	}
    }
    set center {450 310}
    set i 0
    set rnum [llength $routers]
    set pi [expr 2*asin(1.0)]
#next foreach loop: we arrange nodes that we have denoted as
#layer3/router nodes; we place them in a elipse circle and their 
#regular peers (pc or host) are placed above them
    foreach rnode $routers {
	set fi [expr $i*(2*$pi)/$rnum]
	set r [expr 200*(1.0-0.4*abs(sin($fi)))]
	set ximage [expr [lindex $center 0] - $r*cos($fi)]
	set yimage [expr [lindex $center 1] - $r*sin($fi)]
	
	setNodeCoords $rnode "$ximage $yimage"
	setNodeLabelCoords $rnode "$ximage [expr $yimage + 24]"
	set regularPeers [getRegularPeers $rnode]
	set regpeernum [llength $regularPeers]
	set j 0
	foreach peer $regularPeers {
	    if { [hasCoords $peer] >= 0 } {
		continue
	    }
	    set fi1 [expr ($j-$regpeernum/2)*(2*$pi/3)/$regpeernum]
	    set ximage1 [expr $ximage - 200*cos($fi+$fi1)]
	    set yimage1 [expr $yimage - 200*sin($fi+$fi1)]
	    setNodeCoords $peer "$ximage1 $yimage1"
	    set dy 32
	    setNodeLabelCoords $peer "$ximage1 [expr $yimage1 + $dy]"
	    incr j
	}
	incr i
    }
    if { $routers == "" } {
	set i 0
	foreach node $edgeNodes {
	    set fi [expr $i*(2*$pi)/[llength $edgeNodes]]
	    set r [expr 200*(1.0-0.5*abs(sin($fi)))]
	    set ximage [expr [lindex $center 0] - $r*cos($fi)]
	    set yimage [expr [lindex $center 1] - $r*sin($fi)]
	    setNodeCoords $node "$ximage $yimage"
	    set dy 32
	    setNodeLabelCoords $node "$ximage [expr $yimage + $dy]"
	    incr i
	}
    }
}


#****f* ns2imunes.tcl/getRegularPeers
# NAME
#   getRegularPeers -- returns list of pc's and hosts connected with router $node
# SYNOPSIS
#   getRegularPeers $node_id
# INPUTS
#   * node -- node_id of router to which we are finding peers
#****
proc getRegularPeers { node } {
    set interfaces [ifcList $node]
    set regularpeers ""
    foreach ifc $interfaces {
	set peer [peerByIfc $node $ifc]
	if { [nodeType $peer] == "pc" || [nodeType $peer] == "host"} {
	    lappend regularpeers $peer
	}
    }
    return $regularpeers
}


#****f* ns2imunes.tcl/hasCoords
# NAME
#   hasCoords -- detects existence of coords 
# SYNOPSIS
#   getRegularPeers $node_id
# INPUTS
#   * node -- node_id of node.
# RESULT
#   * >=0 -- coords are assigned to $node
#   * ==1 -- coords are not assigned to $node
#****
proc hasCoords {node} {
    global $node
    return [lsearch [set $node] "iconcoords *"]
}
