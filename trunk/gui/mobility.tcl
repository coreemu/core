#
# Copyright 2005-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

# shows the Two-node Tool
proc popupTwoNodeDialog { } {
    global twonodePID lastTwoNodeHop g_twoNodeSelect g_twoNodeSelectCallback
    
    markerOptions off
    set wi .twonodetool
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 200 300
    wm title $wi "Two-node Tool"

    set twonodePID 0
    set lastTwoNodeHop ""
    set g_twoNodeSelect ""
    set g_twoNodeSelectCallback selectTwoNode_twonodetool

    global twoNode1 twoNode2
    frame $wi.e
    labelframe $wi.e.nodes -text "Nodes" -padx 4 -pady 4
    label $wi.e.nodes.srcl -text "source node"
    label $wi.e.nodes.dstl -text "destination node"
    radiobutton $wi.e.nodes.src -text " (none) " -variable g_twoNodeSelect \
	-value "$wi.e.nodes.src" -indicatoron off -activebackground green \
	-selectcolor green -padx 4 -pady 4
    radiobutton $wi.e.nodes.dst -text " (none) " -variable g_twoNodeSelect \
	-value "$wi.e.nodes.dst" -indicatoron off -activebackground red \
	-selectcolor red -padx 4 -pady 4
    label $wi.e.nodes.help -text "click to select nodes"
    pack $wi.e.nodes.srcl $wi.e.nodes.src $wi.e.nodes.dstl $wi.e.nodes.dst \
	-side left
    pack $wi.e.nodes.help -side left -padx 4 -pady 4
    pack $wi.e.nodes $wi.e -side top -fill x


    labelframe $wi.cmd -text "Command line"
    global twoNodeTool
    set twoNodeTool "traceroute"
    radiobutton $wi.cmd.trace -text "traceroute" -variable twoNodeTool \
	-value traceroute -command selectTwoNode_twonodetool
    radiobutton $wi.cmd.ping -text "ping" -variable twoNodeTool \
	-value ping -command selectTwoNode_twonodetool
    entry $wi.cmd.cmd -bg white -width 50
    pack $wi.cmd.trace $wi.cmd.ping $wi.cmd.cmd -side left -padx 4 -pady 4
    pack $wi.cmd -side top -fill x

    # results text box
    labelframe $wi.results -text "Command results"
    text $wi.results.text -bg white -width 80 -height 10 \
	-yscrollcommand "$wi.results.scroll set"
    scrollbar $wi.results.scroll -command "$wi.results.text yview"
    pack $wi.results.text -side left -fill both -expand true -padx 4 -pady 4
    pack $wi.results.scroll -side left -fill y -expand true -padx 4 -pady 4
    pack $wi.results -side top -expand true -fill both

    # buttons on the bottom
    frame $wi.butt -borderwidth 6
    button $wi.butt.run -text "Run" -command "runTwoNodeCommand $wi" 
    button $wi.butt.cancel -text "Clear" -command "clearTwoNodeDialog $wi 0"
    button $wi.butt.close -text "Close" -command "clearTwoNodeDialog $wi 1"
    pack $wi.butt.run $wi.butt.cancel $wi.butt.close -side left
    pack $wi.butt -side bottom
}

#
# reset the Two Node Tool window
proc clearTwoNodeDialog { wi done} {
    global eid activetool twonodePID lastTwoNodeHop systype

    $wi.results.text delete 1.0 end
    clearLinkHighlights
    set lastTwoNodeHop ""
    set node [string trim [$wi.e.nodes.src cget -text]]

    if { $twonodePID > 0 } {
	set os [lindex $systype 0]
	set emul [getEmulPlugin $node]
	set emulation_type [lindex $emul 1]
	    catch {
		if { $os == "FreeBSD" } {
		    exec sudo kill -9 $twonodePID 2> /dev/null
		} else {
		    exec kill -9 $twonodePID 2> /dev/null
		}
	    }
	set twonodePID 0
    }

    if {$done} { ;# close Two Node window
	set activetool select
	.c delete withtag "twonode"
	destroy $wi
    }
}

