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
# This work was supported in part by the Croatian Ministry of Science
# and Technology through the research contract #IP-2003-143.
#

#****h* imunes/editor.tcl
# NAME
#  editor.tcl -- file used for defining functions that can be used in
#  edit mode as well as all the functions which change the appearance 
#  of the imunes GUI.
# FUNCTION
#  This module is used for defining all possible actions in imunes
#  edit mode. It is also used for all the GUI related actions.
#****


proc animateCursor {} {
    global cursorState
    global clock_seconds

    if { [clock seconds] == $clock_seconds } {
	update
	return
    }
    set clock_seconds [clock seconds]
    if { $cursorState } {
	.c config -cursor watch
	set cursorState 0
    } else {
	.c config -cursor pirate
	set cursorState 1
    }
    update
}

#****f* editor.tcl/removeGUILink
# NAME
#   removeGUILink -- remove link from GUI
# SYNOPSIS
#   renoveGUILink $link_id $atomic
# FUNCTION
#   Removes link from GUI. It removes standard links as well as
#   split links and links connecting nodes on different canvases.
# INPUTS
#   * link_id -- the link id
#   * atomic -- defines if the remove was atomic action or a part 
#     of a composed, non-atomic action (relevant for updating log 
#     for undo).
#****

proc removeGUILink { link atomic } {
    global changed

    set nodes [linkPeers $link]
    set node1 [lindex $nodes 0]
    set node2 [lindex $nodes 1]
    if { [nodeType $node1] == "pseudo" } {
	removeLink [getLinkMirror $link]
	removeLink $link
	removeNode [getNodeMirror $node1]
	removeNode $node1
	.c delete $node1
    } elseif { [nodeType $node2] == "pseudo" } {
	removeLink [getLinkMirror $link]
	removeLink $link
	removeNode [getNodeMirror $node2]
	removeNode $node2
	.c delete $node2
    } else {
	removeLink $link
    }
    .c delete $link
    if { $atomic == "atomic" } {
	set changed 1
	updateUndoLog
    }
}

#****f* editor.tcl/removeGUINode
# NAME
#   removeGUINode -- remove node from GUI
# SYNOPSIS
#   renoveGUINode $node_id
# FUNCTION
#   Removes node from GUI. When removing a node from GUI the links
#   connected to that node are also removed.
# INPUTS
#   * node_id -- node id
#****

proc removeGUINode { node } {
    set type [nodeType $node]
    foreach ifc [ifcList $node] {
	set peer [peerByIfc $node $ifc]
	set link [lindex [.c gettags "link && $node && $peer"] 1]
	removeGUILink $link non-atomic
    }
    if { [lsearch -exact "oval rectangle label text marker" $type] != -1 } {
	deleteAnnotation .c $type $node
    } elseif { $type != "pseudo" } {
	removeNode $node
	.c delete $node
    }
}

#****f* editor.tcl/updateUndoLog
# NAME
#   updateUndoLog -- update the undo log
# SYNOPSIS
#   updateUndoLog
# FUNCTION
#   Updates the undo log. Writes the current configuration to the 
#   undolog array and updates the undolevel variable.
#****

proc updateUndoLog {} {
    global changed undolog undolevel redolevel

    if { $changed } {
	global t_undolog undolog
	set t_undolog ""
	dumpCfg string t_undolog
	incr undolevel
	set undolog($undolevel) $t_undolog
	set redolevel $undolevel
	updateUndoRedoMenu ""
# Boeing: XXX why is this set here?
	set changed 0
    }
}

#****f* editor.tcl/undo
# NAME
#   undo -- undo function
# SYNOPSIS
#   undo 
# FUNCTION
#   Undo the change. Reads the undolog and updates the current
#   configuration. Reduces the value of undolevel.
#****

proc undo {} {
    global undolevel undolog oper_mode

    if {$oper_mode == "edit" && $undolevel > 0} {
	incr undolevel -1
	updateUndoRedoMenu ""
	.c config -cursor watch
	loadCfg $undolog($undolevel)
	switchCanvas none
    }
}

#****f* editor.tcl/redo
# NAME
#   redo
# SYNOPSIS
#   redo
# FUNCTION
#   Redo the change if possible (redolevel is greater than 
#   undolevel). Reads the configuration from undolog and
#   updates the current configuration. Increases the value 
#   of undolevel. 
#****

proc redo {} {
    global undolevel redolevel undolog oper_mode

    if {$oper_mode == "edit" && $redolevel > $undolevel} {
	incr undolevel
	updateUndoRedoMenu ""
	.c config -cursor watch
	loadCfg $undolog($undolevel)
	switchCanvas none
    }
}

proc updateUndoRedoMenu { forced } {
    global undolevel redolevel

    if { $forced == "" } {
	if { $undolevel > 0 } { set undo "normal" } else { set undo "disabled" }
	if { $redolevel > $undolevel } { set redo "normal"
	} else { set redo "disabled" }
    } else {
	set undo $forced
	set redo $forced
    }

    .menubar.edit entryconfigure "Undo" -state $undo
    .menubar.edit entryconfigure "Redo" -state $redo
}

#****f* editor.tcl/redrawAll
# NAME
#   redrawAll
# SYNOPSIS
#   redrawAll
# FUNCTION
#   Redraws all the objects on the current canvas.
#****


proc redrawAll {} {
    global node_list plot_list link_list annotation_list plot_list background sizex sizey grid
    global curcanvas zoom
    global showAnnotations showGrid

    #Call_Trace ;# debugging when things disappear

    .bottom.zoom config -text "zoom [expr {int($zoom * 100)}]%"
    set e_sizex [expr {int($sizex * $zoom)}]
    set e_sizey [expr {int($sizey * $zoom)}]
    set border 28
    .c configure -scrollregion \
	"-$border -$border [expr {$e_sizex + $border}] \
	[expr {$e_sizey + $border}]"

 
    saveRestoreWlanLinks .c save
    .c delete all
    set background [.c create rectangle 0 0 $e_sizex $e_sizey \
	-fill white -tags "background"]
    # Boeing: wallpaper
    set wallpaper [lindex [getCanvasWallpaper $curcanvas] 0]
    set wallpaperStyle [lindex [getCanvasWallpaper $curcanvas] 1]
    if { $wallpaper != "" } {
    	drawWallpaper .c $wallpaper $wallpaperStyle
    }
    # end Boeing

    if { $showAnnotations == 1 } {
       foreach obj $annotation_list {
	   # fix annotations having no canvas (from old config)
	   if { [getNodeCanvas $obj] == "" } { setNodeCanvas $obj $curcanvas}
           if { [getNodeCanvas $obj] == $curcanvas } {
               drawAnnotation $obj
           }
       } 
    }

    # Grid
    set e_grid [expr {int($grid * $zoom)}]
    set e_grid2 [expr {$e_grid * 2}]
    if { $showGrid } {
	for { set x $e_grid } { $x < $e_sizex } { incr x $e_grid } {
	    if { [expr {$x % $e_grid2}] != 0 } {
		if { $zoom > 0.5 } {
		    .c create line $x 1 $x $e_sizey \
			-fill gray -dash {1 7} -tags "grid"
		}
	    } else {
		.c create line $x 1 $x $e_sizey -fill gray -dash {1 3} \
		    -tags "grid"
	    }
	}
	for { set y $e_grid } { $y < $e_sizey } { incr y $e_grid } {
	    if { [expr {$y % $e_grid2}] != 0 } {
		if { $zoom > 0.5 } {
		    .c create line 1 $y $e_sizex $y \
			-fill gray -dash {1 7} -tags "grid"
		}
	    } else {
		.c create line 1 $y $e_sizex $y -fill gray -dash {1 3} \
		    -tags "grid"
	    }
	}
    }

    .c lower -withtags background

     foreach node $node_list {
 	if { [getNodeCanvas $node] == $curcanvas } {
 	    drawNode .c $node
 	}
      }

      redrawAllThruplots  
      foreach link $link_list {
 	set nodes [linkPeers $link]
 	if { [getNodeCanvas [lindex $nodes 0]] != $curcanvas ||
 	     [getNodeCanvas [lindex $nodes 1]] != $curcanvas } {
 	    continue
 	}
	drawLink $link
	redrawLink $link
	updateLinkLabel $link
    }
    saveRestoreWlanLinks .c restore

    .c config -cursor left_ptr

    raiseAll .c
}

#****f* editor.tcl/drawNode
# NAME
#   drawNode
# SYNOPSIS
#   drawNode node_id
# FUNCTION
#   Draws the specified node. Draws node's image (router pc
#   host lanswitch rj45 hub pseudo) and label.
#   The visibility of the label depends on the showNodeLabels
#   variable for all types of nodes and on invisible variable 
#   for pseudo nodes.
# INPUTS
#   * node_id -- node id
#****

proc drawNode { c node } {
    global showNodeLabels
    global router pc host lanswitch rj45 hub pseudo
    global curcanvas zoom
    global wlan
    if { $c == "" } { set c .c } ;# default canvas
  
    set type [nodeType $node]
    set coords [getNodeCoords $node]
    set x [expr {[lindex $coords 0] * $zoom}]
    set y [expr {[lindex $coords 1] * $zoom}]
    # special handling for custom images, dummy nodes
    # could move this to separate getImage function
    set model ""
    set cimg ""
    set imgzoom $zoom
    if { $zoom == 0.75 || $zoom == 1.5 } { set imgzoom 1.0 }
    if { $type == "router" } {
	set model [getNodeModel $node]
	set cimg [getNodeTypeImage $model normal]
    }
    set tmp [absPathname [getCustomImage $node]]
    if { $tmp != "" } { set cimg $tmp }
    if { $cimg != "" } {
	# name of global variable storing the image is the filename without path
	set img [file tail $cimg] 
	# create the variable if the image hasn't been loaded before
	global [set img]
	if { ![info exists $img] } {
	    if { [catch {
		set [set img] [image create photo -file $cimg]
		createScaledImages $img
	    } e ] } { ;# problem loading image file
		puts "icon error: $e"
		set cimg "" ;# fall back to default model icon
		setCustomImage $node "" ;# prevent errors elsewhere
	    }
	}
	if { $cimg != "" } { ;# only if image file loaded
	    global $img$imgzoom
	    $c create image $x $y -image [set $img$imgzoom] -tags "node $node"
	}
    }
    if { $cimg == "" } {
    if { $type == "pseudo" } {
        $c create image $x $y -image [set $type] -tags "node $node"
    } else {
        # create scaled images based on zoom level
	global $type$imgzoom
        $c create image $x $y -image [set $type$imgzoom] \
		-tags "node $node"
    }
    }
    set coords [getNodeLabelCoords $node]
    set x [expr {[lindex $coords 0] * $zoom}]
    set y [expr {[lindex $coords 1] * $zoom}]
    if { [nodeType $node] != "pseudo" } { ;# Boeing: show remote server
	set loc [getNodeLocation $node]
	set labelstr0 ""
	if { $loc != "" } { set labelstr0 "([getNodeLocation $node]):" }
	set labelstr1 [getNodeName $node];
	set labelstr2 ""
	if [info exists getNodePartition] { [getNodePartition $node]; }
	set l [format "%s%s\n%s" $labelstr0 $labelstr1 $labelstr2];
	set label [$c create text $x $y -fill blue \
	   -text "$l" \
	   -tags "nodelabel $node"]
    } else {
	set pnode [getNodeName $node]
	set pcanvas [getNodeCanvas $pnode]
	set ifc [ifcByPeer $pnode [getNodeMirror $node]]
	if { $pcanvas != $curcanvas } {
	    set label [$c create text $x $y -fill blue \
		-text "[getNodeName $pnode]:$ifc@[getCanvasName $pcanvas]" \
		-tags "nodelabel $node" -justify center]
	} else {
	    set label [$c create text $x $y -fill blue \
		-text "[getNodeName $pnode]:$ifc" \
		-tags "nodelabel $node" -justify center]
	}
    }
    if { $showNodeLabels == 0} {
	$c itemconfigure $label -state hidden
    }
    global invisible
    if { $invisible == 1 && [nodeType $node] == "pseudo" } {
	$c itemconfigure $label -state hidden
    }
}

#****f* editor.tcl/drawLink
# NAME
#   drawLink
# SYNOPSIS
#   drawLink link_id
# FUNCTION
#   Draws the specified link. An arrow is displayed for links 
#   connected to pseudo nodes. If the variable invisible
#   is specified link connecting a pseudo node stays hidden. 
# INPUTS
#   * link_id -- link id
#****

proc drawLink { link } {
    set nodes [linkPeers $link]
    set lnode1 [lindex $nodes 0]
    set lnode2 [lindex $nodes 1]
    set lwidth [getLinkWidth $link]
    if { [getLinkMirror $link] != "" } {
	set newlink [.c create line 0 0 0 0 \
	    -fill [getLinkColor $link] -width $lwidth \
	    -tags "link $link $lnode1 $lnode2" -arrow both]
    } else {
	set newlink [.c create line 0 0 0 0 \
	    -fill [getLinkColor $link] -width $lwidth \
	    -tags "link $link $lnode1 $lnode2"]
    }
    # Boeing: links between two nodes on different servers
    if { [getNodeLocation $lnode1] != [getNodeLocation $lnode2]} {
    	.c itemconfigure $newlink -dash ",";
    }
    # end Boeing
    # XXX Invisible pseudo-liks
    global invisible
    if { $invisible == 1 && [getLinkMirror $link] != "" } {
	.c itemconfigure $link -state hidden
    }
    # Boeing: wlan links are hidden
    if { [nodeType $lnode1] == "wlan" || [nodeType $lnode2] == "wlan" } {
	global zoom
	set imgzoom $zoom
	if { $zoom == 0.75 || $zoom == 1.5 } { set imgzoom 1.0 }
	global antenna$imgzoom
	.c itemconfigure $link -state hidden
	.c create image 0 0 -image [set antenna$imgzoom] \
			   -tags "antenna $lnode2 $link"
	.c create text 0 0 -tags "interface $lnode1 $link" -justify center
	.c create text 0 0 -tags "interface $lnode2 $link" -justify center
	.c raise interface "link || linklabel || background"
    } else {
    .c raise $newlink background
    .c create text 0 0 -tags "linklabel $link" -justify center
    .c create text 0 0 -tags "interface $lnode1 $link" -justify center
    .c create text 0 0 -tags "interface $lnode2 $link" -justify center
    .c raise linklabel "link || background"
    .c raise interface "link || linklabel || background"
    }
    foreach n [list $lnode1 $lnode2] {
	if { [getNodeHidden $n] } {
	    hideNode $n 
	    statline "Hidden node(s) exist."
	}
    }
}


# draw a green link between wireless nodes (or other color if multiple WLANs)
# WLAN links appear on the canvas but not in the global link_list
proc drawWlanLink { node1 node2 wlan } {
    global zoom defLinkWidth curcanvas
    set c .c

    set wlanlink [$c find withtag "wlanlink && $node1 && $node2 && $wlan"]
    if { $wlanlink != "" } {
	return $wlanlink ;# already exists
    }

    set color [getWlanColor $wlan]

    set xy [getNodeCoords $node1]
    set x [lindex $xy 0]; set y [lindex $xy 1]
    set pxy [getNodeCoords $node2]
    set px [lindex $pxy 0]; set py [lindex $pxy 1]

    set wlanlink [$c create line [expr {$x*$zoom}] [expr {$y*$zoom}] \
				 [expr {$px*$zoom}] [expr {$py*$zoom}] \
				 -fill $color -width $defLinkWidth \
				 -tags "wlanlink $node1 $node2 $wlan"]

    if { [getNodeCanvas $node1] == $curcanvas &&
    	 [getNodeCanvas $node2] == $curcanvas} {
	$c itemconfigure $wlanlink -state normal
	$c raise $wlanlink "background || grid || oval || rectangle"
    } else {
	$c itemconfigure $wlanlink -state hidden
    }

    return $wlanlink
}


#****f* editor.tcl/chooseIfName
# NAME
#   chooseIfName -- choose interface name
# SYNOPSIS
#   set ifcName [chooseIfName $lnode1 $lnode2]
# FUNCTION
#   Choose intreface name. The name can be:
#   * eth -- for interface connecting pc, host and router  
#   * e -- for interface connecting hub and lanswitch
# INPUTS
#   * link_id -- link id
# RESULT
#   * ifcName -- the name of the interface
#****

proc chooseIfName { lnode1 lnode2 } {
    global $lnode1 $lnode2

    # TODO: just check if layer == NETWORK and return eth, LINK return e
    switch -exact -- [nodeType $lnode1] {
	pc {
	    return eth
	}
	host {
	    return eth
	}
	hub {
	    return e
	}
	lanswitch {
	    return e
	}
	router {
	    return eth
	}
	rj45 {
	    return 
	}
	tunnel {
	    return e
	}
	ktunnel {
	    return
	}
	wlan {
	    return e
	}
	default {
	    return eth
# end Boeing: below
	}
    }
}


#****f* editor.tcl/listLANNodes
# NAME
#   listLANNodes -- list LAN nodes
# SYNOPSIS
#   set l2peers [listLANNodes $l2node $l2peers]
# FUNCTION
#   Recursive function for finding all link layer nodes that are 
#   connected to node l2node. Returns the list of all link layer 
#   nodes that are on the same LAN as l2node.
# INPUTS
#   * l2node -- node id of a link layer node
#   * l2peers -- old link layer nodes on the same LAN
# RESULT
#   * l2peers -- new link layer nodes on the same LAN
#****

proc listLANnodes { l2node l2peers } {
    lappend l2peers $l2node
    foreach ifc [ifcList $l2node] {
	set peer [logicalPeerByIfc $l2node $ifc]
	set type [nodeType $peer]
	# Boeing
	if { [ lsearch {lanswitch hub wlan} $type] != -1 } {
	    if { [lsearch $l2peers $peer] == -1 } {
		set l2peers [listLANnodes $peer $l2peers]
	    }
	}
    }
    return $l2peers
}

#****f* editor.tcl/calcDxDy
# NAME
#   calcDxDy lnode -- list LAN nodes
# SYNOPSIS
#   calcDxDy $lnode
# FUNCTION
#   Calculates dx and dy variables of the calling function.
# INPUTS
#   * lnode -- node id of a node whose dx and dy coordinates are 
#   calculated
#****

proc calcDxDy { lnode } {
    global showIfIPaddrs showIfIPv6addrs zoom
    upvar dx x
    upvar dy y

    if { $zoom > 1.0 } {
	set x 1
	set y 1
	return
    }
    switch -exact -- [nodeType $lnode] {
	hub {
	    set x [expr {1.5 / $zoom}]
	    set y [expr {2.6 / $zoom}]
	}
	lanswitch {
	    set x [expr {1.5 / $zoom}]
	    set y [expr {2.6 / $zoom}]
	}
	router {
	    set x [expr {1 / $zoom}]
	    set y [expr {2 / $zoom}]
	}
	rj45 {
	    set x [expr {1 / $zoom}]
	    set y [expr {1 / $zoom}]
	}
	tunnel {
	    set x [expr {1 / $zoom}]
	    set y [expr {1 / $zoom}]
	}
	wlan {
            set x [expr {1.5 / $zoom}]
            set y [expr {2.6 / $zoom}]
	}
	default {
	    set x [expr {1 / $zoom}]
            set y [expr {2 / $zoom}]
	}
    }
    return
}

#****f* editor.tcl/updateIfcLabel
# NAME
#   updateIfcLabel -- update interface label
# SYNOPSIS
#   updateIfcLabel $lnode1 $lnode2
# FUNCTION
#   Updates the interface label, including interface name,
#   interface state (* for interfaces that are down), IPv4
#   address and IPv6 address.
# INPUTS
#   * lnode1 -- node id of a node where the interface resides
#   * lnode2 -- node id of the node that is connected by this 
#   interface. 
#****
proc updateIfcLabel { lnode1 lnode2 } {
    global showIfNames showIfIPaddrs showIfIPv6addrs

    set link [lindex [.c gettags "link && $lnode1 && $lnode2"] 1]
    set ifc [ifcByPeer $lnode1 $lnode2]
    set ifipv4addr [getIfcIPv4addr $lnode1 $ifc]
    set ifipv6addr [getIfcIPv6addr $lnode1 $ifc]
    if { $ifc == 0 } {
	set ifc ""
    }
    if { [getIfcOperState $lnode1 $ifc] == "down" } {
	set labelstr "*"
    } else {
	set labelstr ""
    }
    if { $showIfNames } {
	set labelstr "$labelstr$ifc"
    }
    if { $showIfIPaddrs && $ifipv4addr != "" } {
	set labelstr "$labelstr$ifipv4addr"
    }
    if { $showIfIPv6addrs && $ifipv6addr != "" } {
	set labelstr "$labelstr$ifipv6addr"
    }
    set labelstr \
	[string range $labelstr 0 [expr {[string length $labelstr] - 2}]]
    .c itemconfigure "interface && $lnode1 && $link" \
	-text "$labelstr"
    # Boeing: hide ifc label on wlans
    if { [nodeType $lnode1] == "wlan" } { 
    	.c itemconfigure "interface && $lnode1 && $link" -state hidden
    }
}


#****f* editor.tcl/updateLinkLabel
# NAME
#   updateLinkLabel -- update link label
# SYNOPSIS
#   updateLinkLabel $link
# FUNCTION
#   Updates the link label, including link bandwidth, link delay,
#   BER and duplicate values.
# INPUTS
#   * link -- link id of the link whose labels are updated.
#****
proc updateLinkLabel { link } {
    global showLinkLabels

    set bwstr  [getLinkBandwidthString $link]
    set delstr [getLinkDelayString $link]
    set berstr [getLinkBERString $link]
    set dupstr [getLinkDupString $link]
    set labelstr ""
    if { "$bwstr" != "" } {
	set labelstr "$labelstr$bwstr"
    }
    if { "$delstr" != "" } {
	set labelstr "$labelstr$delstr"
    }
    if { "$berstr" != "" } {
	set labelstr "$labelstr$berstr"
    }
    if { "$dupstr" != "" } {
	set labelstr "$labelstr$dupstr"
    }
    set labelstr \
	[string range $labelstr 0 [expr {[string length $labelstr] - 2}]]
    .c itemconfigure "linklabel && $link" -text "$labelstr"
    if { $showLinkLabels == 0} {
	.c itemconfigure "linklabel && $link" -state hidden
    }
}


#****f* editor.tcl/redrawAllLinks
# NAME
#   redrawAllLinks -- redraw all links
# SYNOPSIS
#   redrawAllLinks
# FUNCTION
#   Redraws all links on the current canvas.
#****
proc redrawAllLinks {} {
    global link_list curcanvas

    foreach link $link_list {
	set nodes [linkPeers $link]
	if { [getNodeCanvas [lindex $nodes 0]] != $curcanvas ||
	    [getNodeCanvas [lindex $nodes 1]] != $curcanvas } {
	    continue
	}
	redrawLink $link
    }
}


