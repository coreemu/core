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

# default built-in model to use and its default parameters
set DEFAULT_WLAN_MODEL basic_range
set DEFAULT_SCRIPT_MODEL ns2script
set DEFAULT_WLAN_MODEL_TYPES "3 3 9 9 9"
set DEFAULT_RANGE 275
set DEFAULT_WLAN_BW 54000000
set DEFAULT_WLAN_DELAY 20000
set DEFAULT_WLAN_MODEL_VALS [list "range=$DEFAULT_RANGE" \
	"bandwidth=$DEFAULT_WLAN_BW" "jitter=0" "delay=$DEFAULT_WLAN_DELAY" \
	"error=0" ]
# default canvas reference point: X Y lat long alt
set DEFAULT_REFPT "0 0 47.5791667 -122.132322 2.0"

#
# look for all wlan nodes connected to peer if specified,
# otherwise in the global list of nodes
proc findWlanNodes { peer } {
    global node_list
    set wlans { }

    # search the global node list for the first wlan node
    if { $peer == "" } {
	foreach node $node_list {
	    if { [nodeType $node] == "wlan" } {
		lappend wlans $node
	    }
	}
    # search peer for wlan node
    } else {
	foreach ifc [ifcList $peer] {
	    set node [peerByIfc $peer $ifc]
	    if { [nodeType $node] == "wlan" } {
		lappend wlans $node
	    }
	}
    }
    return $wlans
}

#
# Returns 1 if the given interface is wireless
proc isIfcWireless { node ifc } {
    if { $ifc == "wireless" } { 
	# wireless peudo-interface
	return false
    }
    set peer [logicalPeerByIfc $node $ifc]
    if { $peer != "" && [nodeType $peer] == "wlan" } {
	return true
    }
    return false
}

#
# remove the (green) WLAN GUI links
#
proc clearWlanLinks { wlan } {
	global .c
	set search "wlanlink"
	if { $wlan != "" } { set search "wlanlink && $wlan" }
	foreach wlanlink [.c find withtag $search] {
		set tags [.c gettags $wlanlink]
		set lnode1 [lindex $tags 1]
		set lnode2 [lindex $tags 2]
		.c delete $wlanlink
		.c delete -withtags "linklabel && $lnode1 && $lnode2"
		# we could also remove wlan node hash table entry for
		# each wlanlink, but we are assuming wlan node will be
		# destroyed anyway
	}
}

