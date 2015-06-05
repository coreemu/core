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


#****f* exec.tcl/nexec
# NAME
#   nexec -- execute program
# SYNOPSIS
#   set result [nexec $args]
# FUNCTION
#   Executes the sting given in args variable. The sting is not executed 
#   if IMUNES is running in editor only mode. Execution of a string can
#   be local or remote. If socket can not be opened in try of a remote
#   execution, mode is switched to editor only mode. 
# INPUTS
#   * args -- the string that should be executed localy or remotely.
# RESULT
#   * result -- the standard output of the executed string.
#****
proc nexec { node args } {
    global exec_servers

# debug output of every command
#puts "nexec($node): $args"
#if {[lsearch $args ngctl] != -1 } {
#	puts "XXX $args"
#    set fileId [open "nexec.log" a]
#    puts $fileId $args
#    close $fileId
#}
    # safely exec the given command, printing errors to stdout
    if { $node == "localnode" } { ;# local execution
	if { [ catch {eval exec $args} e ] } {
	    if { $e == "child process exited abnormally" } { return };# ignore
	    puts "error executing: exec $args ($e)"
	}
	return $e
    } else {
	puts "error: nexec called with node=$node"
    }
}


proc acquireOperModeLock { mode } {
    global setOperMode_lock oper_mode

    if { ![info exists setOperMode_lock] } { set setOperMode_lock 0 }
    if { $oper_mode == "exec" } {
	# user somehow pressed start while we were still shutting down...
	if { $mode == "exec" } {
	    set choice [tk_messageBox -type yesno -default no -icon warning \
			-message "You have selected to start the session while the previous one is still shutting down. Are you sure you want to interrupt the shutdown? (not recommended)"]
	    if { $choice == "no" } { 
		set activetool select
		return; # return and allow previous setOperMode to finish...
	    }
	# check if user pressed stop while we were starting up...
	} elseif { $setOperMode_lock } { ;# mode == "edit"
	    set choice [tk_messageBox -type yesno -default no -icon warning \
			-message "You are trying to stop the session while it is still starting. Are you sure you want to interrupt the startup? (not recommeded)"]
	    if { $choice == "no" } { 
		set activetool select
		return; # return and allow previous setOperMode to finish...
	    }
	}
    }

    set setOperMode_lock 1
}

proc releaseOperModeLock { } {
    global setOperMode_lock
    set setOperMode_lock 0
}

proc checkRJ45s {} {
    global systype node_list g_prefs

    if { [lindex $systype 0] == "Linux" } {
	if { [file isdirectory /sys/class/net] } {
	    set extifcs [nexec localnode ls /sys/class/net]
	} else {
	    set extifcs [nexec localnode /sbin/ifconfig -a -s | tail -n +2 | awk "{ print \$1 }" | xargs]
	}
        set extifcs \
           [lreplace $extifcs [lsearch $extifcs lo] [lsearch $extifcs lo]]
    } else {
        set extifcs [nexec localnode ifconfig -l]
        set extifcs \
           [lreplace $extifcs [lsearch $extifcs lo0] [lsearch $extifcs lo0]]
    }

    foreach node $node_list {
	if { [getNodeLocation $node] != "" } { continue }
        if { [nodeType $node] == "rj45" } {
        set i [lsearch $extifcs [getNodeName $node]]
        if { $i >= 0 } { continue }
        set msg "Error: external interface \"[getNodeName $node]\""
        set msg "$msg does not exist. Press OK to continue with RJ45s"
        set msg "$msg disabled. NOTE: this setting can be re-enabled"
        set msg "$msg through Session > Options..."
        set choice [tk_messageBox -type okcancel -icon error -message $msg]
        if { $choice == "cancel" } {
	    return -1
        }
	setSessionOptions "" "enablerj45=0"
        break;
        }
    }
    return 0
}