#****f* editor.tcl/redrawLink
# NAME
#   redrawLink -- redraw a links
# SYNOPSIS
#   redrawLink $link
# FUNCTION
#   Redraws the specified link.
# INPUTS
#   * link -- link id
#****
proc redrawLink { link } {
    global $link

    set limages [.c find withtag "link && $link"]
    set limage1 [lindex $limages 0]
    set limage2 [lindex $limages 1]
    set tags [.c gettags $limage1]
    set link [lindex $tags 1]
    set lnode1 [lindex $tags 2]
    set lnode2 [lindex $tags 3]

    set coords1 [.c coords "node && $lnode1"]
    set coords2 [.c coords "node && $lnode2"]
    set x1 [lindex $coords1 0]
    set y1 [lindex $coords1 1]
    set x2 [lindex $coords2 0]
    set y2 [lindex $coords2 1]

    .c coords $limage1 $x1 $y1 $x2 $y2
    .c coords $limage2 $x1 $y1 $x2 $y2

    set lx [expr {0.5 * ($x1 + $x2)}]
    set ly [expr {0.5 * ($y1 + $y2)}]
    .c coords "linklabel && $link" $lx $ly

    set n [expr {sqrt (($x1 - $x2) * ($x1 - $x2) + \
	($y1 - $y2) * ($y1 - $y2)) * 0.015}]
    if { $n < 1 } {
	set n 1
    }

    calcDxDy $lnode1
    set lx [expr {($x1 * ($n * $dx - 1) + $x2) / $n / $dx}]
    set ly [expr {($y1 * ($n * $dy - 1) + $y2) / $n / $dy}]
    .c coords "interface && $lnode1 && $link" $lx $ly
    updateIfcLabel $lnode1 $lnode2

    calcDxDy $lnode2
    set lx [expr {($x1 + $x2 * ($n * $dx - 1)) / $n / $dx}]
    set ly [expr {($y1 + $y2 * ($n * $dy - 1)) / $n / $dy}]
    .c coords "interface && $lnode2 && $link" $lx $ly
    updateIfcLabel $lnode2 $lnode1
    # Boeing - wlan antennas
    if { [nodeType $lnode1] == "wlan" } {
	global zoom
	set an [lsearch -exact [findWlanNodes $lnode2] $lnode1]
	if { $an < 0 || $an >= 5 } { set an 0 }
	set dx [expr {20 - (10*$an)}]
	.c coords "antenna && $lnode2 && $link" [expr {$x2-($dx*$zoom)}] \
						[expr {$y2-(20*$zoom)}]
    }
}

# Boeing
proc redrawWlanLink { link } {
    global $link

    set tags [.c gettags $link]
    set lnode1 [lindex $tags 1]
    set lnode2 [lindex $tags 2]
    set coords1 [.c coords "node && $lnode1"]
    set coords2 [.c coords "node && $lnode2"]
    set x1 [lindex $coords1 0]
    set y1 [lindex $coords1 1]
    set x2 [lindex $coords2 0]
    set y2 [lindex $coords2 1]
    set lx [expr {0.5 * ($x1 + $x2)}]
    set ly [expr {0.5 * ($y1 + $y2)}]

    .c coords $link $x1 $y1 $x2 $y2
    .c coords "linklabel && $lnode2 && $lnode1" $lx $ly

    return
}
# end Boeing

#****f* editor.tcl/splitGUILink
# NAME
#   splitGUILink -- splits a links 
# SYNOPSIS
#   splitGUILink $link
# FUNCTION
#   Splits the link and draws new links and new pseudo nodes 
#   on the canvas.
# INPUTS
#   * link -- link id
#****
proc splitGUILink { link } {
    global changed zoom

    set peer_nodes [linkPeers $link]
    set new_nodes [splitLink $link pseudo]
    set orig_node1 [lindex $peer_nodes 0]
    set orig_node2 [lindex $peer_nodes 1]
    set new_node1 [lindex $new_nodes 0]
    set new_node2 [lindex $new_nodes 1]
    set new_link1 [linkByPeers $orig_node1 $new_node1]
    set new_link2 [linkByPeers $orig_node2 $new_node2]
    setLinkMirror $new_link1 $new_link2
    setLinkMirror $new_link2 $new_link1
    setNodeMirror $new_node1 $new_node2
    setNodeMirror $new_node2 $new_node1
    setNodeName $new_node1 $orig_node2
    setNodeName $new_node2 $orig_node1

    set x1 [lindex [getNodeCoords $orig_node1] 0]
    set y1 [lindex [getNodeCoords $orig_node1] 1]
    set x2 [lindex [getNodeCoords $orig_node2] 0]
    set y2 [lindex [getNodeCoords $orig_node2] 1]

    setNodeCoords $new_node1 \
	"[expr {($x1 + 0.4 * ($x2 - $x1)) / $zoom}] \
	[expr {($y1 + 0.4 * ($y2 - $y1)) / $zoom}]"
    setNodeCoords $new_node2 \
	"[expr {($x1 + 0.6 * ($x2 - $x1)) / $zoom}] \
	[expr {($y1 + 0.6 * ($y2 - $y1)) / $zoom}]"
    setNodeLabelCoords $new_node1 [getNodeCoords $new_node1]
    setNodeLabelCoords $new_node2 [getNodeCoords $new_node2]

    set changed 1
    updateUndoLog
    redrawAll
}


#****f* editor.tcl/selectNode
# NAME
#   selectNode -- select node 
# SYNOPSIS
#   selectNode $c $obj
# FUNCTION
#   Crates the selecting box around the specified canvas
#   object.
# INPUTS
#   * c -- tk canvas
#   * obj -- tk canvas object tag id
#****
proc selectNode { c obj } {
    set node [lindex [$c gettags $obj] 1]
    if { $node == "" } { return } ;# Boeing: fix occassional error
    $c addtag selected withtag "node && $node"
    if { [nodeType $node] == "pseudo" } {
	set bbox [$c bbox "nodelabel && $node"]
    } elseif { [nodeType $node] == "rectangle" } {
	$c addtag selected withtag "rectangle && $node"
	set bbox [$c bbox "rectangle && $node"]
    } elseif { [nodeType $node] == "text" } {
	$c addtag selected withtag "text && $node"
	set bbox [$c bbox "text && $node"]
    } elseif { [nodeType $node] == "oval" } {
	$c addtag selected withtag "oval && $node"
	set bbox [$c bbox "oval && $node"]
    } else {
	set bbox [$c bbox "node && $node"]
    }
    set bx1 [expr {[lindex $bbox 0] - 2}]
    set by1 [expr {[lindex $bbox 1] - 2}]
    set bx2 [expr {[lindex $bbox 2] + 1}]
    set by2 [expr {[lindex $bbox 3] + 1}]
    $c delete -withtags "selectmark && $node"
    $c create line $bx1 $by1 $bx2 $by1 $bx2 $by2 $bx1 $by2 $bx1 $by1 \
	-dash {6 4} -fill black -width 1 -tags "selectmark $node"
}

proc selectNodes { nodelist } {
    foreach node $nodelist {
	selectNode .c [.c find withtag "node && $node"]
    }
}

proc selectedNodes {} {
    set selected {}
    foreach obj [.c find withtag "node && selected"] {
	lappend selected [lindex [.c gettags $obj] 1]
    }
    foreach obj [.c find withtag "oval && selected"] {
	lappend selected [lindex [.c gettags $obj] 1]
    }
    foreach obj [.c find withtag "rectangle && selected"] {
	lappend selected [lindex [.c gettags $obj] 1]
    }
    foreach obj [.c find withtag "text && selected"] {
	lappend selected [lindex [.c gettags $obj] 1]
    }
    return $selected
}

proc selectedRealNodes {} {
    set selected {}
    foreach obj [.c find withtag "node && selected"] {
	set node [lindex [.c gettags $obj] 1]
	if { [getNodeMirror $node] != "" ||
	    [nodeType $node] == "rj45" } {
	    continue
	}
	lappend selected $node
    }
    return $selected
}

proc selectAdjacent {} {
    global curcanvas

    set selected [selectedNodes]
    set adjacent {}
    foreach node $selected {
	foreach ifc [ifcList $node] {
	    set peer [peerByIfc $node $ifc]
	    if { [getNodeMirror $peer] != "" } {
		return
	    }
	    if { [lsearch $adjacent $peer] < 0 } {
		lappend adjacent $peer
	    }
	}
    }
    selectNodes $adjacent
}

#****f* editor.tcl/button3link
# NAME
#   button3link 
# SYNOPSIS
#   button3link $c $x $y
# FUNCTION
#   This procedure is called when a right mouse button is 
#   clicked on the canvas. If there is a link on the place of
#   mouse click this procedure creates and configures a popup
#   menu. The options in the menu are:
#   * Configure -- configure the link
#   * Delete -- delete the link
#   * Split -- split the link
#   * Merge -- this option is active only if the link is previously
#   been split, by this action the link is merged.
# INPUTS
#   * c -- tk canvas
#   * x -- x coordinate for popup menu
#   * y -- y coordinate for popup menu
#****
proc button3link { c x y } {
    global oper_mode env eid canvas_list node_list
    global curcanvas

    set link [lindex [$c gettags {link && current}] 1]
    if { $link == "" } {
	set link [lindex [$c gettags {linklabel && current}] 1]
	if { $link == "" } {
	    return
	}
    }

    .button3menu delete 0 end

    #
    # Configure link
    #
    .button3menu add command -label "Configure" \
	-command "popupConfigDialog $c"

    #
    # Delete link
    #
    if { $oper_mode != "exec" } {
	.button3menu add command -label "Delete" \
	    -command "removeGUILink $link atomic"
    } else {
	.button3menu add command -label "Delete" \
	    -state disabled
    }

    #
    # Split link
    #
    if { $oper_mode != "exec" && [getLinkMirror $link] == "" } {
	.button3menu add command -label "Split" \
	    -command "splitGUILink $link"
    } else {
	.button3menu add command -label "Split" \
	    -state disabled
    }

    #
    # Merge two pseudo nodes / links
    #
    if { $oper_mode != "exec" && [getLinkMirror $link] != "" &&
	[getNodeCanvas [getNodeMirror [lindex [linkPeers $link] 1]]] ==
	$curcanvas } {
	.button3menu add command -label "Merge" \
	    -command "mergeGUINode [lindex [linkPeers $link] 1]"
    } else {
	.button3menu add command -label "Merge" -state disabled
    }

    set x [winfo pointerx .]
    set y [winfo pointery .]
    tk_popup .button3menu $x $y
}


#****f* editor.tcl/movetoCanvas
# NAME
#   movetoCanvas -- move to canvas 
# SYNOPSIS
#   movetoCanvas $canvas
# FUNCTION
#   This procedure moves all the nodes selected in the GUI to
#   the specified canvas.
# INPUTS
#   * canvas -- canvas id.
#****
proc movetoCanvas { canvas } {
    global changed

    set selected_nodes [selectedNodes]
    foreach node $selected_nodes {
	setNodeCanvas $node $canvas
	set changed 1
    }
    foreach obj [.c find withtag "linklabel"] {
	set link [lindex [.c gettags $obj] 1]
	set link_peers [linkPeers $link]
	set peer1 [lindex $link_peers 0]
	set peer2 [lindex $link_peers 1]
	set peer1_in_selected [lsearch $selected_nodes $peer1]
	set peer2_in_selected [lsearch $selected_nodes $peer2]
	if { ($peer1_in_selected == -1 && $peer2_in_selected != -1) ||
	    ($peer1_in_selected != -1 && $peer2_in_selected == -1) } {
	    if { [nodeType $peer2] == "pseudo" } {
		setNodeCanvas $peer2 $canvas
		if { [getNodeCanvas [getNodeMirror $peer2]] == $canvas } {
		    mergeLink $link
		}
		continue
	    }
	    set new_nodes [splitLink $link pseudo]
	    set new_node1 [lindex $new_nodes 0]
	    set new_node2 [lindex $new_nodes 1]
	    setNodeMirror $new_node1 $new_node2
	    setNodeMirror $new_node2 $new_node1
	    setNodeName $new_node1 $peer2
	    setNodeName $new_node2 $peer1
	    set link1 [linkByPeers $peer1 $new_node1]
	    set link2 [linkByPeers $peer2 $new_node2]
	    setLinkMirror $link1 $link2
	    setLinkMirror $link2 $link1
	}
    }
    updateUndoLog
    redrawAll
}


#****f* editor.tcl/mergeGUINode
# NAME
#   mergeGUINode -- merge GUI node
# SYNOPSIS
#   mergeGUINode $node
# FUNCTION
#   This procedure removes the specified pseudo node as well
#   as it's mirror copy. Also this procedure removes the
#   pseudo links and reestablish the original link between
#   the non-pseudo nodes.
# INPUTS
#   * node -- node id of a pseudo node.
#****
proc mergeGUINode { node } {
    set link [lindex [linkByIfc $node [ifcList $node]] 0]
    mergeLink $link
    redrawAll
}


#****f* editor.tcl/button3node
# NAME
#   button3node
# SYNOPSIS
#   button3node $c $x $y
# FUNCTION
#   This procedure is called when a right mouse button is 
#   clicked on the canvas. Also called when double-clicking
#   on a node during runtime.
#   If there is a node on the place of
#   mouse click this procedure creates and configures a popup
#   menu. The options in the menu are:
#   * Configure -- configure the node
#   * Create link to -- create a link to any available node,
#   it can be on the same canvas or on a different canvas.
#   * Move to -- move to some other canvas
#   * Merge -- this option is available only for pseudo nodes
#   that have mirror nodes on the same canvas (Pseudo nodes
#   created by splitting a link).
#   * Delete -- delete the node
#   * Shell window -- specifies the shell window to open in 
#   exec mode. This option is available only to nodes on a 
#   network layer
#   * Ethereal -- opens a Ethereal program for the specified 
#   node and the specified interface. This option is available 
#   only for network layer nodes in exec mode.
# INPUTS
#   * c -- tk canvas
#   * x -- x coordinate for popup menu
#   * y -- y coordinate for popup menu
#****
#old proc button3node { c x y } 
#Boeing
proc button3node { c x y button } {
    global oper_mode env eid canvas_list node_list curcanvas systype g_prefs

    set node [lindex [$c gettags {node && current}] 1]
    if { $node == "" } {
	set node [lindex [$c gettags {nodelabel && current}] 1]
	if { $node == "" } {
	    return
	}
    }
    set mirror_node [getNodeMirror $node]

    if { [$c gettags "node && $node && selected"] == "" } {
	$c dtag node selected
	$c delete -withtags selectmark
	selectNode $c [$c find withtag "current"]
    }

    # open up shells upon double-click or shift/ctrl-click
    set shell $g_prefs(shell)
    if { $button == "shift" || $button == "ctrl" } {
	if { [nodeType $node] == "pseudo" } {
	    #
	    # Hyperlink to another canvas
	    #
	    set curcanvas [getNodeCanvas [getNodeMirror $node]]
	    switchCanvas none
	    return
	}
	# only open bash shells for NETWORK nodes and remote routers
	if { [[typemodel $node].layer] != "NETWORK" } {
	    if { [typemodel $node] == "wlan" } {
		wlanDoubleClick $node $button
	    }
	    return
	}
	if { $button == "shift" } {	;# normal bash shell
	    spawnShell $node $shell
	} else { 			;# right-click vtysh shell
	    set cmd [[typemodel $node].shellcmd $node] 
	    if { $cmd != "/bin/sh" && $cmd != "" } { spawnShell $node $cmd }
	}
	return ;# open shell, don't post a menu
    }

    #
    # below here we build and post a menu
    #
    .button3menu delete 0 end

    #
    # Configure node
    #
    if { [nodeType $node] != "pseudo" } {
	.button3menu add command -label "Configure" \
	    -command "popupConfigDialog $c"
    } else {
	.button3menu add command -label "Configure" \
	    -command "popupConfigDialog $c" -state disabled
    }

    #
    # Select adjacent
    #
    if { [nodeType $node] != "pseudo" } {
	.button3menu add command -label "Select adjacent" \
	    -command "selectAdjacent"
    } else {
	.button3menu add command -label "Select adjacent" \
	    -command "selectAdjacent" -state disabled
    }

    #
    # Create a new link - can be between different canvases
    #
    .button3menu.connect delete 0 end
    if { $oper_mode == "exec" || [nodeType $node] == "pseudo" } {
	#.button3menu add cascade -label "Create link to" \
	    -menu .button3menu.connect -state disabled
    } else {
	.button3menu add cascade -label "Create link to" \
	    -menu .button3menu.connect
    }
    destroy .button3menu.connect.selected
    menu .button3menu.connect.selected -tearoff 0
    .button3menu.connect add cascade -label "Selected" \
	-menu .button3menu.connect.selected
    .button3menu.connect.selected add command \
	-label "Chain" -command "P \[selectedRealNodes\]"
    .button3menu.connect.selected add command \
	-label "Star" \
	-command "Kb \[lindex \[selectedRealNodes\] 0\] \
	\[lrange \[selectedNodes\] 1 end\]"
    .button3menu.connect.selected add command \
	-label "Cycle" -command "C \[selectedRealNodes\]"
    .button3menu.connect.selected add command \
	-label "Clique" -command "K \[selectedRealNodes\]"
    .button3menu.connect add separator
    foreach canvas $canvas_list {
	destroy .button3menu.connect.$canvas
	menu .button3menu.connect.$canvas -tearoff 0
	.button3menu.connect add cascade -label [getCanvasName $canvas] \
	    -menu .button3menu.connect.$canvas
    }
    foreach peer_node $node_list {
	set canvas [getNodeCanvas $peer_node]
	if { $node != $peer_node && [nodeType $node] != "rj45" &&
	    [lsearch {pseudo rj45} [nodeType $peer_node]] < 0 &&
	    [ifcByLogicalPeer $node $peer_node] == "" } {
	    .button3menu.connect.$canvas add command \
		-label [getNodeName $peer_node] \
		-command "newGUILink $node $peer_node"
	} elseif { [nodeType $peer_node] != "pseudo" } {
	    .button3menu.connect.$canvas add command \
		-label [getNodeName $peer_node] \
		-state disabled
	}
    }
    #
    # assign to emulation server
    #
    if { $oper_mode != "exec" } {
	global exec_servers node_location
	.button3menu.assign delete 0 end
	.button3menu add cascade -label "Assign to" -menu .button3menu.assign
	.button3menu.assign add command -label "(none)" \
		-command "assignSelection \"\""
	foreach server [lsort -dictionary [array names exec_servers]] {
	    .button3menu.assign add command -label "$server" \
		-command "assignSelection $server"
	}
    }

    #
    # wlan link to all nodes
    #
    if { [nodeType $node] == "wlan" } {
	.button3menu add command -label "Link to all routers" \
		-command "linkAllNodes $node"
	set msg "Select new WLAN $node members:"
	set cmd "linkSelectedNodes $node"
	.button3menu add command -label "Select WLAN members..." \
		-command "popupSelectNodes \"$msg\" \"\" {$cmd}"
	set state normal
	if { $oper_mode != "exec" } { set state disabled }
	.button3menu add command -label "Mobility script..." \
		-command "showMobilityScriptPopup $node" -state $state
    }

    #
    # Move to another canvas
    #
    .button3menu.moveto delete 0 end
    if { $oper_mode != "exec" && [nodeType $node] != "pseudo" } {
	.button3menu add cascade -label "Move to" \
	    -menu .button3menu.moveto
	.button3menu.moveto add command -label "Canvas:" -state disabled
	foreach canvas $canvas_list {
	    if { $canvas != $curcanvas } {
	    .button3menu.moveto add command \
		-label [getCanvasName $canvas] \
		-command "movetoCanvas $canvas"
	    } else {
	    .button3menu.moveto add command \
		-label [getCanvasName $canvas] -state disabled
	    }
	}
    }

    #
    # Merge two pseudo nodes / links
    #
    if { $oper_mode != "exec" && [nodeType $node] == "pseudo" && \
	[getNodeCanvas $mirror_node] == $curcanvas } {
	.button3menu add command -label "Merge" \
	    -command "mergeGUINode $node"
    }

    #
    # Delete selection
    #
    if { $oper_mode != "exec" } {
	.button3menu add command -label "Cut" -command cutSelection
	.button3menu add command -label "Copy" -command copySelection
	.button3menu add command -label "Paste" -command pasteSelection
	.button3menu add command -label "Delete" -command deleteSelection
    }

    .button3menu add command -label "Hide" -command "hideSelected"

    # Boeing: flag used below
    set execstate disabled
    if { $oper_mode == "exec" } { set execstate normal }

    #
    # Shell selection
    #
    .button3menu.shell delete 0 end
    if { $oper_mode == "exec" && [[typemodel $node].layer] == "NETWORK" } {
	.button3menu add cascade -label "Shell window" \
	    -menu .button3menu.shell
	set cmd [[typemodel $node].shellcmd $node]
	if { $cmd != "/bin/sh" && $cmd != "" } { ;# typically adds vtysh
	    .button3menu.shell add command -label "$cmd" \
		-command "spawnShell $node $cmd"
	}
	.button3menu.shell add command -label "/bin/sh" \
	    -command "spawnShell $node sh"
	.button3menu.shell add command -label "$shell" \
	-command "spawnShell $node $shell"
    }

    #
    # services
    #
    .button3menu.services delete 0 end
    if { $oper_mode == "exec" && [[typemodel $node].layer] == "NETWORK" } {
	addServicesRightClickMenu .button3menu $node
    } else {
	.button3menu add command -label "Services..." -command \
		"sendConfRequestMessage -1 $node services 0x1 -1 \"\""
    }

    #
    # Tcpdump, gpsd
    #
    if { $oper_mode == "exec" && [[typemodel $node].layer] == "NETWORK" } {
	addInterfaceCommand $node .button3menu "Tcpdump" "tcpdump -n -l -i" \
		$execstate 1
	addInterfaceCommand $node .button3menu "TShark" "tshark -n -l -i" \
		$execstate 1
	addInterfaceCommand $node .button3menu "Wireshark" "wireshark -k -i" \
		$execstate 0
	# wireshark on host veth pair -- need veth pair name
	#wireshark -k -i 
	if { [lindex $systype 0] == "Linux" } {
	    set name [getNodeName $node]
	    .button3menu add command -label "View log..." -state $execstate \
		-command "spawnShell $node \"less ../$name.log\""
	}
    }

    #
    # Finally post the popup menu on current pointer position
    #
    set x [winfo pointerx .]
    set y [winfo pointery .]

    tk_popup .button3menu $x $y
}


#****f* editor.tcl/spawnShell
# NAME
#   spawnShell -- spawn shell
# SYNOPSIS
#   spawnShell $node $cmd
# FUNCTION
#   This procedure spawns a new shell for a specified node.
#   The shell is specified in cmd parameter.
# INPUTS
#   * node -- node id of the node for which the shell 
#   is spawned.
#   * cmd -- the path to the shell.
#****
proc spawnShell { node cmd } {
    # request an interactive terminal
    set sock [lindex [getEmulPlugin $node] 2]
    set flags 0x44 ;# set TTY, critical flags
    set exec_num [newExecCallbackRequest shell]
    sendExecMessage $sock $node $cmd $exec_num $flags
}

