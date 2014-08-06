#
# Copyright 2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

set g_traffic_start_opt 0
set g_traffic_flows ""

# preset MGEN traffic pattern parameters
#   fields are name [list dst params]
array set traffic_presets {
    "00 1 kbps" {"" "PERIODIC \[1.0 125\]"}
    "01 10 kbps" {"" "PERIODIC \[10.0 125\]"}
    "02 100 kbps" {"" "PERIODIC \[10.0 1250\]"}
    "03 512 kbps" {"" "PERIODIC \[50.0 1280\]"}
    "04 POISSON 10 kbps" {"" "POISSON \[10.0 125\]"}
    "05 POISSON 100 kbps" {"" "POISSON \[10.0 1250\]"}
    "06 POISSON 512 kbps" {"" "POISSON \[50.0 1280\]"}
    "07 3s fixed BURST 75kbps every 15s" {"" "BURST \[REGULAR 15.0 PERIODIC \[10.0 938\] FIXED 3.0\]"}
    "08 0-5s random BURST 100kbps randomly every 10s" {"" "BURST \[RANDOM 10.0 PERIODIC \[10.0 1250\] EXP 5.0\]"}
    "09 3s fixed BURST 256kbps randomly every 5s" {"" "BURST \[RANDOM 5.0 PERIODIC \[25.0 1280\] FIXED 3.0\]"}
    "10 JITTER 10 kbps 0.05-0.15s" {"" "JITTER \[10.0 125 0.5\]"}
    "11 JITTER 75 kbps 0.08-0.12s" {"" "JITTER \[10.0 938 0.2\]"}
    "12 CLONE pcap file" {"" "CLONE \[tcpdump /tmp/source.pcap \[0\]\]"}
    "13 CLONE pcap file continuous" {"" "CLONE \[tcpdump /tmp/source.pcap \[-1\]\]"}
    "14 100 kbps multicast" {"224.225.1.1" "PERIODIC \[10.0 1250\]"}
    "15 POISSON 384 kbps multicast" {"224.225.2.1" "POISSON \[40.0 1200\]"}
}

proc popupTrafficDialog {} {
    global plugin_img_add plugin_img_edit plugin_img_del g_traffic_start_opt
    global oper_mode

    set wi .traffic1
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 0 0
    wm title $wi "CORE traffic flows"

    if { ![info exists g_traffic_start_opt] } { set g_traffic_start_opt 0 }

    labelframe $wi.f -text "Traffic flows"
    listbox $wi.f.flows -selectmode extended -width 50 -exportselection 0 \
	-yscrollcommand "$wi.f.flows_scroll set"
    scrollbar $wi.f.flows_scroll -command "$wi.f.flows yview"
    pack $wi.f.flows $wi.f.flows_scroll -pady 4 -fill both -side left
    pack $wi.f -padx 4 -pady 4 -fill both -side top
    bind $wi.f.flows <Double-Button-1> "trafficHelper $wi edit"
    bind $wi.f.flows <<ListboxSelect>> "trafficHelper $wi sel"

    frame $wi.bbar
    button $wi.bbar.new -image $plugin_img_add -command "trafficHelper $wi new"
    button $wi.bbar.save -image $plugin_img_edit \
	-command "trafficHelper $wi edit"
    button $wi.bbar.del -image $plugin_img_del -command "trafficHelper $wi del"
    label $wi.bbar.help -text \
	"Press the new button to define a new traffic flow."

    pack $wi.bbar.new $wi.bbar.save $wi.bbar.del -side left
    pack $wi.bbar.help -padx 8 -side left
    pack $wi.bbar -padx 4 -pady 4 -fill both -side top

    labelframe $wi.traf -text "Traffic options"
    frame $wi.traf.opt
    radiobutton $wi.traf.opt.opt1 -variable g_traffic_start_opt -value 0 \
	-text "Do not start traffic flows automatically"
    radiobutton $wi.traf.opt.opt2 -variable g_traffic_start_opt -value 1 \
	-text "Start traffic flows after all nodes have booted"
    radiobutton $wi.traf.opt.opt3 -variable g_traffic_start_opt -value 2 \
	-text "Start traffic flows after routing has converged" -state disabled
    pack $wi.traf.opt.opt1 $wi.traf.opt.opt2 $wi.traf.opt.opt3 \
    	-side top -anchor w
    pack $wi.traf.opt -side top
    frame $wi.traf.btn
    set buttonstate disabled
    if { $oper_mode == "exec" } { set buttonstate normal }
    button $wi.traf.btn.start -text "Start all flows" \
	-command startTrafficScripts -state $buttonstate
    button $wi.traf.btn.stop -text "Stop all flows" \
	-command stopTrafficScripts -state $buttonstate
    button $wi.traf.btn.startsel -text "Start selected" \
	-command "trafficHelper $wi start" -state $buttonstate
    button $wi.traf.btn.stopsel -text "Stop selected" \
	-command "trafficHelper $wi stop" -state $buttonstate
    pack $wi.traf.btn.start $wi.traf.btn.stop $wi.traf.btn.startsel \
	$wi.traf.btn.stopsel -side left
    pack $wi.traf.btn -side top -fill x
    pack $wi.traf -side top -fill x

    # save/cancel buttons
    frame $wi.b -borderwidth 4
    button $wi.b.close -text "Close" -command \
	".c delete withtag twonode; destroy $wi"
    pack $wi.b.close -side bottom
    pack $wi.b -side bottom

    refreshTrafficList $wi
}