#
# called from editor.tcl:button1 when user clicks on a node
# g_twoNodeSelect is the global variable of the radio button, whose value is
#  set to the name of the button control to modify
proc selectTwoNode { node } {
    global activetool g_twoNodeSelect g_twoNodeSelectCallback

    if { ![winfo exists $g_twoNodeSelect] } { return }; # user has closed window

    set radius 30
    set color red
    catch {
	# works for radiobutton, but not ttk::checkbutton
        set color [$g_twoNodeSelect cget -selectcolor]
    }
    set deltags "twonode && twonode$g_twoNodeSelect"
    set tags "twonode $node twonode$g_twoNodeSelect"
    $g_twoNodeSelect configure -text " $node "
    drawNodeCircle $node $radius $color $tags $deltags

    eval $g_twoNodeSelectCallback
    set g_twoNodeSelect ""
    set activetool select; # allow moving nodes now
}

# draw a circle around a node
proc drawNodeCircle { node radius color tags deltags } {
    set c .c
    if { $deltags != "" } { $c delete withtag $deltags }
    if { $node == "" } { return }

    set coords [getNodeCoords $node]
    set x [lindex $coords 0]
    set y [lindex $coords 1]
    set x1 [expr {$x-$radius}]; set x2 [expr {$x+$radius}];
    set y1 [expr {$y-$radius}]; set y2 [expr {$y+$radius}];

    $c create oval $x1 $y1 $x2 $y2 -width 5 -outline $color -tags $tags
}

#
# generate a command line string for the two-node tool
# called when tool or either node is selected
proc selectTwoNode_twonodetool { } {
    global eid twoNodeTool
    set wi .twonodetool

    if { ![winfo exists $wi] } { return }; # user has closed window

    # get the tool and its options
    set tool $twoNodeTool
    set opts ""
    if {$twoNodeTool == "traceroute"} {
	set opts "-n -t 0"
    } elseif {$twoNodeTool == "ping"} {
	set opts "-R -n"
    }

    # get source node and destination ip address, if possible
    set src [string trim [$wi.e.nodes.src cget -text]]
    set dst "(none)"
    set node2 [string trim [$wi.e.nodes.dst cget -text]]
    if {$src != "(none)" && $node2 != "(none)"} {
        set dst [getDestinationAddress $src $node2]
    } else {
        $wi.cmd.cmd delete 0 end
	return
    }

    # erase existing command (edits are lost) and insert a new one
    global systype
    set os [lindex $systype 0]
    set emul [getEmulPlugin $src]
    set emulation_type [lindex $emul 1]
    if { $os == "Linux" } {
	if { $emulation_type == "openvz" } {
	    set node_id [string range $src 1 end]
	    incr node_id 1000
	    set cmd "/usr/sbin/vzctl exec $node_id $tool $opts $dst"
	    $wi.cmd.cmd delete 0 end
	    $wi.cmd.cmd insert 0 $cmd
	    return
	}
    }
    set cmd "$tool $opts $dst"
    set sock [lindex $emul 2]
    set flags 0x44;# set TTY, critical flags
    set exec_num [newExecCallbackRequest twonode]
    sendExecMessage $sock $src $cmd $exec_num $flags
}

#
# return an IP address for node2; if node1 is directly connected, return the
# address on that subnet, otherwise pick the first interface address
proc getDestinationAddress { node1 node2 } {
    set ifc ""
    if {$node1 != "" && $node2 != ""} {
        set ifc [ifcByPeer $node2 $node1]; # node2 directly connected to node1?
    }
    if {$ifc == ""} {;# node not directly connected, pick first interface
        set ifc [lindex [ifcList $node2] 0]
    }
    if { $node2 == "" } { return "" }
    return "[lindex [split [getIfcIPv4addr $node2 $ifc] /] 0]"
}