# add a sub-menu to the parentmenu with the given command for each interface
proc addInterfaceCommand { node parentmenu txt cmd state isnodecmd } {
    global g_current_session
    set childmenu "$parentmenu.[lindex $cmd 0]"
    $childmenu delete 0 end
    $parentmenu add cascade -label $txt -menu $childmenu -state $state
    if { ! $isnodecmd } {
	if { $g_current_session == 0 } { set state disabled }
	set ssid [shortSessionID $g_current_session] 
    }
    foreach ifc [ifcList $node] {
        set addr [lindex [getIfcIPv4addr $node $ifc] 0]
        if { $addr != "" } { set addr " ($addr)" }
	if { $isnodecmd } { ;# run command in a node
	    set icmd "spawnShell $node \"$cmd $ifc\""
	} else { ;# exec a command directly
	    set nodenum [string range $node 1 end]
	    set ifnum [string range $ifc 3 end]
	    set localifc veth$nodenum.$ifnum.$ssid
	    set icmd "exec $cmd $localifc &"
	}
        $childmenu add command -label "$ifc$addr" -state $state -command $icmd
    }
}

# Boeing: consolodate various raise statements here
proc raiseAll {c} {
    $c raise rectangle background
    $c raise oval "rectangle || background"
    $c raise grid "oval || rectangle || background"
    $c raise link "grid || oval || rectangle || background"
    $c raise linklabel "link || grid || oval || rectangle || background"
    $c raise newlink "linklabel || link || grid || oval || rectangle || background"
    $c raise wlanlink "newlink || linklabel || link || grid || oval || rectangle || background"
    $c raise antenna "wlanlink || newlink || linklabel || link || grid || oval || rectangle || background"
    $c raise interface "antenna || wlanlink || newlink || linklabel || link || grid || oval || rectangle || background"
    $c raise node "interface || antenna || wlanlink || newlink || linklabel || link || grid || oval || rectangle || background"
    $c raise nodelabel "node || interface || antenna || wlanlink || newlink || linklabel || link || grid || oval || rectangle || background"
    $c raise text "nodelabel || node || interface || antenna || wlanlink || newlink || linklabel || link || grid || oval || rectangle || background"
    $c raise -cursor
}
# end Boeing


#****f* editor.tcl/button1
# NAME
#   button1
# SYNOPSIS
#   button1 $c $x $y $button
# FUNCTION
#   This procedure is called when a left mouse button is 
#   clicked on the canvas. This procedure selects a new
#   node or creates a new node, depending on the selected 
#   tool.
# INPUTS
#   * c -- tk canvas
#   * x -- x coordinate
#   * y -- y coordinate
#   * button -- the keyboard button that is pressed.
#****
proc button1 { c x y button } {
    global node_list plot_list curcanvas zoom
    global activetool activetoolp newlink curobj changed def_router_model
    global router pc host lanswitch rj45 hub
    global oval rectangle text
    global lastX lastY
    global background selectbox
    global defLinkColor defLinkWidth
    global resizemode resizeobj
    global wlan g_twoNodeSelect
    global g_view_locked

    set x [$c canvasx $x]
    set y [$c canvasy $y]

    set lastX $x
    set lastY $y

    # TODO: clean this up
    #   - too many global variables
    #   - too many hardcoded cases (lanswitch, router, etc)
    #   - should be functionalized since lengthy if-else difficult to read

    set curobj [$c find withtag current]
    set curtype [lindex [$c gettags current] 0]

   
    if { $curtype == "node" || \
	 $curtype == "oval" || $curtype == "rectangle" || $curtype == "text" \
	|| ( $curtype == "nodelabel" && \
	[nodeType [lindex [$c gettags $curobj] 1]] == "pseudo") } {
	set node [lindex [$c gettags current] 1]
	set wasselected \
	    [expr {[lsearch [$c find withtag "selected"] \
	    [$c find withtag "node && $node"]] > -1}]
	if { $button == "ctrl" } {
	    if { $wasselected } {
		$c dtag $node selected
		$c delete -withtags "selectmark && $node"
	    }
	} elseif { !$wasselected } {
	    $c dtag node selected
	    $c delete -withtags selectmark
	}
	if { $activetool == "select" && !$wasselected} {
	    selectNode $c $curobj
	}
    } elseif { $curtype == "selectmark" } {
        setResizeMode $c $x $y
    } elseif { $activetool == "plot" } {
	# plot tool: create new plot windows when clicking on a link
	set link ""
	set tags [$c gettags $curobj]
	if { $curtype == "link" || $curtype == "linklabel" } {
	    set link [lindex $tags 1]
	} elseif { $curtype == "interface" } {
	    set link [lindex $tags 2]
	}
	if { $link != "" } {
            thruPlot $c $link $x $y 150 220 false
	}
	return
    } elseif { $button != "ctrl" || $activetool != "select" } {
	$c dtag node selected
	$c delete -withtags selectmark
    }
    # user has clicked on a blank area or background item
    if { [lsearch [.c gettags $curobj] background] != -1 ||
	 [lsearch [.c gettags $curobj] grid] != -1 ||
 	 [lsearch [.c gettags $curobj] annotation] != -1 } {
        # left mouse button pressed to create a new node
	if { [lsearch {select marker link mobility twonode run stop oval \
			rectangle text} $activetool] < 0 } {
	    if { $g_view_locked == 1 } { return }
	    if { $activetoolp == "routers" } {
		set node [newNode router]
		setNodeModel $node $activetool
	    } else {
		set node [newNode $activetool]
	    }
	    setNodeCanvas $node $curcanvas
	    setNodeCoords $node "[expr {$x / $zoom}] [expr {$y / $zoom}]"
	    lassign [getDefaultLabelOffsets $activetool] dx dy
	    setNodeLabelCoords $node "[expr {$x / $zoom + $dx}] \
		[expr {$y / $zoom + $dy}]"
	    drawNode $c $node
	    selectNode $c [$c find withtag "node && $node"]
	    set changed 1
	# remove any existing select box
	} elseif { $activetool == "select" \
	    && $curtype != "node" && $curtype != "nodelabel"} {
	    $c config -cursor cross
	    set lastX $x
	    set lastY $y
	    if {$selectbox != ""} {
		# We actually shouldn't get here!
		$c delete $selectbox
		set selectbox ""
	    }
	# begin drawing an annotation
	} elseif { $activetoolp == "bgobjs" } {
	    set newcursor cross
	    if { $activetool == "text" } { set newcursor xterm }
	    $c config -cursor $newcursor
	    set lastX $x
	    set lastY $y
	# draw with the marker
	} elseif { $activetool == "marker" } {
	    global markersize markercolor
	    set newline [$c create oval $lastX $lastY $x $y \
			-width $markersize -outline $markercolor -tags "marker"]
	    $c raise $newline "background || link || linklabel || interface"
	    set lastX $x
	    set lastY $y
	}
    } else {
	if {$curtype == "node" || $curtype == "nodelabel"} {
	    $c config -cursor fleur
	}
	if {$activetool == "link" && $curtype == "node"} {
	    $c config -cursor cross
	    set lastX [lindex [$c coords $curobj] 0]
	    set lastY [lindex [$c coords $curobj] 1]
	    set newlink [$c create line $lastX $lastY $x $y \
		-fill $defLinkColor -width $defLinkWidth \
		-tags "link"]
	# twonode tool support		
	} elseif {$g_twoNodeSelect != "" && $curtype == "node"} {
    	    set curnode [lindex [$c gettags $curobj] 1]
	    selectTwoNode $curnode
	} elseif { $curtype == "node" } {
	    selectNode $c $curobj
	}
	# end Boeing
    }

    raiseAll $c
}

proc setResizeMode { c x y } {
    set isThruplot false
    set type1 notset

    if {$c == ".c"} { 
        set t1 [$c gettags current]
        set o1 [lindex $t1 1]
        set type1 [nodeType $o1]
    } else {
        set o1 $c
        set c .c
        set isThruplot true    
    }
    #DYL
    #puts "RESIZE NODETYPE = $type1"
    global resizemode resizeobj
    if {$type1== "oval" || $type1== "rectangle" || $isThruplot == true} {
        set resizeobj $o1
        set bbox1 [$c bbox $o1]
        set x1 [lindex $bbox1 0]
        set y1 [lindex $bbox1 1]
        set x2 [lindex $bbox1 2]
        set y2 [lindex $bbox1 3]
        set l 0 ;# left
        set r 0 ;# right
        set u 0 ;# up
        set d 0 ;# down

        if { $x < [expr $x1+($x2-$x1)/8.0]} { set l 1 }
        if { $x > [expr $x2-($x2-$x1)/8.0]} { set r 1 }
        if { $y < [expr $y1+($y2-$y1)/8.0]} { set u 1 }
        if { $y > [expr $y2-($y2-$y1)/8.0]} { set d 1 }

        if {$l==1} {
            if {$u==1} {
                set resizemode lu
            } elseif {$d==1} {
                set resizemode ld
            } else {
                set resizemode l
            }
        } elseif {$r==1} {
            if {$u==1} {
                set resizemode ru
            } elseif {$d==1} {
                set resizemode rd
            } else {
                set resizemode r
            }
        } elseif {$u==1} {
            set resizemode u
        } elseif {$d==1} {
            set resizemode d
        } else {
            set resizemode false
        }
     }
}


#****f* editor.tcl/button1-motion
# NAME
#   button1-motion
# SYNOPSIS
#   button1-motion $c $x $y 
# FUNCTION
#   This procedure is called when a left mouse button is 
#   pressed and the mouse is moved around the canvas. 
#   This procedure creates new select box, moves the 
#   selected nodes or draws a new link.
# INPUTS
#   * c -- tk canvas
#   * x -- x coordinate
#   * y -- y coordinate
#****
proc button1-motion { c x y } {
    global activetool newlink changed
    global lastX lastY sizex sizey selectbox background
    global oper_mode newoval newrect resizemode
    global zoom
    global g_view_locked
    global thruPlotCur thruPlotDragStart

    set x [$c canvasx $x]
    set y [$c canvasy $y]

    if {$thruPlotDragStart == "dragging"} {
        #puts "active tool is $activetool"
        thruPlotDrag $c $thruPlotCur $x $y null true 
        return 
    }

    # fix occasional error
    if { $x == "" || $y == "" || $lastX == "" || $lastY == "" } { return }

    set curobj [$c find withtag current]
    set curtype [lindex [$c gettags current] 0]

    # display <x, y> coordinates in the status bar
    set zoomx [expr {$x / $zoom}]
    set zoomy [expr {$y / $zoom}]
    .bottom.textbox config -text "<$zoomx, $zoomy>"

    # prevent dragging outside of the canvas area
    if { $x < 0 } {
	set x 0
    } elseif { $x > $sizex } {
	set x $sizex
    }
    if { $y < 0 } {
	set y 0
    } elseif { $y > $sizey } {
	set y $sizey
    }

    # marker tool drawing on the canvas
    if { $activetool == "marker" } {
        global markersize markercolor
	set dx [expr {$x-$lastX} ]
	set dy [expr {$y-$lastY} ]
	# this provides smoother drawing
	if { $dx > $markersize || $dy > $markersize } { 
	    set mark [$c create line $lastX $lastY $x $y \
			-width $markersize -fill $markercolor -tags "marker"]
            $c raise $mark \
	        "marker || background || link || linklabel || interface"
	}
	set mark [$c create oval $x $y $x $y \
			-width $markersize -fill $markercolor \
			-outline $markercolor -tags "marker"]
        $c raise $mark "marker || background || link || linklabel || interface"
	set lastX $x
	set lastY $y
	return
    }
    # disable all other mouse drags in locked mode
    if { $g_view_locked == 1 } { return }

    # don't move nodelabels in exec mode, use calcx,y instead of x,y
    if {$oper_mode == "exec" && $curtype == "nodelabel" } {
	set node [lindex [$c gettags $curobj] 1]
	set curobj [$c find withtag "node && $node"]
	set curtype "node"
	set coords [$c coords $curobj]
	set calcx [expr {[lindex $coords 0] / $zoom}]
	set calcy [expr {[lindex $coords 1] / $zoom}]
	selectNode $c $curobj
    } else {
    	set calcx $x
    	set calcy $y
    }
    # drawing a new link
    if {$activetool == "link" && $newlink != ""} {
	$c coords $newlink $lastX $lastY $x $y
    # draw a selection box
    } elseif { $activetool == "select" && \
	( $curobj == $selectbox || $curtype == "background" || $curtype == "grid")} {
	if {$selectbox == ""} {
	    set selectbox [$c create line \
		$lastX $lastY $x $lastY $x $y $lastX $y $lastX $lastY \
		-dash {10 4} -fill black -width 1 -tags "selectbox"]
	    $c raise $selectbox "background || link || linklabel || interface"
	} else {
	    $c coords $selectbox \
		$lastX $lastY $x $lastY $x $y $lastX $y $lastX $lastY
	}
    # move a text annotation
    } elseif { $activetool == "select" && $curtype == "text" } {
	$c move $curobj [expr {$x - $lastX}] [expr {$y - $lastY}]
	set changed 1
	set lastX $x
	set lastY $y
	$c delete [$c find withtag "selectmark"]
    # move a nodelabel apart from a node (edit mode only)
    } elseif { $activetool == "select" && $curtype == "nodelabel" \
	&& [nodeType [lindex [$c gettags $curobj] 1]] != "pseudo" } {
	$c move $curobj [expr {$x - $lastX}] [expr {$y - $lastY}]
	set changed 1
	set lastX $x
	set lastY $y
			# actually we should check if curobj==bkgImage
    # annotations
    } elseif { $activetool == "oval" && \
      ( $curobj == $newoval || $curobj == $background || $curtype == "background" || $curtype == "grid")} {
	# Draw a new oval
	if {$newoval == ""} {
	    set newoval [$c create oval $lastX $lastY $x $y \
			-dash {10 4} -width 1 -tags "newoval"]
	    $c raise $newoval "background || link || linklabel || interface"
	} else {
	    $c coords $newoval \
		$lastX $lastY $x $y
	}
			# actually we should check if curobj==bkgImage
    } elseif { $activetool == "rectangle" && \
      ( $curobj == $newrect || $curobj == $background || $curtype == "background" || $curtype == "grid")} {
      # Draw a new rectangle
	if {$newrect == ""} {
	    set newrect [$c create rectangle $lastX $lastY $x $y \
			-outline blue \
			-dash {10 4} -width 1 -tags "newrect"]
	    $c raise $newrect "oval || background || link || linklabel || interface"
	} else {
	    $c coords $newrect $lastX $lastY $x $y
	}
    # resizing an annotation
    } elseif { $curtype == "selectmark" } {
	foreach o [$c find withtag "selected"] { 
	    set node [lindex [$c gettags $o] 1]
	    set tagovi [$c gettags $o]
	    set koord [getNodeCoords $node]

	    set oldX1 [lindex $koord 0]
	    set oldY1 [lindex $koord 1]
	    set oldX2 [lindex $koord 2]
	    set oldY2 [lindex $koord 3]
	    switch -exact -- $resizemode {
		lu {
		    set oldX1 $x
		    set oldY1 $y
		}
		ld {
		    set oldX1 $x
		    set oldY2 $y
		}
		l {
		    set oldX1 $x
		}
		ru {
		    set oldX2 $x
		    set oldY1 $y
		}
		rd {
		    set oldX2 $x
		    set oldY2 $y
		}
		r {
		    set oldX2 $x
		}
		u {
		    set oldY1 $y
		}
		d {
		    set oldY2 $y
		}
	    }
	    if {$selectbox == ""} {
		# Boeing: fix "bad screen distance" error
		if { $oldX1 == "" || $oldX2 == "" || $oldY1 == "" || \
		     $oldY2 == "" } { return }
		# end Boeing
		set selectbox [$c create line \
		    $oldX1 $oldY1 $oldX2 $oldY1 $oldX2 $oldY2 $oldX1 \
		    $oldY2 $oldX1 $oldY1 \
		    -dash {10 4} -fill black -width 1 -tags "selectbox"]
		$c raise $selectbox \
		    "background || link || linklabel || interface"
	    } else {
		$c coords $selectbox \
		    $oldX1 $oldY1 $oldX2 $oldY1 $oldX2 $oldY2 $oldX1 \
		    $oldY2 $oldX1 $oldY1
	    }
	}
    # selected node(s) are being moved
    } else {
	foreach img [$c find withtag "selected"] {
	    set node [lindex [$c gettags $img] 1]
	    set newcoords [$c coords $img] ;# different than getNodeCoords
	    set img [$c find withtag "selectmark && $node"]
	    if {$curtype == "oval" || $curtype == "rectangle"} {
		$c move $img [expr {($x - $lastX) / 2}] \
			     [expr {($y - $lastY) / 2}]
	    } else {
		$c move $img [expr {$x - $lastX}] [expr {$y - $lastY}]
		set img [$c find withtag "node && $node"]
		$c move $img [expr {$x - $lastX}] [expr {$y - $lastY}]
		set img [$c find withtag "nodelabel && $node"]
		$c move $img [expr {$x - $lastX}] [expr {$y - $lastY}]
		set img [$c find withtag "twonode && $node"]
		if {$img != "" } {; # move Two Node Tool circles around node
		    $c move $img [expr {$x - $lastX}] [expr {$y - $lastY}]
		};
		set img [$c find withtag "rangecircles && $node"]
		if {$img != "" } {; # move throughput circles around node
		    $c move $img [expr {$x - $lastX}] [expr {$y - $lastY}]
		};
		$c addtag need_redraw withtag "link && $node"
	    }
	    if { $oper_mode == "exec" } {
		set newx [expr {[lindex $newcoords 0] / $zoom}]
		set newy [expr {[lindex $newcoords 1] / $zoom}]
		sendNodePosMessage -1 $node -1 $newx $newy -1 0
	    }
	    $c addtag need_redraw withtag "wlanlink && $node"
	    widgets_move_node $c $node 0
	}
	foreach link [$c find withtag "link && need_redraw"] {
	    redrawLink [lindex [$c gettags $link] 1]
	}
	foreach wlanlink [$c find withtag "wlanlink && need_redraw"] {
	    redrawWlanLink $wlanlink
	}
	$c dtag wlanlink need_redraw
	$c dtag link need_redraw
	set changed 1
	set lastX $x
	set lastY $y
    }
}


#****f* editor.tcl/pseudo.layer
# NAME
#   pseudo.layer  
# SYNOPSIS
#   set layer [pseudo.layer]
# FUNCTION
#   Returns the layer on which the pseudo node operates
#   i.e. returns no layer. 
# RESULT
#   * layer -- returns an empty string
#****
proc pseudo.layer {} {
}


#****f* editor.tcl/newGUILink
# NAME
#   newGUILink -- new GUI link
# SYNOPSIS
#   newGUILink $lnode1 $lnode2
# FUNCTION
#   This procedure is called to create a new link between 
#   nodes lnode1 and lnode2. Nodes can be on the same canvas 
#   or on different canvases. The result of this function
#   is directly visible in GUI.
# INPUTS
#   * lnode1 -- node id of the first node
#   * lnode2 -- node id of the second node
#****
proc newGUILink { lnode1 lnode2 } {
    global changed

    set link [newLink $lnode1 $lnode2]
    if { $link == "" } {
	return
    }
    if { [getNodeCanvas $lnode1] != [getNodeCanvas $lnode2] } {
	set new_nodes [splitLink $link pseudo]
	set orig_nodes [linkPeers $link]
	set new_node1 [lindex $new_nodes 0]
	set new_node2 [lindex $new_nodes 1]
	set orig_node1 [lindex $orig_nodes 0]
	set orig_node2 [lindex $orig_nodes 1]
	set new_link1 [linkByPeers $orig_node1 $new_node1]
	set new_link2 [linkByPeers $orig_node2 $new_node2]
	setNodeMirror $new_node1 $new_node2
	setNodeMirror $new_node2 $new_node1
	setNodeName $new_node1 $orig_node2
	setNodeName $new_node2 $orig_node1
	setLinkMirror $new_link1 $new_link2
	setLinkMirror $new_link2 $new_link1
    }
    redrawAll
    set changed 1
    updateUndoLog
}