proc drawToolbar { mode } {
    global CORE_DATA_DIR
    global activetoolp defSelectionColor
    set activetoolp ""
    markerOptions off

    #
    # edit mode button bar
    #
    set buttons [list start link]
    foreach b $buttons {
        if { $mode == "exec"} { destroy .left.$b } else {
	    # add buttons when in edit mode
	    set imgf "$CORE_DATA_DIR/icons/tiny/$b.gif"
	    set image [image create photo -file $imgf]
	    catch { 
	    radiobutton .left.$b -indicatoron 0 \
		-variable activetool -value $b -selectcolor $defSelectionColor \
		-width 32 -height 32 -image $image \
		-command "popupMenuChoose \"\" $b $imgf"
	        leftToolTip $b .left
	    	pack .left.$b -side top
	    }
	}    
    }
    # popup toolbar buttons have submenus
    set buttons {routers hubs bgobjs}
    foreach b $buttons {
        if { $mode == "exec"} { destroy .left.$b } else {
	    # create buttons for parent items
	    set menubuttons { }
	    if { $b == "routers" } {
	    	set menubuttons [getNodeTypeNames]
	    } elseif { $b == "hubs" } {
	        set menubuttons { hub lanswitch wlan rj45 tunnel }
	    } elseif { $b == "bgobjs" } {
	    	set menubuttons { marker oval rectangle text }
	    }
	    set firstb [lindex $menubuttons 0]
	    set firstfn "$CORE_DATA_DIR/icons/tiny/$firstb.gif"
	    set image [image create photo -file $firstfn]
    	    $image read "$CORE_DATA_DIR/icons/tiny/arrow.gif" -to 27 22
	    # create the parent menu
	    menubutton .left.$b -indicatoron 0 -direction right \
	    			-width 32 -height 32 -image $image \
				-padx 0 -pady 0 -relief raised \
				-menu .left.${b}.menu
	    set buttonmenu [menu .left.${b}.menu \
	    			-activebackground $defSelectionColor \
	    			-borderwidth 1 -tearoff 0]
	    # create the child menutbuttons
	    drawToolbarSubmenu $b $menubuttons
	    # tooltips for parent and submenu items 
	    leftToolTip $b .left
	    bind $buttonmenu <<MenuSelect>> {leftToolTipSubMenu %W}
 	    bind $buttonmenu <Leave> {
		set newlen [expr {[string length %W] - 6}]
		set w [string range %W 0 $newlen]
		destroy ${w}.balloon
	    }
	    # set submenu tooltips for user-defined types to type name
	    setLeftTooltips $b $menubuttons
	    pack .left.$b -side top
	}
    }

    # 
    # Exec mode button bar
    #
    if { "$mode" == "edit" } {
	.left.start configure -command "startStopButton exec"
    }
    foreach b {stop observe plot marker twonode run } {
	if { "$mode" != "exec" } { destroy .left.$b } else {
	    set cmd ""
	    set fn "$CORE_DATA_DIR/icons/tiny/$b.gif"
	    set image [image create photo -file $fn]
	    if { $b == "stop" } {
		set cmd "startStopButton edit"
	    } elseif { $b == "observe" } {
	    	set cmd "popupObserverWidgets"
	    } elseif { $b == "marker" } {
		set cmd "markerOptions on"
	    } elseif { $b == "mobility" } {
		set cmd "popupMobilityDialog"
	    } elseif { $b == "twonode" } {
		set cmd "popupTwoNodeDialog"
	    } elseif { $b == "run" } {
		set cmd "popupRunDialog"
	    }
	    # add more cmds here
	    radiobutton .left.$b -indicatoron 0 \
		-variable activetool -value $b -command $cmd \
		-selectcolor [.left cget -bg] \
		-width 32 -height 32 -activebackground gray -image $image
	    leftToolTip $b .left
	    pack .left.$b -side top
	}
    }
    # turn off any existing tooltip
    balloon .left ""
}

