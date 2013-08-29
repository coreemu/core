#
# Copyright 2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

array set g_exceptions {}
global execMode
if { $execMode == "interactive" } {
    set g_img_cel [image create photo -file $CORE_DATA_DIR/icons/tiny/cel.gif]
}
set g_cel_blink_state "off"

# receive an exception into the g_exceptions array from an Exception Message
proc receiveException { valuelist } {
    global g_exceptions EXCEPTION_LEVELS
    set idx [expr {1 + [array size g_exceptions]}]
    array set g_exceptions [list $idx $valuelist]
    # exceptions with level ERROR or FATAL will throw the CEL
    array set vals $valuelist
    if { $vals(level) <= [lsearch -exact $EXCEPTION_LEVELS "ERROR"] } {
	throwCEL false
	if { $vals(level) <= [lsearch -exact $EXCEPTION_LEVELS "FATAL" ] } {
	    blinkCEL start
	}
    }
}

# turn on/off the CEL in the bottom right indicator area
proc throwCEL { clear } {
    global execMode
    if { $execMode != "interactive" } { return }
    global g_img_cel

    if { $clear } {
	.bottom.indicators configure -image "" -width 5
    } else {
	if { [.bottom.indicators cget -image] == "" } {
	    .bottom.indicators configure -image $g_img_cel -width 42
	}
    }
}

# blink the CEL on and off for fatal errors
proc blinkCEL { cmd } {
    global execMode
    if { $execMode != "interactive" } { return }
    # keep track of state so this can be called multiple times
    global g_cel_blink_state
    if { $cmd == "start" } {
	if { $g_cel_blink_state != "off" } { return } ;# already on
	set g_cel_blink_state "on"
    } elseif { $cmd == "stop" } {
	if { $g_cel_blink_state != "on" } { return } ;# already off
	set g_cel_blink_state "off"
    }

    if { $g_cel_blink_state == "off" } {
	throwCEL true
	return
    }

    if { [.bottom.indicators cget -image] == "" } {
	set clear false ;# CEL is off, turn it on
    } else {
	set clear true ;# CEL is on, turn it off
    }
    throwCEL $clear
    after 750 blinkCEL "blink"
}

# clear the g_exceptions array and the CEL
proc clearExceptions { tree txt } {
    global g_exceptions
    array unset g_exceptions
    array set g_exceptions {}
    if  { $tree != "" } {
	exceptionsPopulateTree $tree $txt
    }
}