#****f* editor.tcl/button1-release
# NAME
#   button1-release
# SYNOPSIS
#   button1-release $c $x $y 
# FUNCTION
#   This procedure is called when a left mouse button is 
#   released. 
#   The result of this function depends on the actions
#   during the button1-motion procedure.
# INPUTS
#   * c -- tk canvas
#   * x -- x coordinate
#   * y -- y coordinate
#****
proc button1-release { c x y } {
    global node_list plot_list activetool newlink curobj grid
    global changed undolog undolevel redolevel selectbox
    global lastX lastY sizex sizey zoom
    global autorearrange_enabled
    global resizemode resizeobj
    set redrawNeeded 0
    global oper_mode
    global g_prefs
    global g_view_locked

    set x [$c canvasx $x]
    set y [$c canvasy $y]

    $c config -cursor left_ptr
    # place a new link between items
    if {$activetool == "link" && $newlink != ""} {
        if { $g_view_locked == 1 } { return }
	$c delete $newlink
	set newlink ""
	set destobj ""
	foreach obj [$c find overlapping $x $y $x $y] {
	    if {[lindex [$c gettags $obj] 0] == "node"} {
		set destobj $obj
		break
	    }
	}
	if {$destobj != "" && $curobj != "" && $destobj != $curobj} {
	    set lnode1 [lindex [$c gettags $curobj] 1]
	    set lnode2 [lindex [$c gettags $destobj] 1]
	    if { [ifcByLogicalPeer $lnode1 $lnode2] == "" } {
		set link [newLink $lnode1 $lnode2]
		if { $link != "" } {
		    drawLink $link
		    redrawLink $link
		    updateLinkLabel $link
		    set changed 1
		}
	    }
	}
    # annotations
    } elseif {$activetool == "rectangle" || $activetool == "oval" } {
        if { $g_view_locked == 1 } { return }
	popupAnnotationDialog $c 0 "false"
    # edit text annotation
    } elseif {$activetool == "text" } {
        if { $g_view_locked == 1 } { return }
	textEnter $c $x $y
    }

    if { $changed == 1 } {
	set regular true
	if { [lindex [$c gettags $curobj] 0] == "nodelabel" } {
	    set node [lindex [$c gettags $curobj] 1]
	    selectNode $c [$c find withtag "node && $node"]
	}
	set selected {}
	foreach img [$c find withtag "selected"] {
	    set node [lindex [$c gettags $img] 1]
	    lappend selected $node
	    set coords [$c coords $img]
	    set x [expr {[lindex $coords 0] / $zoom}]
	    set y [expr {[lindex $coords 1] / $zoom}]
	    if { $autorearrange_enabled == 0 && $g_prefs(gui_snap_grid)} {
		set dx [expr {(int($x / $grid + 0.5) * $grid - $x) * $zoom}]
		set dy [expr {(int($y / $grid + 0.5) * $grid - $y) * $zoom}]
		$c move $img $dx $dy
		set coords [$c coords $img]
		set x [expr {[lindex $coords 0] / $zoom}]
		set y [expr {[lindex $coords 1] / $zoom}]
	    } else {
		set dx 0
		set dy 0
	    }
	    if {$x < 0 || $y < 0 || $x > $sizex || $y > $sizey} {
		set regular false
	    }
	    # nodes with four coordinates
	    if { [lindex [$c gettags $node] 0] == "oval" ||
		 [lindex [$c gettags $node] 0] == "rectangle" } {
		set bbox [$c bbox "selectmark && $node"]
		# Boeing: bbox causes annotations to grow, subtract 5
		if { [llength $bbox] > 3 } {
		set x1 [lindex $bbox 0]
		set y1 [lindex $bbox 1]
		set x2 [expr {[lindex $bbox 2] - 5}]
		set y2 [expr {[lindex $bbox 3] - 5}]
		setNodeCoords $node "$x1 $y1 $x2 $y2"
		set redrawNeeded 1
		if {$x1 < 0 || $y1 < 0 || $x1 > $sizex || $y1 > $sizey || \
		    $x2 < 0 || $y2 < 0 || $x2 > $sizex || $y2 > $sizey} {
		    set regular false
		}
		}
	    # nodes with two coordinates
	    } else {
		setNodeCoords $node "$x $y"
	    }
	    if {[$c find withtag "nodelabel && $node"] != "" } {
		$c move "nodelabel && $node" $dx $dy
		set coords [$c coords "nodelabel && $node"]
		set x [expr {[lindex $coords 0] / $zoom}]
		set y [expr {[lindex $coords 1] / $zoom}]
		setNodeLabelCoords $node "$x $y"
		if {$x < 0 || $y < 0 || $x > $sizex || $y > $sizey} {
		    set regular false
		}
	    }
	    $c move "selectmark && $node" $dx $dy
	    $c addtag need_redraw withtag "link && $node"
	    set changed 1
	    if { $oper_mode == "exec" } {
	        # send node position update using x,y stored in node
	        set xy [getNodeCoords $node] ;# read new coordinates
		sendNodePosMessage -1 $node -1 [lindex $xy 0] [lindex $xy 1] \
			-1 0
		widgets_move_node $c $node 1
	    }
	    $c addtag need_redraw withtag "wlanlink && $node"
	} ;# end of: foreach img selected
	if {$regular == "true"} {
	    # user has dragged something within the canvas boundaries
	    foreach link [$c find withtag "link && need_redraw"] {
		redrawLink [lindex [$c gettags $link] 1]
	    }
	} else {
	    # user has dragged something beyond the canvas boundaries
	    .c config -cursor watch
	    loadCfg $undolog($undolevel)
	    redrawAll
	    if {$activetool == "select" } {
		selectNodes $selected
	    }
	    set changed 0
	}
	$c dtag link need_redraw
	nodeEnter $c

    # $changed!=1
    } elseif {$activetool == "select" } { 
	if {$selectbox == ""} {
	    set x1 $x
	    set y1 $y
	    rearrange_off
	} else {
	    set coords [$c coords $selectbox]
	    set x [lindex $coords 0]
	    set y [lindex $coords 1]
	    set x1 [lindex $coords 4]
	    set y1 [lindex $coords 5]
	    $c delete $selectbox
	    set selectbox ""
	}

	if { $resizemode == "false" } {
	    # select tool mouse button release while drawing select box
	    set enclosed {}
	    # fix occasional error
	    if { $x == "" || $y == "" || $x1 == "" || $y1 == "" } { return }
	    foreach obj [$c find enclosed $x $y $x1 $y1] {
		set tags [$c gettags $obj]
		if {[lindex $tags 0] == "node" && [lsearch $tags selected] == -1} {
		    lappend enclosed $obj
		}
		if {[lindex $tags 0] == "oval" && [lsearch $tags selected] == -1} {
		    lappend enclosed $obj
		}
		if {[lindex $tags 0] == "rectangle" && [lsearch $tags selected] == -1} {
		    lappend enclosed $obj
		}
		if {[lindex $tags 0] == "text" && [lsearch $tags selected] == -1} {
		    lappend enclosed $obj
		}
	    }
	    foreach obj $enclosed {
		selectNode $c $obj
	    }
	} else {
	    # select tool resizing an object by dragging its handles
	    # DYL bugfix. if x,y does not change, do not resize!
            # fixes a bug where the object dissappears 
            if { $x != $x1 || $y != $y1 } { 
                setNodeCoords $resizeobj "$x $y $x1 $y1"
	    } 
            set redrawNeeded 1
	    set resizemode false
	}
    }

    if { $redrawNeeded } {
	set redrawNeeded 0
	redrawAll
    } else {
	raiseAll $c
    }
    update
    updateUndoLog
}


#****f* editor.tcl/nodeEnter
# NAME
#   nodeEnter
# SYNOPSIS
#   nodeEnter $c
# FUNCTION
#   This procedure prints the node id, node name and 
#   node model (if exists), as well as all the interfaces
#   of the node in the status line. 
#   Information is presented for the node above which is
#   the mouse pointer.  
# INPUTS
#   * c -- tk canvas
#****
proc nodeEnter { c } {
    global activetool

    set curtags [$c gettags current]
    if { [lsearch -exact "node nodelabel" [lindex $curtags 0]] < 0 } {
	return ;# allow this proc to be called from button1-release
    }
    set node [lindex $curtags 1]
    set type [nodeType $node]
    set name [getNodeName $node]
    set model [getNodeModel $node]
    if { $model != "" } {
	set line "{$node} $name ($model):"
    } else {
	set line "{$node} $name:"
    }
    if { $type != "rj45" && $type != "tunnel" } {
	foreach ifc [ifcList $node] {
	    set line "$line $ifc:[getIfcIPv4addr $node $ifc]"
	}
    }
    set xy [getNodeCoords $node]
    set line "$line <[lindex $xy 0], [lindex $xy 1]>"
    .bottom.textbox config -text "$line"
    widgetObserveNode $c $node
}


#****f* editor.tcl/linkEnter
# NAME
#   linkEnter
# SYNOPSIS
#   linkEnter $c
# FUNCTION
#   This procedure prints the link id, link bandwidth
#   and link delay in the status line.
#   Information is presented for the link above which is
#   the mouse pointer.  
# INPUTS
#   * c -- tk canvas
#****
proc linkEnter {c} {
    global activetool link_list

    set link [lindex [$c gettags current] 1]
    if { [lsearch $link_list $link] == -1 } {
	return
    }
    set line "$link: [getLinkBandwidthString $link] [getLinkDelayString $link]"
    .bottom.textbox config -text "$line"
}


#****f* editor.tcl/anyLeave
# NAME
#   anyLeave
# SYNOPSIS
#   anyLeave $c
# FUNCTION
#   This procedure clears the status line.
# INPUTS
#   * c -- tk canvas
#****
proc anyLeave {c} {
    global activetool

    .bottom.textbox config -text ""
# Boeing
    widgetObserveNode $c ""
#   nodeHighlights $c "" off ""
# end Boeing
}


#****f* editor.tcl/checkIntRange 
# NAME
#   checkIntRange -- check integer range
# SYNOPSIS
#   set check [checkIntRange $str $low $high]
# FUNCTION
#   This procedure checks the input string to see if it is 
#   an integer between the low and high value.
# INPUTS
#   str -- string to check
#   low -- the bottom value
#   high -- the top value
# RESULT
#   * check -- set to 1 if the str is string between low and high
#   value, 0 otherwise.
#****
proc checkIntRange { str low high } {
    if { $str == "" } {
	return 1
    }
    set str [string trimleft $str 0]
    if { $str == "" } {
	set str 0
    }
    if { ![string is integer $str] } {
	return 0
    }
    if { $str < $low || $str > $high } {
	return 0
    }
    return 1
}

proc checkFloatRange { str low high } {
    if { $str == "" } {
	return 1
    }
    set str [string trimleft $str 0]
    if { $str == "" } {
	set str 0
    }
    if { ![string is double $str] } {
	return 0
    }
    if { $str < $low || $str > $high } {
	return 0
    }
    return 1
}

proc checkHostname { str } {
    # per RFC 952 and RFC 1123, any letter, number, or hyphen
    return [regexp {^[A-Za-z0-9-]+$} $str]
}


#****f* editor.tcl/focusAndFlash 
# NAME
#   focusAndFlash -- focus and flash
# SYNOPSIS
#   focusAndFlash $W $count
# FUNCTION
#   This procedure sets the focus on the bad entry field
#   and on this filed it provides an effect of flashing 
#   for approximately 1 second.
# INPUTS
#   * W -- textbox field that caused the bed entry
#   * count -- the parameter that causes flashes.
#   It can be left blank.
#****
proc focusAndFlash {W {count 9}} {
    global badentry

    set fg black
    set bg white

    if { $badentry == -1 } {
	return
    } else {
	set badentry 1
    }

    focus -force $W
    if {$count<1} {
	$W configure -foreground $fg -background $bg
	set badentry 0
    } else {
	if {$count%2} {
	    $W configure -foreground $bg -background $fg
	} else {
	    $W configure -foreground $fg -background $bg
	}
	after 200 [list focusAndFlash $W [expr {$count - 1}]]
    }
}


#****f* editor.tcl/popupConfigDialog
# NAME
#   popupConfigDialog -- popup Configuration Dialog Box
# SYNOPSIS
#   popupConfigDialog $c
# FUNCTION
#   Dynamically creates a popup dialog box for configuring 
#   links or nodes in IMUNES.
# INPUTS
#   * c -- canvas id
#****
proc popupConfigDialog { c } {
    global activetool router_model link_color oper_mode
    global badentry curcanvas
    global node_location systype
    global plugin_img_del
    set type ""

    set wi .popup
    if { [winfo exists $wi ] } {
	return
    }
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 1 1

    set object_type ""
    set tk_type [lindex [$c gettags current] 0]
    set target [lindex [$c gettags current] 1]
    if { [lsearch {node nodelabel interface} $tk_type] > -1 } {
	set object_type node
    }
    if { [lsearch {link linklabel} $tk_type] > -1 } {
	set object_type link
    }
    if { [lsearch {oval} $tk_type] > -1 } {
	set object_type oval
    }
    if { [lsearch {rectangle} $tk_type] > -1 } {
	set object_type rectangle
    }
    if { [lsearch {text} $tk_type] > -1 } {
	set object_type text
    }
    if { "$object_type" == ""} {
	destroy $wi
	return
    }
    if { $object_type == "link" } {
	set n0 [lindex [linkPeers $target] 0]
	set n1 [lindex [linkPeers $target] 1]
	# Boeing: added tunnel check
	#if { [nodeType $n0] == "rj45" || [nodeType $n1] == "rj45" ||  \
	#     [nodeType $n0] == "tunnel" || [nodeType $n1] == "tunnel"  } {
	#    destroy $wi
	#    return
	#}
    }
    $c dtag node selected
    $c delete -withtags selectmark

    switch -exact -- $object_type {
    node {
	set type [nodeType $target]
	if { $type == "pseudo" } {
	    #
	    # Hyperlink to another canvas
	    #
	    destroy $wi
	    set curcanvas [getNodeCanvas [getNodeMirror $target]]
	    switchCanvas none
	    return
	}
	set model [getNodeModel $target]
	set router_model $model
	wm title $wi "$type configuration"
	ttk::frame $wi.ftop -borderwidth 4
	ttk::entry $wi.ftop.name -width 16 \
	    -validate focus -invalidcommand "focusAndFlash %W"
	if { $type == "rj45" } {
	    ttk::label $wi.ftop.name_label -text "Physical interface:"
	} elseif { $type == "tunnel" } {
	    ttk::label $wi.ftop.name_label -text "IP address of tunnel peer:"
	} else {
	    ttk::label $wi.ftop.name_label -text "Node name:"
	    $wi.ftop.name configure -validatecommand {checkHostname %P}
	}
	$wi.ftop.name insert 0 [getNodeName $target]
	set img [getNodeImage $target]
	ttk::button $wi.ftop.img -image $img -command "popupCustomImage $target"
	
	if { $type == "rj45" } {
	    rj45ifclist $wi $target 0
	} 
	# execution server
	global exec_servers node_location
	set node_location [getNodeLocation $target]
	set servers [lsort -dictionary [array names exec_servers]]
	set servers "(none) $servers"
	if { $node_location == "" } { set node_location "(none)" }
	eval tk_optionMenu $wi.ftop.menu node_location $servers
	pack $wi.ftop.img $wi.ftop.menu $wi.ftop.name $wi.ftop.name_label \
	    -side right -padx 4 -pady 4
	# end Boeing
	pack $wi.ftop -side top

	if { $type == "router" } {
	    ttk::frame $wi.model -borderwidth 4
	    ttk::label $wi.model.label -text "Type:"
	    set runstate "disabled"
	    if { $oper_mode == "edit" } {
		eval tk_optionMenu $wi.model.menu router_model \
			[getNodeTypeNames]
		set runstate "normal"
	    } else {
		tk_optionMenu $wi.model.menu router_model $model
	    }
	    # would be nice to update the image upon selection; binding to
	    # <ButtonRelease> will not work
	    #tkwait variable router_model "customImageApply $wi $target"
            set sock [lindex [getEmulPlugin $target] 2]
	    ttk::button $wi.model.services -text "Services..." -state $runstate \
	        -command \
		"sendConfRequestMessage $sock $target services 0x1 -1 \"\""
	    pack $wi.model.services $wi.model.menu $wi.model.label \
	    	-side right -padx 0 -pady 0
	    pack $wi.model -side top
	}

	    if { $type == "wlan" } {
		wlanConfigDialogHelper $wi $target 0
	    } elseif { $type == "tunnel" } {
		#
		# tunnel controls
		#
		ttk::frame $wi.con2
		global conntap
		set conntap [netconfFetchSection $target "tunnel-tap"]
		if { $conntap == "" } { set conntap off }
		# TODO: clean this up
		ttk::radiobutton $wi.con2.dotap0 \
		    -variable conntap -value off \
		    -text "tunnel to another CORE emulation"
		ttk::frame $wi.con2.key
		ttk::label $wi.con2.key.lab -text "GRE key:"
		ttk::entry $wi.con2.key.key -width 6
		ttk::radiobutton $wi.con2.dotap1 -state disabled \
		    -variable conntap -value on \
		    -text "tunnel to the virtual TAP interface of another system"
		pack $wi.con2.key.lab $wi.con2.key.key -side left
		pack $wi.con2.dotap0 -side top -anchor w
		pack $wi.con2.key -side top
		pack $wi.con2.dotap1 -side top -anchor w
		pack $wi.con2 -side top
		set key [netconfFetchSection $target "tunnel-key"]
		if { $key == "" } { set key 1 }
		$wi.con2.key.key insert 0 $key

		# TODO: clean this up
		ttk::frame $wi.conn
		ttk::label $wi.conn.label -text "Transport type:"
		tk_optionMenu $wi.conn.conntype conntype "UDP" "TCP"
		$wi.conn.conntype configure -state disabled
		pack $wi.conn.label $wi.conn.conntype -side left -anchor w
		pack $wi.conn -side top
		global conntype
		set conntype [netconfFetchSection $target "tunnel-type"]
		if { $conntype == "" } { set conntype "UDP" }
	

		# TODO: clean this up
		ttk::frame  $wi.linfo
		ttk::label $wi.linfo.label -text "Local hook:"
		ttk::entry $wi.linfo.local -state disabled
		set localhook [netconfFetchSection $target "local-hook"]
		if { $localhook == "" || $localhook == "(none)" } {
		    # automatically generate local hook name
  		    set ifc [lindex [ifcList $target] 0]
		    if { $ifc != "" } {
			set hname [info hostname]
			set peer [peerByIfc $target $ifc]
			set localhook "$hname$peer"
		    } else {
			set localhook "(none)"
		    }
		}
		$wi.linfo.local insert 0 $localhook
		pack $wi.linfo.label $wi.linfo.local -side left -anchor w
		pack $wi.linfo -side top

		ttk::frame  $wi.pinfo
		ttk::label $wi.pinfo.label -text "Peer hook:"
		ttk::entry $wi.pinfo.peer -state disabled
		$wi.pinfo.peer insert 0 \
			[netconfFetchSection $target "peer-hook"]
		pack $wi.pinfo.label $wi.pinfo.peer -side left -anchor w
		pack $wi.pinfo -side top
	    }

	# interface list
	if { [[typemodel $target].layer] == "NETWORK" } {
	    # canvas used for scrolling frames for each interface
	    ttk::frame $wi.ifaces
	    set height [expr {100 * [llength [ifcList $target]]}]
	    if { $height > 300 } { set height 300 }
            canvas $wi.ifaces.c -height $height -highlightthickness 0 \
		-yscrollcommand "$wi.ifaces.scroll set"
	    scrollbar $wi.ifaces.scroll -command "$wi.ifaces.c yview"
	    pack $wi.ifaces.c -side left -fill both -expand 1
	    pack $wi.ifaces.scroll -side right -fill y
	    pack $wi.ifaces -side top -fill both -expand 1
	    set y 0

	    foreach ifc [lsort -ascii [ifcList $target]] {
		set fr $wi.ifaces.c.if$ifc
		ttk::labelframe $fr -text "Interface $ifc"
		$wi.ifaces.c create window 4 $y -window $fr -anchor nw
		incr y 100

		set peer [peerByIfc $target $ifc]
		if { [isEmane $peer] } {
		    ttk::frame $fr.opts
		    set caps [getCapabilities $peer "mobmodel"]
		    set cap [lindex $caps 0]
		    set cmd "sendConfRequestMessage -1 $target $cap 0x1 -1 \"\""
		    ttk::button $fr.opts.cfg -command $cmd \
						-text "$cap options..."
		    pack $fr.opts.cfg -side left -padx 4
		    pack $fr.opts -side top -anchor w
		    incr y 28
		}

		ttk::frame $fr.cfg
		#
		# MAC address
		#
		ttk::frame $fr.cfg.mac
		ttk::label $fr.cfg.mac.addrl -text "MAC address" \
		    -anchor w
		set macaddr [getIfcMacaddr $target $ifc]
		global if${ifc}_auto_mac
		if { $macaddr == "" } {
		    set if${ifc}_auto_mac 1
		    set state disabled
		} else {
		    set if${ifc}_auto_mac 0
		    set state normal
		}
		ttk::checkbutton $fr.cfg.mac.auto -text "auto-assign" \
		    -variable if${ifc}_auto_mac \
		    -command "macEntryHelper $wi $ifc"
		ttk::entry $fr.cfg.mac.addrv -width 15 \
		    -state $state
		$fr.cfg.mac.addrv insert 0 $macaddr
		pack $fr.cfg.mac.addrl $fr.cfg.mac.auto \
		    $fr.cfg.mac.addrv -side left -padx 4
		pack $fr.cfg.mac -side top -anchor w

		#
		# IPv4 address
		#
		ttk::frame $fr.cfg.ipv4
		ttk::label $fr.cfg.ipv4.addrl -text "IPv4 address" \
		    -anchor w
		ttk::entry $fr.cfg.ipv4.addrv -width 30 \
		    -validate focus -invalidcommand "focusAndFlash %W"
		$fr.cfg.ipv4.addrv insert 0 \
		    [getIfcIPv4addr $target $ifc]
		$fr.cfg.ipv4.addrv configure \
		    -validatecommand {checkIPv4Net %P}
		ttk::button $fr.cfg.ipv4.clear -image $plugin_img_del \
		    -command "$fr.cfg.ipv4.addrv delete 0 end"
		pack $fr.cfg.ipv4.addrl $fr.cfg.ipv4.addrv \
		    $fr.cfg.ipv4.clear -side left
		pack $fr.cfg.ipv4 -side top -anchor w -padx 4

		#
		# IPv6 address
		#
		ttk::frame $fr.cfg.ipv6
		ttk::label $fr.cfg.ipv6.addrl -text "IPv6 address" \
		    -anchor w
		ttk::entry $fr.cfg.ipv6.addrv -width 30 \
		    -validate focus -invalidcommand "focusAndFlash %W"
		$fr.cfg.ipv6.addrv insert 0 \
		    [getIfcIPv6addr $target $ifc]
		$fr.cfg.ipv6.addrv configure -validatecommand {checkIPv6Net %P}
		ttk::button $fr.cfg.ipv6.clear -image $plugin_img_del \
		    -command "$fr.cfg.ipv6.addrv delete 0 end"
		pack $fr.cfg.ipv6.addrl $fr.cfg.ipv6.addrv \
		    $fr.cfg.ipv6.clear -side left
		pack $fr.cfg.ipv6 -side top -anchor w -padx 4
		pack $fr.cfg -side left
		bind $fr.cfg <4> "$wi.ifaces.c yview scroll -1 units"
		bind $fr.cfg <5> "$wi.ifaces.c yview scroll 1 units"
	    } ;# end foreach ifc
            $wi.ifaces.c configure -scrollregion "0 0 250 $y"
	    # mouse wheel bindings for scrolling
	    foreach ctl [list $wi.ifaces.c $wi.ifaces.scroll] {
		bind $ctl <4> "$wi.ifaces.c yview scroll -1 units"
		bind $ctl <5> "$wi.ifaces.c yview scroll 1 units"
		bind $ctl <Up> "$wi.ifaces.c yview scroll -1 units"
		bind $ctl <Down> "$wi.ifaces.c yview scroll 1 units"
	    }
        }
    }
    oval {
	destroy $wi
	annotationConfig $c $target
	return
    }
    rectangle {
	destroy $wi
	annotationConfig $c $target
	return
    }
    text {
	destroy $wi
	annotationConfig $c $target
	return
    }
    link {
	wm title $wi "link configuration"
	ttk::frame $wi.ftop -borderwidth 6
	set nam0 [getNodeName $n0]
	set nam1 [getNodeName $n1]
	ttk::label $wi.ftop.name_label -justify left -text \
	"Link from $nam0 to $nam1"
	pack $wi.ftop.name_label -side right
	pack $wi.ftop -side top

	set spinbox [getspinbox]
        global g_link_config_uni_state
        set g_link_config_uni_state "bid"

	ttk::frame $wi.preset -borderwidth 4
	global link_preset_val
	set link_preset_val unlimited
	set linkpreMenu [tk_optionMenu $wi.preset.linkpre link_preset_val a]
	# unidirectional links not always supported
        if { [isUniSupported $n0 $n1] } {
	    set unistate normal
	} else {
	    set unistate disabled
	}
	ttk::button $wi.preset.uni -text "  >>  " -state $unistate \
	    -command "linkConfigUni $wi"
	pack $wi.preset.uni $wi.preset.linkpre -side right
	linkPresets $wi $linkpreMenu init
	pack $wi.preset -side top -anchor e

	ttk::frame $wi.unilabel -borderwidth 4
	ttk::label $wi.unilabel.updown -text "Symmetric link effects:"
	pack $wi.unilabel.updown -side left -anchor w
	pack $wi.unilabel -side top -anchor w 

	ttk::frame $wi.bandwidth -borderwidth 4
	ttk::label $wi.bandwidth.label -anchor e -text "Bandwidth (bps):"
	$spinbox $wi.bandwidth.value -justify right -width 10 \
	    -validate focus -invalidcommand "focusAndFlash %W"
	$wi.bandwidth.value insert 0 [getLinkBandwidth $target]
	$wi.bandwidth.value configure \
	    -validatecommand {checkIntRange %P 0 1000000000} \
	    -from 0 -to 1000000000 -increment 1000000
	pack $wi.bandwidth.value $wi.bandwidth.label -side right
	pack $wi.bandwidth -side top -anchor e

	ttk::frame $wi.delay -borderwidth 4
	ttk::label $wi.delay.label -anchor e -text "Delay (us):"
	$spinbox $wi.delay.value -justify right -width 10 \
	    -validate focus -invalidcommand "focusAndFlash %W"
	$wi.delay.value insert 0 [getLinkDelay $target]
	# 274 seconds is maximum netem delay for Linux 3.2.0-60-generic kernel
	$wi.delay.value configure \
	    -validatecommand {checkIntRange %P 0 274000000} \
	    -from 0 -to 10000000 -increment 5
	pack $wi.delay.value $wi.delay.label -side right
	pack $wi.delay -side top -anchor e

	ttk::frame $wi.jitter -borderwidth 4
	ttk::label $wi.jitter.label -anchor e -text "Jitter (us):"
	$spinbox $wi.jitter.value -justify right -width 10 \
	    -validate focus -invalidcommand "focusAndFlash %W"
	$wi.jitter.value insert 0 [getLinkJitter $target]
	$wi.jitter.value configure \
	    -validatecommand {checkIntRange %P 0 10000000} \
	    -from 0 -to 10000000 -increment 5
	pack $wi.jitter.value $wi.jitter.label -side right
	pack $wi.jitter -side top -anchor e

	ttk::frame $wi.ber -borderwidth 4
	if { [lindex $systype 0] == "Linux" } {
	    set bertext "Loss (%):"
	    set berinc 0.1
	    set bermax 100.0
	} else { ;# netgraph uses BER
	    set bertext "BER (1/N):"
	    set berinc 1000
	    set bermax 10000000000000
	}
	ttk::label $wi.ber.label -anchor e -text $bertext
	$spinbox $wi.ber.value -justify right -width 10 \
	    -validate focus -invalidcommand "focusAndFlash %W"
	$wi.ber.value insert 0 [getLinkBER $target]
	$wi.ber.value configure \
	    -validatecommand "checkFloatRange %P 0.0 $bermax" \
	    -from 0.0 -to $bermax -increment $berinc
	pack $wi.ber.value $wi.ber.label -side right
	pack $wi.ber -side top -anchor e

	ttk::frame $wi.dup -borderwidth 4
	ttk::label $wi.dup.label -anchor e -text "Duplicate (%):"
	$spinbox $wi.dup.value -justify right -width 10 \
	    -validate focus -invalidcommand "focusAndFlash %W"
	$wi.dup.value insert 0 [getLinkDup $target]
	$wi.dup.value configure \
	    -validatecommand {checkFloatRange %P 0 50} \
	    -from 0 -to 50 -increment 1
	pack $wi.dup.value $wi.dup.label -side right
	pack $wi.dup -side top -anchor e

# Boeing: jitter
#	frame $wi.jitter -borderwidth 4
#	label $wi.jitter.label -anchor e -text "Jitter (us):"
#	spinbox $wi.jitter.value -bg white -justify right -width 10 \
#	    -validate focus -invalidcommand "focusAndFlash %W"
#	$wi.jitter.value insert 0 [getLinkJitter $target]
#	$wi.jitter.value configure \
#	    -validatecommand {checkIntRange %P 0 10000000} \
#	    -from 0 -to 10000000 -increment 5
#	pack $wi.jitter.value $wi.jitter.label -side right
#	pack $wi.jitter -side top -anchor e
# end Boeing

	ttk::frame $wi.color -borderwidth 4
	ttk::label $wi.color.label -anchor e -text "Color:"
	set link_color [getLinkColor $target]
	tk_optionMenu $wi.color.value link_color \
	    Red Green Blue Yellow Magenta Cyan Black
	$wi.color.value configure -width 8
	pack $wi.color.value $wi.color.label -side right
	pack $wi.color -side top -anchor e

	ttk::frame $wi.width -borderwidth 4
	ttk::label $wi.width.label -anchor e -text "Width:"
	$spinbox $wi.width.value -justify right -width 10 \
	    -validate focus -invalidcommand "focusAndFlash %W"
	$wi.width.value insert 0 [getLinkWidth $target]
	$wi.width.value configure \
	    -validatecommand {checkIntRange %P 1 8} \
	    -from 1 -to 8 -increment 1
	pack $wi.width.value $wi.width.label -side right
	pack $wi.width -side top -anchor e

	# auto-expand upstream if values exist
	set bw [getLinkBandwidth $target up]
	set dl [getLinkDelay $target up]
	set jt [getLinkJitter $target up]
	set ber [getLinkBER $target up]
	set dup [getLinkDup $target up]
	if { $bw > 0 || $dl > 0 || $jt > 0 || $ber > 0 || $dup > 0 } {
            linkConfigUni $wi
	    $wi.bandwidth.value2 delete 0 end
	    $wi.bandwidth.value2 insert 0 $bw
	    $wi.delay.value2 delete 0 end
	    $wi.delay.value2 insert 0 $dl
	    $wi.jitter.value2 delete 0 end
	    $wi.jitter.value2 insert 0 $jt
	    $wi.ber.value2 delete 0 end
	    $wi.ber.value2 insert 0 $ber
	    $wi.dup.value2 delete 0 end
	    $wi.dup.value2 insert 0 $dup
	}
    }
    } ;# end switch

    ttk::frame $wi.butt -borderwidth 6
    # NOTE: plugins.tcl:popupCapabilityConfig may read this command option
    ttk::button $wi.butt.apply -text "Apply" -command \
    "popupConfigApply $wi $object_type $target 0"
    focus $wi.butt.apply
    # Boeing: remove range circles upon cancel
    if {$type == "wlan"} { 
    	set cancelcmd "set badentry -1 ; destroy $wi;"
	set cancelcmd "$cancelcmd updateRangeCircles $target 0" 
    } else {
    	set cancelcmd "set badentry -1 ; destroy $wi" 
    }
    ttk::button $wi.butt.cancel -text "Cancel" -command $cancelcmd
    #end Boeing
    pack $wi.butt.cancel $wi.butt.apply -side right
    pack $wi.butt -side bottom
    bind $wi <Key-Escape> $cancelcmd
#    bind $wi <Key-Return> "popupConfigApply $wi $object_type $target 0"
}


