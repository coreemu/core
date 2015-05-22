#
# CORE API
# Copyright 2005-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author:	Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#

# version of the API document that is used
set CORE_API_VERSION 1.23

set DEFAULT_API_PORT 4038
set g_api_exec_num 100; # starting execution number

# set scale for X/Y coordinate translation
set XSCALE 1.0
set YSCALE 1.0
set XOFFSET 0
set YOFFSET 0

# current session; 0 is a new session
set g_current_session 0
set g_session_dialog_hint 1

# this is an array of lists, with one array entry for each widget or callback,
# and the entry is a list of execution numbers (for matching replies with
# requests)
array set g_execRequests { shell "" observer "" }

# for a simulator, uncomment this line or cut/paste into debugger:
#  set XSCALE 4.0; set YSCALE 4.0; set XOFFSET 1800; set YOFFSET 300

array set nodetypes { 	0 def 1 phys 2 xen 3 tbd 4 lanswitch 5 hub \
			6 wlan 7 rj45 8 tunnel 9 ktunnel 10 emane }

array set regtypes { wl 1 mob 2 util 3 exec 4 gui 5 emul 6 }
array set regntypes { 1 wl 2 mob 3 util 4 exec 5 gui 6 emul 7 relay 10 session }
array set regtxttypes { wl "Wireless Module" mob "Mobility Module"	\
			util "Utility Module" exec "Execution Server" 	\
			gui "Graphical User Interface" emul "Emulation Server" \
			relay "Relay" }
set DEFAULT_GUI_REG "gui core_2d_gui"
array set eventtypes {	definition_state 1 configuration_state 2 \
			instantiation_state 3 runtime_state 4 \
			datacollect_state 5 shutdown_state 6 \
			event_start 7 event_stop 8 event_pause 9 \
		        event_restart 10 file_open 11 file_save 12 \
		        event_scheduled 31 }

set CORE_STATES \
    "NONE DEFINITION CONFIGURATION INSTANTIATION RUNTIME DATACOLLECT SHUTDOWN"

set EXCEPTION_LEVELS \
    "NONE FATAL ERROR WARNING NOTICE"

# Event handler invoked for each message received by peer
proc receiveMessage { channel } {
    global curcanvas showAPI
    set prmsg $showAPI
    set type 0
    set flags 0
    set len 0
    set seq 0

    #puts "API receive data."
    # disable the fileevent here, then reinstall the handler at the end
    fileevent $channel readable ""
    # channel closed
    if { [eof $channel] } {
	resetChannel channel 1
	return
    }

    #
    # read first four bytes of message header
    set more_data 1
    while { $more_data == 1 } {
        if { [catch { set bytes [read $channel 4] } e] } {
            # in tcl8.6 this occurs during shutdown
            #puts "channel closed: $e"
            break;
        }
	if { [fblocked $channel]  == 1} {
	    # 4 bytes not available yet
	    break;
	} elseif { [eof $channel] } {
	    resetChannel channel 1
	    break;
	} elseif { [string bytelength $bytes] == 0 } {
	    # zero bytes read - parseMessageHeader would fail
	    break;
	}
	# parse type/flags/length
            if { [parseMessageHeader $bytes type flags len] < 0 } {
	    # Message header error
	    break;
	}
	# read message data of specified length
	set bytes [read $channel $len]
	#if { $prmsg== 1} {
	#  puts "read $len bytes (type=$type, flags=$flags, len=$len)..."
	#}
	# handle each message type
	switch -exact -- "$type" {
	    1 { parseNodeMessage $bytes $len $flags }
	    2 { parseLinkMessage $bytes $len $flags }
	    3 { parseExecMessage $bytes $len $flags $channel }
	    4 { parseRegMessage $bytes $len $flags $channel }
	    5 { parseConfMessage $bytes $len $flags $channel }
	    6 { parseFileMessage $bytes $len $flags $channel }
	    8 { parseEventMessage $bytes $len $flags $channel }
	    9 { parseSessionMessage $bytes $len $flags $channel }
	    10 { parseExceptionMessage $bytes $len $flags $channel;
	    #7 { parseIfaceMessage $bytes $len $flags $channel }
		#
	      }
	    default { puts "Unknown Message = $type" }
	}
	# end switch
    }
    # end while

    # update the canvas
    catch {
    # this messes up widgets
    #raiseAll .c
    .c config -cursor left_ptr ;# otherwise we have hourglass/pirate
    update
    }

    if {$channel != -1 } {
        resetChannel channel 0
    }
}

#
# Open an API socket to the specified server:port, prompt user for retry
# if specified; set the readable file event and parameters; 
# returns the channel name or -1 on error.
#
proc openAPIChannel { server port retry } {
    # use default values (localhost:4038) when none specified
    if { $server == "" || $server == 0 } {
	set server "localhost"
    }
    if { $port == 0 } {
	global DEFAULT_API_PORT
	set port $DEFAULT_API_PORT
    }

    # loop when retry is true
    set s -1
    while { $s < 0 } {
	# TODO: fix this to remove lengthy timeout periods...
	#       (need to convert all channel I/O to use async channel)
	#       vwait doesn't work here, blocks on socket call
	#puts "Connecting to $server:$port..."; # verbose
	set svcstart [getServiceStartString]
	set e "This feature requires a connection to the CORE daemon.\n"
	set e "$e\nFailed to connect to $server:$port!\n"
	set e "$e\nHave you started the CORE daemon with"
	set e "$e '$svcstart'?"
	if { [catch {set s [socket $server $port]} ex] } {
	    puts "\n$e\n  (Error: $ex)"
	    set s -1
	    if { ! $retry } { return $s; }; # error, don't retry
	}
	if { $s > 0 } {	puts "connected." }; # verbose
	if { $retry } {; # prompt user with retry dialog
	    if { $s < 0 } {
		set choice [tk_dialog .connect "Error" $e \
		         error 0 Retry "Start daemon..." Cancel]
	        if { $choice == 2 } { return $s } ;# cancel
		if { $choice == 1 } {
		    set sudocmd "gksudo"
		    set cmd "core-daemon -d"
		    if { [catch {exec $sudocmd $cmd & } e] } {
			puts "Error running '$sudocmd $cmd'!"
		    }
		    after 300 ;# allow time for daemon to start
	        }
		# fall through for retry...
	    }
	}
    }; # end while

    # now we have a valid socket, set up encoding and receive event
    fconfigure $s -blocking 0 -encoding binary -translation { binary binary } \
		   -buffering full -buffersize 4096 
    fileevent $s readable [list receiveMessage $s]
    return $s
}

#
# Reinstall the receiveMessage event handler
#
proc resetChannel { channel_ptr close } {
    upvar 1 $channel_ptr channel
    if {$close == 1} {
	close $channel
	pluginChannelClosed $channel
	set $channel -1
    }
    if { [catch { fileevent $channel readable \
		[list receiveMessage $channel] } ] } {
	# may print error here
    }
}

#
# Catch errors when flushing sockets
#
proc flushChannel { channel_ptr msg } {
    upvar 1 $channel_ptr channel
    if { [catch { flush $channel } err] } {
	puts "*** $msg: $err"
	set channel -1
	return -1
    }
   return 0
}


#
# CORE message header
#
proc parseMessageHeader { bytes type flags len } {
    # variables are passed by reference
    upvar 1 $type mytype
    upvar 1 $flags myflags
    upvar 1 $len mylen

    #
    # read the four-byte message header
    #
    if { [binary scan $bytes ccS mytype myflags mylen] != 3 } {
	puts "*** warning: message header error"
	return -1
    } else {
	set mytype [expr {$mytype & 0xFF}]; # convert signed to unsigned
	set myflags [expr {$myflags & 0xFF}]
	if { $mylen == 0 } {
	    puts "*** warning: zero length message header!"
	    # empty the channel
	    #set bytes [read $channel]
	    return -1
	}
    }
    return 0
}


#
# CORE API Node message TLVs
#
proc parseNodeMessage { data len flags } {
    global node_list curcanvas c router eid showAPI nodetypes CORE_DATA_DIR
    global XSCALE YSCALE XOFFSET YOFFSET deployCfgAPI_lock
    #puts "Parsing node message of length=$len, flags=$flags"
    set prmsg $showAPI
    set current 0

    array set typenames { 1 num 2 type 3 name 4 ipv4_addr 5 mac_addr \
			6 ipv6_addr 7 model 8 emulsrv 10 session \
			32 xpos 33 ypos 34 canv \
			35 emuid 36 netid 37 services \
			48 lat 49 long 50 alt \
			66 icon 80 opaque }
    array set typesizes { num 4 type 4 name -1 ipv4_addr 4 ipv6_addr 16 \
			mac_addr 8 model -1 emulsrv -1 session -1 \
			xpos 2 ypos 2 canv 2 emuid 4 \
			netid 4 services -1 lat 4 long 4 alt 4 \
			icon -1 opaque -1 }
    array set vals { 	num 0 type 0 name "" ipv4_addr -1 ipv6_addr -1 \
			mac_addr -1 model "" emulsrv "" session "" \
			xpos 0 ypos 0 canv "" \
			emuid -1 netid -1 services "" \
			lat 0 long 0 alt 0 \
			icon "" opaque "" }

    if { $prmsg==1 } { puts -nonewline "NODE(flags=$flags," }

    #
    # TLV parsing
    #
    while { $current < $len } {
	# TLV header
	if { [binary scan $data @${current}cc type length] != 2 } {
	    puts "TLV header error"
	    break
	}
	set length [expr {$length & 0xFF}]; # convert signed to unsigned
	if { $length == 0 } {; # prevent endless looping
	    if { $type == 0 } { puts -nonewline "(extra padding)"; break
	    } else { puts "Found zero-length TLV for type=$type, dropping.";
	        break }
	}
	set pad [pad_32bit $length]
	# verbose debugging
	#puts "tlv type=$type length=$length pad=$pad current=$current"
	incr current 2
	
	if {![info exists typenames($type)] } { ;# unknown TLV type
	    if { $prmsg } { puts -nonewline "unknown=$type," }
	    incr current $length
	    continue
	}
	set typename $typenames($type)
	set size $typesizes($typename)
	# 32-bit and 64-bit vals pre-padded
	if { $size == 4 || $size == 8 } { incr current $pad }
	# read TLV data depending on size
	switch -exact -- "$size" {
	2 { binary scan $data @${current}S vals($typename) }
	4 { binary scan $data @${current}I vals($typename) }
	8 { binary scan $data @${current}W vals($typename) }
	16 { binary scan $data @${current}c16 vals($typename) }
	-1 { binary scan $data @${current}a${length} vals($typename) }
	}
	if { $size == -1 } { incr current $pad } ;# string vals post-padded
	if { $type == 6 } { incr current $pad } ;# 128-bit vals post-padded
	incr current $length
	# special handling of data here
	switch -exact -- "$typename" {
	ipv4_addr { array set vals [list $typename \
		[ipv4ToString $vals($typename)] ] }
	mac_addr { array set vals [list $typename \
		[macToString $vals($typename)] ] }
	ipv6_addr { array set vals [list $typename \
		[ipv6ToString $vals($typename)] ] }
	xpos { array set vals [list $typename  \
			[expr { ($vals($typename) * $XSCALE) - $XOFFSET }] ] }
	ypos { array set vals [list $typename \
			[expr { ($vals($typename) * $YSCALE) - $YOFFSET }] ] }
	}
	if { $prmsg } { puts -nonewline "$typename=$vals($typename)," }
    }

    if { $prmsg } { puts ") "}

    #
    # Execution
    #
    # TODO: enforce message parameters here
    if { ![info exists nodetypes($vals(type))] } {
	puts "NODE: invalid node type ($vals(type)), dropping"; return
    }
    set node "n$vals(num)"
    set node_id "$eid\_$node"
    if { [lsearch $node_list $node] == -1 } {; # check for node existance
	set exists false
    } else {
	set exists true
    }
    
    if { $vals(name) == "" } {; # make sure there is a node name
	set name $node
	if { $exists } { set name [getNodeName $node] }
	array set vals [list name $name] 
    }
    if { $exists } {
	if { $flags == 1 } {
	puts "Node add msg but node ($node) already exists, dropping."
	return
	}
    } elseif { $flags != 1 } {
	puts -nonewline "Node modify/delete message but node ($node) does "
	puts "not exist dropping."
	return
    }
    if { $vals(icon) != "" } {
	set icon $vals(icon)
	if { [file pathtype $icon] == "relative" } {
	    set icon "$CORE_DATA_DIR/icons/normal/$icon"
	}
	if { ![file exists $icon ] } {
	    puts "Node icon '$vals(icon)' does not exist."
	    array set vals [list icon ""]
	} else {
	    array set vals [list icon $icon]
	}
    }
    global $node

    set wlans_needing_update { }
    if { $vals(emuid) != -1 } {
	# For Linux (FreeBSD populates ngnodeidmap in l3node.instantiate/
	#  buildInterface when the netgraph ID is known)
	# populate ngnodeidmap for later use with wireless; it is treated as
	# a hex value string (without the leading "0x")
	global ngnodeidmap
	foreach wlan [findWlanNodes $node] {
	if { ![info exists ngnodeidmap($eid\_$wlan)] } {
	    set netid [string range $wlan 1 end]
	    set emulation_type [lindex [getEmulPlugin $node] 1]
	    # TODO: verify that this incr 1000 is for OpenVZ
	    if { $emulation_type == "openvz" } { incr netid 1000 }
	    set ngnodeidmap($eid\_$wlan) [format "%x" $netid]
	}
	if { ![info exists ngnodeidmap($eid\_$wlan-$node)] } {
	    set ngnodeidmap($eid\_$wlan-$node) [format "%x" $vals(emuid)]
	    lappend wlans_needing_update $wlan
	}
	} ;# end foreach wlan
    }

    # local flags: informational message that node was added or deleted
    if {[expr {$flags & 0x8}]} {
	if { ![info exists c] } { return }
	if {[expr {$flags & 0x1}] } { ;# add flag
	    nodeHighlights $c $node on green
	    after 3000 "nodeHighlights .c $node off green"
	} elseif {[expr {$flags & 0x2}] } { ;# delete flag
	    nodeHighlights $c $node on black
	    after 3000 "nodeHighlights .c $node off black"
	}
	# note: we may want to save other data passed in this message here
	#       rather than just returning...
	return
    }
    # now we have all the information about this node
    switch -exact -- "$flags" {
	0 { apiNodeModify $node vals }
	1 { apiNodeCreate $node vals }
	2 { apiNodeDelete $node }
	default { puts "NODE: unsupported flags ($flags)"; return }
    }
}