# helper for start, stop, delete selected, or add/modify flows
proc trafficHelper { wi cmd } {
    set selected [$wi.f.flows curselection]
    # listbox select
    if { $cmd == "sel" } { .c delete withtag "twonode" }
    # start/stop/delete selected
    if { $cmd == "del" || $cmd == "sel" || $cmd == "start" || $cmd == "stop" } {
	foreach i $selected {
	    set name [$wi.f.flows get $i]
	    if { $cmd == "del" } {
		removeTrafficFlow $name
		refreshTrafficList $wi
	    } elseif { $cmd == "sel" } {
		set flow [getTrafficFlow $name]
		set srcnode [lindex $flow 4]
		if { $srcnode != "" } {
		    set tags "twonode $srcnode"
		    drawNodeCircle $srcnode 30 green $tags ""
		}
		set dstnode [lindex $flow 5]
		if { $dstnode != "" } {
		    set tags "twonode $dstnode"
		    drawNodeCircle $dstnode 30 red $tags ""
		}
	    } else {
		set flow [getTrafficFlow $name]
		if { $flow == "" } { continue }
		startstopTrafficScript $flow $cmd
	    }
	}
	return
    }

    set selected [lindex $selected 0]
    if { $selected == "" } {
	set name ""
    } else {
	set name [$wi.f.flows get $selected]
    }
    if { $cmd == "edit" && $name == "" } { return }
    if { $cmd == "new" } {
	# TODO: find the next flow number and set the name
	set name ""
    }
    popupTraffic2Dialog $name
}

proc refreshTrafficList { wi } {
    global g_traffic_flows

    $wi.f.flows delete 0 end
    if { ![info exists g_traffic_flows] } { set g_traffic_flows "" }

    foreach flow $g_traffic_flows {
	set name [lindex $flow 0]
        $wi.f.flows insert end $name
    }
}