#
# callback when exec response is received
proc exec_twonode_callback { node execnum execcmd execres execstatus } {
    set wi .twonodetool
    if { ![winfo exists $wi] } { return }

    set i [string first "&&" $execres]
    if { $i >= 0 } {
	incr i 3
	set execres [string range $execres $i end]
    }
    $wi.cmd.cmd delete 0 end
    $wi.cmd.cmd insert 0 $execres
}

#
# run the command from the Two Node Tool window
proc runTwoNodeCommand { wi } {
    global twoNodeTool node_list
    set c .c

    if { ![winfo exists $wi] } { return }; # user has closed window

    clearTwoNodeDialog $wi 0; # clean up any previous processes

    set node [string trim [$wi.e.nodes.src cget -text]]
    if { [lsearch $node_list $node] < 0 } { return }
    set cmd [$wi.cmd.cmd get]
    set tool $twoNodeTool

    # de-select
    $c dtag node selected
    $c delete -withtags selectmark

    $wi.results.text delete 1.0 end
    $wi.results.text insert end "$cmd\n"
    $wi.results.text see end

    after 100 doTwoNode $tool $node \"$cmd\"
}

#
# dipatch command remotely or to fileevent handler
proc doTwoNode { tool node cmd } {
    global eid twonodePID exec_servers lastTwoNodeHop
    set wi .twonodetool

    set lastTwoNodeHop $node

    if { $cmd == "" } { return }

    # local execution - uses file event handler
    set fileId [open "|$cmd" r]
    fconfigure $fileId -buffering line
    set twonodePID [pid $fileId]
    fileevent $fileId readable [list readTwoNodeStream $node $fileId $tool]
}

#
# event handler for Two Node command pipe
proc readTwoNodeStream { node fileId tool } {
    fileevent $fileId readable ""; # turn handler off
    set wi .twonodetool

    if {![winfo exists $wi]} {
	catch { close $fileId }
	return; # the window has been closed
    }
    if { ![eof $fileId] } {
        gets $fileId line
	$wi.results.text insert end "$line\n"
	$wi.results.text see end
	drawTwoNodeLine $node $line $tool
	update
	# reinstall event handler
        fileevent $fileId readable [list readTwoNodeStream $node $fileId $tool]
    } else {
	#set p [pid $fileId]
	$wi.results.text insert end "done.\n"
	$wi.results.text see end
	catch { close $fileId }
	update
    }
}