proc linkConfigUni { wi } {
    global g_link_config_uni_state

    set capt [lindex [$wi.preset.uni configure -text] 4]

    if { $capt == "  >>  " } {
	set g_link_config_uni_state "uni"
	$wi.preset.uni configure -text "  <<  "
	set txt "Asymmetric effects: downstream  /  upstream"
	$wi.unilabel.updown configure -text $txt

	set spinbox [getspinbox]
	if { ![winfo exists $wi.bandwidth.value2] } {
	    $spinbox $wi.bandwidth.value2 -justify right \
	    	-width 10 -validate focus -invalidcommand "focusAndFlash %W"
	    $wi.bandwidth.value2 configure \
		-validatecommand {checkIntRange %P 0 1000000000} \
		-from 0 -to 1000000000 -increment 1000000
	}
	$wi.bandwidth.value2 delete 0 end
	$wi.bandwidth.value2 insert 0 [$wi.bandwidth.value get]
	pack $wi.bandwidth.value2 -side right
	pack $wi.bandwidth.value2 -before $wi.bandwidth.value

	if { ![winfo exists $wi.delay.value2] } {
	    $spinbox $wi.delay.value2 -justify right -width 10 \
		-validate focus -invalidcommand "focusAndFlash %W"
	    $wi.delay.value2 configure \
		-validatecommand {checkIntRange %P 0 10000000} \
		-from 0 -to 10000000 -increment 5
	}
	$wi.delay.value2 delete 0 end
	$wi.delay.value2 insert 0 [$wi.delay.value get]
	pack $wi.delay.value2 -side right
	pack $wi.delay.value2 -before $wi.delay.value

	if { ![winfo exists $wi.jitter.value2] } {
	    $spinbox $wi.jitter.value2 -justify right -width 10 \
		-validate focus -invalidcommand "focusAndFlash %W"
	    $wi.jitter.value2 configure \
		-validatecommand {checkIntRange %P 0 10000000} \
		-from 0 -to 10000000 -increment 5
	}
	$wi.jitter.value2 delete 0 end
	$wi.jitter.value2 insert 0 [$wi.jitter.value get]
	pack $wi.jitter.value2 -side right
	pack $wi.jitter.value2 -before $wi.jitter.value

	if { ![winfo exists $wi.ber.value2] } {
	    $spinbox $wi.ber.value2 -justify right -width 10 \
		-validate focus -invalidcommand "focusAndFlash %W"
	    $wi.ber.value2 configure \
		-validatecommand "checkFloatRange %P 0.0 100.0" \
		-from 0.0 -to 100.0 -increment 0.1
	}
	$wi.ber.value2 delete 0 end
	$wi.ber.value2 insert 0 [$wi.ber.value get]
	pack $wi.ber.value2 -side right
	pack $wi.ber.value2 -before $wi.ber.value

	if { ![winfo exists $wi.dup.value2] } {
	    $spinbox $wi.dup.value2 -justify right -width 10 \
		-validate focus -invalidcommand "focusAndFlash %W"
	    $wi.dup.value2 configure \
		-validatecommand {checkFloatRange %P 0 50} \
		-from 0 -to 50 -increment 1
	}
	$wi.dup.value2 delete 0 end
	$wi.dup.value2 insert 0 [$wi.dup.value get]
	pack $wi.dup.value2 -side right
	pack $wi.dup.value2 -before $wi.dup.value
    } else {
	set g_link_config_uni_state "bid"
	$wi.preset.uni configure -text "  >>  "
	$wi.unilabel.updown configure -text "Symmetric link effects:"
	pack forget $wi.bandwidth.value2
	pack forget $wi.delay.value2
	pack forget $wi.jitter.value2
	pack forget $wi.ber.value2
	pack forget $wi.dup.value2
    }
}

# unidirectional links are not always supported
proc isUniSupported { n1 n2 } {
    set blacklist [list "hub" "lanswitch"]
    set type1 [nodeType $n1]
    set type2 [nodeType $n2]
    # not yet supported for GRE tap device
    if { $type1 == "tunnel" || $type2 == "tunnel" } {
	return false
    }
    # unidirectional links are supported between two switches/hubs
    if { [lsearch $blacklist $type1] != -1 && \
	 [lsearch $blacklist $type2] != -1 } {
	return true
    }
    # unidirectional links not supported between hub/switch and something else
    if { [lsearch $blacklist $type1] != -1 || \
	 [lsearch $blacklist $type2] != -1 } {
	return false
    }
    # unidirectional links are supported between routers, rj45s, etc.
    # WLANs not included here because they have no link dialog
    return true
}

# toggle the state of the mac address entry, and insert MAC address template
proc macEntryHelper { wi ifc } {
    set fr $wi.ifaces.c.if$ifc
    set ctl $fr.cfg.mac.addrv
    set s normal
    if { [$ctl cget -state] == $s } { set s disabled }
    $ctl configure -state $s

    if { [$ctl get] == "" } { $ctl insert 0 "00:00:00:00:00:00" }
}


#****f* editor.tcl/popupConfigApply
# NAME
#   popupConfigApply -- popup configuration apply
# SYNOPSIS
#   popupConfigApply $w $object_type $target $phase
# FUNCTION
#   This procedure is called when the button apply is pressed in 
#   popup configuration dialog box. It reads different
#   configuration parameters depending on the object_type.
# INPUTS
#   * w -- widget
#   * object_type -- describes the object type that is currently 
#   configured. It can be either link or node.
#   * target -- node id of the configured node or link id of the
#   configured link
#   * phase --  This procedure is invoked in two diffenet phases 
#   to enable validation of the entry that was the last made. 
#   When calling this function always use the phase parameter 
#   set to 0.
#****
proc popupConfigApply { wi object_type target phase } {
    global changed oper_mode router_model link_color badentry
    global customEnabled ipsecEnabled
    global eid

    $wi config -cursor watch
    update
    if { $phase == 0 } {
	set badentry 0
	focus .
	after 100 "popupConfigApply $wi $object_type $target 1"
	return
    } elseif { $badentry } {
	$wi config -cursor left_ptr
	return
    }
    switch -exact -- $object_type {
    #
    # Node
    #
    node {
	set type [nodeType $target]
	set model [getNodeModel $target]
	set name [string trim [$wi.ftop.name get]]
	set changed_to_remote 0
	global node_location
	if { $node_location != [getNodeLocation $target] } {
	    if { $node_location == "(none)" } { set node_location "" }
	    setNodeLocation $target $node_location
	    set changed 1
	}
	set node_location ""
	if { $name != [getNodeName $target] } {
	    setNodeName $target $name
	    set changed 1
	}
	if { $oper_mode == "edit" && $type == "router" && \
	    $router_model != $model } {
	    setNodeModel $target $router_model
	    set changed 1
	    if { $router_model == "remote" } { set changed_to_remote 1 };#Boeing
	}

# Boeing - added wlan, remote, tunnel, ktunnel items
	if { $type == "wlan" } {
	    wlanConfigDialogHelper $wi $target 1	
	} elseif { $type == "tunnel" } {
		#
		# apply tunnel items
		#
	        set ipaddr "$name/24" ;# tunnel name == IP address of peer 
	        set oldipaddr [getIfcIPv4addr $target e0]
		if { $ipaddr != $oldipaddr } {
		    setIfcIPv4addr $target e0 $ipaddr
		}
		global conntype conntap
		set oldconntype [netconfFetchSection $target "tunnel-type"]
		if { $oldconntype != $conntype } {
		    netconfInsertSection $target [list "tunnel-type" $conntype]
		}
		set oldconntap [netconfFetchSection $target "tunnel-tap"]
		if { $oldconntap != $conntap } {
		    netconfInsertSection $target [list "tunnel-tap" $conntap]
		}
		set oldkey [netconfFetchSection $target "tunnel-key"]
		set key [$wi.con2.key.key get]
		if { $oldkey != $key } {
		    netconfInsertSection $target [list "tunnel-key" $key]
		}

		set oldlocal [netconfFetchSection $target "local-hook"]
		set local [$wi.linfo.local get]
		if { $oldlocal != $local } {
		    netconfInsertSection $target [list "local-hook" $local]
		}

		set oldpeer [netconfFetchSection $target "peer-hook"]
		set peer [$wi.pinfo.peer get]
		if { $oldpeer != $peer } {
		    netconfInsertSection $target [list "peer-hook" $peer]
		}
	} elseif { $type == "ktunnel" } {
		#
		# apply ktunnel items
		#
		set oldlocal [netconfFetchSection $target "local-hook"]
		set local [$wi.linfo.local get]
		if { $oldlocal != $local } {
		    netconfInsertSection $target [list "local-hook" $local]
		}
# Boeing changing to interface name for RJ45 
#	    } elseif { $type == "rj45" } {
#		#
#		# apply rj45 items
#		#
#		set ifcName [string trim [$wi.interface.name get]]
#		puts "$ifcName\n"
#
 	    } elseif { $type == "router" && [getNodeModel $target] == "remote" } {
		if { $changed_to_remote == 0 } {
		    set i 1
		    set remoteIP [string trim [$wi.remoteinfo.ip.text get $i.0 $i.end]]
		    if { $remoteIP != [router.remote.getRemoteIP $target] } {
			router.remote.setRemoteIP $target $remoteIP
			set changed 1
		    }
		    set ifc [string trim [$wi.remoteinfo.ifc.text get $i.0 $i.end]]
		    if { $ifc != [router.remote.getCInterface $target] } {
			router.remote.setCInterface $target $ifc
			set changed 1
		    }
		    set startcmd [string trim [$wi.remotecommands.start.text get $i.0 $i.end]]
		    if { $startcmd != [router.remote.getStartCmd $target] } {
			router.remote.setStartCmd $target $startcmd
			set changed 1
		    }
		    set stopcmd [string trim [$wi.remotecommands.stop.text get $i.0 $i.end]]
		    if { $stopcmd != [router.remote.getStopCmd $target] } {
			router.remote.setStopCmd $target $stopcmd
			set changed 1
		    }
		}
	}

	if {[[typemodel $target].layer] == "NETWORK"} {
	    foreach ifc [ifcList $target] {
		set fr $wi.ifaces.c.if$ifc
		set macaddr [$fr.cfg.mac.addrv get]
		global if${ifc}_auto_mac
		if { [set if${ifc}_auto_mac] == 1 } { set macaddr "" }
		set oldmacaddr [getIfcMacaddr $target $ifc]
		if { $macaddr != $oldmacaddr } {
		    setIfcMacaddr $target $ifc $macaddr
		    set changed 1
		}
		set ipaddr [$fr.cfg.ipv4.addrv get]
		set oldipaddr [getIfcIPv4addr $target $ifc]
		if { $ipaddr != $oldipaddr } {
		    setIfcIPv4addr $target $ifc $ipaddr
		    set changed 1
		}
		set ipaddr [$fr.cfg.ipv6.addrv get]
		set oldipaddr [getIfcIPv6addr $target $ifc]
		if { $ipaddr != $oldipaddr } {
		    setIfcIPv6addr $target $ifc $ipaddr
		    set changed 1
		}
	    }
	}
    }

    link {
	global g_link_config_uni_state
	set mirror [getLinkMirror $target]
        
        if { [setIfChanged $target $mirror $wi "bandwidth" "LinkBandwidth"] } {
	    set changed 1
	}
        if { [setIfChanged $target $mirror $wi "delay" "LinkDelay"] } {
	    set changed 1
	}
        if { [setIfChanged $target $mirror $wi "ber" "LinkBER"] } {
	    set changed 1
	}
        if { [setIfChanged $target $mirror $wi "dup" "LinkDup"] } {
	    set changed 1
	}
        if { [setIfChanged $target $mirror $wi "jitter" "LinkJitter"] } {
	    set changed 1
	}

	if { $link_color != [getLinkColor $target] } {
	    setLinkColor $target $link_color
	    if { $mirror != "" } {
		setLinkColor $mirror $link_color
	    }
	    set changed 1
	}
	set width [$wi.width.value get]
	if { $width != [getLinkWidth $target] } {
	    setLinkWidth $target $width
	    if { $mirror != "" } {
		setLinkWidth $mirror $width
	    }
	    set changed 1
	}
	if { $changed == 1 && $oper_mode == "exec" } {
	    execSetLinkParams $eid $target
	}
    }

    }

    popdownConfig $wi
}

# helper for Link Config dialog
# ctl must exist as $wi.$ctl.value{2}, and {get,set}$procname must be valid
# returns true when value has changed, false otherwise
proc setIfChanged { target mirror wi ctl procname } {
    global g_link_config_uni_state

    set val [$wi.$ctl.value get]
    if { $g_link_config_uni_state == "uni" } {
	set val [list $val [$wi.$ctl.value2 get]]
    }
    set oldval [get$procname $target]
    set oldval2 [get$procname $target "up"]
    if { $oldval2 != "" } {
	set oldval [list $oldval $oldval2]
    }
    if { $val != $oldval } {
	set$procname $target $val
	if { $mirror != "" } {
	    set$procname $mirror $val
	}
	return true
    }
    return false
}

#****f* editor.tcl/printCanvas
# NAME
#   printCanvas -- print canvas
# SYNOPSIS
#   printCanvas $w
# FUNCTION
#   This procedure is called when the print button in
#   print dialog box is pressed. 
# INPUTS
#   * w -- print dialog widget
#****
proc printCanvas { w } {
    global sizex sizey

    set prncmd [$w.e1 get]
    destroy $w
    set p [open "|$prncmd" WRONLY]
    puts $p [.c postscript -height $sizey -width $sizex -x 0 -y 0 -rotate yes -pageheight 297m -pagewidth 210m]
    close $p
}


#****f* editor.tcl/deleteSelection
# NAME
#   deleteSelection -- delete selection
# SYNOPSIS
#   deleteSelection
# FUNCTION
#   By calling this procedure all the selected nodes in imunes will 
#   be deleted.
#****
proc deleteSelection { } {
    global changed
    global background 
    global viewid
    catch {unset viewid}
    .c config -cursor watch; update

    foreach lnode [selectedNodes] {
	if { $lnode != "" } {
	    removeGUINode $lnode
	}
	set changed 1
    }

    raiseAll .c
    updateUndoLog
    .c config -cursor left_ptr
    .bottom.textbox config -text ""
}


proc assignSelection { server } {
    global changed
    .c config -cursor watch; update

    foreach node [selectedNodes] {
	if { $node != "" } {
	    setNodeLocation $node $server
	}
	set changed 1
    }

    redrawAll
    updateUndoLog
    .c config -cursor left_ptr
    .bottom.textbox config -text ""
}


proc align2grid {} {
    global sizex sizey grid zoom changed

    set node_objects [.c find withtag node]
    if { [llength $node_objects] == 0 } {
	return
    }

    set step [expr {$grid * 4}]

    for { set x $step } { $x <= [expr {$sizex - $step}] } { incr x $step } {
	for { set y $step } { $y <= [expr {$sizey - $step}] } { incr y $step } {
	    if { [llength $node_objects] == 0 } {
		set changed 1
		updateUndoLog
		redrawAll
		return
	    }
	    set node [lindex [.c gettags [lindex $node_objects 0]] 1]
	    set node_objects [lreplace $node_objects 0 0]
	    setNodeCoords $node "$x $y"
	    lassign [getDefaultLabelOffsets [nodeType $node]] dx dy
	    setNodeLabelCoords $node "[expr {$x + $dx}] [expr {$y + $dy}]"
	}
    }
}