#
# modify a node
#
proc apiNodeModify { node vals_ref } {
    global c eid zoom curcanvas
    upvar $vals_ref vals
    if { ![info exists c] } { return } ;# batch mode
    set draw 0
    if { $vals(icon) != "" } {
	setCustomImage $node $vals(icon)
	set draw 1
    }
    # move the node and its links
    if {$vals(xpos) != 0 && $vals(ypos) != 0} {
	moveNodeAbs $c $node [expr {$zoom * $vals(xpos)}] \
			     [expr {$zoom * $vals(ypos)}]
    }
    if { $vals(name) != "" } {
	setNodeName $node $vals(name)
	set draw 1
    }
    if { $vals(services) != "" } {
	set services [split $vals(services) |]
	setNodeServices $node $services
    }
    # TODO: handle other optional on-screen data
    # lat, long, alt, heading, platform type, platform id
    if { $draw && [getNodeCanvas $node] == $curcanvas }  {
	.c delete withtag "node && $node"
	.c delete withtag "nodelabel && $node"
	drawNode .c $node
    }
}

#
# add a node
#
proc apiNodeCreate { node vals_ref } {
    global $node nodetypes node_list canvas_list curcanvas eid
    upvar $vals_ref vals

    # create GUI object
    set nodetype $nodetypes($vals(type))
    set nodename $vals(name)
    if { $nodetype == "emane" } { set nodetype "wlan" } ;# special case - EMANE
    if { $nodetype == "def" || $nodetype == "xen" } { set nodetype "router" }
    newNode [list $nodetype $node] ;# use node number supplied from API message
    setNodeName $node $nodename
    if { $vals(canv) == "" } {
	setNodeCanvas $node $curcanvas
    } else {
	set canv $vals(canv)
	if { ![string is integer $canv] || $canv < 0 || $canv > 100} {
	    puts "warning: invalid canvas '$canv' in Node message!"
	    return
	}
	set canv "c$canv"
	if { [lsearch $canvas_list $canv] < 0 && $canv == "c0" } { 
	    # special case -- support old imn files with Canvas0
	    global $canv
	    lappend canvas_list $canv
	    set $canv {}
	    setCanvasName $canv "Canvas0"
	    set curcanvas $canv
	    switchCanvas none
	} else {
	    while { [lsearch $canvas_list $canv] < 0 } {
		set canvnew [newCanvas ""]
		switchCanvas none ;# redraw canvas tabs
	    }
	}
	setNodeCanvas $node $canv
    }
    setNodeCoords $node "$vals(xpos) $vals(ypos)"
    lassign [getDefaultLabelOffsets [nodeType $node]] dx dy
    setNodeLabelCoords $node "[expr $vals(xpos) + $dx] [expr $vals(ypos) + $dy]"
    setNodeLocation $node $vals(emulsrv)
    if { $vals(icon) != "" } {
	setCustomImage $node $vals(icon)
    }
    drawNode .c $node

    set model $vals(model)
    if { $model != ""  && $vals(type) < 4} {
	# set model only for (0 def 1 phys 2 xen 3 tbd) 4 lanswitch
	setNodeModel $node $model
	if { [lsearch -exact [getNodeTypeNames] $model] == -1 } {
	    puts "warning: unknown node type '$model' in Node message!"
	}
    }
    if { $vals(services) != "" } {
	set services [split $vals(services) |]
	setNodeServices $node $services
    }

    if { $vals(type) == 7 } { ;# RJ45 node - used later to control linking
	netconfInsertSection $node [list model $vals(model)]
    } elseif { $vals(type) == 10 } { ;# EMANE node
	set section [list mobmodel coreapi ""]
	netconfInsertSection $node $section
        #set sock [lindex [getEmulPlugin $node] 2]
	#sendConfRequestMessage $sock $node "all" 0x1 -1 ""
    } elseif { $vals(type) == 6 } { ;# WLAN node
	if { $vals(opaque) != "" } {
	    # treat opaque as a list to accomodate other data
	    set i [lsearch $vals(opaque) "range=*"]
	    if { $i != -1 } {
		set range [lindex $vals(opaque) $i]
		setNodeRange $node [lindex [split $range =] 1]
	    }
	}
    }
}

#
# delete a node
#
proc apiNodeDelete { node } {
    removeGUINode $node
}

#
# CORE API Link message TLVs
#
proc parseLinkMessage { data len flags } {
    global router def_router_model eid
    global link_list node_list ngnodeidmap ngnodeidrmap showAPI execMode
    set prmsg $showAPI
    set current 0
    set c .c
    #puts "Parsing link message of length=$len, flags=$flags"

    array set typenames {	1 node1num 2 node2num 3 delay 4 bw 5 per \
			6 dup 7 jitter 8 mer 9 burst 10 session \
			16 mburst 32 ltype 33 guiattr 34 uni \
			35 emuid1 36 netid 37 key \
			48 if1num 49 if1ipv4 50 if1ipv4mask 51 if1mac \
			52 if1ipv6 53 if1ipv6mask \
			54 if2num 55 if2ipv4 56 if2ipv4mask 57 if2mac \
			64 if2ipv6 65 if2ipv6mask }
    array set typesizes {	node1num 4 node2num 4 delay 8 bw 8 per -1 \
			dup -1 jitter 8 mer 2 burst 2 session -1 \
			mburst 2 ltype 4 guiattr -1 uni 2 \
			emuid1 4 netid 4 key 4 \
			if1num 2 if1ipv4 4 if1ipv4mask 2 if1mac 8 \
			if1ipv6 16 if1ipv6mask 2 \
			if2num 2 if2ipv4 4 if2ipv4mask 2 if2mac 8 \
			if2ipv6 16 if2ipv6mask 2 }
    array set vals {	node1num -1 node2num -1 delay 0 bw 0 per "" \
			dup "" jitter 0 mer 0 burst 0 session "" \
			mburst 0 ltype 0 guiattr "" uni 0 \
			emuid1 -1 netid -1 key -1 \
			if1num -1 if1ipv4 -1 if1ipv4mask 24 if1mac -1 \
			if1ipv6 -1 if1ipv6mask 64 \
			if2num -1 if2ipv4 -1 if2ipv4mask 24 if2mac -1 \
			if2ipv6 -1 if2ipv6mask 64 }
    set emuid1 -1

    if { $prmsg==1 } { puts -nonewline "LINK(flags=$flags," }

    #
    # TLV parsing
    #
    while { $current < $len } {
	# TLV header
	if { [binary scan $data @${current}cc type length] != 2 } {
	puts "TLV header error"
	break
	}
	set length [expr {$length & 0xFF}]; # convert signed to unsigned
	if { $length == 0 } {; # prevent endless looping
	if { $type == 0 } { puts -nonewline "(extra padding)"; break
	} else { puts "Found zero-length TLV for type=$type, dropping.";
	    break }
	}
	set pad [pad_32bit $length]
	# verbose debugging
	#puts "tlv type=$type length=$length pad=$pad current=$current"
	incr current 2

	if {![info exists typenames($type)] } { ;# unknown TLV type
		if { $prmsg } { puts -nonewline "unknown=$type," }
	incr current $length
	continue
	}
	set typename $typenames($type)
	set size $typesizes($typename)
	# 32-bit and 64-bit vals pre-padded
	if { $size == 4 || $size == 8} { incr current $pad }
	# read TLV data depending on size
	switch -exact -- "$size" {
	2 { binary scan $data @${current}S vals($typename) }
	4 { binary scan $data @${current}I vals($typename) }
	8 { binary scan $data @${current}W vals($typename) }
	16 { binary scan $data @${current}c16 vals($typename) }
	-1 { binary scan $data @${current}a${length} vals($typename) }
	}
	incr current $length
	# special handling of data here
	switch -exact -- "$typename" {
	delay -
	jitter { if { $vals($typename) > 2000000 } {
	    array set vals [list $typename 2000000] } }
	bw { if { $vals($typename) > 1000000000 } {
	    array set vals [list $typename 0] } }
	per { if { $vals($typename) > 100 } {
	    array set vals [list $typename 100] } }
	dup { if { $vals($typename) > 50 } {
	    array set vals [list $typename 50] } }
	emuid1 { if { $emuid1 == -1 } {
		set emuid $vals($typename)
	    } else { ;# this sets emuid2 if we already have emuid1
		array set vals [list emuid2 $vals($typename) ]
		array set vals [list emuid1 $emuid1 ]
	    }
	}
	if1ipv4 -
	if2ipv4 { array set vals [list $typename \
		[ipv4ToString $vals($typename)] ] }
	if1mac -
	if2mac { array set vals [list $typename \
		[macToString $vals($typename)] ] }
	if1ipv6 -
	if2ipv6 { array set vals [list $typename \
		[ipv6ToString $vals($typename)] ] }
	}
	if { $prmsg } { puts -nonewline "$typename=$vals($typename)," }
	if { $size == 16 } { incr current $pad } ;# 128-bit vals post-padded
	if { $size == -1 } { incr current $pad } ;# string vals post-padded
    }

    if { $prmsg == 1 } { puts ") " }

    # perform some sanity checking of the link message
    if { $vals(node1num) == $vals(node2num) || \
	 $vals(node1num) < 0 || $vals(node2num) < 0 } {
	puts -nonewline "link message error - node1=$vals(node1num), "
	puts "node2=$vals(node2num)"
	return
    }

    # convert node number to node and check for node existance
    set node1 "n$vals(node1num)"
    set node2 "n$vals(node2num)"
    if { [lsearch $node_list $node1] == -1 || \
	 [lsearch $node_list $node2] == -1 } {
	puts "Node ($node1/$node2) in link message not found, dropping"
	return
    }

    # set IPv4 and IPv6 address if specified, otherwise may be automatic
    set prefix1 [chooseIfName $node1 $node2]
    set prefix2 [chooseIfName $node2 $node1]
    foreach i "1 2" {
	# set interface name/number
	if { $vals(if${i}num) == -1 } {
	    set ifname [newIfc [set prefix${i}] [set node${i}]]
	    set prefixlen [string length [set prefix${i}]]
	    set if${i}num [string range $ifname $prefixlen end]
	    array set vals [list if${i}num [set if${i}num]]
	}
	set ifname [set prefix${i}]$vals(if${i}num)
	array set vals [list if${i}name $ifname]
	# record IPv4/IPv6 addresses for newGUILink
	foreach j "4 6" {
    	    if { $vals(if${i}ipv${j}) != -1 } {
		setIfcIPv${j}addr [set node${i}] $ifname \
			$vals(if${i}ipv${j})/$vals(if${i}ipv${j}mask)
	    }
	}
	if { $vals(if${i}mac) != -1 } {
	    setIfcMacaddr [set node${i}] $ifname $vals(if${i}mac)
	}
    }
    # adopt network address for WLAN (WLAN must be node 1)
    if { [nodeType $node1] == "wlan" } {
	set v4addr $vals(if2ipv4)
	if { $v4addr != -1 } {
	    set v4net [ipv4ToNet $v4addr $vals(if2ipv4mask)]
	    setIfcIPv4addr $node1 wireless "$v4net/$vals(if2ipv4mask)"
	}
	set v6addr $vals(if2ipv6)
	if { $v6addr != -1 } {
	    set v6net [ipv6ToNet $v6addr $vals(if2ipv6mask)]
	    setIfcIPv6addr $node1 wireless "${v6net}::0/$vals(if2ipv6mask)"
	}
    }

    if { $execMode == "batch" } {
	return ;# no GUI to update in batch mode
    }
    # treat 100% loss as link delete
    if { $flags == 0 && $vals(per) == 100 } {
	apiLinkDelete $node1 $node2 vals
	return
    }

    # now we have all the information about this node
    switch -exact -- "$flags" {
	0 { apiLinkAddModify $node1 $node2 vals 0 }
	1 { apiLinkAddModify $node1 $node2 vals 1 }
	2 { apiLinkDelete $node1 $node2 vals }
	default { puts "LINK: unsupported flags ($flags)"; return }
    }
}

#
# add or modify a link
# if add flag is set, check if two nodes are part of same wlan, and do wlan
# linkage, or add a wired link; otherwise modify wired/wireless link with
# supplied parameters
proc apiLinkAddModify { node1 node2 vals_ref add } {
    global eid defLinkWidth
    set c .c
    upvar $vals_ref vals

    if {$vals(key) > -1} {
	if { [nodeType $node1] == "tunnel" } {
	    netconfInsertSection $node1 [list "tunnel-key" $vals(key)]
	}
	if { [nodeType $node2] == "tunnel" } {
	    netconfInsertSection $node2 [list "tunnel-key" $vals(key)]
	}
    }

    # look for a wired link in the link list
    set wired_link [linkByPeers $node1 $node2]
    if { $wired_link != "" && $add == 0 } { ;# wired link exists, modify it
	#puts "modify wired link"
	if { $vals(uni) == 1 } { ;# unidirectional link effects message
	    set peers [linkPeers $wired_link]
	    if { $node1 == [lindex $peers 0] } { ;# downstream n1 <-- n2
		set bw     [list $vals(bw) [getLinkBandwidth $wired_link up]]
		set delay  [list $vals(delay) [getLinkDelay $wired_link up]]
		set per    [list $vals(per) [getLinkBER $wired_link up]]
		set dup    [list $vals(dup) [getLinkBER $wired_link up]]
		set jitter [list $vals(jitter) [getLinkJitter $wired_link up]]
	    } else { ;# upstream n1 --> n2
		set bw     [list [getLinkBandwidth $wired_link] $vals(bw)]
		set delay  [list [getLinkDelay $wired_link] $vals(delay)]
		set per    [list [getLinkBER $wired_link] $vals(per)]
		set dup    [list [getLinkBER $wired_link] $vals(dup)]
		set jitter [list $vals(jitter) [getLinkJitter $wired_link]]
	    }
	    setLinkBandwidth $wired_link $bw
	    setLinkDelay $wired_link $delay
	    setLinkBER $wired_link $per
	    setLinkDup $wired_link $dup
	    setLinkJitter $wired_link $jitter
	} else {
	    setLinkBandwidth $wired_link $vals(bw)
	    setLinkDelay $wired_link $vals(delay)
	    setLinkBER $wired_link $vals(per)
	    setLinkDup $wired_link $vals(dup)
	    setLinkJitter $wired_link $vals(jitter)
	}
	updateLinkLabel $wired_link
	updateLinkGuiAttr $wired_link $vals(guiattr)
	return
    # if add flag is set and a wired link already exists, assume wlan linkage
    # special case: rj45  model=1 means link via wireless 
    } elseif {[nodeType $node1] == "rj45" || [nodeType $node2] == "rj45"} {
	if { [nodeType $node1] == "rj45" } {
	    set rj45node $node1; set othernode $node2;
	} else { set rj45node $node2; set othernode $node1; }
	if { [netconfFetchSection $rj45node model] == 1 } { 
	    set wlan [findWlanNodes $othernode]
	    if {$wlan != ""} {newGUILink $wlan $rj45node};# link rj4node to wlan
	}
    }

    # no wired link; determine if both nodes belong to the same wlan, and
    # link them; otherwise add a wired link if add flag is set
    set wlan $vals(netid)
    if { $wlan < 0 } {
	# WLAN not specified with netid, search for common WLAN
	set wlans1 [findWlanNodes $node1]
	set wlans2 [findWlanNodes $node2]
	foreach w $wlans1 {
	    if { [lsearch -exact $wlans2 $w] < 0 } { continue }
	    set wlan $w
	    break
        }
    }

    if { $wlan < 0 } { ;# no common wlan
	if {$add == 1} { ;# add flag was set - add a wired link
	    global g_newLink_ifhints
	    set g_newLink_ifhints [list $vals(if1name) $vals(if2name)]
	    newGUILink $node1 $node2
	    if { [getNodeCanvas $node1] != [getNodeCanvas $node2] } {
		set wired_link [linkByPeersMirror $node1 $node2]
	    } else {
		set wired_link [linkByPeers $node1 $node2]
	    }
	    setLinkBandwidth $wired_link $vals(bw)
	    setLinkDelay $wired_link $vals(delay)
	    setLinkBER $wired_link $vals(per)
	    setLinkDup $wired_link $vals(dup)
	    setLinkJitter $wired_link $vals(jitter)
	    updateLinkLabel $wired_link
	    updateLinkGuiAttr $wired_link $vals(guiattr)
	    # adopt link effects for WLAN (WLAN must be node 1)
	    if { [nodeType $node1] == "wlan" } {
		setLinkBandwidth $node1 $vals(bw)
		setLinkDelay $node1 $vals(delay)
		setLinkBER $node1 $vals(per)
	    }
	    return
	} else { ;# modify link, but no wired link or common wlan!
	    puts -nonewline "link modify message received, but no wired link"
	    puts " or wlan for nodes $node1-$node2, dropping"
	    return
	}
    }

    set wlan "n$wlan"
    drawWlanLink $node1 $node2 $wlan
}