proc popupTraffic2Dialog { name } {
    global g_twoNodeSelect g_twoNodeSelectCallback activetool
    global traffic_flow_protocol traffic_presets
    global g_traffic_pat

    set wi .traffic
    catch {destroy $wi}
    toplevel $wi

    set activetool select

    wm transient $wi
    wm resizable $wi 0 0
    wm title $wi "Edit traffic flow"

    set g_twoNodeSelect ""
    set g_twoNodeSelectCallback selectTwoNodeTrafficCallback

    labelframe $wi.e -text "Flow configuration"

    frame $wi.e.flow -borderwidth 4
    label $wi.e.flow.namel -text "name"
    entry $wi.e.flow.name -bg white -width 20
    label $wi.e.flow.numl -text "flow number"
    entry $wi.e.flow.num -bg white -width 4
    label $wi.e.flow.timestartl -text "start time"
    entry $wi.e.flow.timestart -bg white -width 4
    label $wi.e.flow.timestopl -text "stop time"
    entry $wi.e.flow.timestop -bg white -width 4
    pack $wi.e.flow.namel $wi.e.flow.name \
	$wi.e.flow.numl $wi.e.flow.num $wi.e.flow.timestartl \
	$wi.e.flow.timestart $wi.e.flow.timestopl $wi.e.flow.timestop -side left
    pack $wi.e.flow -side top -fill both

    # sending node
    frame $wi.e.nodes -borderwidth 4
    set sf $wi.e.nodes.src
    labelframe $sf -text "source"

    frame $sf.n -borderwidth 4
    label $sf.n.srcl -text "source node"
    radiobutton $sf.n.src -text " (none) " -variable g_twoNodeSelect \
	-value "$sf.n.src" -indicatoron off -activebackground green \
	-selectcolor green -padx 4 -pady 4
    pack $sf.n.srcl $sf.n.src -side left -padx 4 -pady 4
    pack $sf.n -side top -anchor w

    frame $sf.ipp
    button $sf.ipp.ipl -text "IP" -command \
	"popupAddressPicker $sf.n.src $sf.ipp.ip"
    entry $sf.ipp.ip -bg white -width 15
    label $sf.ipp.pl -text "port"
    entry $sf.ipp.p -bg white -width 5
    pack $sf.ipp.ipl $sf.ipp.ip $sf.ipp.pl $sf.ipp.p -side left -padx 4 -pady 4
    pack $sf.ipp -side top -anchor w

    frame $sf.traff -borderwidth 4
    label $sf.traff.protol -text "protocol"
    tk_optionMenu $sf.traff.proto traffic_flow_protocol "TCP" "UDP" "SINK"
    label $sf.traff.tosl -text "TOS"
    entry $sf.traff.tos -bg white -width 5
    pack $sf.traff.protol $sf.traff.proto $sf.traff.tosl \
	$sf.traff.tos -side left
    pack $sf.traff -side top

    frame $sf.patt -borderwidth 4
    label $sf.patt.patl -text "pattern"
    set trafficpresetsMenu [tk_optionMenu $sf.patt.pat g_traffic_pat presets]
    entry $sf.patt.p -bg white -width 20 
    pack $sf.patt.patl $sf.patt.pat $sf.patt.p -side left
    pack $sf.patt -side top

    frame $sf.log -borderwidth 4
    label $sf.log.l -text "log file"
    entry $sf.log.file -bg white -width 30 
    pack $sf.log.l $sf.log.file -side left
    pack $sf.log -side top

    # receiving node
    set df $wi.e.nodes.dst
    labelframe $df -text "destination"

    frame $df.n -borderwidth 4
    label $df.n.dstl -text "destination node"
    radiobutton $df.n.dst -text " (none) " -variable g_twoNodeSelect \
	-value "$df.n.dst"  -indicatoron off -activebackground red \
	-selectcolor red -padx 4 -pady 4
    button $df.n.clear -text "clear" -command "$df.n.dst configure -text \" (none) \""
    pack $df.n.dstl $df.n.dst $df.n.clear -side left -padx 4 -pady 4
    pack $df.n -side top -anchor w

    frame $df.ipp
    button $df.ipp.ipl -text "IP" -command \
	"popupAddressPicker $df.n.dst $df.ipp.ip"
    entry $df.ipp.ip -bg white -width 15
    label $df.ipp.pl -text "port"
    entry $df.ipp.p -bg white -width 5
    pack $df.ipp.ipl $df.ipp.ip $df.ipp.pl $df.ipp.p -side left -padx 4 -pady 4
    pack $df.ipp -side top -anchor w

    frame $df.log -borderwidth 4
    label $df.log.l -text "log file"
    entry $df.log.file -bg white -width 30
    pack $df.log.l $df.log.file -side left
    pack $df.log -side top

    pack $sf $df -side left -fill both
    pack $wi.e.nodes -side top -fill x

    frame $wi.e.extra -borderwidth 4
    label $wi.e.extra.lab -text "additional MGEN parameters"
    entry $wi.e.extra.txt -bg white -width 40
    pack $wi.e.extra.lab $wi.e.extra.txt -side left
    pack $wi.e.extra -side top -fill x

    pack $wi.e -side top

    set g_traffic_pat presets

    # save/cancel buttons
    frame $wi.b -borderwidth 4
    button $wi.b.apply -text "Apply" \
	-command "popdownTrafficDialog $wi save \"$name\""
    button $wi.b.cancel -text "Cancel" \
	-command "popdownTrafficDialog $wi cancel \"$name\""
    pack $wi.b.cancel $wi.b.apply -side right
    pack $wi.b -side bottom

    # populate traffic presets
    $trafficpresetsMenu delete 0
    foreach p [lsort -dictionary [array names traffic_presets]] {
	set txt [string range $p 3 end]
	$trafficpresetsMenu add radiobutton -label $txt -value $txt \
		-variable g_traffic_pay \
		-command "trafficPresets $wi \"$p\""
    }

    # default values
    .c delete withtag "twonode"
    set flow ""
    if {$name != "" } { set flow [getTrafficFlow $name] }
    if { $flow == "" } {
	set flownum [nextTrafficFlowNumber]
	$wi.e.flow.name insert 0 $name
	$wi.e.flow.num insert 0 $flownum
	$wi.e.flow.timestart insert 0 "0.0"

	set traffic_flow_protocol "UDP"
	$sf.ipp.p insert 0 "5000"
	$df.ipp.p insert 0 "5000"
	$df.log.file insert 0 "/var/log/mgen$flownum.log"
    # load values from flow list
    } else {
	$wi.e.flow.name insert 0 [lindex $flow 0]
	$wi.e.flow.num insert 0 [lindex $flow 1]
	$wi.e.flow.timestart insert 0 [lindex $flow 2]
	$wi.e.flow.timestop insert 0 [lindex $flow 3]
	set srcnode [lindex $flow 4]
	if { $srcnode != "" } {
	    set tags "twonode $srcnode twonode$sf.n.src"
	    $wi.e.nodes.src.n.src configure -text " $srcnode "
	    drawNodeCircle $srcnode 30 green $tags ""
	}
	set dstnode [lindex $flow 5]
	if { $dstnode != "" } {
	    set tags "twonode $dstnode twonode$df.n.dst"
	    $wi.e.nodes.dst.n.dst configure -text " $dstnode "
	    drawNodeCircle $dstnode 30 red $tags ""
	}
	$wi.e.nodes.src.ipp.ip insert 0 [lindex $flow 6]
	$wi.e.nodes.src.ipp.p insert 0 [lindex $flow 7]
	$wi.e.nodes.src.log.file insert 0 [lindex $flow 8]
	$wi.e.nodes.dst.ipp.ip insert 0 [lindex $flow 9]
	$wi.e.nodes.dst.ipp.p insert 0 [lindex $flow 10]
	$wi.e.nodes.dst.log.file insert 0 [lindex $flow 11]
	set traffic_flow_protocol [lindex $flow 12]
	$wi.e.nodes.src.traff.tos insert 0 [lindex $flow 13]
	$wi.e.nodes.src.patt.p insert 0 [lindex $flow 14]
	$wi.e.extra.txt insert 0 [lindex $flow 15]
    }
}