#
# parse a line of trace/ping output and highlight the next hop
proc drawTwoNodeLine { node line type } {
    global lastTwoNodeHop

    # parse the nexthop from raw input
    set nexthop ""
    if {$type == "traceroute"} {
	set tmp [string range $line 2 17]
	set nexthop [regexp -inline {[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+} $tmp]
    } elseif {$type == "ping"} {
	set first [string range $line 0 0]
	if {$first == "R"} { ;# RR: (reroute header)
	    clearLinkHighlights ;# new route will be displayed, color old one?
	    set tmp [string range $line 4 end]
	} elseif {$first == "	" } { ;# tab character
	    set tmp [string range $line 1 end]
	} else { ;# not reroute info
	    set lastTwoNodeHop $node ;# need beginning node
	    return
	}
	set nexthop [regexp -inline {[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+} $tmp]
    }
    if { $nexthop == "" } { return }; # garbage

    # search for hops matching this nexthop address
    set hops [findNextHops $lastTwoNodeHop $nexthop ""]
    if {[llength $hops] == 0} {
    	puts "Couldn't highlight next hop: $nexthop"; 
	return
    }

    # highlight the path 
    set a $lastTwoNodeHop
    foreach b $hops {
	highlightLink $a $b
	set a $b
    }
    set lastTwoNodeHop $b
}

#
# search for a peer node having the nexthop address
# lastnode parameter prevents infinite recursion
proc findNextHops { node nexthop lastnode } {
    if { $node == "" } { return "" }; # initial lastTwoNodeHop value

    foreach ifc [ifcList $node] {
	set peer [peerByIfc $node $ifc]
	if { $peer == "" } { continue }
	if { $lastnode != "" && $peer == $lastnode } { continue };# no recursion
	set peertype [nodeType $peer]
	switch $peertype {
	lanswitch  -
	hub  -
	wlan {
	    set hops [findNextHops $peer $nexthop $node]
	    if { [llength $hops] > 0 } {
		# don't include wlan in list of hops
		if {$peertype == "wlan"} { return $hops }
		# include peer in list of hops
	    	return [linsert $hops 0 $peer]
	    }
	}
	default {
	    if { [nodeHasAddr $peer $nexthop] } { return $peer }
	}
	};# end switch
    }
    return ""
}

#
# returns 1 if node has address, 0 otherwise
# (getIfcByPeer and getIfcIPv4addr are not enough, since traceroute can report
# any of the peer's addresses)
proc nodeHasAddr { node addr } {
    foreach ifc [ifcList $node] {
	set nodeaddr [lindex [split [getIfcIPv4addr $node $ifc] /] 0]
	if { $nodeaddr == $addr } {
	    return 1
	}
    }	
    return 0
}

#
# Highlight the link between two nodes
proc highlightLink { node1 node2 } {
    global link_list
    set hlink ""

    set wlanlinks [.c find withtag "wlanlink && $node1 && $node2"]
    if { $wlanlinks != "" } {
	set hlink [lindex $wlanlinks 0]
    } else {
	set links [.c find withtag "link && $node1 && $node2"]
	if { $links != "" } { set hlink [lindex $links 0] }
    }
    if  { $hlink == "" } { return }
    # don't mess with link width! labels will redraw vertically
    .c itemconfigure "$hlink" -fill "#E4CF30" -width 5
    update
}

#
# Remove highlighting from all links
proc clearLinkHighlights { } {
	global link_list defLinkColor
	foreach link $link_list {
	    set limages [.c find withtag "link && $link"]
	    set limage1 [lindex $limages 0]
	    set tags [.c gettags $limage1]
	    set lnode1 [lindex $tags 2]
	    set lnode2 [lindex $tags 3]
	    set width [getLinkWidth $link]
	    set fill [getLinkColor $link]
	    .c itemconfigure "link && $link" -fill $fill -width $width
	    .c itemconfigure "linklabel && $link" -fill black
	    if { $lnode1 != "" && $link != "" } {
		.c itemconfigure "interface && $lnode1 && $link" -fill black
	    }
	    if { $lnode2 != "" && $link != "" } {
		.c itemconfigure "interface && $lnode2 && $link" -fill black
	    }
	}
	foreach wlanlink [.c find withtag wlanlink] {
	    set tags [.c gettags $wlanlink]
	    set wlan [lindex $tags 3]
	    set color [getWlanColor $wlan]
	    .c itemconfigure "$wlanlink" -fill $color -width 2
	}
	update
}

#
# Boeing: shows the Two-node Tool
proc popupRunDialog { } {
    global node_list activetool systype
   
    set activetool select
    markerOptions off
    set wi .runtool
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 200 300
    wm title $wi "Run Tool"

    global runnodelist
    set runnodelist $node_list

    labelframe $wi.n -text "Run on these nodes"
    frame $wi.n.nodes
    listbox $wi.n.nodes.nodes -width 15 -height 11 -selectmode extended \
	-exportselection 0 \
	-listvariable runnodelist -yscrollcommand "$wi.n.nodes.scroll set"
    scrollbar $wi.n.nodes.scroll -command "$wi.n.nodes.nodes yview"
    frame $wi.n.nodesel -height 5
    button $wi.n.nodesel.all -text "all" \
 	-command "$wi.n.nodes.nodes selection set 0 end"
    button $wi.n.nodesel.none -text "none" \
 	-command "$wi.n.nodes.nodes selection clear 0 end"
    pack $wi.n.nodes.nodes $wi.n.nodes.scroll -side left -fill y -padx 4 -pady 4
    pack $wi.n.nodesel.all $wi.n.nodesel.none -side left -padx 4 -pady 4
    pack $wi.n.nodes -side top -expand true -fill both
    pack $wi.n.nodesel -side bottom -fill x
    pack $wi.n -side right -fill both

    $wi.n.nodes.nodes selection set 0 end ;# select all

    labelframe $wi.cmd -text "Command line"
    entry $wi.cmd.cmd -bg white -width 50
    pack $wi.cmd.cmd -side left -padx 4 -pady 4
    pack $wi.cmd -side top -fill x

    set cmd "ps ax"
    set os [lindex $systype 0]
    # TODO: use CORE API Execute message for all cases
    if { $os == "Linux" } {
	set emulation_type [lindex [getEmulPlugin "*"] 1]
	if { $emulation_type == "openvz" } {
	    set cmd "/usr/sbin/vzctl exec NODE $cmd"
	}
    }
    $wi.cmd.cmd insert 0 $cmd

    # results text box
    labelframe $wi.results -text "Command results"
    text $wi.results.text -bg white -width 80 -height 10 \
	-yscrollcommand "$wi.results.scroll set"
    scrollbar $wi.results.scroll -command "$wi.results.text yview"
    pack $wi.results.text -side left -fill both -expand true -padx 4 -pady 4
    pack $wi.results.scroll -side left -fill y 	-padx 4 -pady 4
    pack $wi.results -side top -expand true -fill both

    # buttons on the bottom
    frame $wi.butt -borderwidth 6
    button $wi.butt.run -text "Run" -command "runToolCommand $wi \"\"" 
    button $wi.butt.close -text "Close" -command "destroy $wi"
    pack $wi.butt.run $wi.butt.close -side left
    pack $wi.butt -side bottom
}

#
# run the command from the Run Tool window
proc runToolCommand { wi node } {
    global node_list eid systype
    set c .c

    if { ![winfo exists $wi] } { return }; # user has closed window

    # start running commands
    if { $node == "" } { 
	$wi.results.text delete 1.0 end
	set selected [$wi.n.nodes.nodes curselection]
	if { [llength $selected] == 0 } {
	    $wi.results.text insert end "No nodes are selected. Highlight one or more nodes on the right and try again."
	    return
	}
	set node [lindex $node_list [lindex $selected 0]]
	after 100 runToolCommand $wi $node; # callback for starting node
	return
    }

    set next ""
    set getnext 0
    foreach i [$wi.n.nodes.nodes curselection] { ;# find the next node 
        set n [lindex $node_list $i] 
	if {$n == $node } {
	    set getnext 1
	} elseif { $getnext == 1 } {
	    # only run commands on router/pc/host nodes
	    if {[lsearch {router pc host} [nodeType $n]] < 0} { continue }
	    set next $n
	    break
	}
    }

    # build the command (replace NODE with node name)
    set cmd [$wi.cmd.cmd get]
    set i [string first "NODE" $cmd]
    set os [lindex $systype 0]
    set node_id $node
    $wi.results.text insert end "> $cmd\n"
    $wi.results.text see end
    update

    # run the command via Execute API message
    set exec_num [newExecCallbackRequest runtool]
    set plugin [getEmulPlugin $node]
    set emulation_sock [lindex $plugin 2]
    sendExecMessage $emulation_sock $node $cmd $exec_num 0x30

    if { $next != "" } {
	runToolCommand $wi $next; # callback for next node in list
    }
}

# callback after receiving exec message response
proc exec_runtool_callback { node execnum cmd result status } {
    set wi .runtool
    
    if { ![winfo exists $wi] } { return }; # user has closed window

    $wi.results.text insert end "> $node > $cmd:\n"
    $wi.results.text insert end "$result\n"
    $wi.results.text see end
}