#
# delete a link
#
proc apiLinkDelete { node1 node2 vals_ref } {
    global eid
    upvar $vals_ref vals
    set c .c

    # look for a wired link in the link list
    set wired_link [linkByPeers $node1 $node2]
    if { $wired_link != "" } {
	removeGUILink $wired_link non-atomic
	return
    }

    set wlan $vals(netid)
    if { $wlan < 0 } {
	# WLAN not specified with netid, search for common WLAN
	set wlans1 [findWlanNodes $node1]
	set wlans2 [findWlanNodes $node2]
	foreach w $wlans1 {
	    if { [lsearch -exact $wlans2 $w] < 0 } { continue }
	    set wlan $w
	    break
        }
    }
    if { $wlan < 0 } {
	puts "apiLinkDelete: no common WLAN!"
	return
    }
    set wlan "n$wlan"

    # look for wireless link on the canvas, remove GUI object
    $c delete -withtags "wlanlink && $node2 && $node1 && $wlan"
    $c delete -withtags "linklabel && $node2 && $node1 && $wlan"
}

#
# CORE API Execute message TLVs
#
proc parseExecMessage { data len flags channel } {
    global node_list curcanvas c router eid showAPI
    global XSCALE YSCALE XOFFSET YOFFSET
    set prmsg $showAPI
    set current 0

    # set default values
    set nodenum 0
    set execnum 0
    set exectime 0
    set execcmd ""
    set execres ""
    set execstatus 0
    set session ""

    if { $prmsg==1 } { puts -nonewline "EXEC(flags=$flags," }

    # parse each TLV
    while { $current < $len } {
	# TLV header
	set typelength [parseTLVHeader $data current]
	set type [lindex $typelength 0]
	set length [lindex $typelength 1]
	if { $length == 0 || $length == "" } { break }
	set pad [pad_32bit $length]
	# verbose debugging
	#puts "exec tlv type=$type length=$length pad=$pad current=$current"
	if { [expr {$current + $length + $pad}] > $len } {
	    puts "error with EXEC message length (len=$len, TLV length=$length)"
	    break
	}
	# TLV data
	switch -exact -- "$type" {
	    1 {
		incr current $pad
		binary scan $data @${current}I nodenum
		if { $prmsg==1 } { puts -nonewline "node=$nodenum/" }
	    }
	    2 {
		incr current $pad
		binary scan $data @${current}I execnum
		if { $prmsg == 1} { puts -nonewline "exec=$execnum," }
	    }
	    3 {
		incr current $pad
		binary scan $data @${current}I exectime
		if { $prmsg == 1} { puts -nonewline "time=$exectime," }
	    }
	    4 {
		binary scan $data @${current}a${length} execcmd
		if { $prmsg == 1} { puts -nonewline "cmd=$execcmd," }
		incr current $pad
	    }
	    5 {
		binary scan $data @${current}a${length} execres
		if { $prmsg == 1} { puts -nonewline "res=($length bytes)," }
		incr current $pad
	    }
	    6 {
		incr current $pad
		binary scan $data @${current}I execstatus
		if { $prmsg == 1} { puts -nonewline "status=$execstatus," }
	    }
	    10 {
		binary scan $data @${current}a${length} session
		if { $prmsg == 1} { puts -nonewline "session=$session," }
		incr current $pad
	    }
	    default {
		if { $prmsg == 1} { puts -nonewline "unknown=" }
		if { $prmsg == 1} { puts -nonewline "$type," }
	    }
	}
	# end switch

	# advance current pointer
	incr current $length
    }
    if { $prmsg == 1 } { puts ") "}

    set node "n$nodenum"
    set node_id "$eid\_$node"
    # check for node existance
    if { [lsearch $node_list $node] == -1 } {
	puts "Execute message but node ($node) does not exist, dropping."
	return
    }
    global $node

    # Callback support - match execnum from response with original request, and
    #                    invoke type-specific callback
    global g_execRequests
    foreach type [array names g_execRequests] {
	set idx [lsearch $g_execRequests($type) $execnum]
	if { $idx > -1 } {
	    set g_execRequests($type) \
		[lreplace $g_execRequests($type) $idx $idx]
	    exec_${type}_callback $node $execnum $execcmd $execres $execstatus
	    return
	}
    }
}

# spawn interactive terminal
proc exec_shell_callback { node execnum execcmd execres execstatus } {
    #puts "opening terminal for $node by running '$execres'"
    set title "CORE: [getNodeName $node] (console)"
    set term [get_term_prog false]
    set xi [string first "xterm -e" $execres]

    # shell callback already has xterm command, launch it using user-defined
    # term program (e.g. remote nodes 'ssh -X -f a.b.c.d xterm -e ...'
    if { $xi > -1 } {
	set execres [string replace $execres $xi [expr $xi+7] $term]
        if { [catch {exec sh -c "$execres" & } ] } {
	    puts "Warning: failed to open terminal for $node"
        }
	return
    # no xterm command; execute shell callback in a terminal (e.g. local nodes)
    } elseif { \
        [catch {eval exec $term "$execres" & } ] } {
	puts "Warning: failed to open terminal for $node: ($term $execres)"
    }
}


#
# CORE API Register message TLVs
# parse register message into plugin capabilities
#
proc parseRegMessage { data len flags channel } {
    global regntypes showAPI
    set prmsg $showAPI
    set current 0
    set str 0
    set session ""
    set fnhint ""

    set plugin_cap_list {} ;# plugin capabilities list

    if { $prmsg==1 } { puts -nonewline "REG(flags=$flags," }

    # parse each TLV
    while { $current < $len } {
		# TLV header
		if { [binary scan $data @${current}cc type length] != 2 } {
		    puts "TLV header error"
		    break 
		}
		set length [expr {$length & 0xFF}]; # convert signed to unsigned
		if { $length == 0 } {
		    # prevent endless looping
		    if { $type == 0 } {
			puts -nonewline "(extra padding)"
			break
		    } else {
		        puts "Found zero-length TLV for type=$type, dropping."
		        break
		    }
		}
		set pad [pad_32bit $length]
		# verbose debugging
		#puts "tlv type=$type length=$length pad=$pad current=$current"
		incr current 2
		# TLV data
		if { [info exists regntypes($type)] } {
		    set plugin_type $regntypes($type)
		    binary scan $data @${current}a${length} str
		    if { $prmsg == 1} { puts -nonewline "$plugin_type=$str," }
		    if { $type ==  10 } { ;# session number
			set session $str
		    } else {
		        lappend plugin_cap_list "$plugin_type=$str"
			if { $plugin_type == "exec" } { set fnhint $str }
		    }
		} else {
		    if { $prmsg == 1} { puts -nonewline "unknown($type)," }
		}
		incr current $pad
		# end switch

		# advance current pointer
		incr current $length
    }
    if { $prmsg == 1 } { puts ") "}

    # reg message with session number indicates the sid of a session that
    # was just started from XML or Python script (via reg exec=scriptfile.py)
    if { $session != "" } {
	# The channel passed to here is soon after discarded for
	# sessions that are started from XML or Python scripts. This causes
	# an exception in the GUI when responding back to daemon if the 
	# response is sent after the channel has been destroyed. Setting 
	# the channel to -1 basically disables the GUI response to the daemon, 
	# but it turns out the daemon does not need the response anyway.
	set channel -1
	# assume session string only contains one session number
	connectShutdownSession connect $channel $session $fnhint
	return
    }

    set plugin [pluginByChannel $channel]
    if { [setPluginCapList $plugin $plugin_cap_list] < 0 } {
	return
    }

    # callback to refresh any open dialogs this message may refresh
    pluginsConfigRefreshCallback
}

proc parseConfMessage { data len flags channel } {
    global showAPI node_list MACHINE_TYPES
    set prmsg $showAPI
    set current 0
    set str 0
    set nodenum -1
    set obj ""
    set tflags 0
    set types {}
    set values {}
    set captions {}
    set bitmap {}
    set possible_values {}
    set groups {}
    set opaque {}
    set session ""
    set netid -1

    if { $prmsg==1 } { puts -nonewline "CONF(flags=$flags," }

    # parse each TLV
    while { $current < $len } {
	set typelength [parseTLVHeader $data current]
	set type [lindex $typelength 0]
	set length [lindex $typelength 1]
	set pad [pad_32bit $length]
	if { $length == 0 || $length == "" } {
	    # allow some zero-length string TLVs
            if { $type < 5 || $type > 9 } { break }
	}
	# verbose debugging
	#puts "tlv type=$type length=$length pad=$pad current=$current"
	# TLV data
	switch -exact -- "$type" {
	    1 {
		incr current $pad
		binary scan $data @${current}I nodenum
		if { $prmsg == 1} { puts -nonewline "node=$nodenum/" }
	    }
	    2 {
		binary scan $data @${current}a${length} obj
		if { $prmsg == 1} { puts -nonewline "obj=$obj," }
		incr current $pad
	    }
	    3 {
		binary scan $data @${current}S tflags
		if { $prmsg == 1} { puts -nonewline "cflags=$tflags," }
	    }
	    4 {
		set type 0
		set types {}
		if { $prmsg == 1} { puts -nonewline "types=" }
		# number of 16-bit values
		set types_len $length
		# get each 16-bit type value, add to list
		while {$types_len > 0} {
		    binary scan $data @${current}S type
		    if {$type > 0 && $type < 12} {
			lappend types $type
			if { $prmsg == 1} { puts -nonewline "$type/" }
		    }
		    incr current 2
		    incr types_len -2
		}
		if { $prmsg == 1} { puts -nonewline "," }
		incr current -$length; # length incremented below
		incr current $pad
	    }
	    5 {
		set values {}
		binary scan $data @${current}a${length} vals
		if { $prmsg == 1} { puts -nonewline "vals=$vals," }
		set values [split $vals |]
		incr current $pad
	    }
	    6 {
		set captions {}
		binary scan $data @${current}a${length} capt
		if { $prmsg == 1} { puts -nonewline "capt=$capt," }
		set captions [split $capt |]
		incr current $pad
	    }
	    7 {
		set bitmap {}
		binary scan $data @${current}a${length} bitmap
		if { $prmsg == 1} { puts -nonewline "bitmap," }
		incr current $pad
	    }
	    8 {
		set possible_values {}
		binary scan $data @${current}a${length} pvals
		if { $prmsg == 1} { puts -nonewline "pvals=$pvals," }
		set possible_values [split $pvals |]
		incr current $pad
	    }
	    9 {
		set groups {}
		binary scan $data @${current}a${length} groupsstr
		if { $prmsg == 1} { puts -nonewline "groups=$groupsstr," }
		set groups [split $groupsstr |]
		incr current $pad
	    }
	    10 {
		binary scan $data @${current}a${length} session
		if { $prmsg == 1} { puts -nonewline "session=$session," }
		incr current $pad
	    }
	    35 {
		incr current $pad
		binary scan $data @${current}I netid
		if { $prmsg == 1} { puts -nonewline "netid=$netid/" }
	    }
	    80 {
		set opaque {}
		binary scan $data @${current}a${length} opaquestr
		if { $prmsg == 1} { puts -nonewline "opaque=$opaquestr," }
		set opaque [split $opaquestr |]
		incr current $pad
	    }
	    default {
		if { $prmsg == 1} { puts -nonewline "unknown=" }
		if { $prmsg == 1} { puts -nonewline "$type," }
	    }
	}
	# end switch

	# advance current pointer
	incr current $length
    }

    if { $prmsg == 1 } { puts ") "}

    set objs_ok [concat "services session metadata emane" $MACHINE_TYPES]
    if { $nodenum > -1 } {
	set node "n$nodenum"
    } else {
	set node ""
    }
    # check for node existance
    if { [lsearch $node_list $node] == -1 } {
	if { [lsearch $objs_ok $obj] < 0 } {
	    set msg "Configure message for $obj but node ($node) does"
	    set msg "$msg not exist, dropping."
	    puts $msg
	    return
        }
    } else {
	global $node
    }

    # for handling node services
    # this could be improved, instead of checking for the hard-coded object
    # "services" and opaque data for service customization
    if { $obj == "services" } {
	if { $tflags & 0x2 } { ;# update flag
	    if { $opaque != "" } {
		set services [lindex [split $opaque ":"] 1]
		set services [split $services ","]
		customizeServiceValues n$nodenum $values $services
	    }
	    # TODO: save services config with the node
	} elseif { $tflags & 0x1 } { ;# request flag
	    # TODO: something else
        } else {
	    popupServicesConfig $channel n$nodenum $types $values $captions \
	    			$possible_values $groups $session
	}
	return
    # metadata received upon XML file load
    } elseif { $obj == "metadata" } {
	parseMetaData $values
	return
    # session options received upon XML file load
    } elseif { $obj == "session" && $tflags & 0x2 } {
	setSessionOptions $types $values
	return
    }
    # handle node machine-type profile
    if { [lsearch $MACHINE_TYPES $obj] != -1 } {
	if { $tflags == 0 } {
	    popupNodeProfileConfig $channel n$nodenum $obj $types $values \
	    		$captions $bitmap $possible_values $groups $session \
			$opaque
	} else {
	    puts -nonewline "warning: received Configure message for profile "
	    puts "with unexpected flags!"
	}
	return
    }

    # update the configuration for a node without displaying dialog box
    if { $tflags & 0x2 } {
	if { $obj == "emane" && $node == "" } {
	    set node [lindex [findWlanNodes ""] 0]
        }
	if { $node == "" } {
	    puts "ignoring Configure message for $obj with no node"
	    return
        }
	# this is similar to popupCapabilityConfigApply
	setCustomConfig $node $obj $types $values 0
	if { $obj != "emane" && [nodeType $node] == "wlan"} {
	    set section [list mobmodel coreapi $obj]
	    netconfInsertSection $node $section
	}
    # configuration request - unhandled
    } elseif { $tflags & 0x1 } {
    # configuration response data from our request (from GUI plugin configure)
    } else {
	popupCapabilityConfig $channel n$nodenum $obj $types $values \
				$captions $bitmap $possible_values $groups
    }
}

