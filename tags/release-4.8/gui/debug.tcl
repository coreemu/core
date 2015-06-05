#
# CORE Debugger
# Copyright 2005-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
#  author:       Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#

.menubar.tools add command -label "Debugger..." -command popupDebugger

set g_last_debug_cmd "puts \"Hello world\""

proc popupDebugger {} {
    global g_last_debug_cmd

    set wi .debugger
    catch { destroy $wi }
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 300 200
    wm title $wi "CORE Debugger"
   
    frame $wi.dbg -borderwidth 4
    label $wi.dbg.label1 \
	-text "Enter TCL/Tk commands below, press Run to evaluate:"
    text $wi.dbg.cmd -bg white -width 100 -height 3

    pack $wi.dbg.label1 $wi.dbg.cmd -side top -anchor w -padx 4 -pady 4
    pack $wi.dbg -side top 

    $wi.dbg.cmd insert end "$g_last_debug_cmd"

    frame $wi.btn
    # evaluate debugging commands entered into the text box below
    button $wi.btn.exec -text "Run" -command {
	global g_last_debug_cmd
	set wi .debugger
	set i 1
	set g_last_debug_cmd ""
	while { 1 } {
	    set cmd [$wi.dbg.cmd get $i.0 $i.end]
	    set g_last_debug_cmd "$g_last_debug_cmd$cmd\n"
	    if { $cmd == "" } { break }
	    catch { eval $cmd } output
	    puts $output
	    incr i
	}
    }
    button $wi.btn.close -text "Close" -command "destroy .debugger"

    pack $wi.btn.exec $wi.btn.close -side left -padx 4 -pady 4
    pack $wi.btn -side bottom
}