proc drawToolbarSubmenu { b menubuttons } {
    global CORE_DATA_DIR
    set buttonmenu .left.${b}.menu

    if { ![winfo exists $buttonmenu] } {
	return ;# this may occur in exec mode
    }

    $buttonmenu delete 0 end

    foreach menubutton $menubuttons {
	if { $b == "routers" } {
	    set imgf [getNodeTypeImage $menubutton tiny]
	} else {
	    set imgf "$CORE_DATA_DIR/icons/tiny/${menubutton}.gif"
	}
	if { ![file exists $imgf] } { ;# pop custom filename from list
	    puts "**warning: missing icon $imgf"
	    continue
	}
	set img [createImageButton $imgf 0]
	$buttonmenu add command -image $img -columnbreak 1  \
		-command "popupMenuChoose $b $menubutton $imgf"
    }
    # add an edit button to the end of the row 
    if { $b == "routers" } {
	set imgf "$CORE_DATA_DIR/icons/normal/document-properties.gif"
	set img [createImageButton $imgf 0]
	$buttonmenu add command -image $img -columnbreak 1 \
		-command "popupNodesConfig"
    }
}

proc setSessionStartStopMenu { mode } {
    if { $mode == "exec" } {
	catch   {.menubar.session entryconfigure "Start" \
		-label "Stop" -command "startStopButton edit"} 
    } else {
	catch  {.menubar.session entryconfigure "Stop" \
	   	-label "Start" -command "startStopButton exec"}
    }
}

proc updateMenus { mode } {
    set s "normal"
    if { $mode == "exec" } {
	set s "disabled"
    }
    .menubar.tools entryconfigure "Auto rearrange all" -state $s
    .menubar.tools entryconfigure "Auto rearrange selected" -state $s
    .menubar.session entryconfigure "Node types..." -state $s
    .menubar.session entryconfigure "Emulation servers..." -state $s

    if { $s == "normal" } { set s "" }
    updateUndoRedoMenu $s
}

proc startStopButton { mode } {
    global activetool
    #
    # Prepare API channel for emulation. Do this before any GUI changes
    # so that connect failures leave the GUI in edit mode.
    setSystype
    global systype
    set emul_sock 0
    if { $mode == "exec" } {
	set msg "The CORE daemon must be running and your kernel must support"
	set msg "$msg virtualization for the emulation to start."
    } elseif { $mode == "edit" } {
	set msg "Communication with daemon was lost."
    } else {
	puts "unsupported mode: $mode"
	return
    }

    set plugin [lindex [getEmulPlugin "*"] 0]
    set emul_sock [pluginConnect $plugin connect true]

    if { $emul_sock == "" || $emul_sock == -1 } {
	tk_messageBox -type ok -icon warning -message $msg
	releaseOperModeLock
	set activetool select
	return
    }
    setOperMode $mode
}

#****f* exec.tcl/setOperMode
# NAME
#   setOperMode -- set operating mode
# SYNOPSIS
#   setOperMode $mode
# FUNCTION
#   Sets imunes operating mode to the value of the parameter mode.
#   The mode can be set only to edit or exec.
#   When changing the mode to exec all the emulation interfaces are
#   checked (if they are nonexistent the message is displayed, and 
#   mode is not changed), all the required buttons are disabled 
#  (except the simulation/Terminate button, that is enabled) and
#   procedure deployCfg is called.
#   When changing the mode to edit, all required buttons are enabled
#   (except for simulation/Terminate button that is disabled) and
#   procedure cleanupCfg is called.
# INPUTS
#   * mode -- the new operating mode. Can be edit or exec.
#****
proc setOperMode { mode { type "" } } {
    global oper_mode activetool
    global undolevel redolevel
    global g_prefs

    # special handling when experiment is already running
    acquireOperModeLock $mode

    # Verify that links to external interfaces are properly configured
    if { $mode == "exec" && [getSessionOption enablerj45 1]==1 } {
	if { [checkRJ45s] < 0 } {
	    releaseOperModeLock
	    set activetool select
	    return
	}
    }

    # start/stop menu item
    setSessionStartStopMenu $mode

    #
    # take care of GUI changes and bindings when switching modes
    #
    drawToolbar $mode
    if { $mode == "edit" } { ;# these are the default bindings
	.c bind node <Double-1> "popupConfigDialog .c"
	.c bind nodelabel <Double-1> "popupConfigDialog .c"
    } else { ;# double-click to open shell
	.c bind node <Double-1> "button3node .c %x %y shift"
	.c bind nodelabel <Double-1> "button3node .c %x %y shift"
    }
    set activetool select
    .left.select configure -state active
    updateMenus $mode
    blinkCEL "stop"

    #
    # Start/stop the emulation
    # 
    ### start button is pressed
    if { "$mode" == "exec" } {
	rearrange_off
	set oper_mode exec
	resetAllNodeCoords save
	clearExceptions "" ""
	throwCEL true
	    
	# Bind left mouse click to displaying the CPU usage in 
	# a graph format
	bind .bottom.cpu_load <1> {manageCPUwindow %X %Y 1}
    
	monitor_loop
        set plugin [lindex [getEmulPlugin "*"] 0]
        set emul_sock [pluginConnect $plugin connect false]
	if {$type != "connect"} {
	    deployCfgAPI $emul_sock
	}
	widget_loop
	mobility_script_loop
    ### stop button is pressed
    } else {
	if {$oper_mode != "edit"} {
	    set t_start [clock seconds]
	    shutdownSession
	    statgraph off 0
	    set t_elapsed [expr {[clock seconds] - $t_start}]
	    statline "Cleanup completed in $t_elapsed seconds."
	}
	clearLinkHighlights
	catch { destroy .popup }
	clearWlanLinks ""
	widgets_stop
	set oper_mode edit
	    
	# Bind left mouse click to clearing the CPU graph
	bind .bottom.cpu_load <1> {manageCPUwindow %X %Y 0}
	manageCPUwindow %X %Y 0
    }
    .c config -cursor left_ptr
    releaseOperModeLock
}