# process metadata received from Conf Message when loading XML
proc parseMetaData { values } {
    global canvas_list annotation_list execMode g_comments

    foreach value $values {
	# data looks like this: "annotation a1={iconcoords {514.0 132.0...}}"
	lassign [splitKeyValue $value] key object_config
	lassign $key class object
	# metadata with no object name e.g. comments="Comment text"
	if { "$class" == "comments" } {
	    set g_comments $object_config
	    continue
	} elseif { "$class" == "global_options" } {
	    foreach opt $object_config {
		lassign [split $opt =] key value
		setGlobalOption $key $value
	    }
	    continue
	}
	# metadata having class and object name
	if {"$class" == "" || $object == ""} {
	    puts "warning: invalid metadata value '$value'"
	}
	if { "$class" == "canvas" } {
	    if { [lsearch $canvas_list $object] < 0 } {
		lappend canvas_list $object
	    }
	} elseif { "$class" == "annotation" } {
	    if { [lsearch $annotation_list $object] < 0 } {
		lappend annotation_list $object
	    }
	} else {
	    puts "metadata parsing error: unknown object class $class"
	}
	global $object
	set $object $object_config
    }

    if { $execMode == "batch" } { return }
    switchCanvas none
    redrawAll
}

proc parseFileMessage { data len flags channel } {
    global showAPI node_list
    set prmsg $showAPI

    array set tlvnames { 1 num 2 name 3 mode 4 fno 5 type 6 sname \
			10 session 16 data 17 cdata }
    array set tlvsizes { num 4 name -1 mode -3 fno 2 type -1 sname -1 \
			session -1 data -1 cdata -1 }
    array set defvals {	num -1 name "" mode -1 fno -1 type "" sname "" \
			session "" data "" cdata "" }

    if { $prmsg==1 } { puts -nonewline "FILE(flags=$flags," }
    array set vals [parseMessage $data $len $flags [array get tlvnames] \
			[array get tlvsizes] [array get defvals]]
    if { $prmsg } { puts ") "}

    # hook scripts received in File Message
    if { [string range $vals(type) 0 4] == "hook:" } {
	global g_hook_scripts
	set state [string range $vals(type) 5 end]
	lappend g_hook_scripts [list $vals(name) $state $vals(data)]
	return
    }

    # required fields
    foreach t "num name data" {
	if { $vals($t) == $defvals($t) } {
	    puts "Received File Message without $t, dropping."; return;
	}
    }

    # check for node existance
    set node "n$vals(num)"
    if { [lsearch $node_list $node] == -1 } {
	puts "File message but node ($node) does not exist, dropping."
	return
    } else {
	global $node
    }

    # service customization received in File Message
    if { [string range $vals(type) 0 7] == "service:" } {
	customizeServiceFile $node $vals(name) $vals(type) $vals(data) true
    }
}

proc parseEventMessage { data len flags channel } {
    global showAPI eventtypes g_traffic_start_opt execMode node_list
    set prmsg $showAPI
    set current 0
    set nodenum -1
    set eventtype -1
    set eventname ""
    set eventdata ""
    set eventtime ""
    set session ""

    if { $prmsg==1 } { puts -nonewline "EVENT(flags=$flags," }

    # parse each TLV
    while { $current < $len } {
	set typelength [parseTLVHeader $data current]
	set type [lindex $typelength 0]
	set length [lindex $typelength 1]
	if { $length == 0 || $length == "" } { break }
	set pad [pad_32bit $length]
	# verbose debugging
	#puts "tlv type=$type length=$length pad=$pad current=$current"
	# TLV data
	switch -exact -- "$type" {
	    1 {
		incr current $pad
		binary scan $data @${current}I nodenum
		if { $prmsg == 1} { puts -nonewline "node=$nodenum," }
	    }
	    2 {
		incr current $pad
		binary scan $data @${current}I eventtype
		if { $prmsg == 1} { 
		    set typestr ""
		    foreach t [array names eventtypes] {
			if { $eventtypes($t) == $eventtype } {
			    set typestr "-$t"
			    break
			}
		    }
		    puts -nonewline "type=$eventtype$typestr,"
		}
	    }
	    3 {
		binary scan $data @${current}a${length} eventname
		if { $prmsg == 1} { puts -nonewline "name=$eventname," }
		incr current $pad
	    }
	    4 {
		binary scan $data @${current}a${length} eventdata
		if { $prmsg == 1} { puts -nonewline "data=$eventdata," }
		incr current $pad
	    }
	    5 {
		binary scan $data @${current}a${length} eventtime
		if { $prmsg == 1} { puts -nonewline "time=$eventtime," }
		incr current $pad
	    }
	    10 {
		binary scan $data @${current}a${length} session
		if { $prmsg == 1} { puts -nonewline "session=$session," }
		incr current $pad
	    }
	    default {
		if { $prmsg == 1} { puts -nonewline "unknown=" }
		if { $prmsg == 1} { puts -nonewline "$type," }
	    }
	}
	# end switch

	# advance current pointer
	incr current $length
    }

    if { $prmsg == 1 } { puts ") "}

    # TODO: take other actions here based on Event Message
    if { $eventtype == 4 } { ;# entered the runtime state
	if { $g_traffic_start_opt == 1 } { startTrafficScripts }
	if { $execMode == "batch" } {
	    global g_current_session g_abort_session
	    if {$g_abort_session} {
		puts "Current session ($g_current_session) aborted. Disconnecting."
		shutdownSession
	    } else {
		puts "Session running. Session id is $g_current_session. Disconnecting."
	    }
	    exit.real
	}
    } elseif { $eventtype == 6 } { ;# shutdown state
	set name [lindex [getEmulPlugin "*"] 0]
	if { [getAssignedRemoteServers] == "" } {
	    # start a new session if not distributed
	    #   otherwise we need to allow time for node delete messages 
	    #   from other servers
	    pluginConnect $name disconnect 1
	    pluginConnect $name connect 1
	}
    } elseif { $eventtype >= 7 || $eventtype <= 10 } {
	if { [string range $eventname 0 8] == "mobility:" } {
	    set node "n$nodenum"
	    if {[lsearch $node_list $node] == -1} {
		puts "Event message with unknown node %nodenum."
		return
	    }
	    handleMobilityScriptEvent $node $eventtype $eventdata $eventtime
	}
    }
}

proc parseSessionMessage { data len flags channel } {
    global showAPI g_current_session g_session_dialog_hint execMode
    set prmsg $showAPI
    set current 0
    set sessionids {}
    set sessionnames {}
    set sessionfiles {}
    set nodecounts {}
    set sessiondates {}
    set thumbs {}
    set sessionopaque {}

    if { $prmsg==1 } { puts -nonewline "SESSION(flags=$flags," }

    # parse each TLV
    while { $current < $len } {
	set typelength [parseTLVHeader $data current]
	set type [lindex $typelength 0]
	set length [lindex $typelength 1]
	if { $length == 0 || $length == "" } { 
	    puts "warning: zero-length TLV, discarding remainder of message!"
	    break
	}
	set pad [pad_32bit $length]
	# verbose debugging
	#puts "tlv type=$type length=$length pad=$pad current=$current"
	# TLV data
	switch -exact -- "$type" {
	    1 {
		set sessionids {}
		binary scan $data @${current}a${length} sids
		if { $prmsg == 1} { puts -nonewline "sids=$sids," }
		set sessionids [split $sids |]
		incr current $pad
	    }
	    2 {
		set sessionnames {}
		binary scan $data @${current}a${length} snames
		if { $prmsg == 1} { puts -nonewline "names=$snames," }
		set sessionnames [split $snames |]
		incr current $pad
	    }
	    3 {
		set sessionfiles {}
		binary scan $data @${current}a${length} sfiles
		if { $prmsg == 1} { puts -nonewline "files=$sfiles," }
		set sessionfiles [split $sfiles |]
		incr current $pad
	    }
	    4 {
		set nodecounts {}
		binary scan $data @${current}a${length} ncs
		if { $prmsg == 1} { puts -nonewline "ncs=$ncs," }
		set nodecounts [split $ncs |]
		incr current $pad
	    }
	    5 {
		set sessiondates {}
		binary scan $data @${current}a${length} sdates
		if { $prmsg == 1} { puts -nonewline "dates=$sdates," }
		set sessiondates [split $sdates |]
		incr current $pad
	    }
	    6 {
		set thumbs {}
		binary scan $data @${current}a${length} th
		if { $prmsg == 1} { puts -nonewline "thumbs=$th," }
		set thumbs [split $th |]
		incr current $pad
	    }
	    10 {
		set sessionopaque {}
		binary scan $data @${current}a${length} sessionopaque
		if { $prmsg == 1} { puts -nonewline "$sessionopaque," }
		incr current $pad
	    }
	    default {
		if { $prmsg == 1} { puts -nonewline "unknown=" }
		if { $prmsg == 1} { puts -nonewline "$type," }
	    }
	}
	# end switch

	# advance current pointer
	incr current $length
    }

    if { $prmsg == 1 } { puts ") "}

    if {$g_current_session == 0} {
	# set the current session to the channel port number
	set current_session [lindex [fconfigure $channel -sockname] 2]
    } else {
	set current_session $g_current_session
    }

    if {[lsearch $sessionids $current_session] == -1} {
	puts -nonewline "*** warning: current session ($g_current_session) "
	puts "not found in session list: $sessionids"
    }

    set orig_session_choice $g_current_session
    set g_current_session $current_session
    setGuiTitle ""

    if {$execMode == "closebatch"} {
	# we're going to close some session, so this is expected
	global g_session_choice

	if {[lsearch $sessionids $g_session_choice] == -1} {
	    puts -nonewline "*** warning: current session ($g_session_choice) "
	    puts "not found in session list: $sessionids"
	} else {
	    set flags 0x2 ;# delete flag
	    set sid $g_session_choice
	    set name ""
	    set f ""
	    set nodecount ""
	    set thumb ""
	    set user ""
	    sendSessionMessage $channel $flags $sid $name $f $nodecount $thumb $user

	    puts "Session shutdown message sent."
	}
	exit.real
    }

    if {$orig_session_choice == 0 && [llength $sessionids] == 1} {
	# we just started up and only the current session exists
        set g_session_dialog_hint 0
	return
    }

    if {$execMode == "batch"} {
        puts "Another session is active."
        exit.real
    }

    if { $g_session_dialog_hint } {
	popupSessionConfig $channel $sessionids $sessionnames $sessionfiles \
	    $nodecounts $sessiondates $thumbs $sessionopaque
    }
    set g_session_dialog_hint 0
}

# parse message TLVs given the possible TLV names and sizes
# default values are supplied in defaultvals, parsed values are returned
proc parseMessage { data len flags tlvnamesl tlvsizesl defaultvalsl } {
    global showAPI
    set prmsg $showAPI

    array set tlvnames $tlvnamesl
    array set tlvsizes $tlvsizesl
    array set vals $defaultvalsl ;# this array is returned

    set current 0

    while { $current < $len } {
	set typelength [parseTLVHeader $data current]
	set type [lindex $typelength 0]
	set length [lindex $typelength 1]
	if { $length == 0 || $length == "" } { break }
	set pad [pad_32bit $length]

	if {![info exists tlvnames($type)] } { ;# unknown TLV type
	    if { $prmsg } { puts -nonewline "unknown=$type," }
	    incr current $length
	    continue
	}
	set tlvname $tlvnames($type)
	set size $tlvsizes($tlvname)
	# 32-bit and 64-bit vals pre-padded
	if { $size == 4 || $size == 8 } { incr current $pad }
	# read TLV data depending on size
	switch -exact -- "$size" {
	2 { binary scan $data @${current}S vals($tlvname) }
	4 { binary scan $data @${current}I vals($tlvname) }
	8 { binary scan $data @${current}W vals($tlvname) }
	16 { binary scan $data @${current}c16 vals($tlvname) }
	-1 { binary scan $data @${current}a${length} vals($tlvname) }
	}
	if { $size == -1 } { incr current $pad } ;# string vals post-padded
	if { $type == 6 } { incr current $pad } ;# 128-bit vals post-padded
	incr current $length

	if { $prmsg } { puts -nonewline "$tlvname=$vals($tlvname)," }
    }
    return [array get vals]
}

proc parseExceptionMessage { data len flags channel } {
    global showAPI
    set prmsg $showAPI

    array set typenames { 1 num 2 sess 3 level 4 src 5 date 6 txt 10 opaque }
    array set typesizes { num 4 sess -1 level 2 src -1 date -1 txt -1 \
			  opaque -1 }
    array set defvals { num -1 sess "" level -1 src "" date "" txt "" opaque ""}

    if { $prmsg==1 } { puts -nonewline "EXCEPTION(flags=$flags," }
    array set vals [parseMessage $data $len $flags [array get typenames] \
    			[array get typesizes] [array get defvals]]
    if { $prmsg == 1 } { puts ") "}

    if { $vals(level) == $defvals(level) } {
	puts "Exception Message received without an exception level."; return;
    }

    receiveException [array get vals]
}