#****f* editor.tcl/rearrange
# NAME
#   rearrange
# SYNOPSIS
#   rearrange $mode
# FUNCTION
#   This procedure rearranges the position of nodes in imunes.
#   It can be used to rearrange all the nodes or only the selected
#   nodes. 
# INPUTS
#   * mode -- when set to "selected" only the selected nodes will be
#   rearranged.
#****
proc rearrange { mode } {
    global link_list autorearrange_enabled sizex sizey curcanvas zoom activetool

    set activetool select

    if { $autorearrange_enabled } {
	rearrange_off
	return
    }
    set autorearrange_enabled 1
    .bottom.mbuf config -text "autorearrange"
    if { $mode == "selected" } {
	.menubar.tools entryconfigure "Auto rearrange all" -state disabled
	.menubar.tools entryconfigure "Auto rearrange all" -indicatoron off
	.menubar.tools entryconfigure "Auto rearrange selected" -indicatoron on
	set tagmatch "node && selected"
    } else {
	.menubar.tools entryconfigure "Auto rearrange all" -indicatoron on
	.menubar.tools entryconfigure "Auto rearrange selected" -state disabled
	.menubar.tools entryconfigure "Auto rearrange selected" -indicatoron off
	set tagmatch "node"
    }
    set otime [clock clicks -milliseconds]
    while { $autorearrange_enabled } {
	set ntime [clock clicks -milliseconds]
	if { $otime == $ntime } {
	    set dt 0.001
	} else {
	    set dt [expr {($ntime - $otime) * 0.001}]
	    if { $dt > 0.2 } {
		set dt 0.2
	    }
	    set otime $ntime
	}

	set objects [.c find withtag $tagmatch]
	set peer_objects [.c find withtag node]
	foreach obj $peer_objects {
	    set node [lindex [.c gettags $obj] 1]
	    set coords [.c coords $obj]
	    set x [expr {[lindex $coords 0] / $zoom}]
	    set y [expr {[lindex $coords 1] / $zoom}]
	    set x_t($node) $x
	    set y_t($node) $y

	    if { $x > 0 } {
		set fx [expr {1000 / ($x * $x + 100)}]
	    } else {
		set fx 10
	    }
	    set dx [expr {$sizex - $x}]
	    if { $dx > 0 } {
		set fx [expr {$fx - 1000 / ($dx * $dx + 100)}]
	    } else {
		set fx [expr {$fx - 10}]
	    }

	    if { $y > 0 } {
		set fy [expr {1000 / ($y * $y + 100)}]
	    } else {
		set fy 10
	    }
	    set dy [expr {$sizey - $y}]
	    if { $dy > 0 } {
		set fy [expr {$fy - 1000 / ($dy * $dy + 100)}]
	    } else {
		set fy [expr {$fy - 10}]
	    }
	    set fx_t($node) $fx
	    set fy_t($node) $fy
	}

	foreach obj $objects {
	    set node [lindex [.c gettags $obj] 1]
	    set i [lsearch -exact $peer_objects $obj]
	    set peer_objects [lreplace $peer_objects $i $i]
	    set x $x_t($node)
	    set y $y_t($node)
	    foreach other_obj $peer_objects {
		set other [lindex [.c gettags $other_obj] 1]
		set o_x $x_t($other)
		set o_y $y_t($other)
		set dx [expr {$x - $o_x}]
		set dy [expr {$y - $o_y}]
		set d [expr {hypot($dx, $dy)}]
		set d2 [expr {$d * $d}]
		set p_fx [expr {1000.0 * $dx / ($d2 * $d + 100)}]
		set p_fy [expr {1000.0 * $dy / ($d2 * $d + 100)}]
		if {[linkByPeers $node $other] != ""} {
		    set p_fx [expr {$p_fx - $dx * $d2 * .0000000005}]
		    set p_fy [expr {$p_fy - $dy * $d2 * .0000000005}]
		}
		set fx_t($node) [expr {$fx_t($node) + $p_fx}]
		set fy_t($node) [expr {$fy_t($node) + $p_fy}]
		set fx_t($other) [expr {$fx_t($other) - $p_fx}]
		set fy_t($other) [expr {$fy_t($other) - $p_fy}]
	    }

	    foreach link $link_list {
		set nodes [linkPeers $link]
		if { [getNodeCanvas [lindex $nodes 0]] != $curcanvas ||
		    [getNodeCanvas [lindex $nodes 1]] != $curcanvas ||
		    [getLinkMirror $link] != "" } {
		    continue
		}
		set peers [linkPeers $link]
		set coords0 [getNodeCoords [lindex $peers 0]]
		set coords1 [getNodeCoords [lindex $peers 1]]
		set o_x \
		    [expr {([lindex $coords0 0] + [lindex $coords1 0]) * .5}]
		set o_y \
		    [expr {([lindex $coords0 1] + [lindex $coords1 1]) * .5}]
		set dx [expr {$x - $o_x}]
		set dy [expr {$y - $o_y}]
		set d [expr {hypot($dx, $dy)}]
		set d2 [expr {$d * $d}]
		set fx_t($node) \
		    [expr {$fx_t($node) + 500.0 * $dx / ($d2 * $d + 100)}]
		set fy_t($node) \
		    [expr {$fy_t($node) + 500.0 * $dy / ($d2 * $d + 100)}]
	    }
	}

	foreach obj $objects {
	    set node [lindex [.c gettags $obj] 1]
	    if { [catch "set v_t($node)" v] } {
		set vx 0.0
		set vy 0.0
	    } else {
		set vx [lindex $v_t($node) 0]
		set vy [lindex $v_t($node) 1]
	    }
	    set vx [expr {$vx + 1000.0 * $fx_t($node) * $dt}]
	    set vy [expr {$vy + 1000.0 * $fy_t($node) * $dt}]
	    set dampk [expr {0.5 + ($vx * $vx + $vy * $vy) * 0.00001}]
	    set vx [expr {$vx * exp( - $dampk * $dt)}]
	    set vy [expr {$vy * exp( - $dampk * $dt)}]
	    set dx [expr {$vx * $dt}]
	    set dy [expr {$vy * $dt}]
	    set x [expr {$x_t($node) + $dx}]
	    set y [expr {$y_t($node) + $dy}]
	    set v_t($node) "$vx $vy"

	    setNodeCoords $node "$x $y"
	    set e_dx [expr {$dx * $zoom}]
	    set e_dy [expr {$dy * $zoom}]
	    .c move $obj $e_dx $e_dy
	    set img [.c find withtag "selectmark && $node"]
	    .c move $img $e_dx $e_dy
	    set img [.c find withtag "nodelabel && $node"]
	    .c move $img $e_dx $e_dy
	    set x [expr {[lindex [.c coords $img] 0] / $zoom}]
	    set y [expr {[lindex [.c coords $img] 1] / $zoom}]
	    setNodeLabelCoords $node "$x $y"
	    .c addtag need_redraw withtag "link && $node"
	}
	foreach link [.c find withtag "link && need_redraw"] {
	    redrawLink [lindex [.c gettags $link] 1]
	}
	.c dtag link need_redraw
	update
    }

    rearrange_off
    .bottom.mbuf config -text ""
}

proc rearrange_off { } {
    global autorearrange_enabled
    set autorearrange_enabled 0
    .menubar.tools entryconfigure "Auto rearrange all" -state normal
    .menubar.tools entryconfigure "Auto rearrange all" -indicatoron off
    .menubar.tools entryconfigure "Auto rearrange selected" -state normal
    .menubar.tools entryconfigure "Auto rearrange selected" -indicatoron off
}