#****f* exec.tcl/statline
# NAME
#   statline -- status line
# SYNOPSIS
#   statline $line
# FUNCTION
#   Sets the string of the status line. If the execution mode is 
#   set to batch the line is just printed on the standard output.
# INPUTS
#   * line -- line to be displayed
#****
proc statline {line} {
    global execMode

    if {$execMode == "batch" || $execMode == "addons"} {
	puts $line
    } else {
	.bottom.textbox config -text "$line"
	animateCursor
    }
}

proc getNextMac {} {
    global mac_byte4 mac_byte5

    set a [format %.2x $mac_byte4]
    set b [format %.2x $mac_byte5]
    incr mac_byte5
    if { $mac_byte5 >= 255 } {
	set mac_byte5 0
	incr mac_byte4
    }
    return "00:00:00:aa:$a:$b"
}


#****f* exec.tcl/monitor_loop
# NAME
#   monitor_loop -- monitor loop
# SYNOPSIS
#   monitor_loop
# FUNCTION
#   Calculates the usage of cpu, mbuffers and mbuf clusters.
#   The results are displayed in status line and updated 
#   every two seconds.
#****
proc monitor_loop {} {
    global oper_mode systype
    global server_cpuusage
    global exec_servers 

	
    if {$oper_mode != "exec"} {
	.bottom.cpu_load config -text ""
	.bottom.mbuf config -text ""
	return
    }

    if { [lindex $systype 0] == "Linux" } {
	set cpuusage [getCPUUsage]
	    
	#TODO: get the cpu usage on all the assigned server
	# store usage history for each server stored in an array list
	set assigned_servers [getAssignedRemoteServers]
	for {set i 0} {$i <= [llength $assigned_servers]} {incr i} {
	    if {$i == [llength $assigned_servers]} {
		# localhost
		set ip [getMyIP]
		set cpuusageforserver [lindex $cpuusage 0]
	    } else {
		set server [lindex $assigned_servers $i]
                set srv [array get exec_servers $server]
                if { $srv == "" } { continue }
                set ip [lindex $srv 0]
		# TODO: receive CPU usage from other servers
		set cpuusageforserver 0
	    }
		    
	    # append the latest cpu value to the end of list and
	    # only keep and display the last 20 values for each server
	    set server_cpuusage($ip) [lappend server_cpuusage($ip) $cpuusageforserver]		
	    if { [llength $server_cpuusage($ip)] > 20 } {
		set server_cpuusage($ip) [lreplace $server_cpuusage($ip) 0 0]
	    }		
	}
	    
	    
	#plot the usage data if cpu windows already opened
	# for all servers
	if { [winfo exists .cpu]} {
	    plotCPUusage
	}
    	    
	set cputxt "CPU [lindex $cpuusage 0]% ("
	set cpuusage [lreplace $cpuusage 0 0]
	for { set n 0 } { $n < [llength $cpuusage] } { incr n } {
	    if { $n > 0 } { set cputxt "${cputxt}/" }
	    set cputxt "${cputxt}[lindex $cpuusage $n]"
	}
	set cputxt "$cputxt)"
	set cpulen [expr {[string length $cputxt] - 2}]
	set labellen [.bottom.cpu_load cget -width]
	if { $cpulen < $labellen } { set cpulen $labellen }
	set stats [nexec localnode vmstat | tail -n 1 ]
	set mem_free [lindex $stats 3]
	set mem_free_mb [expr { $mem_free / 1024 }]
        .bottom.cpu_load config -text $cputxt -width $cpulen
	.bottom.mbuf config -text " ${mem_free_mb}M free"
	after 2000 { monitor_loop }
	return
    }

    if { $systype == "FreeBSD 4.11-RELEASE" } {
    	set defaultname "default"
	set cpun 3
    } else {
        set defaultname "."
	set cpun 4
    }

    # CPU usage from `vimage -l`
    set vimagetext [nexec localnode vimage -l $defaultname | xargs]
    set vimagelist [split $vimagetext :]
    set cpuline [lindex $vimagelist $cpun]
    set cpu [lindex [split $cpuline %] 0]

    .bottom.cpu_load config -text "CPU $cpu%"

    # mbuf usage from `netstat -m`
    set nstout [split [nexec localnode netstat -m] ]
    set mbufline [split [lindex $nstout 0] /]
    set mbufs [lindex $mbufline 0]
    set nmbufs [lindex [split [lindex $mbufline 2] " "] 0]
    set mbufp [expr $mbufs * 100 / $nmbufs]
    .bottom.mbuf config -text "mbuf $mbufp%"

    after 2000 { monitor_loop }
}