proc sendNodePosMessage { channel node nodeid x y wlanid force } {
    global showAPI
    set prmsg $showAPI

    if { $channel == -1 } {
        set channel [lindex [getEmulPlugin $node] 2]
	if { $channel == -1 } { return }
    }
    set node_num [string range $node 1 end]
    set x [format "%u" [expr int($x)]]
    set y [format "%u" [expr int($y)]]
    set len [expr 8+4+4] ;# node number, x, y
    if {$nodeid > -1} { incr len 8 }
    if {$wlanid > -1} { incr len 8 }
    if {$force == 1 } { set crit 0x4 } else { set crit 0x0 }
    #puts "sending [expr $len+4] bytes: $nodeid $x $y $wlanid"
    if { $prmsg == 1 } { 
	puts -nonewline ">NODE(flags=$crit,$node,x=$x,y=$y" }
    set msg [binary format ccSc2sIc2Sc2S \
			1 $crit $len \
			{1 4} 0 $node_num \
			{0x20 2} $x \
			{0x21 2} $y
	    ]

    set msg2 ""
    set msg3 ""
    if { $nodeid > -1 } {
	if { $prmsg == 1 } { puts -nonewline ",emuid=$nodeid" }
	set msg2 [binary format c2sI {0x23 4} 0 $nodeid]
    }
    if { $wlanid > -1 } {
	if { $prmsg == 1 } { puts -nonewline ",netid=$wlanid" }
	set msg3 [binary format c2sI {0x24 4} 0 $wlanid]
    }

    if { $prmsg == 1 } { puts ")" }
    puts -nonewline $channel $msg$msg2$msg3
    flushChannel channel "Error sending node position"
}

# build a new node
proc sendNodeAddMessage { channel node } {
    global showAPI CORE_DATA_DIR
    set prmsg $showAPI
    set len [expr {8+8+4+4}]; # node number, type, x, y
    set ipv4 0
    set ipv6 0
    set macstr ""
    set wireless 0

    # type, name
    set type [getNodeTypeAPI $node]
    set model [getNodeModel $node]
    set model_len [string length $model]
    set model_pad_len [pad_32bit $model_len]
    set model_pad [binary format x$model_pad_len]
    set name [getNodeName $node]
    set name_len [string length $name]
    set name_pad_len [pad_32bit $name_len]
    set name_pad [binary format x$name_pad_len]
    incr len [expr { 2+$name_len+$name_pad_len}]
    if {$model_len > 0} { incr len [expr {2+$model_len+$model_pad_len }] }
    set node_num [string range $node 1 end]

    # fixup node type for EMANE-enabled WLAN nodes
    set opaque ""
    if { [isEmane $node] } { set type 0xA }

    # emulation server (node location)
    set emusrv [getNodeLocation $node]
    set emusrv_len [string length $emusrv]
    set emusrv_pad_len [pad_32bit $emusrv_len]
    set emusrv_pad [binary format x$emusrv_pad_len]
    if { $emusrv_len > 0 } { incr len [expr {2+$emusrv_len+$emusrv_pad_len } ] }

    # canvas
    set canv [getNodeCanvas $node]
    if { $canv != "c1" } {
	set canv [string range $canv 1 end] ;# convert "c2" to "2"
	incr len 4
    } else {
	set canv ""
    }
    
    # services 
    set svc [getNodeServices $node false]
    set svc [join $svc "|"]
    set svc_len [string length $svc]
    set svc_pad_len [pad_32bit $svc_len]
    set svc_pad [binary format x$svc_pad_len]
    if { $svc_len > 0 } { incr len [expr {2+$svc_len+$svc_pad_len } ] }

    # icon
    set icon [getCustomImage $node]
    if { [file dirname $icon] == "$CORE_DATA_DIR/icons/normal" } {
	set icon [file tail $icon] ;# don't include standard icon path
    }
    set icon_len [string length $icon]
    set icon_pad_len [pad_32bit $icon_len]
    set icon_pad [binary format x$icon_pad_len]
    if { $icon_len > 0 } { incr len [expr {2+$icon_len+$icon_pad_len} ] }

    # opaque data
    set opaque_len [string length $opaque]
    set opaque_pad_len [pad_32bit $opaque_len]
    set opaque_pad [binary format x$opaque_pad_len]
    if { $opaque_len > 0 } { incr len [expr {2+$opaque_len+$opaque_pad_len} ] }

    # length must be calculated before this
    if { $prmsg == 1 } {
	puts -nonewline ">NODE(flags=add/str,$node,type=$type,$name,"
    }
    set msg [binary format c2Sc2sIc2sIcc \
		{0x1 0x11} $len \
		{0x1 4} 0 $node_num \
		{0x2 4} 0 $type \
		0x3 $name_len ]
    puts -nonewline $channel $msg$name$name_pad

    # IPv4 address
    if { $ipv4 > 0 } {
	if { $prmsg == 1 } { puts -nonewline "$ipv4str," }
	set msg [binary format c2sI {0x4 4} 0 $ipv4]
	puts -nonewline $channel $msg
    }

    # MAC address
    if { $macstr != "" } {
	if { $prmsg == 1 } { puts -nonewline "$macstr," }
	set mac [join [split $macstr ":"] ""]
	puts -nonewline $channel [binary format c2x2W {0x5 8} 0x$mac]
    }
    
    # IPv6 address
    if { $ipv6 != 0 } {
	if { $prmsg == 1 } { puts -nonewline "$ipv6str," }
	set msg [binary format c2 {0x6 16} ]
	puts -nonewline $channel $msg
	foreach ipv6w [split $ipv6 ":"] {
	    set msg [binary format S 0x$ipv6w]
	    puts -nonewline $channel $msg
	}
	puts -nonewline $channel [binary format x2]; # 2 bytes padding
    }

    # model type
    if { $model_len > 0 } {
	set mh [binary format cc 0x7 $model_len]
	puts -nonewline $channel $mh$model$model_pad
	if { $prmsg == 1 } { puts -nonewline "m=$model," }
    }

    # emulation server
    if { $emusrv_len > 0 } {
	puts -nonewline $channel [binary format cc 0x8 $emusrv_len]
	puts -nonewline $channel $emusrv$emusrv_pad
	if { $prmsg == 1 } { puts -nonewline "srv=$emusrv," }
    }

    # X,Y coordinates
    set coords [getNodeCoords $node]
    set x [format "%u" [expr int([lindex $coords 0])]]
    set y [format "%u" [expr int([lindex $coords 1])]]
    set msg [binary format c2Sc2S {0x20 2} $x {0x21 2} $y]
    puts -nonewline $channel $msg

    # canvas
    if { $canv != "" } {
	if { $prmsg == 1 } { puts -nonewline "canvas=$canv," }
	set msg [binary format c2S {0x22 2} $canv]
	puts -nonewline $channel $msg
    }

    if { $prmsg == 1 } { puts -nonewline "x=$x,y=$y" }

    # services
    if { $svc_len > 0 } {
	puts -nonewline $channel [binary format cc 0x25 $svc_len]
	puts -nonewline $channel $svc$svc_pad
	if { $prmsg == 1 } { puts -nonewline ",svc=$svc" }
    }

    # icon
    if { $icon_len > 0 } {
	puts -nonewline $channel [binary format cc 0x42 $icon_len]
	puts -nonewline $channel $icon$icon_pad
	if { $prmsg == 1 } { puts -nonewline ",icon=$icon" }
    }

    # opaque data
    if { $opaque_len > 0 } {
	puts -nonewline $channel [binary format cc 0x50 $opaque_len]
	puts -nonewline $channel $opaque$opaque_pad
	if { $prmsg == 1 } { puts -nonewline ",opaque=$opaque" }
    }

    if { $prmsg == 1 } { puts ")" }

    flushChannel channel "Error sending node add"
}

# delete a node
proc sendNodeDelMessage { channel node } {
    global showAPI
    set prmsg $showAPI
    set len 8; # node number
    set node_num [string range $node 1 end]

    if { $prmsg == 1 } { puts ">NODE(flags=del/str,$node_num)" }
    set msg [binary format c2Sc2sI \
		{0x1 0x12} $len \
		{0x1 4} 0 $node_num ]
    puts -nonewline $channel $msg
    flushChannel channel "Error sending node delete"
}

# send a message to build, modify, or delete a link
# type should indicate add/delete/link/unlink
proc sendLinkMessage { channel link type {sendboth true} } {
    global showAPI
    set prmsg $showAPI
    
    set node1 [lindex [linkPeers $link] 0]
    set node2 [lindex [linkPeers $link] 1]
    set if1 [ifcByPeer $node1 $node2]; set if2 [ifcByPeer $node2 $node1]
    if { [nodeType $node1] == "pseudo" } { return } ;# never seems to occur
    if { [nodeType $node2] == "pseudo" } {
	set mirror2 [getLinkMirror $node2]
	set node2 [getNodeName $node2]
	if { [string range $node1 1 end] > [string range $node2 1 end] } {
	    return ;# only send one link message (for two pseudo-links)
	}
	set if2 [ifcByPeer $node2 $mirror2]
    }
    set node1_num [string range $node1 1 end]
    set node2_num [string range $node2 1 end]

    # flag for sending unidirectional link messages
    set uni 0
    if { $sendboth && [isLinkUni $link] } {
	set uni 1
    }

    # set flags and link message type from supplied type parameter
    set flags 0
    set ltype 1 ;# add/delete a link (not wireless link/unlink)
    set netid -1
    if { $type == "add" || $type == "link" } {
	set flags 1
    } elseif { $type == "delete" || $type == "unlink" } {
	set flags 2
    }
    if { $type == "link" || $type == "unlink" } {
	set ltype 0 ;# a wireless link/unlink event
	set tmp [getLinkOpaque $link net]
	if { $tmp != "" } { set netid [string range $tmp 1 end] }
    }

    set key ""
    if { [nodeType $node1] == "tunnel" } {
	set key [netconfFetchSection $node1 "tunnel-key"]
	if { $key == "" } { set key 1 }
    }
    if {[nodeType $node2] == "tunnel" } {
	set key [netconfFetchSection $node2 "tunnel-key"]
	if { $key == "" } { set key 1 }
    }

    if { $prmsg == 1 } {
	puts -nonewline ">LINK(flags=$flags,$node1_num-$node2_num,"
    }

    # len = node1num, node2num, type
    set len [expr {8+8+8}]
    set delay [getLinkDelay $link]
    if { $delay == "" } { set delay 0 }
    set jitter [getLinkJitter $link]
    if { $jitter == "" } { set jitter 0 }
    set bw [getLinkBandwidth $link]
    if { $bw == "" } { set bw 0 }
    set per [getLinkBER $link]; # PER and BER
    if { $per == "" } { set per 0 }
    set per_len 0
    set per_msg [buildStringTLV 0x5 $per per_len]
    set dup [getLinkDup $link]
    if { $dup == "" } { set dup 0 }
    set dup_len 0
    set dup_msg [buildStringTLV 0x6 $dup dup_len]
    if { $type != "delete" } {
        incr len [expr {12+12+$per_len+$dup_len+12}] ;# delay,bw,per,dup,jitter
	if {$prmsg==1 } {
	    puts -nonewline "$delay,$bw,$per,$dup,$jitter,"
	}
    }
    # TODO: mer, burst, mburst
    if { $prmsg == 1 } { puts -nonewline "type=$ltype," }
    if { $uni } {
	incr len 4
	if { $prmsg == 1 } { puts -nonewline "uni=$uni," }
    }
    if { $netid > -1 } {
	incr len 8
	if { $prmsg == 1 } { puts -nonewline "netid=$netid," }
    }
    if { $key != "" } {
	incr len 8
	if { $prmsg == 1 } { puts -nonewline "key=$key," }
    }

    set if1num [ifcNameToNum $if1]; set if2num [ifcNameToNum $if2]
    set if1ipv4 0; set if2ipv4 0; set if1ipv6 ""; set if2ipv6 "";
    set if1ipv4mask 0; set if2ipv4mask 0;
    set if1ipv6mask ""; set if2ipv6mask ""; set if1mac ""; set if2mac "";

    if { $if1num >= 0 && ([[typemodel $node1].layer] == "NETWORK" || \
	 [nodeType $node1] == "tunnel") } {
	incr len 4
	if { $prmsg == 1 } { puts -nonewline "if1n=$if1num," }
	if { $type != "delete" } {
	    getIfcAddrs $node1 $if1 if1ipv4 if1ipv6 if1mac if1ipv4mask \
	    		if1ipv6mask len
        }
    }
    if { $if2num >= 0 && ([[typemodel $node2].layer] == "NETWORK" || \
	 [nodeType $node2] == "tunnel") } {
	incr len 4
	if { $prmsg == 1 } { puts -nonewline "if2n=$if2num," }
	if { $type != "delete" } {
	    getIfcAddrs $node2 $if2 if2ipv4 if2ipv6 if2mac if2ipv4mask \
	    		if2ipv6mask len
	}
    }

    # start building the binary message on channel
    # length must be calculated before this
    set msg [binary format ccSc2sIc2sI \
		{0x2} $flags $len \
		{0x1 4} 0 $node1_num \
		{0x2 4} 0 $node2_num ]
    puts -nonewline $channel $msg

    if { $type != "delete" } {
	puts -nonewline $channel [binary format c2sW {0x3 8} 0 $delay]
	puts -nonewline $channel [binary format c2sW {0x4 8} 0 $bw]
	puts -nonewline $channel $per_msg
	puts -nonewline $channel $dup_msg
	puts -nonewline $channel [binary format c2sW {0x7 8} 0 $jitter]
    }
    # TODO: mer, burst, mburst

    # link type
    puts -nonewline $channel [binary format c2sI {0x20 4} 0 $ltype]

    # unidirectional flag
    if { $uni } {
	puts -nonewline $channel [binary format c2S {0x22 2} $uni]
    }

    # network ID
    if { $netid > -1 } {
	puts -nonewline $channel [binary format c2sI {0x24 4} 0 $netid]
    }

    if { $key != "" } {
	puts -nonewline $channel [binary format c2sI {0x25 4} 0 $key]
    }

    # interface 1 info
    if { $if1num >= 0 && ([[typemodel $node1].layer] == "NETWORK" || \
	 [nodeType $node1] == "tunnel") } {
	puts -nonewline $channel [ binary format c2S {0x30 2} $if1num ]
    }
    if { $if1ipv4 > 0 } { puts -nonewline $channel [binary format c2sIc2S \
				{0x31 4} 0 $if1ipv4 {0x32 2} $if1ipv4mask ] }
    if { $if1mac != "" } {
	set if1mac [join [split $if1mac ":"] ""]
	puts -nonewline $channel [binary format c2x2W {0x33 8} 0x$if1mac]
    }
    if {$if1ipv6 != ""} { puts -nonewline $channel [binary format c2 {0x34 16}]
	foreach ipv6w [split $if1ipv6 ":"] { puts -nonewline $channel \
						[binary format S 0x$ipv6w] }
	puts -nonewline $channel [binary format x2c2S {0x35 2} $if1ipv6mask] }

    # interface 2 info
    if { $if2num >= 0 && ([[typemodel $node2].layer] == "NETWORK" || \
	 [nodeType $node2] == "tunnel") } {
	puts -nonewline $channel [ binary format c2S {0x36 2} $if2num ]
    }
    if { $if2ipv4 > 0 } { puts -nonewline $channel [binary format c2sIc2S \
				{0x37 4} 0 $if2ipv4 {0x38 2} $if2ipv4mask ] }
    if { $if2mac != "" } {
	set if2mac [join [split $if2mac ":"] ""]
	puts -nonewline $channel [binary format c2x2W {0x39 8} 0x$if2mac]
    }
    if {$if2ipv6 != ""} { puts -nonewline $channel [binary format c2 {0x40 16}]
	foreach ipv6w [split $if2ipv6 ":"] { puts -nonewline $channel \
						[binary format S 0x$ipv6w] }
	puts -nonewline $channel [binary format x2c2S {0x41 2} $if2ipv6mask] }

    if { $prmsg==1 } { puts ")" }
    flushChannel channel "Error sending link message"

    ##########################################################
    # send a second Link Message for unidirectional link effects
    if { $uni < 1 } {
	return
    }
    # first calculate length and possibly print the message
    set flags 0
    if { $prmsg == 1 } {
        puts -nonewline ">LINK(flags=$flags,$node2_num-$node1_num,"
    }
    set len [expr {8+8+8}] ;# len = node2num, node1num (swapped), type
    set delay [getLinkDelay $link up]
    if { $delay == "" } { set delay 0 }
    set jitter [getLinkJitter $link up]
    if { $jitter == "" } { set jitter 0 }
    set bw [getLinkBandwidth $link up]
    if { $bw == "" } { set bw 0 }
    set per [getLinkBER $link up]; # PER and BER
    if { $per == "" } { set per 0 }
    set per_len 0
    set per_msg [buildStringTLV 0x5 $per per_len]
    set dup [getLinkDup $link up]
    if { $dup == "" } { set dup 0 }
    set dup_len 0
    set dup_msg [buildStringTLV 0x6 $dup dup_len]
    incr len [expr {12+12+$per_len+$dup_len+12}] ;# delay,bw,per,dup,jitter
    if {$prmsg==1 } {
        puts -nonewline "$delay,$bw,$per,$dup,$jitter,"
    }
    if { $prmsg == 1 } { puts -nonewline "type=$ltype," }
    incr len 4 ;# unidirectional flag
    if { $prmsg == 1 } { puts -nonewline "uni=$uni," }
    # note that if1num / if2num are reversed here due to reversed node nums
    if { $if2num >= 0 && ([[typemodel $node2].layer] == "NETWORK" || \
         [nodeType $node2] == "tunnel") } {
        incr len 4
        if { $prmsg == 1 } { puts -nonewline "if1n=$if2num," }
    }
    if { $if1num >= 0 && ([[typemodel $node1].layer] == "NETWORK" || \
         [nodeType $node1] == "tunnel") } {
        incr len 4
        if { $prmsg == 1 } { puts -nonewline "if2n=$if1num," }
    }
    # build and send the link message
    set msg [binary format ccSc2sIc2sI \
    	{0x2} $flags $len \
    	{0x1 4} 0 $node2_num \
    	{0x2 4} 0 $node1_num ]
    puts -nonewline $channel $msg
    puts -nonewline $channel [binary format c2sW {0x3 8} 0 $delay]
    puts -nonewline $channel [binary format c2sW {0x4 8} 0 $bw]
    puts -nonewline $channel $per_msg
    puts -nonewline $channel $dup_msg
    puts -nonewline $channel [binary format c2sW {0x7 8} 0 $jitter]
    puts -nonewline $channel [binary format c2sI {0x20 4} 0 $ltype]
    puts -nonewline $channel [binary format c2S {0x22 2} $uni]
    if { $if2num >= 0 && ([[typemodel $node2].layer] == "NETWORK" || \
         [nodeType $node2] == "tunnel") } {
        puts -nonewline $channel [ binary format c2S {0x30 2} $if2num ]
    }
    if { $if1num >= 0 && ([[typemodel $node1].layer] == "NETWORK" || \
         [nodeType $node1] == "tunnel") } {
        puts -nonewline $channel [ binary format c2S {0x36 2} $if1num ]
    }
    if { $prmsg==1 } { puts ")" }
    flushChannel channel "Error sending link message"
}