#****f* editor.tcl/switchCanvas 
# NAME
#   switchCanvas -- switch canvas
# SYNOPSIS
#   switchCanvas $direction
# FUNCTION
#   This procedure switches the canvas in one of the defined 
#   directions (previous, next, first and last).
# INPUTS
#   * direction -- the direction of switching canvas. Can be: prev -- 
#   previus, next -- next, first -- first, last -- last.
#****
proc switchCanvas { direction } {
    global canvas_list curcanvas
    global sizex sizey

    set i [lsearch $canvas_list $curcanvas]
    switch -exact -- $direction {
    prev {
	incr i -1
	if { $i < 0 } {
	set curcanvas [lindex $canvas_list end]
	} else {
	set curcanvas [lindex $canvas_list $i]
	}
    }
    next {
	incr i
	if { $i >= [llength $canvas_list] } {
	set curcanvas [lindex $canvas_list 0]
	} else {
	set curcanvas [lindex $canvas_list $i]
	}
    }
    first {
	set curcanvas [lindex $canvas_list 0]
    }
    last {
	set curcanvas [lindex $canvas_list end]
    }
    }

    .hframe.t delete all
    set x 0
    foreach canvas $canvas_list {
    set text [.hframe.t create text 0 0 \
	-text "[getCanvasName $canvas]" -tags "text $canvas"]
    set ox [lindex [.hframe.t bbox $text] 2]
    set oy [lindex [.hframe.t bbox $text] 3]
    set tab [.hframe.t create polygon $x 0 [expr {$x + 7}] 18 \
	[expr {$x + 2 * $ox + 17}] 18 [expr {$x + 2 * $ox + 24}] 0 $x 0 \
	-fill gray -tags "tab $canvas"]
    set line [.hframe.t create line 0 0 $x 0 [expr {$x + 7}] 18 \
	[expr {$x + 2 * $ox + 17}] 18 [expr {$x + 2 * $ox + 24}] 0 999 0 \
	-fill #808080 -width 2 -tags "line $canvas"]
    .hframe.t coords $text [expr {$x + $ox + 12}] [expr {$oy + 2}]
    .hframe.t raise $text
    incr x [expr {2 * $ox + 17}]
    }
    incr x 7
    .hframe.t raise "$curcanvas"
    .hframe.t itemconfigure "tab && $curcanvas" -fill #e0e0e0
    .hframe.t configure -scrollregion "0 0 $x 18"
    update
    set width [lindex [.hframe.t configure -width] 4]
    set lborder [lindex [.hframe.t bbox "tab && $curcanvas"] 0]
    set rborder [lindex [.hframe.t bbox "tab && $curcanvas"] 2]
    set lmargin [expr {[lindex [.hframe.t xview] 0] * $x - 1}]
    set rmargin [expr {[lindex [.hframe.t xview] 1] * $x + 1}]
    if { $lborder < $lmargin } {
	.hframe.t xview moveto [expr {1.0 * ($lborder - 10) / $x}]
    }
    if { $rborder > $rmargin } {
	.hframe.t xview moveto [expr {1.0 * ($rborder - $width + 10) / $x}]
    }

    set sizex [lindex [getCanvasSize $curcanvas] 0]
    set sizey [lindex [getCanvasSize $curcanvas] 1]

    redrawAll
}

proc resizeCanvasPopup {} {
    global curcanvas

    set w .canvasSizeScaleDialog
    catch {destroy $w}
    toplevel $w

    wm transient $w .
    wm title $w "Canvas Size and Scale"

    frame $w.buttons
    pack $w.buttons -side bottom -fill x -pady 2m
    button $w.buttons.print -text "Apply" -command "resizeCanvasApply $w"
    button $w.buttons.cancel -text "Cancel" -command "destroy $w"
    pack $w.buttons.print $w.buttons.cancel -side left -expand 1

    set cursize [getCanvasSize $curcanvas]
    set x [lindex $cursize 0]
    set y [lindex $cursize 1]
    set scale [getCanvasScale $curcanvas]
    set refpt [getCanvasRefPoint $curcanvas]
    set refx [lindex $refpt 0]
    set refy [lindex $refpt 1]
    set latitude [lindex $refpt 2]
    set longitude [lindex $refpt 3]
    set altitude [lindex $refpt 4]


    labelframe $w.size -text "Size"
    frame $w.size.pixels
    pack $w.size $w.size.pixels -side top -padx 4 -pady 4 -fill x 
    spinbox $w.size.pixels.x -bg white -width 5
    $w.size.pixels.x insert 0 $x
    $w.size.pixels.x configure -from 300 -to 5000 -increment 2
    label $w.size.pixels.label -text "W x"
    spinbox $w.size.pixels.y -bg white -width 5
    $w.size.pixels.y insert 0 $y
    $w.size.pixels.y configure -from 300 -to 5000 -increment 2
    label $w.size.pixels.label2 -text "H pixels"
    pack $w.size.pixels.x $w.size.pixels.label $w.size.pixels.y \
        $w.size.pixels.label2 -side left -pady 2 -padx 2 -fill x
    
    frame $w.size.meters
    pack $w.size.meters -side top -padx 4 -pady 4 -fill x 
    spinbox $w.size.meters.x -bg white -width 7 
    $w.size.meters.x configure -from 300 -to 10000 -increment 100
    label $w.size.meters.label -text "x"
    spinbox $w.size.meters.y -bg white -width 7
    $w.size.meters.y configure -from 300 -to 10000 -increment 100
    label $w.size.meters.label2 -text "meters"
    pack $w.size.meters.x $w.size.meters.label $w.size.meters.y \
        $w.size.meters.label2 -side left -pady 2 -padx 2 -fill x

    labelframe $w.scale -text "Scale"
    frame $w.scale.ppm
    pack $w.scale $w.scale.ppm -side top -padx 4 -pady 4 -fill x
    label $w.scale.ppm.label -text "100 pixels ="
    entry $w.scale.ppm.metersper100 -bg white -width 10
    $w.scale.ppm.metersper100 insert 0 $scale
    label $w.scale.ppm.label2 -text "meters"
    pack $w.scale.ppm.label $w.scale.ppm.metersper100 \
        $w.scale.ppm.label2 -side left -pady 2 -padx 2 -fill x

    bind $w.size.pixels.x <Button> "syncSizeScale $w xp"
    bind $w.size.pixels.y <Button> "syncSizeScale $w yp"
    bind $w.size.pixels.x <FocusOut> "syncSizeScale $w xp"
    bind $w.size.pixels.y <FocusOut> "syncSizeScale $w yp"
    bind $w.size.meters.x <FocusOut> "syncSizeScale $w xm"
    bind $w.size.meters.y <FocusOut> "syncSizeScale $w ym"
    bind $w.size.meters.x <Button> "syncSizeScale $w xm"
    bind $w.size.meters.y <Button> "syncSizeScale $w ym"
    bind $w.scale.ppm.metersper100 <FocusOut> "syncSizeScale $w scale"
    #bind $w.scale.ppm.metersper100 <KeyPress> "syncSizeScale $w"

    labelframe $w.ref -text "Reference point"
    frame $w.ref.pt
    pack $w.ref $w.ref.pt -side top -padx 4 -pady 4 -fill x
    set hlp "The default reference point is (0,0), the upper-left corner of"
    set hlp "$hlp the canvas."
    label $w.ref.pt.help -text $hlp
    entry $w.ref.pt.x -bg white -width 4
    label $w.ref.pt.label -text "X,"
    entry $w.ref.pt.y -bg white -width 4
    label $w.ref.pt.label2 -text "Y ="
    entry $w.ref.pt.lat -bg white -width 12
    label $w.ref.pt.label3 -text "lat,"
    entry $w.ref.pt.long -bg white -width 12
    label $w.ref.pt.label4 -text "long"
    $w.ref.pt.x insert 0 $refx
    $w.ref.pt.y insert 0 $refy
    $w.ref.pt.lat insert 0 $latitude
    $w.ref.pt.long insert 0 $longitude
    pack $w.ref.pt.help -side top -anchor w
    pack $w.ref.pt.x $w.ref.pt.label $w.ref.pt.y $w.ref.pt.label2 \
    	$w.ref.pt.lat $w.ref.pt.label3 $w.ref.pt.long $w.ref.pt.label4 \
	-side left -pady 2 -padx 2 -fill x

    frame $w.ref.alt
    pack $w.ref.alt -side top -padx 6 -pady 6 -fill x
    label $w.ref.alt.label -text "Altitude:"
    entry $w.ref.alt.altitude -bg white -width 10
    label $w.ref.alt.label2 -text "meters"
    $w.ref.alt.altitude insert 0 $altitude
    pack $w.ref.alt.label $w.ref.alt.altitude $w.ref.alt.label2 -side left \
        -pady 2 -padx 2 -fill x


    global resize_canvas_save_default
    set resize_canvas_save_default 0
    frame $w.default
    checkbutton $w.default.save -text "Save as default" \
	-variable resize_canvas_save_default
    pack $w.default.save -side left -pady 2 -padx 2 -fill x
    pack $w.default -side bottom -fill x 

    # update the size in meters based on pixels
    syncSizeScale $w xp
}

# called when scale or size values change
proc syncSizeScale { w type } {
    set xp [$w.size.pixels.x get]
    set yp [$w.size.pixels.y get]
    set xm [$w.size.meters.x get]
    set ym [$w.size.meters.y get]
    set scale [$w.scale.ppm.metersper100 get]
    set newxp $xp
    set newyp $yp
    set newxm $xm
    set newym $ym

    # prevent some math errors
    if { ![string is double $scale] } { puts "invalid scale=$scale"; return }
    if { $scale == 0 } { puts "zero scale"; return }

    switch -exact -- $type {
	scale -
	xp -
	yp {
        # changing the scale or size in pixels updates the size in meters
	    set newxm [expr { $xp * $scale / 100.0 }]
	    set newym [expr { $yp * $scale / 100.0 }]
        }
	xm -
	ym {
        # changing the size in meters updates the size in pixels
	    set newxp [expr { round(100.0 * $xm / $scale) } ]
	    set newyp [expr { round(100.0 * $ym / $scale) } ]
	}
    }
    if {$xm != $newxm} {
	    $w.size.meters.x delete 0 end
	    $w.size.meters.x insert 0 $newxm
    }
    if {$ym != $newym} {
	    $w.size.meters.y delete 0 end
	    $w.size.meters.y insert 0 $newym
    }
    if {$xp != $newxp} {
        $w.size.pixels.x delete 0 end
        $w.size.pixels.x insert 0 $newxp
    }
    if {$yp != $newyp} {
        $w.size.pixels.y delete 0 end
        $w.size.pixels.y insert 0 $newyp
    }
}

proc resizeCanvasApply { w } {
    global curcanvas changed
    global g_prefs resize_canvas_save_default

    set x [$w.size.pixels.x get]
    set y [$w.size.pixels.y get]
    set scale [$w.scale.ppm.metersper100 get]
    # refpt x,y
    # refpt lat, long, alt
    set refx [$w.ref.pt.x get]
    set refy [$w.ref.pt.y get]
    set latitude [$w.ref.pt.lat get]
    set longitude [$w.ref.pt.long get]
    set altitude [$w.ref.alt.altitude get]
    set refpt [list $refx $refy $latitude $longitude $altitude]

    if { $resize_canvas_save_default } {
	array set g_prefs "gui_canvas_x $x gui_canvas_y $y"
	array set g_prefs "gui_canvas_scale $scale"
	array set g_prefs [list "gui_canvas_refpt" $refpt]
    }
    destroy $w
    if { "$x $y" != [getCanvasSize $curcanvas] || \
          $scale != [getCanvasScale $curcanvas] || \
          $refpt != [getCanvasRefPoint $curcanvas] } {
	set changed 1
    }
    setCanvasSize $curcanvas $x $y
    setCanvasScale $curcanvas $scale
    setCanvasRefPoint $curcanvas $refpt
    switchCanvas none
    updateUndoLog
}

#****f* editor.tcl/animate
# NAME
#   animate
# SYNOPSIS
#   animate
# FUNCTION
#   This function animates the selectbox. The animation looks 
#   different for edit and exec mode.
#****
proc animate {} {
    global animatephase oper_mode
    .c raise -cursor
    if { [catch { if { ![winfo exists .c] } { return } }] } {
	return ;# user has exited using the window manager
    }
    .c itemconfigure "selectmark || selectbox" -dashoffset $animatephase
    incr animatephase 2
    if { $animatephase == 100 } {
	set animatephase 0
    }

    if { $oper_mode == "edit" } {
	after 250 animate
    } else {
	after 1500 animate
    }
}


proc zoom { dir } {
    global zoom

    set stops ".25 .5 .75 1.0 1.5 2.0 4.0"
    # set i [lsearch $stops $zoom]
    set minzoom [lindex $stops 0]
    set maxzoom [lindex $stops [expr [llength $stops] - 1]]
    switch -exact -- $dir {
	"down" {
	    if {$zoom > $maxzoom} {
		set zoom $maxzoom
	    } elseif {$zoom < $minzoom} {
		; # leave it unchanged
	    } else {
		set newzoom $minzoom
		foreach z $stops {
		    if {$zoom <= $z} {
			break
		    } else {
			set newzoom $z
		    }
		}
		set zoom $newzoom 
	    }
	    redrawAll
	}
	"up" {
	    if {$zoom < $minzoom} {
		set zoom $minzoom
	    } elseif {$zoom > $maxzoom} {
		; # leave it unchanged
	    } else {
		foreach z [lrange $stops 1 end] {
		    set newzoom $z
		    if {$zoom < $z} {
			break
		    }
		}
		set zoom $newzoom 
	    }
	    redrawAll
	}
	default {
	    if { $i < [expr [llength $stops] - 1] } {
		set zoom [lindex $stops [expr $i + 1]]
		redrawAll
	    }
	}
    }
}


#****h* editor.tcl/double1onGrid
# NAME
#  double1onGrid.tcl -- called on Double-1 click on grid (bind command)
# SYNOPSIS
#  double1onGrid $c %x %y
# FUNCTION
#  As grid is layered above annotations this procedure is used to find 
#  annotation object closest to cursor
#****

proc double1onGrid { c x y } {
    set obj [$c find closest $x $y]
    set tags [$c gettags $obj]
    set node [lindex $tags 1]
    if {[lsearch $tags grid] != -1 || [lsearch $tags background] != -1} {
	return
    }
    # Is this really necessary?
    set coords [getNodeCoords $node] 
    set x1 [lindex $coords 0]
    set y1 [lindex $coords 1]
    set x2 [lindex $coords 2]
    set y2 [lindex $coords 3]
    if {$x < $x1 || $x > $x2 || $y < $y1 || $y > $y2} {
	# cursor is not ON the closest object
	return
    } else {
	annotationConfig $c $node
    }
}


proc setZoomApply { w } {
    global zoom changed

    set newzoom [expr [$w.e1 get] / 100.0]
    if { $newzoom != $zoom } {
	set zoom $newzoom
	redrawAll
    }
    destroy $w
}

proc selectZoom { x y } {
    global curcanvas
    global zoom

    set stops ".25 .5 .75 1.0 1.5 2.0 4.0"

    set w .entry1
    catch {destroy $w}
    toplevel $w -takefocus 1

    if { $x == 0 && $y == 0 } {
	set screen [wm maxsize .]
	set x [expr {[lindex $screen 0] / 2}]
	set y [expr {[lindex $screen 1] / 2}]
    } else {
	set x [expr {$x + 10}]
	set y [expr {$y - 90}]
    }
    wm geometry $w +$x+$y
    wm title $w "Select zoom %"
    wm iconname $w "Select zoom %"

    frame $w.buttons
    pack $w.buttons -side bottom -fill x -pady 2m
    button $w.buttons.print -text "Apply" -command "setZoomApply $w"
    button $w.buttons.cancel -text "Cancel" -command "destroy $w"
    pack $w.buttons.print $w.buttons.cancel -side left -expand 1

    bind $w <Key-Escape> "destroy $w"
    bind $w <Key-Return> "setZoomApply $w"

    entry $w.e1 -bg white
    $w.e1 insert 0 [expr {int($zoom * 100)}]
    pack $w.e1 -side top -pady 5 -padx 10 -fill x

    update
    focus $w.e1
    grab $w
}


# configure remote servers
# popup a dialog box for editing the remote server list
# results are stored in servers.conf file
proc configRemoteServers {} {
    global exec_servers last_server_selected
    global plugin_img_add plugin_img_save plugin_img_del
    global DEFAULT_API_PORT

    set wi .remoteConfig
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 0 0
    wm title $wi "CORE emulation servers"

    set last_server_selected -1

    # list of servers
    frame $wi.s -borderwidth 4
    listbox $wi.s.servers -selectmode single -width 60 \
	-yscrollcommand "$wi.s.servers_scroll set" -exportselection 0
    scrollbar $wi.s.servers_scroll -command "$wi.s.servers yview" 
    pack $wi.s.servers $wi.s.servers_scroll -fill both -side left
    pack $wi.s -fill both -side top
    # add scrollbar

    bind $wi.s.servers <<ListboxSelect>> "selectRemoteServer $wi"

    # populate the list
    foreach server [lsort -dictionary [array names exec_servers]] {
	$wi.s.servers insert end $server
    }

    # controls for editing entries
    labelframe $wi.c -text "Server configuration"
    frame $wi.c.c -borderwidth 4
    label $wi.c.c.namelab -text "Name"
    entry $wi.c.c.name -bg white -width 15
    bind $wi.c.c.name <KeyPress> "$wi.c.c.add configure -state normal"
    label $wi.c.c.iplab -text "IP"
    entry $wi.c.c.ip -bg white -width 10
    label $wi.c.c.portlab -text "port"
    entry $wi.c.c.port -bg white -width 5
    pack $wi.c.c.namelab $wi.c.c.name $wi.c.c.iplab $wi.c.c.ip -side left
    pack $wi.c.c.portlab $wi.c.c.port -side left
    pack $wi.c.c -fill x -side top
    $wi.c.c.port insert 0 $DEFAULT_API_PORT

    button $wi.c.c.add -image $plugin_img_add \
	-command "configRemoteServersHelper $wi 1"
    button $wi.c.c.mod -image $plugin_img_save \
	-command "configRemoteServersHelper $wi 2" 
    button $wi.c.c.del -image $plugin_img_del \
	-command "configRemoteServersHelper $wi 3" 
    pack $wi.c.c.add $wi.c.c.mod $wi.c.c.del -side left
    pack $wi.c -fill x -side top
    # assignment buttons
    labelframe $wi.a -borderwidth 4 -text "Assign selected server to:"
    button $wi.a.applyall -text "all nodes" -command {
	global node_list last_server_selected
	set wi .remoteConfig
	if { $last_server_selected < 0 } { return }
	set server [$wi.s.servers get $last_server_selected]
	foreach node $node_list { setNodeLocation $node $server }
	$wi.b.cancel configure -text "Close"
	highlightAssignedServers $wi
	redrawAll
    }
    button $wi.a.applysel -text "selected nodes" -command {
	global last_server_selected
	set wi .remoteConfig
	if { $last_server_selected < 0 } { return }
	set server [$wi.s.servers get $last_server_selected]
	set items [.c find withtag "node && selected"]
	foreach item $items {
	    set node [lindex [.c gettags $item] 1]
	    setNodeLocation $node $server
	}
	$wi.b.cancel configure -text "Close"
	highlightAssignedServers $wi
	redrawAll
    }
    label $wi.a.lab -text "Assigned servers are shown in blue."
    pack $wi.a.applyall $wi.a.applysel $wi.a.lab -side left
    pack $wi.a -fill x -side top
    highlightAssignedServers $wi

    # apply/cancel buttons
    frame $wi.b -borderwidth 4
    button $wi.b.apply -text "Apply" -command \
    	"writeServersConf; redrawAll; destroy $wi" 
    button $wi.b.cancel -text "Cancel" -command "loadServersConf;  destroy $wi"
    pack $wi.b.cancel $wi.b.apply -side right
    pack $wi.b -side bottom
    focus $wi.b.apply

    after 100 {	catch { grab .remoteConfig } }
}

# add/modify/remove server in list
proc configRemoteServersHelper { wi action } {
    global exec_servers last_server_selected
    set index end
    set sock -1

    # delete from list, array
    if { $action > 1 } { ;# delete/modify
	if { $last_server_selected < 0 } { return }
	set server [$wi.s.servers get $last_server_selected]
	$wi.s.servers delete $last_server_selected
	set sock [lindex $exec_servers($server) 2]
	array unset exec_servers $server
	if { $action == 3 } {
	    $wi.c.c.add configure -state normal
	    $wi.s.servers selection set $index
	    set last_server_selected $index
	    return
	}
	set index $last_server_selected
    }

    # update the list
    set newserver [$wi.c.c.name get]
    $wi.s.servers insert $index $newserver
    # update the array
    set conf [list [$wi.c.c.ip get] [$wi.c.c.port get]] 
    array set exec_servers [list $newserver $conf]
    $wi.s.servers selection set $index
    set last_server_selected $index
    $wi.c.c.add configure -state disabled
}

# connects the servers listbox with entry elements
proc selectRemoteServer { wi } {
    global exec_servers last_server_selected
    set selected [$wi.s.servers curselection]

    # clear entries
    $wi.c.c.name delete 0 end; $wi.c.c.ip delete 0 end;
    $wi.c.c.port delete 0 end 

    set server [$wi.s.servers get $selected]
    if { ![info exists exec_servers($server)] } { return }
    $wi.c.c.add configure -state disabled
    set last_server_selected $selected

    # insert entries from array
    $wi.c.c.name insert 0 $server
    $wi.c.c.ip   insert 0 [lindex $exec_servers($server) 0]
    $wi.c.c.port insert 0 [lindex $exec_servers($server) 1]
}

# helper to highlight servers that have been assigned
proc highlightAssignedServers { wi } {
    set servers [getAssignedRemoteServers]
    set n [$wi.s.servers size]
    for { set i 0 } { $i < $n } { incr i } {
        set s [$wi.s.servers get $i]
	set color blue
	if { [lsearch -exact $servers $s] < 0 } { set color black }
	$wi.s.servers itemconfigure $i -foreground $color
    }
}

# Boeing: custom image dialog box
proc popupCustomImage { node } {
    global CORE_DATA_DIR

    set wi .customimagedialog
    catch {destroy $wi}
    toplevel $wi -takefocus 1
    wm transient $wi .popup 
    wm resizable $wi 0 0
    wm title $wi "[getNodeName $node] ($node) image"
    grab $wi

    frame $wi.ftop -borderwidth 4
    label $wi.ftop.filelabel -text "Image file:"
    entry $wi.ftop.filename -bg white -width 32
    set cimg [getCustomImage $node]
    $wi.ftop.filename insert 0 $cimg

    global configwin
    set configwin $wi
    button $wi.ftop.filebtn -text "..." -command { 
	global configwin g_imageFileTypes
	set f [tk_getOpenFile -filetypes $g_imageFileTypes \
		-initialdir "$CORE_DATA_DIR/icons/normal"]
	if { $f != "" } { 
	    set node [string trim [lindex [wm title $configwin] 1] "()"]
	    $configwin.ftop.filename delete 0 end
	    $configwin.ftop.filename insert 0 $f
            popupCustomImagePreview $configwin $node
	}
    }
    pack $wi.ftop.filebtn $wi.ftop.filename $wi.ftop.filelabel \
	-side right -padx 4 -pady 4
    pack  $wi.ftop -side top

    frame $wi.fmid -borderwidth 4
    canvas $wi.fmid.c -width 300 -height 100
    pack $wi.fmid.c -side top -padx 4 -pady 4
    pack $wi.fmid -side top


    frame $wi.fbot -borderwidth 4
    button $wi.fbot.apply -text "Apply" -command "customImageApply $wi $node"
    set msg "Select nodes to apply custom image to:"
    set cmd "customImageApplyMultiple $wi"
    button $wi.fbot.applym -text "Apply to multiple..." \
	-command "popupSelectNodes \"$msg\" $node {$cmd}"
    button $wi.fbot.cancel -text "Cancel" -command "destroy $wi"
    pack $wi.fbot.cancel $wi.fbot.applym $wi.fbot.apply \
	-side right -padx 4 -pady 4
    pack  $wi.fbot -side bottom

    popupCustomImagePreview $wi $node
}

proc popupCustomImagePreview { wi node } {
    set coords_save [getNodeCoords $node]
    set labelcoords_save [getNodeLabelCoords $node]
    set img_save [getCustomImage $node]
    set img_new [$wi.ftop.filename get]

    setNodeCoords $node "150 50"
    setNodeLabelCoords $node "150 78"
    if { $img_save != $img_new } { setCustomImage $node $img_new } 
    $wi.fmid.c delete all
    drawNode $wi.fmid.c $node

    setNodeCoords $node $coords_save
    setNodeLabelCoords $node $labelcoords_save
    if { $img_save != $img_new } { setCustomImage $node $img_save }
}

# Boeing: helper for custom image apply button
proc customImageApply { wi node } {
    global changed
    setCustomImage $node [$wi.ftop.filename get]
    set changed 1
    # update the custom image button in the parent dialog
    set img [getNodeImage $node]
    .popup.ftop.img configure -image $img
    destroy $wi
}

proc customImageApplyMultiple { wi nodes } {
    global changed
    set imgfile [$wi.ftop.filename get]

    foreach node $nodes {
	setCustomImage $node $imgfile
	set changed 1
    }
    destroy $wi
}


# Boeing: create several scaled copies of an image for use with each zoomlevel
proc createScaledImages { img } {
    global $img
    set w [image width [set $img]]
    set h [image height [set $img]]
    # we skip 75% and 150% since resulting images are the same (due to int())
    foreach size {.25 .5 1.0 2.0 4.0} {
	# image will be globally accessible
	global $img$size
	# create empty photo object
	set $img$size [image create photo]
	# copy a scaled version
    	if { $size > 1.0 } {
		[set $img$size] copy [set $img] -zoom [expr { int($size) } ]
	} else {
		[set $img$size] copy [set $img] -subsample \
			[expr { int($w / ($w * $size)) }] \
			[expr { int($h / ($h * $size)) }]
	}
    }
}

# Boeing: clear marker drawing
proc clearMarker { } {
    .c delete -withtags marker
}

# Boeing: show or hide the marker options palette
proc markerOptions { show } {
    global CORE_DATA_DIR markersize markercolor

    catch { destroy .left.markeropt }
    if { $show == "off" } { return }

    frame .left.markeropt
    # eraser
    set img [image create photo -file $CORE_DATA_DIR/icons/tiny/eraser.gif]
    button .left.markeropt.eraser -image $img \
	-relief flat -command clearMarker
    pack .left.markeropt.eraser -side top -pady 8
    # marker sizes
    canvas .left.markeropt.sizes -height 40 -width 32
    pack .left.markeropt.sizes -side top
    bind .left.markeropt.sizes <1> "markerSize %x %y"
    drawMarkerSizes .left.markeropt.sizes [expr $markersize / 5]
    # color selection buttons
    set img [image create photo -file $CORE_DATA_DIR/icons/tiny/blank.gif]
    foreach clr { black red yellow blue green } {
	radiobutton .left.markeropt.$clr -indicatoron 0 -image $img \
		-variable markercolor -value $clr -width 16 -height 16 \
		-selectcolor $clr -highlightbackground $clr -background $clr \
		-highlightcolor $clr -activebackground $clr
	pack .left.markeropt.$clr -side top
    }
    pack .left.markeropt -side bottom
}

# Boeing: draw the marker sizes tool on a small canvas
proc drawMarkerSizes { c sel } {
	# determine the coordinates of the selection box based on value of sel
	if       { $sel == 1 } { set coords {0 0 16 16}   
	} elseif { $sel == 2 } { set coords {16 0 32 16}  
	} elseif { $sel == 3 } { set coords {0 16 16 32}  
	} else { set coords {16 16 32 32} }
	# draw the selection box
	$c create rectangle $coords -fill gray -tag square -width 0
	# draw each circle
	$c create oval 8 8 8 8 -width 2 -fill blue -tag circle
	$c create oval 24 8 24 8 -width 5 -fill black -tag circle
	$c create oval 8 24 8 24 -width 10 -fill black -tag circl
	$c create oval 24 24 24 24 -width 15 -fill black -tag circle
}

# Boeing: receive click from the marker sizes tool
proc markerSize { x y } {
    global markersize
    # determine which circle was selected, 1-4
    if { $x > 16 } {
    	if { $y > 16 } { set sel 4
	} else { set sel 2 }
    } else {
    	if { $y > 16 } { set sel 3
	} else { set sel 1 }
    }
    set markersize [expr {$sel * 5}]
    # redraw selection tool
    .left.markeropt.sizes delete -withtag "square || circle"
    drawMarkerSizes .left.markeropt.sizes $sel
}

# Boeing: set canvas wallpaper 
proc wallpaperPopup {} {
    global curcanvas

    set w .wallpaperDlg
    catch {destroy $w}
    toplevel $w
   
    wm transient $w .
    wm title $w "Set Canvas Wallpaper"
    grab $w
    
    # preview
    canvas $w.preview -background white -relief sunken -width 200 -height 100 \
    	-borderwidth 1
    pack $w.preview -side top -padx 10 -pady 10
    $w.preview create text 100 50 -fill gray -text "(image preview)" \
    	-justify center -tag "wallpaper"


    # file
    frame $w.f
    label $w.f.lab -text "Image filename:" -justify left
    entry $w.f.file

    # file browse button
    global configwin
    set configwin $w
    button $w.f.filebtn -text "..." -command { 
	global configwin showGrid adjustCanvas fileDialogBox_initial
	global g_imageFileTypes
	# use default conf file path upon first run
	if { $fileDialogBox_initial == 0} {
	    set fileDialogBox_initial 1
	    set dir $g_prefs(default_conf_path)
	    set f [tk_getOpenFile -filetypes $g_imageFileTypes -initialdir $dir]
	} else {
	    set f [tk_getOpenFile -filetypes $g_imageFileTypes]
	}
	if { $f != "" } {
	    $configwin.f.file delete 0 end
	    $configwin.f.file insert 0 $f
	    set showGrid 0
	    set adjustCanvas 1
	}
	wallpaperPopupPreview $configwin
	raise $configwin
    }

    # clear wallpaper button
    button $w.f.clear -text "clear" -command { 
		global configwin wallpaperStyle
		$configwin.f.file delete 0 end
		$configwin.preview delete "wallpaper"
    		$configwin.preview create text 100 50 -fill gray \
			-text "(image preview)" -justify center -tag "wallpaper"
		set wallpaperStyle upperleft
		raise $configwin
	}

    set currfile [lindex [getCanvasWallpaper $curcanvas] 0]
    set currstyle [lindex [getCanvasWallpaper $curcanvas] 1]
    pack $w.f.lab -side top -anchor w
    pack $w.f.file $w.f.filebtn $w.f.clear -side left -fill x
    pack $w.f -side top
    $w.f.file insert 0 $currfile

    # wallpaper style
    frame $w.style
    global wallpaperStyle
    if {$currstyle == "" } {
	set wallpaperStyle upperleft
    } else {
	set wallpaperStyle $currstyle
    }
    radiobutton $w.style.lft -text "upper-left" -variable wallpaperStyle \
    	-value upperleft -command "wallpaperPopupPreview $w"
    radiobutton $w.style.ctr -text "centered" -variable wallpaperStyle \
    	-value centered -command "wallpaperPopupPreview $w"
    radiobutton $w.style.scl -text "scaled" -variable wallpaperStyle \
    	-value scaled -command "wallpaperPopupPreview $w"
    radiobutton $w.style.til -text "tiled" -variable wallpaperStyle \
    	-value tiled -command "wallpaperPopupPreview $w"

    pack $w.style.lft $w.style.ctr -side left
    pack $w.style.scl $w.style.til -side left
    pack $w.style -side top

    # options
    frame $w.opts
    checkbutton $w.opts.showgrid -text "Show grid" -variable showGrid
    checkbutton $w.opts.adjcanvas \
    	-text "Adjust canvas size to image dimensions" \
    	-variable adjustCanvas
    pack $w.opts.showgrid $w.opts.adjcanvas -side top -anchor w
    pack $w.opts -side top


    # buttons
    frame $w.btns
    button $w.btns.apply -text "Apply" -command { 
		global configwin wallpaperStyle curcanvas adjustCanvas
		set f [$configwin.f.file get]
		if {$adjustCanvas} { 
			wallpaperAdjustCanvas $curcanvas $f $wallpaperStyle 
		}
		setCanvasWallpaper $curcanvas $f $wallpaperStyle
		redrawAll
		destroy $configwin
	}
    button $w.btns.cancel -text "Cancel" -command "destroy $w"
    pack $w.btns.apply $w.btns.cancel -side left -fill x
    pack $w.btns -side top

    if {$currfile != ""} {
	wallpaperPopupPreview $w
    }
    raise $w
}

# adjust wallpaper dialog preview canvas
proc wallpaperPopupPreview { w } {
    global wallpaperStyle

    set f [$w.f.file get]
    if { $f == "" } {
    	return
    }
    drawWallpaper $w.preview $f $wallpaperStyle
}

# auto-adjust the canvas in an intelligent fashion
proc wallpaperAdjustCanvas { c f style } {
    set cx [lindex [getCanvasSize $c] 0]
    set cy [lindex [getCanvasSize $c] 1]

    if {$f==""} { return }
    set img [image create photo -file $f]
    set imgx [image width $img]
    set imgy [image height $img]

    #puts -nonewline  "wallpaperAdjustCanvas img($imgx, $imgy) $cx, $cy -> "

    # For scaled and tiled styles, expand canvas x and y to a multiple of 
    # imgx, imgy for better stretching. If the image is larger than the canvas,
    # just increase the canvas size to accomodate it.
    if {$style == "scaled" || $style == "tiled"} {
    	if {$cx > $imgx} {
	    if { [expr { $cx % $imgx }] > 0} {
		set cx [expr { (1+int($cx/$imgx)) * $imgx }]
	    }
	} elseif { $cx < $imgx } {
	    set cx $imgx
	}
    	if {$cy > $imgy} {
	    if { [expr { $cy % $imgy }] > 0} {
	        # there is a fractional part, round up
		set cy [expr { (1+int($cy/$imgy)) * $imgy }]
	    }
	} elseif { $cy < $imgy } {
	    set cy $imgy
	}
    # For topleft and centered, resize the canvas to fit the image
    # if the size difference isn't too large
    } elseif { $style == "topleft" || $style == "centered" } {
        if { [expr {abs($cx - $imgx)} ] < 300 } {
	    set cx $imgx
	}
        if { [expr {abs($cy - $imgy)} ] < 300 } {
	    set cy $imgy
	}
    }

    #puts "$cx, $cy"
    setCanvasSize $c $cx $cy
    switchCanvas none
    updateUndoLog
}

# draw the image from filename f onto the wallpaper c in the specified style
proc drawWallpaper { c f style } {
    global $c

    # clear the canvas
    $c delete "wallpaper"
    if { $f == "" } {
        return
    }

    if { $c == ".wallpaperDlg.preview" } {
	set cx [expr [$c cget -width]-2]
	set cy [expr [$c cget -height]-2]
    } else {
    	global curcanvas
	# subtract 2 for canvas border
	set cx [expr [lindex [getCanvasSize $curcanvas] 0]-2]
	set cy [expr [lindex [getCanvasSize $curcanvas] 1]-2]
    }
    set f [absPathname $f]
    if { [ catch { set img [image create photo -file $f] } e ] } {
	puts "Error: couldn't open wallpaper file $f: $e"
	return
    }
    set imgx [image width $img]
    set imgy [image height $img]

    # scaled: grow/shrink the image to fit the canvas size
    if { $style == "scaled" } {
    	set img2 [image create photo -width $cx -height $cy]
	# grow image
	if { $cx >= $imgx || $cy > $imgy } {
	    set x [expr 1+($cx / $imgx)]
	    set y [expr 1+($cy / $imgy)] 
	    $img2 copy $img -zoom $x $y
	# shrink image
	} else {
	    $img2 copy $img -subsample \
		[expr { int($imgx / $cx) }] \
		[expr { int($imgy / $cy) }] 
	}
        $c create image [expr 1+$cx/2] [expr 1+$cy/2] -image $img2 \
		-tags "background wallpaper"
    # centered: center of image at center of canvas
    } elseif { $style == "centered" } {
        $c create image [expr $cx/2] [expr $cy/2] -image $img \
			-tags "background wallpaper"
    # tiled: repeat image several times
    } elseif { $style == "tiled" } {
	for {set y [expr $imgy/2]} {$y < $cy} {incr y $imgy} {
	    for {set x [expr $imgx/2]} {$x < $cx} {incr x $imgx} {
		$c create image $x $y -image $img -tags "background wallpaper"
	    }
	}
    # upper-left: top left corner of image at 0,0
    } else {
    	set img2 [image create photo -width $cx -height $cy]
	$img2 copy $img -shrink
        $c create image [expr 1+$cx/2] [expr 1+$cy/2] -image $img2 \
		-tags "background wallpaper"
    }

    raiseAll $c
    
}

# helper for close/cancel buttons
proc popdownConfig { w } {
    global changed
    if { $changed == 1 } {
	redrawAll
	updateUndoLog
    }
    destroy $w
}

# helper for rj45 config dialog
proc rj45ifclist { wi node wasclicked } {
    # user has double-clicked an entry
    if { $wasclicked } {
    	set selected [$wi.ftop.ifc.ifc_list curselection]
	set chosen [$wi.ftop.ifc.ifc_list get $selected]
	set ifname [lindex [split $chosen] 0]
	$wi.ftop.name delete 0 end
	$wi.ftop.name insert 0 $ifname
	return
    }

    # build a list of interfaces
    frame $wi.ftop.ifc
    listbox $wi.ftop.ifc.ifc_list -height 4 -width 30 \
	-selectmode browse -yscrollcommand "$wi.ftop.ifc.ifc_scroll set"
    scrollbar $wi.ftop.ifc.ifc_scroll \
	-command "$wi.ftop.ifc.ifc_list yview" 

    set ifname ""
    set ifip ""
    # this handles differences between Linux and FreeBSD ifconfig
    foreach line [split [nexec localnode ifconfig -a] "\n"] {
	set char [string index $line 0]
	if { $char != " " && $char != "	" } {
	    if { $ifname != "" } {
		$wi.ftop.ifc.ifc_list insert end "$ifname ($ifip)"
		set ifname ""
		set ifip ""
	    }
	    if { [string match "*Link encap:*" $line] } {
	        set ifname [lindex [split $line " "] 0]
	    } else {
		set ifname [lindex [split $line :] 0]
	    }
	} elseif { [string match "*inet addr:*" $line] } {
	    set inetidx [string first i $line]
	    set t [lindex [split [string range $line $inetidx end]] 1]
	    set ifip [lindex [split $t ":"] 1]
	} elseif { [string match "	inet *" $line] } {
	    set ifip [lindex [split $line] 2]
	}
    }
    if { $ifname != "" } {
	$wi.ftop.ifc.ifc_list insert end "$ifname ($ifip)"
    }

    bind $wi.ftop.ifc.ifc_list <Double-1> "rj45ifclist $wi $node 1"
    bind $wi.ftop.ifc.ifc_list <<ListboxSelect>> "rj45ifclist $wi $node 1"
    pack $wi.ftop.ifc.ifc_list $wi.ftop.ifc.ifc_scroll -side left -fill y
    pack $wi.ftop.ifc -side bottom -padx 4 -pady 4
}

# link preset values - bandwidth delay ber duplicate
array set link_presets {
	"unlimited" { 0 0 0 0 0 }
	"1000M" { 1000000000 100 0 0.0 0.0}
	"100M"  {  100000000 110 0 0.0 0.0}
	"10M"   {   10000000 160 0 0.0 0.0}
	"512kbps" { 512000 50000 0 0.0 0.0}
	"256kbps" { 256000 75000 0 0.0 0.0}
	"64kbps"  {  64000 80000 0 0.0 0.0}
}

# link presets
proc linkPresets { wi linkpreMenu cmd } {
    global link_presets link_preset_val
    global g_link_config_uni_state

    if { $cmd == "init" } { ;# populate the list with presets and exit
    	$linkpreMenu delete 0
    	foreach p [lsort [array names link_presets]] {
	    $linkpreMenu add radiobutton -label $p -value $p \
	    	-variable link_preset_val \
	    	-command "linkPresets $wi $linkpreMenu set"
	}
	return
    }

    # set the selected link presets
    set params $link_presets($link_preset_val)
    $wi.bandwidth.value delete 0 end
    $wi.delay.value delete 0 end
    $wi.jitter.value delete 0 end
    $wi.ber.value delete 0 end
    $wi.dup.value delete 0 end
    $wi.bandwidth.value insert 0 [lindex $params 0]
    $wi.delay.value insert 0 [lindex $params 1]
    $wi.jitter.value insert 0 [lindex $params 2]
    $wi.ber.value insert 0 [lindex $params 3]
    $wi.dup.value insert 0 [lindex $params 4]
    if { $g_link_config_uni_state == "uni" } {
	$wi.bandwidth.value2 delete 0 end
	$wi.delay.value2 delete 0 end
	$wi.jitter.value2 delete 0 end
	$wi.ber.value2 delete 0 end
	$wi.dup.value2 delete 0 end
	$wi.bandwidth.value2 insert 0 [lindex $params 0]
	$wi.delay.value2 insert 0 [lindex $params 1]
	$wi.jitter.value2 insert 0 [lindex $params 2]
	$wi.ber.value2 insert 0 [lindex $params 3]
	$wi.dup.value2 insert 0 [lindex $params 4]
    }
}

set last_nodeHighlights [clock clicks -milliseconds]
proc nodeHighlights { c node onoff color } {
    global execMode zoom
    if { $execMode != "interactive"} { return } ; # batch mode
    #puts "nodeHighlights $c $node $onoff $color"
    $c delete -withtags "highlight && $node"
    if { $onoff == "off" } {
	if { $node == "" } { ;# remove all highlights
	    $c delete -withtags highlight
	}
	return
    } elseif { $onoff == "single" } {
	# this was called from nodeEnter binding, perform rate limiting
	set now [clock clicks -milliseconds]
	global last_nodeHighlights
	if { [expr $now - $last_nodeHighlights] < 100 } { return }
	set last_nodeHighlights $now
    }

    # this could be improved to draw hidden items if not on current canvas,
    # then properly unhide/hide when switching canvases
    global curcanvas
    if { [getNodeCanvas $node] != $curcanvas } { return }

    set coords [getNodeCoords $node]
    set x [lindex $coords 0]
    set y [lindex $coords 1]

    set wd 4; # line width
    set d 35; # box size
    set w [expr {50 * $zoom}]; # corner size
    set x0 [expr {($x - $d) * $zoom}]
    set y0 [expr {($y - $d) * $zoom}]
    set x1 [expr {($x + $d) * $zoom}]
    set y1 [expr {($y + $d) * $zoom}]
    # upper left
    $c create line $x0 $y0 [expr {$x1-$w}] $y0 \
		-tags "marker highlight $node" -width $wd -fill $color
    $c create line $x0 $y0 $x0 [expr {$y1-$w}] \
		-tags "marker highlight $node" -width $wd -fill $color
    # upper right
    $c create line $x1 $y0 [expr {$x0+$w}] $y0 \
		-tags "marker highlight $node" -width $wd -fill $color
    $c create line $x1 $y0 $x1 [expr {$y1-$w}] \
		-tags "marker highlight $node" -width $wd -fill $color
    # lower left
    $c create line $x0 $y1 [expr {$x1-$w}] $y1 \
		-tags "marker highlight $node" -width $wd -fill $color
    $c create line $x0 $y1 $x0 [expr {$y0+$w}] \
		-tags "marker highlight $node" -width $wd -fill $color
    # lower right
    $c create line $x1 $y1 [expr {$x0+$w}] $y1 \
		-tags "marker highlight $node" -width $wd -fill $color
    $c create line $x1 $y1 $x1 [expr {$y0+$w}] \
		-tags "marker highlight $node" -width $wd -fill $color
}

# show the hook scripts dialog for editing session hooks
proc popupHooksConfig {} {
    global plugin_img_add plugin_img_edit plugin_img_del
    global oper_mode

    set wi .hooks
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 0 0
    wm title $wi "CORE Session Hooks"

    labelframe $wi.f -text "Hooks"
    listbox $wi.f.hooks -selectmode extended -width 50 -exportselection 0 \
	-yscrollcommand "$wi.f.hooks_scroll set" -height 5
    scrollbar $wi.f.hooks_scroll -command "$wi.f.hooks yview"
    pack $wi.f.hooks $wi.f.hooks_scroll -pady 4 -fill both -side left
    pack $wi.f -padx 4 -pady 4 -fill both -side top
    bind $wi.f.hooks <Double-Button-1> "hooksHelper $wi edit"

    frame $wi.bbar
    button $wi.bbar.new -image $plugin_img_add -command "hooksHelper $wi new"
    button $wi.bbar.save -image $plugin_img_edit \
	-command "hooksHelper $wi edit"
    button $wi.bbar.del -image $plugin_img_del -command "hooksHelper $wi del"
    label $wi.bbar.help -text "Press the new button to create a hook script."

    pack $wi.bbar.new $wi.bbar.save $wi.bbar.del -side left
    pack $wi.bbar.help -padx 8 -side left
    pack $wi.bbar -padx 4 -pady 4 -fill both -side top

    frame $wi.b -borderwidth 4
    button $wi.b.close -text "Close" -command "destroy $wi"
    pack $wi.b.close -side bottom
    pack $wi.b -side bottom

    refreshHooksList $wi
}

proc hooksHelper { wi cmd } {
    global g_hook_scripts
    set selected [lindex [$wi.f.hooks curselection] 0]
    set name ""
    if { $selected != "" } { set name [$wi.f.hooks get $selected] }
    # start/stop/delete selected
    if { $cmd == "del" } {
	removeHook $name
	refreshHooksList $wi
	return
    }

    if { $cmd == "edit" && $name == "" } { return }
    if { $cmd == "new" } {
	set name ""
    }
    popupHookScript $name
}

proc refreshHooksList { wi } {
    global g_hook_scripts

    $wi.f.hooks delete 0 end
    if { ![info exists g_hook_scripts] } { set g_hook_scripts "" }

    foreach hook $g_hook_scripts {
	set name [lindex $hook 0]
        $wi.f.hooks insert end $name
    }
}

proc removeHook { name } {
    global g_hook_scripts
    for { set i 0 } { $i < [llength $g_hook_scripts] } { incr i } {
	set flow [lindex $g_hook_scripts $i]
	if { [lindex $flow 0] == $name } {
	    set g_hook_scripts [lreplace $g_hook_scripts $i $i]
	    return $i
	}
    }
    return end
}

# show the script config dialog, for specifying an optional global session
# startup script that is run on the host after the emulation has been started
proc popupHookScript { name } {
    global g_hook_scripts CORE_STATES plugin_img_open plugin_img_save
    set wi .scriptConfig

    catch {destroy $wi}

    if { ![info exists g_hook_scripts] } { set g_hook_scripts "" }
    toplevel $wi
    wm transient $wi .hooks
    wm resizable $wi 1 1
    wm title $wi "CORE Hook Script"

    # help text at top
    ttk::frame $wi.top
    set helptext "This is an optional script that is run"
    set helptext "$helptext on the host when the\n emulation reaches the"
    set helptext "$helptext specified state. It is saved with the config file."
    ttk::label $wi.top.help -text $helptext
    pack $wi.top.help -side top -fill both -expand true
    pack $wi.top -padx 4 -pady 4 -side top

    ttk::frame $wi.n
    ttk::label $wi.n.lab -text "Hook script name:"
    ttk::entry $wi.n.name -width 35
    foreach c [list open save] {
	ttk::button $wi.n.$c -image [set plugin_img_$c] -command \
	    "genericOpenSaveButtonPress $c $wi.mid.script $wi.n.name"
    }
    ttk::combobox $wi.n.state -width 15 -state readonly -exportselection 0 \
	-values $CORE_STATES 
    pack $wi.n.lab $wi.n.name -padx 4 -pady 4 -side left
    pack $wi.n.open $wi.n.save -pady 4 -side left
    pack $wi.n.state -padx 4 -pady 4 -side left
    pack $wi.n -padx 4 -pady 4 -side top -anchor w

    bind $wi.n.state <<ComboboxSelected>> "setHookName $wi"

    set hook ""
    if { $name == "" } {
	$wi.n.state current 4
	setHookName $wi
    } else {
	$wi.n.name insert 0 $name
	foreach hook $g_hook_scripts {
	    if { [lindex $hook 0] == $name } {
		$wi.n.state current [lindex $hook 1]
		break
	    }
	}
    }

    # text box for script entry with scroll bar
    ttk::frame $wi.mid
    text $wi.mid.script -relief sunken -bd 2 \
	-yscrollcommand "$wi.mid.scroll set" -setgrid 1 -height 30 -undo 1 \
	-autosep 1 -background white
    ttk::scrollbar $wi.mid.scroll -command "$wi.mid.script yview"
    pack $wi.mid.script -side left -fill both -expand true
    pack $wi.mid.scroll -side right -fill y
    pack $wi.mid -side top -fill both -expand true

    # load any existing script text
    if { $hook == "" } { ;# some default text
	$wi.mid.script insert end "#!/bin/sh\n"
	$wi.mid.script insert end "# session hook script; write commands here to execute on the host at the\n# specified state\n"
    } else {
	$wi.mid.script insert end [lindex $hook 2]
    }

    # buttons on the bottom
    ttk::frame $wi.btm
    ttk::button $wi.btm.apply -text "Apply" -command \
	"popupHookScriptApply $wi \"$name\""
    ttk::button $wi.btm.cancel -text "Cancel" -command "destroy $wi"
    pack $wi.btm.apply $wi.btm.cancel -side left
    pack $wi.btm

    focus $wi.mid.script
}

proc popupHookScriptApply { wi oldname } {
    global g_hook_scripts CORE_STATES

    set name [$wi.n.name get]
    set state [$wi.n.state get]
    # convert state to a number
    for { set i 0 } { $i < [llength $CORE_STATES] } { incr i } {
	if {[lindex $CORE_STATES $i] == $state } {
	    set state $i
	    break
	}
    }
    set script [string trim [$wi.mid.script get 0.0 end-1c]]

    set hook [list $name $state $script]

    set i end
    if { $oldname != "" } { set i [removeHook $oldname] }
    set g_hook_scripts [linsert $g_hook_scripts $i $hook]

    refreshHooksList .hooks
    destroy $wi
}

proc setHookName { wi } {
    global g_hook_scripts
    set state [string tolower [$wi.n.state get]]
    set name "${state}_hook.sh"
    set n 1
    set names ""
    foreach hook $g_hook_scripts {
	lappend names [lindex $hook 0]
    }
    while { [lsearch $names $name] >= 0 } {
	incr n
	set name "${state}${n}_hook.sh"
    }
    $wi.n.name delete 0 end
    $wi.n.name insert 0 $name
}

# show the comments dialog for adding comments to a scenario
proc popupCommentsConfig {} {
    global g_comments
    set wi .commentsConfig

    catch {destroy $wi}

    if { ![info exists g_comments] } { set g_comments "" }
    toplevel $wi
    wm transient $wi .
    wm resizable $wi 1 1
    wm title $wi "CORE Session Comments"

    # help text at top
    frame $wi.top
    set helptext "Optional text comments associated with this scenario may"
    set helptext "$helptext be entered below and saved with the config file."
    label $wi.top.help -text $helptext
    pack $wi.top.help -side top -fill both -expand true
    pack $wi.top -padx 4 -pady 4 -side top

    # text box for comment entry with scroll bar
    frame $wi.mid
    text $wi.mid.comments -relief sunken -bd 2 \
	-yscrollcommand "$wi.mid.scroll set" -setgrid 1 -height 30 -undo 1 \
	-autosep 1 -background white
    scrollbar $wi.mid.scroll -command "$wi.mid.comments yview"
    pack $wi.mid.comments -side left -fill both -expand true
    pack $wi.mid.scroll -side right -fill y
    pack $wi.mid -side top -fill both -expand true

    # load any existing comment text
    if { $g_comments != "" } {
	$wi.mid.comments insert end $g_comments
    }

    # buttons on the bottom
    frame $wi.btm
    button $wi.btm.apply -text "Apply" -command {
	set wi .commentsConfig
	global g_comments
	set g_comments [string trim [$wi.mid.comments get 0.0 end-1c]]
	destroy $wi
    }
    button $wi.btm.cancel -text "Cancel" -command "destroy $wi"
    pack $wi.btm.apply $wi.btm.cancel -side left
    pack $wi.btm

    focus $wi.mid.comments
}

# show the contents of a file
proc popupFileView { pathname } {
    set wi .fileview
    catch {destroy $wi}

    toplevel $wi
    wm transient $wi .
    wm resizable $wi 1 1
    wm title $wi "File: $pathname"

    ttk::frame $wi.top
    ttk::label $wi.top.fnl -text "File:"
    ttk::entry $wi.top.fn
    #ttk::entry $wi.top.fn -state readonly
    pack $wi.top.fnl -padx 4 -side left 
    pack $wi.top.fn  -padx 4 -side left -fill both -expand true
    pack $wi.top -padx 4 -pady 4 -side top -fill both -expand true
    $wi.top.fn insert 0 $pathname
    $wi.top.fn state readonly

    ttk::frame $wi.mid
    text $wi.mid.contents -relief sunken -bd 2 \
	-yscrollcommand "$wi.mid.scroll set" -setgrid 1 -height 30 -undo 1 \
	-autosep 1 -background white
    ttk::scrollbar $wi.mid.scroll -command "$wi.mid.contents yview"
    pack $wi.mid.contents -side left -fill both -expand true
    pack $wi.mid.scroll -side right -fill y
    pack $wi.mid -side top -fill both -expand true

    if { [catch { set f [open $pathname r] } e] } {
	$wi.mid.contents insert end "error: $e"
    } else {
	while { [ gets $f line] >= 0 } {
	    $wi.mid.contents insert end "$line\n"
	}
	close $f
    }

    # buttons on the bottom
    ttk::frame $wi.btm
    ttk::button $wi.btm.close -text "Close" -command "destroy $wi"
    pack $wi.btm.close -side left
    pack $wi.btm

    $wi.mid.contents see end
    focus $wi.mid.contents
}

# helper for "..." buttons for browsing for files
# ctl is the text entry to populate
proc fileButtonPopup { ctl initial } {
    set f [tk_getOpenFile -initialdir $initial]
    if { $f != "" } {
	$ctl delete 0 end
	$ctl insert 0 $f
    }
}

# helper to get the name of the image representing a node; first, use any
# custom image defined, then customizable node type image, then finally the
# node's type name
proc getNodeImage { node } {
    set type [nodeType $node]
    set model [getNodeModel $node]

    set imgname [getNodeTypeImage $model normal]
    set cimg [absPathname [getCustomImage $node]]
    if { $cimg != "" } { set imgname $cimg }

    set imgname [file tail $imgname]
    if { $imgname == "" } { set imgname $type}
    global $imgname
    return [set $imgname]
}

proc hideSelected { } {
    foreach node [selectedNodes] { hideNode $node }
    .c delete -withtags selectmark
}

proc hideNode { node } {
    set c .c
    setNodeHidden $node 1
    $c itemconfigure "node && $node" -state hidden
    $c itemconfigure "nodelabel && $node" -state hidden
    $c itemconfigure "highlight && $node" -state hidden
    $c itemconfigure "$node && antenna" -state hidden
    $c itemconfigure "$node && link" -state hidden
    $c itemconfigure "$node && interface" -state hidden
    foreach l [$c find withtag "$node && link"] {
	set link [lindex [$c gettags $l] 1]
	$c itemconfigure "linklabel && $link" -state hidden
    }
}

# this is a helper to save/restore the (green) WLAN wireless links used with
# the basic range model, because they are not saved on the global link_list
# called from proc redrawAll
proc saveRestoreWlanLinks { c cmd } {
    global wlink_list

    if { $cmd == "save" } {
	set wlink_list {}
	foreach item [$c find withtag "wlanlink"] {
	    set tags [$c gettags $item] ;# tags = "wlanlink n1 n2 wlan need_r"
	    lappend wlink_list [lrange $tags 1 3]
	}
    } elseif { $cmd == "restore" } {
	if { ![info exists wlink_list] } {
	    return
	}
	foreach wlink $wlink_list {
	    lassign $wlink node1 node2 wlan
	    drawWlanLink $node1 $node2 $wlan
	}
    }
}

proc cutSelection {} {
    editCopy
    deleteSelection
}

proc copySelection {} {
    global clipboard
    set clipboard {}
    set c .c
    set copied ""
    foreach img [$c find withtag "selected"] {
	set tags [$c gettags $img]
	set objtype [lindex $tags 0]
	set objname [lindex $tags 1]
	# some objects (e.g. oval) consist of multiple canvas objects
	if { [lsearch $copied $objname] != -1 } { continue}
	global $objname
	if { ![info exists $objname] } { continue }
	set item [list $tags [set $objname]]
	lappend clipboard $item
	lappend copied $objname
    }
}

proc pasteSelection {} {
    global clipboard
    global node_list link_list annotation_list curcanvas

    array set node_map ""
    set new_nodes ""
    set new_annotations ""
    set v4blacklist ""
    set v6blacklist ""
    set dx 75; set dy 50 ;# paste offset

    if { ![info exists clipboard] } { return }

    # pass 1 - make new nodes
    foreach item $clipboard {
	set tags [lindex $item 0]
	set olddata [lindex $item 1] ;# allows copy, change, paste
	set old [lindex $tags 1]

	# annotations
	set type [nodeType $old]
	if { [lsearch -exact "oval rectangle text" $type] != -1 } {
	    set new [newObjectId annotation]
	    global $new
	    set $new $olddata
	    lappend annotation_list $new
	    lappend new_annotations $new
	    moveAnnotation $new $dx $dy
	    continue
	}
	if { $type == "pseudo" } { continue }

	set new [newObjectId node]
	set node_map($old) $new
	global $new
	# set $new [set $old] would copy the current node's data, but using
	# $olddata instead will copy node data at the time "copy" was invoked
	set $new $olddata
	lappend node_list $new
	lappend new_nodes $new
	if { [getNodeName $old] != $old } {
	    setNodeName $new [getNodeName $old] ;# preserve textual names
	} else {
	    setNodeName $new $new
	}
	setNodeCanvas $new $curcanvas

	if { [nodeType $new] == "wlan" } {
	    setIfcIPv4addr $new wireless "[findFreeIPv4Net 24].0/32"
	    setIfcIPv6addr $new wireless "[findFreeIPv6Net 64]::0/128"
	    continue
	}

	# remove existing addresses, generate new ones later
	if { [[typemodel $new].layer] != "NETWORK" } { continue }
	foreach ifc [ifcList $new] {
	    if { [getIfcIPv4addr $new $ifc] == "" } {
		lappend v4blacklist ${new}_${ifc} ;# preserve empty addrs
	    } else {
		setIfcIPv4addr $new $ifc ""
	    }
	    if { [getIfcIPv6addr $new $ifc] == "" } {
		lappend v6blacklist ${new}_${ifc} ;# preserve empty addrs
	    } else {
		setIfcIPv6addr $new $ifc ""
	    }
	}
    }
    # pass 2 update interfaces and coordinates
    foreach item $clipboard {
	set tags [lindex $item 0]
	set old [lindex $tags 1]
	set type [nodeType $old]
	if { [lsearch -exact "oval rectangle text pseudo" $type] != -1 } {
	    continue
	}
	set new $node_map($old)

	# update coordinates, shifting by <dx, dy>
	lassign [getNodeCoords $new] x y
	setNodeCoords $new "[expr $x + $dx] [expr $y + $dy]"
	lassign [getNodeLabelCoords $new] x y
	setNodeLabelCoords $new "[expr $x + $dx] [expr $y + $dy]"

	foreach ifc [ifcList $new] {
	    set old_peer [peerByIfc $new $ifc]
	    set i [lsearch [set $new] "interface-peer {$ifc $old_peer}"]
	    set logical [logicalPeerByIfc $new $ifc]
	    if { $logical != $old_peer } { ;# prune links to other canvases
		set $new [lreplace [set $new] $i $i]; continue;
	    }
	    if { [lindex [array get node_map $old_peer] 1] != "" } {
		set peer $node_map($old_peer)
		set $new [lreplace [set $new] $i $i \
		    "interface-peer {$ifc $peer}"]
	    } else {
		# old peer is not being copied, create a new interface
		set peer $old_peer
		set peer_ifc [newIfc [chooseIfName $peer $new] $peer]
		global $old_peer
		lappend $old_peer "interface-peer {$peer_ifc $new}"
		if {[[typemodel $peer].layer] == "NETWORK"} {
		    autoIPv4addr $peer $peer_ifc
		    autoIPv6addr $peer $peer_ifc
		}
	    }

	    # a new link already has been created (when peer interfaces were
	    # iterated)
	    if { [linkByPeers $new $peer] != "" } { continue }
	    set oldlink [linkByPeers $old $old_peer]
	    global $oldlink
	    if { [lindex [linkPeers $oldlink] 0] == $old } {
		set newpeers "$new $peer"
	    } else {
		set newpeers "$peer $new"
	    }
	    set newlink [newObjectId link]
	    global $newlink
	    set $newlink [set $oldlink] ;# copies all attributes
	    set i [lsearch [set $oldlink] "nodes {*}"]
	    set $newlink [lreplace [set $newlink] $i $i "nodes {$newpeers}"]
	    lappend link_list $newlink
	}
    }

    # pass 3 - readdress (must occur after all links are updated above)
    foreach new $new_nodes {
	if {[[typemodel $new].layer] != "NETWORK"} { continue }
	foreach ifc [ifcList $new] {
	    if { [lsearch -exact $v4blacklist ${new}_${ifc}] == -1 } {
		autoIPv4addr $new $ifc
	    }
	    if { [lsearch -exact $v6blacklist ${new}_${ifc}] == -1 } {
		autoIPv6addr $new $ifc
	    }
	}
    }
    set changed 1
    updateUndoLog
    redrawAll
    selectNodes $new_nodes
    foreach a $new_annotations { selectNode .c $a }
}