# fill in traffic pattern field when preset has been selected from menu
proc trafficPresets { wi preset } {
    global traffic_presets
    set patterndata $traffic_presets($preset)
    set dst [lindex $patterndata 0]
    set params [lindex $patterndata 1]

    set sf $wi.e.nodes.src
    $sf.patt.p delete 0 end
    $sf.patt.p insert end $params

    set df $wi.e.nodes.dst
    if { $dst != "" } {
	$df.ipp.ip delete 0 end
	$df.ipp.ip insert end $dst
    }
}

# close the traffic window
proc popdownTrafficDialog { wi cmd oldname } {
    global g_traffic_flows traffic_flow_protocol oper_mode
    if { $cmd == "cancel" } {
	.c delete withtag "twonode"
	destroy $wi
	return
    }
    # apply button was pressed
    set num [$wi.e.flow.num get]
    set name [$wi.e.flow.name get]
    set start [$wi.e.flow.timestart get]
    if { $start == "" || $start < 0.0 } { set start 0.0 } 
    set stop [$wi.e.flow.timestop get]

    foreach n [list src dst] {
	set ${n}node [string trim [$wi.e.nodes.$n.n.$n cget -text]]
	set ${n}ip [$wi.e.nodes.$n.ipp.ip get]
	set ${n}port [$wi.e.nodes.$n.ipp.p get]
	set ${n}log [$wi.e.nodes.$n.log.file get]

    }
    set proto $traffic_flow_protocol
    set tos [$wi.e.nodes.src.traff.tos get]
    set pat [$wi.e.nodes.src.patt.p get]
    set extra [$wi.e.extra.txt get]

    if { $oldname != "" } { removeTrafficFlow $oldname }
    
    set trafficentry [list "$name" $num "$start" "$stop" "$srcnode" "$dstnode" \
    	"$srcip" "$srcport" "$srclog" \
	"$dstip" "$dstport" "$dstlog" \
	"$proto" "$tos" "$pat" "$extra"]
    lappend g_traffic_flows $trafficentry
    refreshTrafficList .traffic1
    .c delete withtag "twonode"
    destroy $wi
    if { $oper_mode == "exec" } {
	set sock [lindex [getEmulPlugin $srcnode] 2]
	sendTrafficScript $trafficentry $sock
    }
}