# helper to get IPv4, IPv6, MAC address and increment length
# also prints TLV-style addresses if showAPI is true
proc getIfcAddrs { node ifc ipv4p ipv6p macp ipv4maskp ipv6maskp lenp } {
    global showAPI
    upvar $ipv4p ipv4
    upvar $ipv6p ipv6
    upvar $macp mac
    upvar $ipv4maskp ipv4mask
    upvar $ipv6maskp ipv6mask
    upvar $lenp len

    if { $ifc == "" || $node == "" } { return }

    # IPv4 address
    set ipv4str [getIfcIPv4addr $node $ifc]
    if {$ipv4str != ""} { 
	set ipv4 [lindex [split $ipv4str /] 0]
	if { [info exists ipv4mask ] } {
	    set ipv4mask [lindex [split $ipv4str / ] 1]
	    incr len 12; # 8 addr + 4 mask
	    if { $showAPI == 1 } { puts -nonewline "$ipv4str," }
	} else {
	    incr len 8; # 8 addr
	    if { $showAPI == 1 } { puts -nonewline "$ipv4," }
	}
	set ipv4 [stringToIPv4 $ipv4]; # convert to integer
    }

    # IPv6 address
    set ipv6str [getIfcIPv6addr $node $ifc]
    if {$ipv6str != ""} { 
	set ipv6 [lindex [split $ipv6str /] 0]
	if { [info exists ipv6mask ] } {
	    set ipv6mask [lindex [split $ipv6str / ] 1]
	    incr len 24; # 20 addr + 4 mask
	    if { $showAPI == 1 } { puts -nonewline "$ipv6str," }
	} else {
	    incr len 20; # 20 addr
	    if { $showAPI == 1 } { puts -nonewline "$ipv6," }
	}
	set ipv6 [expandIPv6 $ipv6]; # convert to long string
    }

    # MAC address (from conf if there, otherwise generated)
    if { [info exists mac] } {
	set mac [lindex [getIfcMacaddr $node $ifc] 0]
	if {$mac == ""} {
	    set mac [getNextMac]
	}
	if { $showAPI == 1 } { puts -nonewline "$mac," }
	incr len 12;
    }
}

#
# Register Message: (registration types)
# This is a simple Register Message, types is an array of 
#  <module TLV, string> tuples.
proc sendRegMessage { channel flags types_list } {
    global showAPI regtypes
    set prmsg $showAPI

    if { $channel == -1 || $channel == "" } {
	set plugin [lindex [getEmulPlugin "*"] 0]
	set channel [pluginConnect $plugin connect true]
	if { $channel == -1 } { return }
    }
    set len 0
    array set types $types_list

    # array names output is unreliable, sort it
    set type_list [lsort -dict [array names types]]
    foreach type $type_list {
	if { ![info exists regtypes($type)] } {
	    puts "sendRegMessage: unknown registration type '$type'"
	    return -1
	}
	set str_$type $types($type)
	set str_${type}_len [string length [set str_$type]]
	set str_${type}_pad_len [pad_32bit [set str_${type}_len]]
	set str_${type}_pad [binary format x[set str_${type}_pad_len]]
	incr len [expr { 2 + [set str_${type}_len] + [set str_${type}_pad_len]}]
    }

    if { $prmsg == 1 } { puts ">REG($type_list)" }
    # message header
    set msg1 [binary format ccS 4 $flags $len]
    puts -nonewline $channel $msg1

    foreach type $type_list {
	set type_num $regtypes($type)
	set tlvh [binary format cc $type_num [set str_${type}_len]]
	puts -nonewline $channel $tlvh[set str_${type}][set str_${type}_pad]
    }

    flushChannel channel "Error: API channel was closed"
}

#
# Configuration Message: (object, type flags, node)
# This is a simple Configuration Message containing flags
proc sendConfRequestMessage { channel node model flags netid opaque } {
    global showAPI
    set prmsg $showAPI

    if { $channel == -1 || $channel == "" } {
	set pname [lindex [getEmulPlugin $node] 0]
	set channel [pluginConnect $pname connect true]
	if { $channel == -1 } { return }
    }

    set model_len [string length $model]
    set model_pad_len [pad_32bit $model_len]
    set model_pad [binary format x$model_pad_len ]
    set len [expr {4+2+$model_len+$model_pad_len}]
    # optional network ID to provide Netgraph mapping
    if { $netid != -1 } { incr len 8 }
    # convert from node name to number
    if { [string is alpha [string range $node 0 0]] } {
	set node [string range $node 1 end]
    }

    if { $node > 0 } { incr len 8 }
    # add a session number when configuring services
    set session ""
    set session_len 0
    set session_pad_len 0
    set session_pad ""
    if { $node <= 0 && $model == "services" } {
	global g_current_session
	set session [format "0x%x" $g_current_session]
	set session_len [string length $session]
	set session_pad_len [pad_32bit $session_len]
	set session_pad [binary format x$session_pad_len]
	incr len [expr {2 + $session_len + $session_pad_len}]
    }
    # opaque data - used when custom configuring services
    set opaque_len 0
    set msgop [buildStringTLV 0x50 $opaque opaque_len]
    if { $opaque_len > 0 } { incr len $opaque_len }

    if { $prmsg == 1 } {
	puts -nonewline ">CONF(flags=0,"
	if { $node > 0 } { puts -nonewline "node=$node," }
	puts -nonewline "obj=$model,cflags=$flags"
	if { $session != "" } { puts -nonewline ",session=$session" }
	if { $netid > -1 } { puts -nonewline ",netid=$netid" }
	if { $opaque_len > 0 } { puts -nonewline ",opaque=$opaque" }
	puts ") request"
    }
    # header, node node number, node model header
    set msg1 [binary format c2S {5 0} $len ]
    set msg1b ""
    if { $node > 0 } { set msg1b [binary format c2sI {1 4} 0 $node] }
    set msg1c [binary format cc 2 $model_len]
    # request flag
    set msg2 [binary format c2S {3 2} $flags ]
    # session number
    set msg3 ""
    if { $session != "" } {
        set msg3 [binary format cc 0x0A $session_len]
	set msg3 $msg3$session$session_pad
    }
    # network ID
    set msg4 ""
    if { $netid != -1 } {
        set msg4 [binary format c2sI {0x23 4} 0 0x$netid ]
    }

    #catch {puts -nonewline $channel $msg1$model$model_pad$msg2$msg3$msg4$msg5} 
    puts -nonewline $channel $msg1$msg1b$msg1c$model$model_pad$msg2$msg3$msg4
    if { $opaque_len > 0 } { puts -nonewline $channel $msgop }

    flushChannel channel "Error: API channel was closed"
}

#
# Configuration Message: (object, type flags, node, types, values)
# This message is more complicated to build because of the list of
# data types and values.
proc sendConfReplyMessage { channel node model types values opaque } {
    global showAPI
    set prmsg $showAPI
    # convert from node name to number
    if { [string is alpha [string range $node 0 0]] } {
	set node [string range $node 1 end]
    }
    # add a session number when configuring services
    set session ""
    set session_len 0
    set session_pad_len 0
    set session_pad ""
    if { $node <= 0 && $model == "services" && $opaque == "" } {
	global g_current_session
	set session [format "0x%x" $g_current_session]
	set session_len [string length $session]
	set session_pad_len [pad_32bit $session_len]
	set session_pad [binary format x$session_pad_len]
	incr len [expr {$session_len + $session_pad_len}]
    }

    if { $prmsg == 1 } {
	puts -nonewline ">CONF(flags=0,"
	if {$node > -1 } { puts -nonewline "node=$node," }
	puts -nonewline "obj=$model,cflags=0"
	if {$session != "" } { puts -nonewline "session=$session," }
	if {$opaque != "" } { puts -nonewline "opaque=$opaque," }
	puts "types=<$types>,values=<$values>) reply"
    }

    # types (16-bit values) and values
    set n 0
    set type_len [expr {[llength $types] * 2} ]
    set type_data [binary format cc 4 $type_len]
    set value_data ""
    foreach type $types {
	set t [binary format S $type]
	set type_data $type_data$t
	set val [lindex $values $n]
	if { $val == "" } {
	    #puts "warning: empty value $n (type=$type)"
	    if { $type != 10 } { set val 0 }
	}
	incr n
	lappend value_data $val
    }; # end foreach
    set value_len 0
    set value_data [join $value_data |]
    set msgval [buildStringTLV 0x5 $value_data value_len]
    set type_pad_len [pad_32bit $type_len]
    set type_pad [binary format x$type_pad_len ]
    set model_len [string length $model]
    set model_pad_len [pad_32bit $model_len]
    set model_pad [binary format x$model_pad_len ]
    # opaque data - used when custom configuring services
    set opaque_len 0
    set msgop [buildStringTLV 0x50 $opaque opaque_len]

    # 4 bytes header, model TLV
    set len [expr 4+2+$model_len+$model_pad_len]
    if { $node > -1 } { incr len 8 }
    # session number
    set msg3 ""
    if { $session != "" } {
	incr len [expr {2 + $session_len + $session_pad_len }] 
        set msg3 [binary format cc 0x0A $session_len]
	set msg3 $msg3$session$session_pad
    }
    if { $opaque_len > 0 } { incr len $opaque_len }
    # types TLV, values TLV
    incr len [expr {2 + $type_len + $type_pad_len + $value_len}]

    # header, node node number, node model header
    set msgh [binary format c2S {5 0} $len ]
    set msgwl ""
    if { $node > -1 } { set msgwl [binary format c2sI {1 4} 0 $node] }
    set model_hdr [binary format cc 2 $model_len]
    # no flags
    set type_hdr [binary format c2S {3 2} 0 ]
    set msg $msgh$msgwl$model_hdr$model$model_pad$type_hdr$type_data$type_pad
    set msg $msg$msgval$msg3
    puts -nonewline $channel $msg
    if { $opaque_len > 0 } { puts -nonewline $channel $msgop }
    flushChannel channel "Error sending conf reply"
}