# draws circles in GUI representing wlan range
proc updateRangeCircles { wlan range } {
    global .c zoom g_selected_model
    set c .c
   
    set radius [expr {$zoom * $range/2}]
    $c delete -withtag rangecircles
    if { $radius == 0 } {
    	return
    }
    if { $g_selected_model != "none" } {
    	return
    }
    foreach ifc [ifcList $wlan] {
	set node [peerByIfc $wlan $ifc]
	set coords [getNodeCoords $node]
	set x [expr {[lindex $coords 0] * $zoom}]
	set y [expr {[lindex $coords 1] * $zoom}]
	set x1 [expr $x - $radius]
	set y1 [expr $y - $radius]
	set x2 [expr $x + $radius]
	set y2 [expr $y + $radius]

	set newcircle [$c create oval $x1 $y1 $x2 $y2 \
		-width 2 -outline #00A000 -tags "circle rangecircles"]
    }
}

proc linkSelectedNodes { wlan nodes } {
    foreach node $nodes {
	if { $wlan == $node } { continue } ;# don't link to self
	if { [ifcByPeer $wlan $node] != "" } { continue } ;# already linked
        newGUILink $wlan $node
    }
}

proc linkAllNodes { wlan } {
    global node_list

    # vars related to the status bar graph
    set num 0
    set num_nodes [llength $node_list]
    statgraph on $num_nodes
    set update_interval [expr {$num_nodes / 15}]
    .c config -cursor watch; update

    foreach node $node_list {
        statgraph inc 1
	incr num
	# GUI update slows this down considerably, so update every so often
	if { $update_interval > 0 && \
	     [expr { ($num % $update_interval) }] == 0 } { update }
        if { [nodeType $node] != "router" } { continue }
	if { [ifcByPeer $wlan $node] != "" } { continue } ;# already linked
        newGUILink $wlan $node
    }
    .c config -cursor left_ptr; update
    statgraph off 0
}

proc getWlanColor { wlan } {
	global node_list wlanLinkColors
	set colornum 0
	foreach node $node_list {
		if {[nodeType $node] != "wlan"} {
			continue
		}
		if {$node == $wlan} { 
			return [lindex $wlanLinkColors $colornum]
		}
		incr colornum
		if { $colornum >= [llength $wlanLinkColors] } { set colornum 0 }
	}
	# default color
	return [lindex $wlanLinkColors 0]
}
 
# move a node given incremental coordinates
# dx dy should be adjusted for zoom
proc moveNodeIncr { c node dx dy } {
    global node_list
    #puts "moveNodeIncr $node $dx $dy"
    # check that node exists
    if {[lsearch $node_list $node] == -1 } {
	return
    }
    # move the node and its links
    set img [$c find withtag "node && $node"]
    set coords [$c coords $img]
    set x [lindex $coords 0]
    set y [lindex $coords 1]
    # move doesn't take incremental coordinates
    set xpos [expr ($x + $dx)]
    set ypos [expr ($y + $dy)]
    moveNode $c $node $img $xpos $ypos $dx $dy
}

# move a node given absolute coordinates
# xpos,ypos should be adjusted for zoom
proc moveNodeAbs { c node xpos ypos } {
    global node_list
    # check that node exists
    if {[lsearch $node_list $node] == -1 } {
	return
    }
    # move the node and its links
    if {$xpos != 0 && $ypos != 0} {
        set img [$c find withtag "node && $node"]
        set coords [$c coords $img]
        set x [lindex $coords 0]
        set y [lindex $coords 1]
	# move doesn't take absolute coordinates
        set dx [expr ($xpos - $x)]
        set dy [expr ($ypos - $y)]
	moveNode $c $node $img $xpos $ypos $dx $dy
    }
}

# move a node on the canvas along with its labels and links
# helper function used by moveNodeIncr and moveNodeAbs
proc moveNode { c node img xpos ypos dx dy } {
    global zoom
    $c move $img $dx $dy
    set xposz [expr {$xpos / $zoom}]; set yposz [expr {$ypos / $zoom}]
    setNodeCoords $node "$xposz $yposz"
    $c move "nodelabel && $node" $dx $dy
    $c move "highlight && $node" $dx $dy
    $c move "rangecircles && $node" $dx $dy
    lassign [getDefaultLabelOffsets [nodeType $node]] ldx ldy
    setNodeLabelCoords $node "[expr {$xposz + $ldx}] [expr {$yposz + $ldy}]"
    $c addtag need_redraw withtag "link && $node"
    $c addtag need_redraw withtag "wlanlink && $node"
    foreach link [$c find withtag "link && need_redraw"] {
        redrawLink [lindex [$c gettags $link] 1]
    }
    foreach wlanlink [$c find withtag \
      "wlanlink && need_redraw"] {
        redrawWlanLink $wlanlink
    }
    $c dtag node selected
    $c delete -withtags selectmark
    $c dtag link need_redraw
    $c dtag wlanlink need_redraw

    # callback for updating any widgets
    widgets_move_node $c $node 1
}

# called from cfgparse when loading imn file
proc upgradeWlanConfigs {} {
    global node_list
    set model_list [getPluginsCapList]
    foreach node $node_list {
	if { [nodeType $node] != "wlan" } { continue }
	set modcfg [netconfFetchSection $node "mobmodel"]
	if { [lindex $modcfg 0] == "range" } {
	    upgradeWlanRangeConfig $node
	    set modcfg [netconfFetchSection $node "mobmodel"]
	}
	foreach model [lrange $modcfg 1 end] {
	    if { [lsearch $model_list "*=$model"] == -1 } {
		puts "***Warning: missing model '$model'!"
	    }
	}
    }
}

# backwards compatibility with old config files
# convert from "range" model to "basic_range" coreapi model
proc upgradeWlanRangeConfig { wlan } {
    global DEFAULT_RANGE DEFAULT_WLAN_MODEL
    global DEFAULT_WLAN_MODEL_TYPES DEFAULT_WLAN_BW DEFAULT_WLAN_DELAY

    netconfInsertSection $wlan [list mobmodel coreapi $DEFAULT_WLAN_MODEL]
    set range [getNodeRange $wlan]
    if { $range == "" } { set range $DEFAULT_RANGE }
    set bw [getLinkBandwidth $wlan]
    if { $bw == "" } { set bw $DEFAULT_WLAN_BW }
    set jitter 0
    set delay [getLinkDelay $wlan]
    if { $delay == "" } { set delay $DEFAULT_WLAN_DELAY }
    set per [getLinkBER $wlan]
    if { $per == "" } { set per 0 }
    set types $DEFAULT_WLAN_MODEL_TYPES
    set vals [list "range=$range" "bandwidth=$bw" "jitter=$jitter" \
		"delay=$delay" "error=$per"]
    setCustomConfig $wlan $DEFAULT_WLAN_MODEL $types $vals 0
    setNodeRange $wlan ""
    setLinkBandwidth $wlan ""
    setLinkDelay $wlan ""
    setLinkBER $wlan ""
}

# helper to populate popup config for wlan nodes
proc wlanConfigDialogHelper { wi target apply } {
    global range DEFAULT_RANGE DEFAULT_WLAN_MODEL changed
    global DEFAULT_WLAN_MODEL_VALS DEFAULT_WLAN_MODEL_TYPES
    global DEFAULT_SCRIPT_MODEL
    global systype
    global plugin_img_edit
    global g_selected_model
    global oper_mode

    set wlan $target
    set emulation_type [lindex [getEmulPlugin $target] 1]

    set modcfg [netconfFetchSection $target "mobmodel"]
    set mobmodel [lindex [split $modcfg] 1]

    # apply values from the config dialog
    if { $apply } {

	# basic range selected
	if { $g_selected_model == "none" } {
	    set mobmodel $DEFAULT_WLAN_MODEL
	    # bw/delay/ber
	    set rb $wi.wl.note.basic.rb
	    set de $wi.wl.note.basic.de
	    set jt $wi.wl.note.basic.jt
	    set bw [$rb.value get]
	    set jitter [$jt.value1 get]
	    set delay [$de.value2 get]
	    set per [$de.value3 get]
	    set types $DEFAULT_WLAN_MODEL_TYPES
	    set vals [list "range=$range" "bandwidth=$bw" "jitter=$jitter" \
			"delay=$delay" "error=$per"]
	    setCustomConfig $wlan $DEFAULT_WLAN_MODEL $types $vals 0
	# EMANE model selected
	} else {
	    set mobmodel $g_selected_model
	}

	# ns-2 mobility script file
	set scriptcfg [getCustomConfigByID $wlan $DEFAULT_SCRIPT_MODEL]
	if { $scriptcfg != "" } {
	    netconfInsertSection $target \
		[list mobmodel coreapi $mobmodel $DEFAULT_SCRIPT_MODEL]
	} else {
	    netconfInsertSection $target [list mobmodel coreapi $mobmodel]
	}

	# ipv4/ipv6 address
	set ipv4changed 0
	set ipv6changed 0
	set ipaddr [$wi.bottom.ipv4.addrv get]
	set oldipaddr [getIfcIPv4addr $target wireless]
	if { $ipaddr != $oldipaddr } {
	    setIfcIPv4addr $target wireless $ipaddr
	    set changed 1
	    set ipv4changed 1
	}
	set ipaddr [$wi.bottom.ipv6.addrv get]
	set oldipaddr [getIfcIPv6addr $target wireless]
	if { $ipaddr != $oldipaddr } {
	    setIfcIPv6addr $target wireless $ipaddr
	    set changed 1
	    set ipv6changed 1
	}
	foreach ifc [ifcList $target] {
	    set lnode [lindex [linkByIfc $target $ifc] 0]
	    # erase IPv4/IPv6 addresses as needed
	    set peer [peerByIfc $target $ifc]
	    set peerifc [ifcByPeer $peer $target]
	    if { $ipv4changed } { setIfcIPv4addr $peer $peerifc "" }
	    if { $ipv6changed } { setIfcIPv6addr $peer $peerifc "" }
	}
	# addresses have been zeroed above to force using the WLAN subnet
	foreach ifc [ifcList $target] {
	    set peer [peerByIfc $target $ifc]
	    set peerifc [ifcByPeer $peer $target]
	    if { $ipv4changed } { autoIPv4addr $peer $peerifc }
	    if { $ipv6changed } { autoIPv6addr $peer $peerifc }
	}
	# remove any range circles
	updateRangeCircles $target 0

	if { $oper_mode == "exec" } {
	    # this generates Config Messages for updating the model parameters
	    pluginCapsInitialize $target "mobmodel"
	}
	return
    }

    # use default model/values when none configured for this node
    if { $mobmodel == "" } {
	set mobmodel $DEFAULT_WLAN_MODEL 
	set vals $DEFAULT_WLAN_MODEL_VALS
    # look for customized range/bw/jitter/delay/per
    } else {
	set vals [getCustomConfigByID $target $DEFAULT_WLAN_MODEL]
	if { $vals == "" } { set vals $DEFAULT_WLAN_MODEL_VALS }
    }

    # set radio button variable
    if { $mobmodel == $DEFAULT_WLAN_MODEL } {
	set g_selected_model "none"
    } else {
	set g_selected_model $mobmodel
    }

    set range  [getServiceValuesItem $vals "range" 0]
    set bw     [getServiceValuesItem $vals "bandwidth" 1]
    set jitter [getServiceValuesItem $vals "jitter" 2]
    set delay  [getServiceValuesItem $vals "delay" 3]
    set per    [getServiceValuesItem $vals "error" 4]

    ttk::labelframe $wi.wl -text "Wireless"
    pack $wi.wl -fill both -expand true -padx 4 -pady 4

    ttk::notebook $wi.wl.note
    pack $wi.wl.note -fill both -expand true -padx 4 -pady 4
    ttk::notebook::enableTraversal $wi.wl.note

    ##
    ## basic range
    ##
    ttk::frame $wi.wl.note.basic
    $wi.wl.note add $wi.wl.note.basic -text "Basic" -underline 0
    set txt "The basic range model calculates on/off connectivity based on"
    set txt "$txt pixel\n distance between nodes."
    ttk::label $wi.wl.note.basic.tlab -text $txt
    pack $wi.wl.note.basic.tlab -side top -anchor w -padx 4 -pady 4

    # range and bandwidth (rb) frame
    set rb $wi.wl.note.basic.rb
    ttk::frame $rb
    ttk::label $rb.rlab -text "Range:"
    ttk::scale $rb.rscale -command "updateRangeCircles $target" \
			-to 1500 -orient horizontal -variable range
    ttk::entry $rb.range -width 5 -textvariable range
    pack $rb.rlab $rb.rscale $rb.range -side left -padx 4 -pady 4

    # bandwidth
    set spinbox [getspinbox]
    ttk::label $rb.label -anchor w -text "Bandwidth (bps):"
    $spinbox $rb.value -justify right -width 10 -validate focus
    $rb.value configure -validatecommand {checkIntRange %P 0 1000000000} \
			-from 0 -to 1000000000 -increment 1000000
    $rb.value insert 0 $bw
    pack $rb.label $rb.value \
	-side left -padx 4 -pady 4
    pack $rb -side top -anchor w -padx 4 -pady 4

    # delay and error (de) frame
    set de $wi.wl.note.basic.de
    ttk::frame $de

    ttk::label $de.label2 -anchor w -text "Delay (us):"
    $spinbox $de.value2 -justify right -width 10 -validate focus
    $de.value2 configure -validatecommand {checkIntRange %P 0 10000000} \
			-from 0 -to 10000000 -increment 5000
    $de.value2 insert 0 $delay
    pack $de.label2 $de.value2 -side left -padx 4 -pady 4

    $spinbox $de.value3 -justify right -width 5 -validate focus
    if { [lindex $systype 0] == "Linux" } {
	ttk::label $de.label3 -anchor w -text "Loss (%):"
	$de.value3 configure -from 0 -to 100.0 -increment 0.1
    } else { ;# netgraph
	ttk::label $de.label3 -anchor w -text "Bit Error (1/N):"
	$de.value3 configure -width 10 -validatecommand \
			{checkIntRange %P 0 10000000000000} \
			-from 0 -to 10000000000000 -increment 1000
    }
    $de.value3 insert 0 $per
    pack $de.label3 $de.value3 \
	-side left -padx 4 -pady 4
    pack $de -side top -anchor w -padx 4 -pady 4

    # jitter frame 
    set jt $wi.wl.note.basic.jt
    ttk::frame $jt
    ttk::label $jt.label1 -anchor w -text "Jitter (us):"
    $spinbox $jt.value1 -justify right -width 10 -validate focus
    $jt.value1 configure -validatecommand {checkIntRange %P 0 10000000} \
			-from 0 -to 10000000 -increment 5000
    $jt.value1 insert 0 $jitter
    pack $jt.label1 $jt.value1 -side left -padx 4 -pady 4
    pack $jt -side top -anchor w -padx 4 -pady 4

    ###
    ### EMANE
    ###
    ttk::frame $wi.wl.note.emane
    $wi.wl.note add $wi.wl.note.emane -text "EMANE" -underline 0
    set txt "The EMANE emulation system provides more complex wireless radio"
    set txt "$txt emulation\n using pluggable MAC and PHY modules."
    ttk::label $wi.wl.note.emane.tlab -text $txt
    pack $wi.wl.note.emane.tlab -side top -anchor w -padx 4 -pady 4

    # models
    set mod $wi.wl.note.emane.models
    ttk::labelframe $mod -text "EMANE Models"
    pack $mod -side top -fill both -expand true -padx 4 -pady 4

    set side "nw"
    ttk::radiobutton $mod.none -text "none" -command "updateOptBtn $wi none" \
	-value "none" -variable g_selected_model -width 12
    pack $mod.none -side top -anchor w -padx 4 -pady 0

    set caplist [getPluginsCapList]
    set emane_models {}
    set have_emane_models false
    # TODO: a refresh button here would be nice
    foreach cap $caplist {
	set captype [lindex [split $cap =] 0]
	set capname [lindex [split $cap =] 1]
	if { [string range $capname 0 5] != "emane_" } { continue }
	set emane_model [capTitle $capname]

	ttk::radiobutton $mod.$capname -text $emane_model -value $capname \
		-variable g_selected_model -width 12 \
		-command "updateOptBtn $wi $emane_model"
	pack $mod.$capname -side top -anchor w -padx 4 -pady 0
	set have_emane_models true
    }
    if { ! $have_emane_models } {
	# show connection dialog box to indicate why there are no EMANE models
	$mod.none configure -text "none - connection to CORE daemon required!" \
		-width "45"
	after 500 {
	    update ;# allow dialog layout, otherwise strange results
	    pluginConnect "" connect true
	}
    }

    # options buttons
    set opts $wi.wl.note.emane.opts
    ttk::frame $opts
    ttk::button $opts.model -text "model options" \
	-image $plugin_img_edit -compound right -command "" -state disabled \
	-command "configCap $target \[set g_selected_model\]"
    # global EMANE model uses no node in config request message, although any
    # config will be stored with the EMANE node having the lowest ID
    ttk::button $opts.gen -text "EMANE options" \
	-image $plugin_img_edit -compound right \
	-command "configCap -1 emane"
	#-command "popupPluginsCapConfigHelper $wi config $target"
    pack $opts.model $opts.gen -side left -padx 4 -pady 4
    pack $opts -side top -anchor c -padx 4 -pady 4

    # show correct tab basic/emane based on selection
    if { $g_selected_model == "none" } {
	$wi.wl.note select $wi.wl.note.basic
    } else {
	$wi.wl.note select $wi.wl.note.emane
    }
    updateOptBtn $wi [capTitle $g_selected_model]


    # WLAN has not been linked yet, generate addresses here.
    if { [getIfcIPv4addr $target wireless] == "" } {
        setIfcIPv4addr $target wireless "[findFreeIPv4Net 24].0/32"
    }
    if { [getIfcIPv6addr $target wireless] == "" } {
        setIfcIPv6addr $target wireless "[findFreeIPv6Net 64]::0/128"
    }

    frame $wi.bottom -padx 4 -pady 4

    # 4. IPv4/IPv6 addresses
    #
    # IPv4 address
    #
    frame $wi.bottom.ipv4
    label $wi.bottom.ipv4.addrl -text "IPv4 subnet" \
    	-anchor w
    entry $wi.bottom.ipv4.addrv -bg white -width 30 \
        -validate focus -invcmd "focusAndFlash %W"
    $wi.bottom.ipv4.addrv insert 0 \
        [getIfcIPv4addr $target wireless]
    $wi.bottom.ipv4.addrv configure \
        -vcmd {checkIPv4Net %P}

    #
    # IPv6 address
    #
    frame $wi.bottom.ipv6
    label $wi.bottom.ipv6.addrl -text "IPv6 subnet" \
    	-anchor w
    entry $wi.bottom.ipv6.addrv -bg white -width 30 \
        -validate focus -invcmd "focusAndFlash %W"
    $wi.bottom.ipv6.addrv insert 0 \
        [getIfcIPv6addr $target wireless]
    $wi.bottom.ipv6.addrv configure \
        -vcmd {checkIPv6Net %P}

    #
    # Link all nodes button
    #
    button $wi.bottom.script -text "ns-2 mobility script..." \
    	-command "sendConfRequestMessage -1 $target ns2script 0x1 -1 {}"
    button $wi.bottom.linkall -text "Link to all routers" \
        -command "linkAllNodes $target"
    set msg "Select new WLAN $target members:"
    set cmd "linkSelectedNodes $target"
    button $wi.bottom.memb -text "Choose WLAN members" \
	-command "popupSelectNodes \"$msg\" \"\" {$cmd}"
    
    # layout items
    
    pack $wi.bottom.ipv4.addrl $wi.bottom.ipv4.addrv -side left
    pack $wi.bottom.ipv4 -side top -anchor w
    pack $wi.bottom.ipv6.addrl $wi.bottom.ipv6.addrv -side left
    pack $wi.bottom.ipv6 -side top -anchor w
    pack $wi.bottom.script $wi.bottom.linkall $wi.bottom.memb \
	-side left -anchor center
    
    pack $wi.bottom -side top -anchor w
}

# toggle the enabling/disabling of Basic/EMANE controls
proc updateOptBtn { wi txt } {
    set s normal
    set bs disabled
    if { $txt == "none" } { set s disabled; set bs !disabled; set txt "model" }
    $wi.wl.note.emane.opts.model configure -text "$txt options" -state $s

    $wi.wl.note.basic.rb.range configure -state $bs
    $wi.wl.note.basic.rb.rscale state $bs
    if { $bs == "disabled" } { .c delete -withtag rangecircles }

    # spinbox state: disabled/!disabled (Tk 8.5.8) or disabled/normal (ttk)
    set spinboxstate $bs
    if { [info command ttk::spinbox] == "" && $spinboxstate == "!disabled" } {
	set spinboxstate normal
    }
    $wi.wl.note.basic.rb.value configure -state $spinboxstate
    $wi.wl.note.basic.de.value2 configure -state $spinboxstate
    $wi.wl.note.basic.de.value3 configure -state $spinboxstate
    $wi.wl.note.basic.jt.value1 configure -state $spinboxstate
}

proc wlanDoubleClick { node button } {
    set modeldata [netconfFetchSection $node "mobmodel"]
    # modeldata e.g. = "coreapi emane_rfpipe"
    set modeltype [lindex $modeldata 1]
    if { [string range $modeltype 0 4] == "emane" } {
	if { [string range $modeltype 6 end] == "commeffect" } {
	    set cmd "emanecommeffectcontroller"
	    if { [catch {exec $cmd & } e] } {
		tk_messageBox -icon error -message "Error launching $cmd: $e"
	    }
	}
    } else {
	# TODO: non-EMANE WLAN dialog, e.g. mobility
    }
}

# helper returns true for WLANs configured with EMANE models
proc isEmane { node } {
    if { [nodeType $node] != "wlan" } {
	return false
    }
    set modeldata [netconfFetchSection $node "mobmodel"]
    set modeltype [lindex $modeldata 1]
    if { [string range $modeltype 0 4] == "emane" } {
	return true
    } else {
	return false
    }
}

# return the EMANE node (WLAN) having the lowest node number
# the EMANE global config will be stored with this node
proc minEmaneNode {} {
    global node_list
    set min ""
    foreach node $node_list {
	if { ![isEmane $node] } { continue }
        set nodenum [string range $node 1 end]
	if { $min == "" || $nodenum < $min } {
	    set min $nodenum
	}
    }
    if { $min != "" } { set min "n$min" }
    return $min
}
