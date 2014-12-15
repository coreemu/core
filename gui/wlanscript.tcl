#
# Copyright 2005-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

#
# run a scengen mobility script
proc wlanRunMobilityScript { wlan } {
    global DEFAULT_SCRIPT_MODEL

    set models [netconfFetchSection $wlan "mobmodel"]
    if { [lsearch $models $DEFAULT_SCRIPT_MODEL] < 0 } { return }

    set scriptcfg [getCustomConfigByID $wlan $DEFAULT_SCRIPT_MODEL]
    if { $scriptcfg == "" } { return }

    global script_${wlan}
    # the end time of the script
    set script_${wlan}(max_time) 1
    # script filename 
    set fn [file tail [getKeyValue "file" $scriptcfg 50]]
    set script_${wlan}(filename) $fn
    # resolution for timer firing in milliseconds
    set script_${wlan}(res) [getKeyValue "refresh_ms" $scriptcfg 50]
    # simulated time -- tied to timescale widget
    set script_${wlan}(time) 0
    # used for updating simulated time
    set script_${wlan}(last_time) 0
    # tied to loop checkbox
    set script_${wlan}(loop) [getKeyValue "loop" $scriptcfg 0]
    # tied to play/pause/stop buttons
    set script_${wlan}(state) init
}

#
# show a script dialog box
proc showMobilityScriptPopup { wlan } {
    global script_$wlan CORE_DATA_DIR

    if { ![info exists script_$wlan] } {
	set msg "No script configured for WLAN $wlan."
	tk_messageBox -type ok -icon warning -message $msg
	return
    }

    set w .scriptpopup$wlan
    catch {destroy $w}
    toplevel $w

    wm transient $w .
    wm title $w "[getNodeName $wlan] mobility script"
    wm geometry $w 320x80

    ttk::frame $w.name -borderwidth 0
    ttk::label $w.name.lab -text "Script file:"
    ttk::label $w.name.file -text [set script_${wlan}(filename)]
    pack $w.name.lab $w.name.file -side left -padx 4 -pady 0
    pack $w.name -side top -anchor w

    #
    # scale frame
    #frame $w.fsc -borderwidth 4
    ttk::frame $w.fsc -borderwidth 0
    ttk::scale $w.fsc.timescale -from 0 -to [set script_${wlan}(max_time)] \
    	-orient horizontal -variable script_${wlan}(time)
    ttk::label $w.fsc.lab -textvariable script_${wlan}(time)
    # -state disabled
    pack $w.fsc.timescale -side left -fill x -expand true
    pack $w.fsc.lab -side left 
    pack $w.fsc -side top -anchor w -padx 4 -fill x -expand true
    
    #
    # control frame
    #
    ttk::frame $w.fctl -borderwidth 0
    # play/pause buttons
    foreach b {play pause stop} {
	set fn "$CORE_DATA_DIR/icons/tiny/script_$b.gif"
	set img$b [image create photo -file $fn]
	ttk::radiobutton $w.fctl.$b -image [set img${b}] \
		-variable script_${wlan}(state) -value $b -style Toolbutton
    }
    $w.fctl.play configure -command "controlMobilityScript $wlan start"
    $w.fctl.stop configure -command "controlMobilityScript $wlan stop"
    $w.fctl.pause configure -command "controlMobilityScript $wlan pause"
    # loop checkbox
    ttk::checkbutton $w.fctl.loop -text "loop" -variable script_${wlan}(loop) \
    	-state disabled
    # resolution text entry
    ttk::label $w.fctl.resl -text "resolution:"
    ttk::entry $w.fctl.res -width 4 -textvariable script_${wlan}(res) \
			-state disabled
    ttk::label $w.fctl.resl2 -text "ms"
    pack $w.fctl.play $w.fctl.pause $w.fctl.stop -side left
    pack $w.fctl.loop -side left
    pack $w.fctl.resl $w.fctl.res $w.fctl.resl2 -side left -padx 4 -pady 4
    pack $w.fctl -side bottom -anchor w

    #$w.fctl.res insert 0 [set script_${wlan}(res)]
    
}

#
# this loop fires periodically, started from exec.tcl/setOperMode(exec)
proc mobility_script_loop {} {
    global oper_mode
    set c .c
    set now [clock clicks -milliseconds]
    set refresh_ms 5000

    set wlanlist [findWlanNodes ""]

    # terminates this event loop
    if { $oper_mode != "exec" } {
	# close any script windows, cleanup
	foreach wlan $wlanlist {
	    global script_$wlan
	    if { [info exists script_$wlan] } {
		set script_${wlan}(state) stop
	        catch {destroy .scriptpopup$wlan}
	    }
	}
        return
    }

    foreach wlan $wlanlist {
        # skip wlan nodes that do not have a mobility script
	global script_$wlan
    	if { ![info exists script_$wlan] } {
	    continue
	}
	if { [set script_${wlan}(state)] == "pause" ||
	     [set script_${wlan}(state)] == "stop" } {
            set script_${wlan}(last_time) 0
	    continue
	}
	if { [set script_${wlan}(state)] == "init" } {
	    if { ![info exists .scriptpopup$wlan] } { 
	        showMobilityScriptPopup $wlan
	    }
	    set script_${wlan}(state) stop
	    continue
	}
	if { [set script_${wlan}(state)] == "play" } {
	    if { [set script_${wlan}(last_time)] == 0 } {
		set script_${wlan}(last_time) $now
	    }
	    # dt is time in seconds since last loop update
	    set dt [expr { ($now - [set script_${wlan}(last_time)]) / 1000.0}]
	    set script_${wlan}(last_time) $now
	    set t [set script_${wlan}(time)]
	    set t [expr {$t + $dt}]
	    set script_${wlan}(time) [format "%.03f" $t]
	}
#	if { [set script_${wlan}(res)] < $refresh_ms } { 
#		set refresh_ms [set script_${wlan}(res)] 
#	}
    }
    
    after 90 { mobility_script_loop }
}

# send an Event Message to the mobility script for start/stop/pause
proc controlMobilityScript { wlan cmd } {
    global DEFAULT_SCRIPT_MODEL
    global eventtypes

    set plugin [lindex [getEmulPlugin "*"] 0]
    set sock [pluginConnect $plugin connect true]

    set type $eventtypes(event_$cmd)
    set nodenum [string range $wlan 1 end]
    set name "mobility:$DEFAULT_SCRIPT_MODEL"
    set data ""

    sendEventMessage $sock $type $nodenum $name $data 0
}

# Event Message has been received indicating a mobility script has been
# started/stopped/paused. Set the global state that controls the WLAN script
# dialog, and correct the end (max) time.
proc handleMobilityScriptEvent { node etype edata etime } {
    global script_${node}

    if { ![info exists script_${node}] } {
	set msg "Received Event Message, but no script configured for $node."
	puts "warning: $msg"
	return
    }

    if { $etype == 7 } {
	set script_${node}(state) "play"
    } elseif { $etype == 8 } {
	set script_${node}(state) "stop"
    } elseif { $etype == 9 } {
	set script_${node}(state) "pause"
    }

    set t [getKeyValue "start" $edata [set script_${node}(time)]]
    set max [getKeyValue "end" $edata [set script_${node}(max_time)]]
    # event time etime is currently ignored

    set script_${node}(time) $t
    set script_${node}(max_time) $max

    set w .scriptpopup$node
    if {[winfo exists $w]} { $w.fsc.timescale configure -to $max }
}