#****f* exec.tcl/execSetLinkParams
# NAME
#   execSetLinkParams -- in exec mode set link parameters
# SYNOPSIS
#   execSetLinkParams $eid $link
# FUNCTION
#   Sets the link parameters during execution. 
#   All the parameters are set at the same time.
# INPUTS
#   eid -- experiment id
#   link -- link id
#****
proc execSetLinkParams { eid link } {
    set lnode1 [lindex [linkPeers $link] 0]
    set sock [lindex [getEmulPlugin $lnode1] 2]
    sendLinkMessage $sock $link modify
    return
}


# command executed when popup menu item is selected
proc popupMenuChoose { parent b imgf } {
    global activetool activetool_prev activetool_prev_imgf activetoolp
    #puts "popupMenuChoose $parent -> $b ($activetoolp -> $activetool)"

    # deselect previous item
    if { $activetoolp != "" } {
	set img [createImageButton $activetool_prev_imgf 1]
	.left.$activetoolp configure -image $img -relief raised
    }
    if {$activetool_prev == "marker"} { markerOptions off }

    # change the active item; we need activetool_prev b/c of radio button
    set activetoolp $parent
    set activetool $b
    set activetool_prev $b	;# previously-selected activetool
    set activetool_prev_imgf $imgf ;# previously-selected button image file

    # hint for topogen
    global g_last_selected_node_type
    if { $activetoolp == "routers" || $activetoolp == "hubs" } {
	set g_last_selected_node_type [list $parent $b $imgf]
    }

    # select a new button
    if { $parent != "" } {
	set img [createImageButton $imgf 2]
	.left.$parent configure -image $img -relief sunken
    }

    if {$activetool == "marker"} { markerOptions on }

    # status message
    .bottom.textbox config -text "$b tool selected"

}