# Event Message
proc sendEventMessage { channel type nodenum name data flags } {
    global showAPI eventtypes
    set prmsg $showAPI

    set len [expr 8] ;# event type
    if {$nodenum > -1} { incr len 8 }
    set name_len [string length $name]
    set name_pad_len [pad_32bit $name_len]
    if { $name_len > 0 } { incr len [expr {2 + $name_len + $name_pad_len}] }
    set data_len [string length $data]
    set data_pad_len [pad_32bit $data_len]
    if { $data_len > 0 } { incr len [expr {2 + $data_len + $data_pad_len}] }

    if { $prmsg == 1 } { 
	puts -nonewline ">EVENT(flags=$flags," }
    set msg [binary format ccS 8 $flags $len ] ;# message header

    set msg2 ""
    if { $nodenum > -1 } {
	if { $prmsg == 1 } { puts -nonewline "node=$nodenum," }
	set msg2 [binary format c2sI {0x01 4} 0 $nodenum]
    }
    if { $prmsg == 1} { 
	set typestr ""
	foreach t [array names eventtypes] {
	    if { $eventtypes($t) == $type } { set typestr "-$t"; break }
	}
	puts -nonewline "type=$type$typestr,"
    }
    set msg3 [binary format c2sI {0x02 4} 0 $type]
    set msg4 ""
    set msg5 ""
    if { $name_len > 0 } {
	if { $prmsg == 1 } { puts -nonewline "name=$name," }
	set msg4 [binary format cc 0x03 $name_len ]
        set name_pad [binary format x$name_pad_len ]
	set msg5 $name$name_pad
    }
    set msg6 ""
    set msg7 ""
    if { $data_len > 0 } {
	if { $prmsg == 1 } { puts -nonewline "data=$data" }
	set msg6 [binary format cc 0x04 $data_len ]
        set data_pad [binary format x$data_pad_len ]
	set msg7 $data$data_pad
    }

    if { $prmsg == 1 } { puts ")" }
    puts -nonewline $channel $msg$msg2$msg3$msg4$msg5$msg6$msg7
    flushChannel channel "Error sending Event type=$type"
}


#  deploy working configuration using CORE API
#   Deploys a current working configuration. It creates all the 
#   nodes and link as defined in configuration file.
proc deployCfgAPI { sock } {
    global eid
    global node_list link_list annotation_list canvas_list
    global mac_byte4 mac_byte5
    global execMode
    global ngnodemap
    global mac_addr_start
    global deployCfgAPI_lock
    global eventtypes
    global g_comments

    if { ![info exists deployCfgAPI_lock] } { set deployCfgAPI_lock 0 }
    if { $deployCfgAPI_lock } {
    	puts "***error: deployCfgAPI called while deploying config"
	return
    }

    set deployCfgAPI_lock 1 ;# lock

    set mac_byte4 0
    set mac_byte5 0
    if { [info exists mac_addr_start] } { set mac_byte5 $mac_addr_start }
    set t_start [clock seconds]

    global systype
    set systype [lindex [checkOS] 0]
    statgraph on [expr (2*[llength $node_list]) + [llength $link_list]]


    sendSessionProperties $sock

    # this tells the CORE services that we are starting to send 
    # configuration data
    # clear any existing config
    sendEventMessage $sock $eventtypes(definition_state) -1 "" "" 0
    # inform CORE services about emulation servers, hook scripts, canvas info,
    #  and services
    sendEventMessage $sock $eventtypes(configuration_state) -1 "" "" 0 
    sendEmulationServerInfo $sock 0
    sendSessionOptions $sock
    sendHooks $sock
    sendCanvasInfo $sock
    sendNodeTypeInfo $sock 0
    # send any custom service info before the node messages
    sendNodeCustomServices $sock

    # send Node add messages for all emulation nodes
    foreach node $node_list {
	set node_id "$eid\_$node"
	set type [nodeType $node]
	set name [getNodeName $node]
	if { $type == "pseudo" } { continue }
	
	statgraph inc 1
	statline "Creating node $name"
	if { [[typemodel $node].layer] == "NETWORK" } {
	    nodeHighlights .c $node on red
	}
	# inform the CORE daemon of the node
	sendNodeAddMessage $sock $node
	pluginCapsInitialize $node "mobmodel"
	writeNodeCoords $node [getNodeCoords $node]
    }

    # send Link add messages for all network links
    for { set pending_links $link_list } { $pending_links != "" } {} {
	set link [lindex $pending_links 0]
	set i [lsearch -exact $pending_links $link]
	set pending_links [lreplace $pending_links $i $i]
	statgraph inc 1

	set lnode1 [lindex [linkPeers $link] 0]
	set lnode2 [lindex [linkPeers $link] 1]
	if { [nodeType $lnode2] == "router" && \
	     [getNodeModel $lnode2] == "remote" } {
	    continue; # remote routers are ctrl. by GUI; TODO: move to daemon
	}
	sendLinkMessage $sock $link add
    }

    # GUI-specific meta-data send via Configure Messages
    if { [llength $annotation_list] > 0 }  {
	sendMetaData $sock $annotation_list "annotation"
    }
    sendMetaData $sock $canvas_list "canvas" ;# assume >= 1 canvas
    # global GUI options - send as meta-data
    set obj "metadata"
    set values [getGlobalOptionList]
    sendConfReplyMessage $sock -1 $obj "10" "{global_options=$values}" ""
    if { [info exists g_comments] && $g_comments != "" } {
	sendConfReplyMessage $sock -1 $obj "10" "{comments=$g_comments}" ""
    }

    # status bar graph
    statgraph off 0
    statline "Network topology instantiated in [expr [clock seconds] - $t_start] seconds ([llength $node_list] nodes and [llength $link_list] links)."
   
    # TODO: turn on tcpdump if enabled; customPostConfigCommands;
    #       addons 4 deployCfgHook

    # draw lines between wlan nodes
    # initialization does not work earlier than this

    foreach node $node_list {
	# WLAN handling: draw lines between wireless nodes
	if { [nodeType $node] == "wlan" && $execMode == "interactive" } {
	    wlanRunMobilityScript $node
	}
    }

    sendTrafficScripts $sock

    # tell the CORE services that we are ready to instantiate
    sendEventMessage $sock $eventtypes(instantiation_state) -1 "" "" 0 
    
    set deployCfgAPI_lock 0 ;# unlock

    statline "Network topology instantiated in [expr [clock seconds] - $t_start] seconds ([llength $node_list] nodes and [llength $link_list] links)."
}

#
# emulation shutdown procedure when using the CORE API
proc shutdownSession {} {
    global link_list node_list eid eventtypes execMode

    set nodecount [getNodeCount]
    if { $nodecount == 0 } {
	# This allows switching to edit mode without extra API messages,
	# such as when file new is selected while running an existing session.
	return
    }

    # prepare the channel
    set plugin [lindex [getEmulPlugin "*"] 0]
    set sock [pluginConnect $plugin connect true]

    sendEventMessage $sock $eventtypes(datacollect_state) -1 "" "" 0 

    # shut down all links
    foreach link $link_list {

	set lnode2 [lindex [linkPeers $link] 1]
	if { [nodeType $lnode2] == "router" && \
	     [getNodeModel $lnode2] == "remote" } {
	    continue; # remote routers are ctrl. by GUI; TODO: move to daemon
	}

	sendLinkMessage $sock $link delete false
    }
    # shut down all nodes
    foreach node $node_list {
	set type [nodeType $node]
        if { [[typemodel $node].layer] == "NETWORK"  && $execMode != "batch" } {
	    nodeHighlights .c $node on red
	}
	sendNodeDelMessage $sock $node
	pluginCapsDeinitialize $node "mobmodel"
	deleteNodeCoords $node
    }

    sendNodeTypeInfo $sock 1
    sendEmulationServerInfo $sock 1
}

# inform the CORE services about the canvas information to support
# conversion between X,Y and lat/long coordinates
proc sendCanvasInfo { sock } {
    global curcanvas

    if { ![info exists curcanvas] } { return } ;# batch mode
    set obj "location"

    set scale [getCanvasScale $curcanvas]
    set refpt [getCanvasRefPoint $curcanvas]
    set refx [lindex $refpt 0]
    set refy [lindex $refpt 1]
    set latitude [lindex $refpt 2]
    set longitude [lindex $refpt 3]
    set altitude [lindex $refpt 4]

    set types [list 2 2 10 10 10 10]
    set values [list $refx $refy $latitude $longitude $altitude $scale]

    sendConfReplyMessage $sock -1 $obj $types $values ""
}

# inform the CORE services about the default services for a node type, which
# are used when node-specific services have not been configured for a node
proc sendNodeTypeInfo { sock reset } {
    global node_list

    set obj "services"

    if { $reset  == 1} {
	sendConfRequestMessage $sock -1 "all" 0x3 -1 ""
	return
    }
    # build a list of node types in use 
    set typesinuse ""
    foreach node $node_list {
	set type [nodeType $node]
	if { $type != "router" } { continue }
	set model [getNodeModel $node]
	if { [lsearch $typesinuse $model] < 0 } { lappend typesinuse $model }
    }

    foreach type $typesinuse {
	# build a list of type + enabled services, all strings
	set values [getNodeTypeServices $type]
	set values [linsert $values 0 $type]
	set types [string repeat "10 " [llength $values]]
	sendConfReplyMessage $sock -1 $obj $types $values ""
	# send any custom profiles for a node type; node type passed in opaque
	set machine_type [getNodeTypeMachineType $type]
	set values [getNodeTypeProfile $type]
	if { $values != "" } {
	    set types [string repeat "10 " [llength $values]]
	    sendConfReplyMessage $sock -1 $machine_type $types $values \
	    	"$machine_type:$type"
	}
    }

}

# inform the CORE services about any services that have been customized for
# a particular node
proc sendNodeCustomServices { sock } {
    global node_list
    foreach node $node_list {
	set cfgs [getCustomConfig $node]
	set cfgfiles ""
	foreach cfg $cfgs {
	    set ids [split [getConfig $cfg "custom-config-id"] :]
	    if { [lindex $ids 0] != "service" } { continue }
	    if { [llength $ids] == 3 } {
		# customized service config file -- build a list
		lappend cfgfiles $cfg
		continue
	    }
	    set s [lindex $ids 1]
	    set values [getConfig $cfg "config"]
	    set t [string repeat "10 " [llength $values]]
	    sendConfReplyMessage $sock $node services $t $values "service:$s"
	}
	# send customized service config files after the service info
	foreach cfg $cfgfiles {
	    set idstr [getConfig $cfg "custom-config-id"]
	    set ids [split $idstr :]
	    if { [lindex $ids 0] != "service" } { continue }
	    set s [lindex $ids 1]
	    set filename [lindex $ids 2]
	    set data [join [getConfig $cfg "config"] "\n"]
	    sendFileMessage $sock $node "service:$s" $filename "" $data \
	         [string length $data]
	}
    }
}

# publish hooks to the CORE services
proc sendHooks { sock } {
    global g_hook_scripts
    if { ![info exists g_hook_scripts] } { return }
    foreach hook $g_hook_scripts {
	set name [lindex $hook 0]
	set state [lindex $hook 1]
	set data [lindex $hook 2]
	# TODO: modify sendFileMessage to make node number optional
	sendFileMessage $sock n0 "hook:$state" $name "" $data \
		[string length $data]
    }
}

# inform the CORE services about the emulation servers that will be used
proc sendEmulationServerInfo { sock reset } {
    global exec_servers
    set node -1 ;# not used
    set obj "broker"

    set servernames [getAssignedRemoteServers]
    if { $servernames == "" } { return } ;# not using emulation servers

    if { $reset  == 1} {
	sendConfRequestMessage $sock $node $obj 0x3 -1 ""
	return
    }

    set servers ""
    foreach servername $servernames {
	set host [lindex $exec_servers($servername) 0]
	set port [lindex $exec_servers($servername) 1]
	lappend servers "$servername:$host:$port"
    }

    set serversstring [join $servers ,]

    set types [list 10]
    set values [list $serversstring]

    sendConfReplyMessage $sock $node $obj $types $values ""
}

# returns the length of node_list minus any pseudo-nodes (inter-canvas nodes)
proc getNodeCount {} {
    global node_list
    set nodecount 0
    foreach node $node_list {
        if { [nodeType $node] != "pseudo" } { incr nodecount }
    }
    return $nodecount
}

# send basic properties of a session
proc sendSessionProperties { sock } {
    global currentFile CORE_DATA_DIR CORE_USER
    set sessionname [file tail $currentFile]
    set nodecount [getNodeCount]
    if { $sessionname == "" } { set sessionname "untitled" }
    set tf "/tmp/thumb.jpg"
    if { ![writeCanvasThumbnail .c $tf] } {
	set src "$CORE_DATA_DIR/icons/normal/thumb-unknown.gif"
	set tf "/tmp/thumb.gif"
	if [catch { file copy $src $tf } e] {
	    puts -nonewline "warning: failed to copy $src to $tf\n($e)"
	    set tf ""
	}
    }
    set user $CORE_USER
    sendSessionMessage $sock 0 0 $sessionname $currentFile $nodecount $tf $user
}

# send session options from global array in Config Message
proc sendSessionOptions { sock } {
    if { $sock == -1 } {
        set sock [lindex [getEmulPlugin "*"] 2]
    }
    set values [getSessionOptionsList]
    set types [string repeat "10 " [llength $values]]
    sendConfReplyMessage $sock -1 "session" $types $values ""
}

# send annotations as key=value metadata in Config Message
proc sendAnnotations { sock } {
    global annotation_list

    if { $sock == -1 } {
        set sock [lindex [getEmulPlugin "*"] 2]
    }
    set values ""
    foreach a $annotation_list {
	global $a
	set val [set $a]
	lappend values "annotation $a=$val"
    }
    set types [string repeat "10 " [llength $values]]
    sendConfReplyMessage $sock -1 "metadata" $types $values ""
}

# send items as key=value metadata in Config Message
proc sendMetaData { sock items itemtype } {

    if { $sock == -1 } {
        set sock [lindex [getEmulPlugin "*"] 2]
    }
    set values ""
    foreach i $items {
	global $i
	set val [set $i]
	lappend values "$itemtype $i=$val"
    }
    set types [string repeat "10 " [llength $values]]
    sendConfReplyMessage $sock -1 "metadata" $types $values ""
}