# show the CEL dialog for viewing a list of exceptions
proc popupExceptions {} {
    global g_img_cel CORE_STATE_DIR
    set w .popupExceptions
    catch {destroy $w}
    toplevel $w
    wm transient $w .
    wm title $w "CEL"

    ttk::frame $w.top
    ttk::label $w.top.icon -image $g_img_cel
    ttk::label $w.top.lab -text "Check Emulation Light"
    pack $w.top.icon $w.top.lab -side left -padx 4
    pack $w.top -side top -padx 4 -pady 4

    ttk::frame $w.mid
    ttk::treeview $w.mid.tree -columns {time level node source} -show headings \
	-yscroll "$w.mid.vsb set" -xscroll "$w.mid.hsb set"
    ttk::scrollbar $w.mid.vsb -orient vertical -command "$w.mid.tree yview"
    ttk::scrollbar $w.mid.hsb -orient horizontal -command "$w.mid.tree xview"
    pack $w.mid -side top -fill both -expand true -padx 4 -pady 4
    grid $w.mid.tree $w.mid.vsb -in $w.mid -sticky nsew
    grid $w.mid.hsb -in $w.mid -sticky nsew
    grid column $w.mid 0 -weight 1
    grid row $w.mid 0 -weight 1

    ttk::frame $w.detail
    text $w.detail.txt -height 10 -yscrollcommand "$w.detail.vsb set"
    ttk::scrollbar $w.detail.vsb -orient vertical -command "$w.detail.txt yview"
    pack $w.detail -side top -fill both -expand true -padx 4 -pady 4
    grid $w.detail.txt $w.detail.vsb -in $w.detail -sticky nsew
    grid column $w.detail 0 -weight 1
    grid row $w.detail 0 -weight 1

    bind $w.mid.tree <<TreeviewSelect>> \
	"exceptionSelect $w.mid.tree $w.detail.txt"

    ttk::frame $w.btn
    set clearhicmd "drawNodeCircle {} {} {} {} excphi"
    set clearexcpcmd "clearExceptions $w.mid.tree $w.detail.txt"
    set closecmd "destroy $w; $clearhicmd"
    bind $w <Key-Escape> $closecmd
    ttk::button $w.btn.reset -text "Reset CEL" \
	-command "throwCEL true; blinkCEL stop; $clearhicmd; $clearexcpcmd"
    ttk::button $w.btn.log -text "View core-daemon log" \
	-command "popupFileView $CORE_STATE_DIR/log/core-daemon.log"
    ttk::button $w.btn.nlog -text "View node log" -state disabled
    ttk::button $w.btn.close -text "Close" -command $closecmd
    pack $w.btn.reset $w.btn.log $w.btn.nlog $w.btn.close -side left
    pack $w.btn -side top -padx 4 -pady 4

    # populate treeview
    set widths { 150 40 40 60 }; set i 0
    foreach col {time level node source} {
	$w.mid.tree heading $col -text $col
	set width [lindex $widths $i]; incr i
	$w.mid.tree column $col -width $width
    }
    exceptionsPopulateTree $w.mid.tree $w.detail.txt
}

# populate the given TreeView with a list of exceptions from g_exceptions
proc exceptionsPopulateTree { tree txt } {
    global g_exceptions

    set items [$tree children {}]
    $tree delete $items
    $txt delete 0.0 end

    foreach idx [lsort -integer [array names g_exceptions]] {
	array set vals $g_exceptions($idx)
	set level [exceptionLevelText $vals(level)]
	$tree insert {} end -id $idx \
		-values [list $vals(date) "$level ($vals(level))" \
			$vals(num) $vals(src)]
    }
}

# user has clicked on an exception from the TreeView, display the details
proc exceptionSelect { tree txt } {
    global g_exceptions g_current_session
    set idx [$tree selection]
    set btn .popupExceptions.btn.nlog

    $txt delete 0.0 end
    drawNodeCircle "" "" "" "" excphi

    if { ![info exists g_exceptions($idx)] } {
	puts "missing exception data"
	return
    }
    array set vals $g_exceptions($idx)
    $txt insert end "DATE: $vals(date)\n"
    set level [exceptionLevelText $vals(level)]
    $txt insert end "LEVEL: $level ($vals(level))\n"
    set node ""
    if { $vals(num) >= 0 } {
	set node "n$vals(num)"
	global $node
	if { [info exists $node] } {
	    drawNodeCircle $node 30 red excphi ""
	    set node [getNodeName $node]
	    $btn configure -command \
	    	"popupFileView /tmp/pycore.$g_current_session/$node.log"
	    $btn state !disabled
	} else {
	    $btn state disabled
	}
    } else {
	$btn state disabled
    }
    $txt insert end "NODE: $vals(num)\t($node)\n"
    $txt insert end "SESSION: $vals(sess)\n"
    $txt insert end "SOURCE: $vals(src)\n"
    $txt insert end "\n$vals(txt)\n\n"
    if { $vals(opaque) != "" } {
	$txt insert end "\nOPAQUE: $vals(opaque)\n\n"
    }
}

proc exceptionLevelText { level } {
    global EXCEPTION_LEVELS ;# from api.tcl
    if { $level < 0 || $level >= [llength $EXCEPTION_LEVELS] } {
	return "UNKNOWN"
    } else {
	return [lindex $EXCEPTION_LEVELS $level]
    }
}