#
# Boeing - create an image for use on the button toolbar
# style 0 = no arrow, 1 = arrow, 2 = arrow + select color
proc createImageButton { imgf style } {
    global CORE_DATA_DIR defSelectionColor

    if { [catch {set img [image create photo -file $imgf] } e] } {
	puts "warning: error opening button image $imgf ($e)"
	set img [image create photo] ;# blank button
    }
    # add an arrow to the button
    if { $style > 0 } {
	$img read "$CORE_DATA_DIR/icons/tiny/arrow.gif" -to 27 22
	if { $style == 2 } { ;# highlight the button
	    set img2 [image create photo]
	    $img2 put [$img data -background $defSelectionColor]
	    set img $img2
	}
    }
    return $img
    
}

# Boeing: status bar graph
proc statgraph { cmd n } {
    global statgraph_max statgraph_current tk_patchLevel execMode

    if { $execMode != "interactive" || ![info exists tk_patchLevel] } {
	return
    }

    switch -exact $cmd {
	on {
		if { $n == 0 } { return } ;# Boeing: prevent div by 0
		set statgraph_max $n
		set statgraph_current 0
		label .bottom.status -relief sunken -bd 1 -anchor w -width 2 \
			-background green -justify center
		label .bottom.status2 -relief sunken -bd 1 -anchor w -width 12
		pack .bottom.status .bottom.status2  -side left \
			-before .bottom.textbox
	}
	off {
		set statgraph_max 0
		set statgraph_current 0
		destroy .bottom.status
		destroy .bottom.status2
	}
	inc {
		# Boeing: prevent div by 0
		if { $n == 0 || $statgraph_max == 0 } { return }
		incr statgraph_current $n
		set p [expr $statgraph_current.0 / $statgraph_max.0]
		set width [expr int($p * 15)]
		.bottom.status config -width $width
    		.bottom.status config -text "  ([expr int($p*100)]%)"
		.bottom.status2 config -width [expr 15-$width]
	}
    }
}
    
proc popupConnectMessage { dst } {
    global CORE_DATA_DIR execMode

    if { $execMode != "interactive" } { return }

    set wi .popupConnectMessage
    catch { destroy $wi }
    toplevel $wi
    wm transient $wi .
    wm title $wi "Connecting"

    set i [image create photo -file $CORE_DATA_DIR/icons/normal/lanswitch.gif]
    frame $wi.txt
    label $wi.txt.ico -image $i
    label $wi.txt.label1 -text "Please wait, connecting to $dst..."
    pack $wi.txt.ico $wi.txt.label1 -side left -padx 4 -pady 4
    pack $wi.txt -side top

    if { [exec id -u] != 0 } {
	frame $wi.txt2
	set longtext "(Note: remote emulation may have been enabled\n"
	set longtext "$longtext because you are not running as root.)"
	label $wi.txt2.label2 -text $longtext
	pack $wi.txt2.label2 -side left -padx 4 -pady 4
	pack $wi.txt2 -side bottom
    }

    after 100 { catch { grab .popupConnectMessage } }
    update
}

proc popdownConnectMessage { } {
	catch { destroy .popupConnectMessage }
}

proc updateConnectMessage { dst } {
    set wi .popupConnectMessage
    catch {
    $wi.txt.label1 configure -text "Please wait, connecting to $dst..."
    }
}

# helper to return the list of assigned remote execution servers
proc getAssignedRemoteServers {} {
    global node_list
    set servers {}
    foreach node $node_list {
	set server [getNodeLocation $node]
	if { $server == "" } { continue }
	if { [lsearch -exact $servers $server] < 0 } {
	    lappend servers $server
	}
    }
    return $servers
}

# generate a separate window for displaying CPU
proc manageCPUwindow {xpos ypos start} {

    global exec_servers
    global server_cpuusage
	
    if {$start == 1} {
	if { ![winfo exists .cpu]} {    
            toplevel .cpu
	    wm geometry .cpu 200x210+$xpos+$ypos
	    wm resizable .cpu 0 0
	    wm title .cpu "CPU Usage"				
	    canvas .cpu.graph -width 200 -height 210		
	    pack .cpu.graph
	}	    	    	    
    } else {
	if { [winfo exists .cpu]} {
	    destroy .cpu
	    set assigned_servers [getAssignedRemoteServers]
		
	    for {set i 0} {$i <= [llength $assigned_servers]} {incr i} {
		if {$i == [llength $assigned_servers]} {
		    set ip [getMyIP]
		} else {
		    set server [lindex $assigned_servers $i]
		    set srv [array get exec_servers $server]
		    if { $srv == "" } { continue }
		    set ip [lindex $srv 0]
		}	
		set server_cpuusage($ip) [lreplace $server_cpuusage($ip) 0 end]
	    }
	}
    }
}