# called from editor.tcl:button1 when user clicks on a node
# search for IP address and populate
proc selectTwoNodeTrafficCallback { } {
    set wi .traffic
    
    if { ![winfo exists $wi] } { return }; # user has closed window
    foreach n [list src dst] {
        set node$n [string trim [$wi.e.nodes.$n.n.$n cget -text]]
        if { [set node$n] == "(none)" } { set node$n "" }
        $wi.e.nodes.$n.ipp.ip delete 0 end
    }
    $wi.e.nodes.src.ipp.ip insert 0 [getDestinationAddress $nodedst $nodesrc]
    $wi.e.nodes.dst.ipp.ip insert 0 [getDestinationAddress $nodesrc $nodedst]

    if { [$wi.e.flow.name get] == "" && $nodesrc != "" && $nodedst != "" } {
	set num [$wi.e.flow.num get]
	$wi.e.flow.name insert 0 "flow $num from $nodesrc to $nodedst"
    }
}

proc popupAddressPicker { ctl dstentry } {
    set wi .addressPicker

    set node [string trim [$ctl cget -text]]

    catch {destroy $wi}
    toplevel $wi

    wm transient $wi
    wm resizable $wi 0 0
    wm title $wi "Select IP"

    # listbox
    labelframe $wi.a -text "IP addresses"
    listbox $wi.a.addrs -selectmode single -width 16 -exportselection 0 \
	-yscrollcommand "$wi.a.addrs_scroll set"
    scrollbar $wi.a.addrs_scroll -command "$wi.a.addrs yview"
    pack $wi.a.addrs $wi.a.addrs_scroll -pady 4 -fill both -side left
    pack $wi.a -padx 4 -pady 4 -fill both -side top
    bind $wi.a.addrs <Double-Button-1> "popdownAddressPicker $wi $dstentry"

    # OK button
    frame $wi.b -borderwidth 4
    button $wi.b.ok -text "OK" -command "popdownAddressPicker $wi $dstentry"
    pack $wi.b.ok $wi.b -side bottom

    # populate the address list
    if { $node == "" || $node == "(none)" } { return }
    set dst [$dstentry get]
    set i 0; set selected 0 
    foreach ifc [ifcList $node] {
	set addr [lindex [split [getIfcIPv4addr $node $ifc] /] 0]
	$wi.a.addrs insert end $addr
	if { $addr == $dst } { set selected $i }
	incr i
    }
    $wi.a.addrs selection set $selected
}

proc popdownAddressPicker { wi dstentry } {
    $dstentry delete 0 end
    set sel [$wi.a.addrs curselection]
    if { $sel != "" } { $dstentry insert 0 [$wi.a.addrs get $sel] }
    destroy $wi
}

proc nextTrafficFlowNumber { } {
    global g_traffic_flows
    set max 0
    foreach flow $g_traffic_flows {
	set n [lindex $flow 1]
	if { $n > $max } { set max $n }
    }
    set next [expr {$max + 1}]
    return $next
}

proc getTrafficFlow { name } {
    global g_traffic_flows
    foreach flow $g_traffic_flows {
	if { [lindex $flow 0] == $name } { return $flow }
    }
    return ""
}

proc removeTrafficFlow { name } {
    global g_traffic_flows
    for { set i 0 } { $i < [llength $g_traffic_flows] } { incr i } {
	set flow [lindex $g_traffic_flows $i]
	if { [lindex $flow 0] == $name } {
	    set g_traffic_flows [lreplace $g_traffic_flows $i $i]
	    return true
	}
    }
    return false
}