# send an Event message for the definition state (this clears any existing
# state), then send all node and link definitions to the CORE services
proc sendNodeLinkDefinitions { sock } {
    global node_list link_list annotation_list canvas_list eventtypes
    global g_comments
    #sendEventMessage $sock $eventtypes(definition_state) -1 "" "" 0
    foreach node $node_list {
	sendNodeAddMessage $sock $node
	pluginCapsInitialize $node "mobmodel"
    }
    foreach link $link_list { sendLinkMessage $sock $link add }
    # GUI-specific meta-data send via Configure Messages
    sendMetaData $sock $annotation_list "annotation"
    sendMetaData $sock $canvas_list "canvas"
    set obj "metadata"
    set values [getGlobalOptionList]
    sendConfReplyMessage $sock -1 $obj "10" "{global_options=$values}" ""
    if { [info exists g_comments] && $g_comments != "" } {
	sendConfReplyMessage $sock -1 $obj "10" "{comments=$g_comments}" ""
    }
}

proc getNodeTypeAPI { node } {
    set type [nodeType $node]
    if { $type == "router" } {
	set model [getNodeModel $node]
	set type [getNodeTypeMachineType $model]
    }
    switch -exact -- "$type" {
	router  { return 0x0 }
	netns   { return 0x0 }
	jail    { return 0x0 }
	physical { return 0x1 }
	xen	{ return 0x2 }
	tbd	{ return 0x3 }
	lanswitch { return 0x4 }
	hub	{ return 0x5 }
	wlan	{ return 0x6 }
	rj45	{ return 0x7 }
	tunnel	{ return 0x8 }
	ktunnel	{ return 0x9 }
	emane	{ return 0xA }
	default { return 0x0 }
    }
}

# send an Execute message
proc sendExecMessage { channel node cmd exec_num flags } {
    global showAPI g_api_exec_num
    set prmsg $showAPI

    set node_num [string range $node 1 end]
    set cmd_len [string length $cmd]
    if { $cmd_len > 255 } { puts "sendExecMessage error: cmd too long!"; return}
    set cmd_pad_len [pad_32bit $cmd_len]
    set cmd_pad [binary format x$cmd_pad_len]

    if { $exec_num == 0 } {
	incr g_api_exec_num
	set exec_num $g_api_exec_num
    }

    # node num + exec num + command string
    set len [expr {8 + 8 + 2 + $cmd_len + $cmd_pad_len}]

    if { $prmsg == 1 } {puts ">EXEC(flags=$flags,$node,n=$exec_num,cmd='$cmd')" }

    set msg [binary format ccSc2sIc2sIcc \
			3 $flags $len \
			{1 4} 0 $node_num \
			{2 4} 0 $exec_num \
			4 $cmd_len \
	    ]
    puts -nonewline $channel $msg$cmd$cmd_pad
    flushChannel channel "Error sending file message"
}

# if source file (sf) is specified, then send a message that the file source
# file should be copied to the given file name (f); otherwise, include the file
# data in this message
proc sendFileMessage { channel node type f sf data data_len } {
    global showAPI
    set prmsg $showAPI

    set node_num [string range $node 1 end]
    
    set f_len [string length $f]
    set f_pad_len [pad_32bit $f_len]
    set f_pad [binary format x$f_pad_len]
    set type_len [string length $type]
    set type_pad_len [pad_32bit $type_len]
    set type_pad [binary format x$type_pad_len]
    if { $sf != "" } {
	set sf_len [string length $sf]
	set sf_pad_len [pad_32bit $sf_len]
	set sf_pad [binary format x$sf_pad_len]
	set data_len 0
	set data_pad_len 0
    } else {
	set sf_len 0
	set sf_pad_len 0
	set data_pad_len [pad_32bit $data_len]
	set data_pad [binary format x$data_pad_len]
    }
    # TODO: gzip compression w/tlv type 0x11

    # node number TLV + file name TLV + ( file src name / data TLV)
    set len [expr {8 + 2 + 2  + $f_len + $f_pad_len + $sf_len + $sf_pad_len \
		   + $data_len + $data_pad_len}]
    # 16-bit data length
    if { $data_len > 255 } {
	incr len 2
	if { $data_len > 65536 } {
	    puts -nonewline "*** error: File Message data length too large "
	    puts "($data_len > 65536)"
	    return
	}
    }
    if { $type_len > 0 } { incr len [expr {2 + $type_len + $type_pad_len}] }
    set flags 1; # add flag

    if { $prmsg == 1 } {
	puts -nonewline ">FILE(flags=$flags,$node,f=$f,"
	if { $type != "" } { puts -nonewline "type=$type," }
	if { $sf != "" } {	puts "src=$sf)" 
	} else {		puts "data=($data_len))" }
    }

    set msg [binary format ccSc2sIcc \
			6 $flags $len \
			{1 4} 0 $node_num \
			2 $f_len \
	    ]
    set msg2 ""
    if { $type_len > 0 } {
	set msg2 [binary format cc 0x5 $type_len]
	set msg2 $msg2$type$type_pad
    }
    if { $sf != "" } {	;# source file name TLV
	set msg3 [binary format cc 0x6 $sf_len]
	puts -nonewline $channel $msg$f$f_pad$msg2$msg3$sf$sf_pad
    } else {		;# file data TLV
	if { $data_len > 255 } {
	    set msg3 [binary format ccS 0x10 0 $data_len]
	} else {
	    set msg3 [binary format cc 0x10 $data_len]
	}
	puts -nonewline $channel $msg$f$f_pad$msg2$msg3$data$data_pad
    }
    flushChannel channel "Error sending file message"
}

# Session Message
proc sendSessionMessage { channel flags num name sfile nodecount tf user } {
    global showAPI
    set prmsg $showAPI

    if { $channel == -1 } {
	set pname [lindex [getEmulPlugin "*"] 0]
	set channel [pluginConnect $pname connect true]
	if { $channel == -1 } { return }
    }

    set num_len [string length $num]
    set num_pad_len [pad_32bit $num_len]
    set len [expr {2 + $num_len + $num_pad_len}]
    if { $num_len <= 0 } {
	puts "error: sendSessionMessage requires at least one session number"
	return
    }
    set name_len [string length $name]
    set name_pad_len [pad_32bit $name_len]
    if { $name_len > 0 } { incr len [expr { 2 + $name_len + $name_pad_len }] }
    set sfile_len [string length $sfile]
    set sfile_pad_len [pad_32bit $sfile_len]
    if { $sfile_len > 0 } {
	incr len [expr { 2 + $sfile_len + $sfile_pad_len }]
    }
    set nc_len [string length $nodecount]
    set nc_pad_len [pad_32bit $nc_len]
    if { $nc_len > 0 } { incr len [expr { 2 + $nc_len + $nc_pad_len }] }
    set tf_len [string length $tf]
    set tf_pad_len [pad_32bit $tf_len]
    if { $tf_len > 0 } { incr len [expr { 2 + $tf_len + $tf_pad_len }] }
    set user_len [string length $user]
    set user_pad_len [pad_32bit $user_len]
    if { $user_len > 0 } { incr len [expr { 2 + $user_len + $user_pad_len }] }

    if { $prmsg == 1 } { 
	puts -nonewline ">SESSION(flags=$flags" }
    set msgh [binary format ccS 0x09 $flags $len ] ;# message header

    if { $prmsg == 1 } { puts -nonewline ",sids=$num" }
    set num_hdr [binary format cc 0x01 $num_len]
    set num_pad [binary format x$num_pad_len ]
    set msg1 "$num_hdr$num$num_pad"

    set msg2 ""
    if { $name_len > 0 } {
	if { $prmsg == 1 } { puts -nonewline ",name=$name" }
	# TODO: name_len > 255 
	set name_hdr [binary format cc 0x02 $name_len]
	set name_pad [binary format x$name_pad_len]
	set msg2 "$name_hdr$name$name_pad"
    }
    set msg3 ""
    if { $sfile_len > 0 } {
	if { $prmsg == 1 } { puts -nonewline ",file=$sfile" }
	# TODO: sfile_len > 255 
	set sfile_hdr [binary format cc 0x03 $sfile_len]
	set sfile_pad [binary format x$sfile_pad_len]
	set msg3 "$sfile_hdr$sfile$sfile_pad"
    }
    set msg4 ""
    if { $nc_len > 0 } {
	if { $prmsg == 1 } { puts -nonewline ",nc=$nodecount" }
	set nc_hdr [binary format cc 0x04 $nc_len]
	set nc_pad [binary format x$nc_pad_len]
	set msg4 "$nc_hdr$nodecount$nc_pad"
    }
    set msg5 ""
    if { $tf_len > 0 } {
	if { $prmsg == 1 } { puts -nonewline ",thumb=$tf" }
	set tf_hdr [binary format cc 0x06 $tf_len]
	set tf_pad [binary format x$tf_pad_len]
	set msg5 "$tf_hdr$tf$tf_pad"
    }
    set msg6 ""
    if { $user_len > 0 } {
	if { $prmsg == 1 } { puts -nonewline ",user=$user" }
	set user_hdr [binary format cc 0x07 $user_len]
	set user_pad [binary format x$user_pad_len]
	set msg6 "$user_hdr$user$user_pad"
    }

    if { $prmsg == 1 } { puts ")" }
    puts -nonewline $channel $msgh$msg1$msg2$msg3$msg4$msg5$msg6
    flushChannel channel "Error sending Session num=$num"
}

# return a new execution number and record it in the execution request list
# for the given callback (e.g. widget) type
proc newExecCallbackRequest { type } {
    global g_api_exec_num g_execRequests
    incr g_api_exec_num
    set exec_num $g_api_exec_num
    lappend g_execRequests($type) $exec_num
    return $exec_num
}

# ask daemon to load or save an XML file based on the current session
proc xmlFileLoadSave { cmd name } {
    global oper_mode eventtypes

    set plugin [lindex [getEmulPlugin "*"] 0]
    set sock [pluginConnect $plugin connect true]
    if { $sock == -1 || $sock == "" } { return }

    # inform daemon about nodes and links when saving in edit mode
    if { $cmd == "save" && $oper_mode != "exec" } {
	sendSessionProperties $sock
	# this tells the CORE services that we are starting to send 
	# configuration data
	# clear any existing config
	sendEventMessage $sock $eventtypes(definition_state) -1 "" "" 0
	sendEventMessage $sock $eventtypes(configuration_state) -1 "" "" 0 
	sendEmulationServerInfo $sock 0
	sendSessionOptions $sock
	sendHooks $sock
	sendCanvasInfo $sock
	sendNodeTypeInfo $sock 0
	# send any custom service info before the node messages
	sendNodeCustomServices $sock
	sendNodeLinkDefinitions $sock
    } elseif { $cmd == "open" } {
	# reset config objects
	sendNodeTypeInfo $sock 1
    }
    sendEventMessage $sock $eventtypes(file_$cmd) -1 $name "" 0
}

############################################################################
#
# Helper functions below here
#

# helper function to get interface number from name
proc ifcNameToNum { ifc } {
    # eth0, eth1, etc.
    if {[string range $ifc 0 2] == "eth"} {
	set ifnum [string range $ifc 3 end]
    # l0, l1, etc.
    } else {
	set ifnum [string range $ifc 1 end]
    }
    if { $ifnum == "" } {
	return -1
    }
    if {![string is integer $ifnum]} {
	return -1
    }
    return $ifnum
}

#
# parse the type and length from a TLV header
proc parseTLVHeader { data current_ref } {
    global showAPI
    set prmsg $showAPI
    upvar $current_ref current

    if { [binary scan $data @${current}cc type length] != 2 } {
        if { $prmsg == 1 } { puts "TLV header error" }
        return ""
    }
    set length [expr {$length & 0xFF}]; # convert signed to unsigned
    if { $length == 0 } {
        if { $type == 0 } {
            # prevent endless looping
	    if { $prmsg == 1 } { puts -nonewline "(extra padding)" }
            return ""
        } else {
            # support for length > 255
            incr current 2
            if { [binary scan $data @${current}S length] != 1 } {
                puts "error reading TLV length (type=$type)"
                return ""
            }
            set length [expr {$length & 0xFFFF}]
	    if { $length == 0 } {
                # zero-length string, not length > 255
                incr current -2
            }
        }
    }
    incr current 2
    return [list $type $length]
}

# return the binary string, and length by reference
proc buildStringTLV { type data len_ref } {
    upvar $len_ref len
    set data_len [string length $data]
    if { $data_len > 65536 } {
	puts "warning: buildStringTLV data truncated"
	set data_len 65536
	set data [string range 0 65535]
    }
    set data_pad_len [pad_32bit $data_len]
    set data_pad [binary format x$data_pad_len]

    if { $data_len == 0 } {
	set len 0
	return ""
    }

    if { $data_len > 255 } {
	set hdr [binary format ccS $type 0 $data_len] 
	set hdr_len 4
    } else {
	set hdr [binary format cc $type $data_len]
	set hdr_len 2
    }

    set len [expr {$hdr_len + $data_len + $data_pad_len}]

    return $hdr$data$data_pad
}

# calculate padding to 32-bit word boundary
# 32-bit and 64-bit values are pre-padded, strings and 128-bit values are
# post-padded to word boundary, depending on type
proc pad_32bit { len } {
    # total length = 2 + len + pad
    if { $len < 256 } {
	set hdrsiz 2
    } else {
	set hdrsiz 4
    }
    # calculate padding to fill 32-bit boundary
    return [expr { -($hdrsiz + $len) % 4 }]
}

proc macToString { mac_num } {
    set mac_bytes ""
    # convert 64-bit integer into 12-digit hex string 
    set mac_num 0x[format "%.12lx" $mac_num]
    while { $mac_num > 0 } {
	# append 8-bit hex number to list
        set uchar [format "%02x" [expr $mac_num & 0xFF]]
	lappend mac_bytes $uchar
	# shift off 8-bits
	set mac_num [expr $mac_num >> 8]
    }

    # make sure we have six hex digits
    set num_zeroes [expr 6 - [llength $mac_bytes]]
    while { $num_zeroes > 0 } {
    	lappend mac_bytes 00
	incr num_zeroes -1
    }

    # this is lreverse in tcl8.5 and later
    set r {}
    set i [llength $mac_bytes]
    while { $i > 0 } { lappend r [lindex $mac_bytes [incr i -1]] }
    
    return [join $r :]
}

proc hexdump { data } {
    # read data as hex
    binary scan $data H* hex
    # split into pairs of hex digits
    regsub -all -- {..} $hex {& } hex
    return $hex
}