proc getMyIP { } {
    if { [catch {set theServer [socket -server none -myaddr \
                                [info hostname] 0]} ] } {
        return "127.0.0.1"
    }
    set myIP [lindex [fconfigure $theServer -sockname] 0]
    close $theServer
    return $myIP
	
}

# display all values stored in cpu usage history for each server
proc plotCPUusage { } {
    global cpu_palettes
    global exec_servers
    global server_cpuusage
		
    .cpu.graph delete "all"	
    .cpu.graph create line 0 100 200 100 -width 2
    .cpu.graph create line 0 80 200 80 -width 1
    .cpu.graph create line 0 60 200 60 -width 1
    .cpu.graph create line 0 40 200 40 -width 1
    .cpu.graph create line 0 20 200 20 -width 1
    .cpu.graph create line 0 0 200 0 -width 1
	
    .cpu.graph create line 40 0 40 100 -width 1
    .cpu.graph create line 80 0 80 100 -width 1
    .cpu.graph create line 120 0 120 100 -width 1
    .cpu.graph create line 160 0 160 100 -width 1
    .cpu.graph create line 200 0 200 100 -width 1

    # for each server create a plot of cpu usage								
    set assigned_servers [getAssignedRemoteServers]	
    for {set i 0} {$i <= [llength $assigned_servers]} {incr i} {	    
	if {$i == [llength $assigned_servers]} {
	    set ip [getMyIP]
	} else {
	    set server [lindex $assigned_servers $i]
            set srv [array get exec_servers $server]
            if { $srv == "" } { continue }
            set ip [lindex $srv 0]
	}
		
	#need to add multiple cpuusgaehistory (array)
	for { set n 1 } { $n < [llength $server_cpuusage($ip)] } { incr n } {	    		    
	    set prevn [expr {$n - 1}]
	    set x1 [expr {$prevn * 10}]
	    set y1 [expr {100 - [lindex $server_cpuusage($ip) $prevn]}]
	    set x2 [expr {$n * 10}]
	    set y2 [expr {100 - [lindex $server_cpuusage($ip) $n]}]
	    if {$i < [llength $cpu_palettes]} {
		    .cpu.graph create line $x1 $y1 $x2 $y2 -fill [lindex $cpu_palettes $i]
		} else {
		    .cpu.graph create line $x1 $y1 $x2 $y2 -fill [lindex $cpu_palettes end]

		}
	    #debug    
	    #puts " cpu $x1 $y1 $x2 $y2"		
	}
				
	#for each server create a legend (limited to 8)
	set legendtext $ip
	append legendtext " " [lindex $server_cpuusage($ip) end] "%"
		
	set legendy [expr {($i * 10) + 120}] 
	set legendx 10
	if {$i < [llength $cpu_palettes]} {
	    .cpu.graph create rectangle $legendx $legendy \
		[expr {$legendx + 8}] [expr {$legendy + 8}] \
		-fill [lindex $cpu_palettes $i]
	    .cpu.graph create text [expr {$legendx + 15}] [expr {$legendy + 4}]\
		-text $legendtext -fill [lindex $cpu_palettes $i] \
		-anchor w -justify left
	} else {
	    .cpu.graph create rectangle $legendx $legendy \
		[expr {$legendx + 8}] [expr {$legendy + 8}] \
		-fill [lindex $cpu_palettes end]
	    .cpu.graph create text [expr {$legendx + 15}] [expr {$legendy + 4}]\
		-text $legendtext -fill [lindex $cpu_palettes end] \
		-anchor w -justify left
		
	}
	    
    }
}