# returns a list of node numbers and MGEN scripts for a particular flow
proc getTrafficScripts { flow } {
    if { $flow == "" } { return [list "" "" "" ""] }

    set name [lindex $flow 0]
    set num [lindex $flow 1]
    set start [lindex $flow 2]
    set stop [lindex $flow 3]
    set srcnode [lindex $flow 4]
    set dstnode [lindex $flow 5]
    set srcip "" ;#[lindex $flow 6]   source IP is currently ignored
    set srcport [lindex $flow 7]
    set srclog [lindex $flow 8]
    set dstip [lindex $flow 9]
    set dstport [lindex $flow 10]
    set dstlog [lindex $flow 11]
    set proto [lindex $flow 12]
    set tos [lindex $flow 13]
    set patt [lindex $flow 14]
    set extra [lindex $flow 15]

    foreach n [list src dst] {
	if { [set ${n}ip] != "" } {
	    if { [set ${n}port] != "" } {
		set n${n} "[set ${n}ip]/[set ${n}port]"
	    } else {
		set n${n} [set ${n}ip] 
	    }
	} else { set n${n} [set ${n}port] }
    }
    if { $tos != "" } { set tos "TOS $tos " }

    set s ""; set d ""

    if { $srcnode != "" } {
	set s "# CORE MGEN script: $name"
	set s "$s\n$start ON $num $proto SRC $nsrc DST $ndst $patt $tos$extra"
    }
    if { $dstnode != "" } {
	set d "# CORE MGEN script: $name"
	if { [isMulticast $dstip] } {
	    set d "$d\n$start JOIN $dstip"
	    if { $dstport != "" } { set d "$d PORT $dstport" }
	}
	set d "$d\n$start LISTEN $proto $dstport"
    }

    if { $stop != "" } {
	if { $s != "" } { set s "$s\n$stop OFF $num" }
	if { $d != "" } {
	    set d "$d\n$stop IGNORE $proto $dstport"
	    if { [isMulticast $dstip] } {
		set d "$d\n$stop LEAVE $dstip"
		if { $dstport != "" } { set d "$d PORT $dstport" }
	    }
	}
    }
    return [list $srcnode $dstnode "$s\n" "$d\n"]
}

# send File API messages to create traffic scripts on nodes
proc sendTrafficScripts { sock } {
    global g_traffic_flows
    foreach flow $g_traffic_flows { sendTrafficScript $flow $sock }
}

proc sendTrafficScript { flow sock } {
    set scripts [getTrafficScripts $flow]
    set srcnode [lindex $scripts 0]
    set dstnode [lindex $scripts 1]
    set flownum [lindex $flow 1]
    set name "flow$flownum.mgn" 
    if { $srcnode != "" } {
        set data [lindex $scripts 2]
        set data_len [string length $data]
        sendFileMessage $sock $srcnode "" $name "" $data $data_len
    }
    if { $dstnode != "" } {
        set data [lindex $scripts 3]
        set data_len [string length $data]
        sendFileMessage $sock $dstnode "" $name "" $data $data_len
    }
}

proc startTrafficScripts { } {
    global g_traffic_flows
    foreach flow $g_traffic_flows { startstopTrafficScript $flow start }
}

proc stopTrafficScripts { } {
    global g_traffic_flows
    foreach flow $g_traffic_flows { startstopTrafficScript $flow stop }
}

proc startstopTrafficScript { flow startstop } {
    set flownum [lindex $flow 1]
    set srcnode [lindex $flow 4]
    set dstnode [lindex $flow 5]
    set srclog [lindex $flow 8]
    set dstlog [lindex $flow 11]
    set name "flow$flownum.mgn"
    set mgen "mgen" ;# assume mgen is in PATH, otherwise change this

    # start receiving script first, then sender
    foreach n [list dst src] {
	set sock [lindex [getEmulPlugin [set ${n}node]] 2]
	if { [set ${n}node] == "" || $sock == -1 } { continue }
	if { $startstop == "start" } {
	    set cmd "$mgen instance [set ${n}node]$name input $name"
	    if { [set ${n}log] != "" } { set cmd "$cmd output [set ${n}log]" }
	} else {
	    set cmd "$mgen instance [set ${n}node]$name stop"
	}
	sendExecMessage $sock [set ${n}node] $cmd 0 0
    }
}

