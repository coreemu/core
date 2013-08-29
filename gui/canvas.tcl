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
#

#****h* imunes/canvas.tcl
# NAME
#  canvas.tcl -- file used for manipultaion with canvases in IMUNES
# FUNCTION
#  This module is used to define all the actions used for configuring 
#  canvases in IMUNES. On each canvas a part of the simulation is presented
#  If there is no additional canvas defined, simulation is presented on the 
#  defalut canvas.
#
#****

#****f* canvas.tcl/removeCanvas
# NAME
#   removeCanvas -- remove canvas 
# SYNOPSIS
#   removeCanvas $canvas_id
# FUNCTION
#   Removes the canvas from simulation. This function does not change the 
#   configuration of the nodes, i.e. nodes attached to the removed canvas 
#   remain attached to the same non existing canvas.
# INPUTS
#   * canvas_id -- canvas id
#****

proc removeCanvas { canvas } {
    global canvas_list $canvas

    set i [lsearch $canvas_list $canvas]
    set canvas_list [lreplace $canvas_list $i $i]
    set $canvas {}
}

#****f* canvas.tcl/newCanvas
# NAME
#   newCanvas -- craete new canvas 
# SYNOPSIS
#   set canvas_id [newCanvas $canvas_name]
# FUNCTION
#   Creates new canvas. Returns the canvas_id of the new canvas.
#   If the canvas_name parameter is empty, the name of the new canvas
#   is set to CanvasN, where N represents the canvas_id of the new canvas.
# INPUTS
#   * canvas_name -- canvas name
# RESULT
#   * canvas_id -- canvas id
#****

proc newCanvas { name } {
    global canvas_list

    set canvas [newObjectId canvas]
    global $canvas
    lappend canvas_list $canvas
    set $canvas {}
    if { $name != "" } {
	setCanvasName $canvas $name
    } else {
	setCanvasName $canvas Canvas[string range $canvas 1 end]
    }

    return $canvas
}


proc setCanvasSize { canvas x y } {
    global $canvas

    set i [lsearch [set $canvas] "size *"]
    if { $i >= 0 } {
	set $canvas [lreplace [set $canvas] $i $i "size {$x $y}"]
    } else {
	set $canvas [linsert [set $canvas] 1 "size {$x $y}"]
    }
}

proc getCanvasSize { canvas } {
    global $canvas g_prefs

    set entry [lrange [lsearch -inline [set $canvas] "size *"] 1 end]
    set size [string trim $entry \{\}]
    if { $size == "" } {
	return "$g_prefs(gui_canvas_x) $g_prefs(gui_canvas_y)"
    } else {
	return $size
    }
}

#****f* canvas.tcl/getCanvasName
# NAME
#   getCanvasName -- get canvas name
# SYNOPSIS
#   set canvas_name [getCanvasName $canvas_id]
# FUNCTION
#   Returns the name of the canvas.
# INPUTS
#   * canvas_id -- canvas id
# RESULT
#   * canvas_name -- canvas name
#****

proc getCanvasName { canvas } {
    global $canvas

    set entry [lrange [lsearch -inline [set $canvas] "name *"] 1 end]
    return [string trim $entry \{\}]
}

#****f* canvas.tcl/setCanvasName
# NAME
#   setCanvasName -- set canvas name
# SYNOPSIS
#   setCanvasName $canvas_id $canvas_name
# FUNCTION
#   Sets the name of the canvas.
# INPUTS
#   * canvas_id -- canvas id
#   * canvas_name -- canvas name
#****

proc setCanvasName { canvas name } {
    global $canvas

    set i [lsearch [set $canvas] "name *"]
    if { $i >= 0 } {
	set $canvas [lreplace [set $canvas] $i $i "name {$name}"]
    } else {
	set $canvas [linsert [set $canvas] 1 "name {$name}"]
    }
}

# Boeing: canvas wallpaper support
proc getCanvasWallpaper { canvas } {
    global $canvas

    set entry [lrange [lsearch -inline [set $canvas] "wallpaper *"] 1 end]
    set entry2 [lrange [lsearch -inline \
    	[set $canvas] "wallpaper-style *"] 1 end]
    return [list [string trim $entry \{\}] [string trim $entry2 \{\}]]
}

proc setCanvasWallpaper { canvas file style} {
    global $canvas

    set i [lsearch [set $canvas] "wallpaper *"]
    if { $i >= 0 } {
	set $canvas [lreplace [set $canvas] $i $i "wallpaper {$file}"]
    } else {
	set $canvas [linsert [set $canvas] 1 "wallpaper {$file}"]
    }

    set i [lsearch [set $canvas] "wallpaper-style *"]
    if { $i >= 0 } {
	set $canvas [lreplace [set $canvas] $i $i "wallpaper-style {$style}"]
    } else {
	set $canvas [linsert [set $canvas] 1 "wallpaper-style {$style}"]
    }
}

# Boeing: manage canvases
proc manageCanvasPopup { x y } {
    global curcanvas CORE_DATA_DIR

    set w .entry1
    catch {destroy $w}
    toplevel $w -takefocus 1

    if { $x == 0 && $y == 0 } {
	set screen [wm maxsize .]
	set x [expr {[lindex $screen 0] / 4}]
	set y [expr {[lindex $screen 1] / 4}]
    } else {
	set x [expr {$x + 10}]
	set y [expr {$y - 250}]
    }
    wm geometry $w +$x+$y
    wm title $w "Manage Canvases"
    wm iconname $w "Manage Canvases"


    ttk::frame $w.name
    ttk::label $w.name.lab -text "Canvas name:"
    ttk::entry $w.name.ent
    $w.name.ent insert 0 [getCanvasName $curcanvas]
    pack $w.name.lab $w.name.ent -side left -fill x
    pack $w.name -side top -padx 4 -pady 4
    
    global canvas_list
    ttk::frame $w.canv
    listbox $w.canv.cl -bg white -yscrollcommand "$w.canv.scroll set"
    ttk::scrollbar $w.canv.scroll -orient vertical -command "$w.canv.cl yview"
    foreach canvas $canvas_list {
	$w.canv.cl insert end [getCanvasName $canvas]
	if { $canvas == $curcanvas } {
	    set curindex [expr {[$w.canv.cl size] - 1}]
	}
    }
    pack $w.canv.cl -side left -pady 4 -fill both -expand true
    pack $w.canv.scroll -side left -fill y
    pack $w.canv -side top -fill both -expand true -padx 4 -pady 4
    $w.canv.cl selection set $curindex
    $w.canv.cl see $curindex
    bind $w.canv.cl <Double-1> "manageCanvasSwitch $w"

    ttk::frame $w.buttons2
    foreach b {up down} {
        set fn "$CORE_DATA_DIR/icons/tiny/arrow.${b}.gif"
        set img$b [image create photo -file $fn]
	ttk::button $w.buttons2.$b -image [set img${b}] \
			-command "manageCanvasUpDown $w $b"
    }
    pack $w.buttons2.up $w.buttons2.down -side left -expand 1
    pack $w.buttons2 -side top -fill x -pady 2

    # hidden list of canvas numbers
    ttk::label $w.list -text $canvas_list

    ttk::frame $w.buttons
    ttk::button $w.buttons.apply -text "Apply" -command "manageCanvasApply $w"
    ttk::button $w.buttons.cancel -text "Cancel" -command "destroy $w"
    pack $w.buttons.apply $w.buttons.cancel -side left -expand 1
    pack $w.buttons -side bottom -fill x -pady 2m

    bind $w <Key-Escape> "destroy $w"
    bind $w <Key-Return> "manageCanvasApply $w"

}

# Boeing: manage canvases helper
# called when a canvas in the list is double-clicked
proc manageCanvasSwitch { w } {
    global canvas_list curcanvas
    set i [$w.canv.cl curselection]
    if {$i == ""} { return}
    set i [lindex $i 0]
    set item [$w.canv.cl get $i]

    foreach canvas $canvas_list {
	if {[getCanvasName $canvas] == $item} {
	    $w.name.ent delete 0 end
    	    $w.name.ent insert 0 $item
	    set curcanvas $canvas
	    switchCanvas none
	    return
	}
    }
}

# manage canvases helper
# handle the move up/down buttons for the canvas selection window
proc manageCanvasUpDown { w dir } {
    global canvas_list
    # get the currently selected item
    set i [$w.canv.cl curselection]
    if {$i == ""} { return}
    set i [lindex $i 0]
    set item [$w.canv.cl get $i]

    if {$dir == "down" } {
        set max [expr {[llength $canvas_list] - 1}]
    	if {$i >= $max } { return }
	set newi [expr {$i + 1}]
    } else {
    	if {$i <= 0} { return }
	set newi [expr {$i - 1}]
    }

    # change the position
    $w.canv.cl delete $i
    $w.canv.cl insert $newi $item
    $w.canv.cl selection set $newi
    $w.canv.cl see $newi

    # update hidden list of canvas numbers
    set new_canvas_list [$w.list cget -text]
    set item [lindex $new_canvas_list $i]
    set new_canvas_list [lreplace $new_canvas_list $i $i]
    set new_canvas_list [linsert $new_canvas_list $newi $item]
    $w.list configure -text $new_canvas_list
}

# manage canvases helper
# called when apply button is pressed - changes the order of the canvases
proc manageCanvasApply { w } {
   global canvas_list curcanvas changed
   # we calculated this list earlier, making life easier here
   set new_canvas_list [$w.list cget -text]
   if {$canvas_list != $new_canvas_list} {
	set canvas_list $new_canvas_list
   }
   set newname [$w.name.ent get]
   destroy $w
   if { $newname != [getCanvasName $curcanvas] } {
       set changed 1
   }
   setCanvasName $curcanvas $newname
   switchCanvas none
   updateUndoLog
}

proc setCanvasScale { canvas scale } {
    global $canvas

    set i [lsearch [set $canvas] "scale *"]
    if { $i >= 0 } {
	set $canvas [lreplace [set $canvas] $i $i "scale $scale"]
    } else {
	set $canvas [linsert [set $canvas] 1 "scale $scale"]
    }
}

proc getCanvasScale { canvas } {
    global $canvas g_prefs

    set entry [lrange [lsearch -inline [set $canvas] "scale *"] 1 end]
    set scale [string trim $entry \{\}]
    if { $scale == "" } {
	if { ![info exists g_prefs(gui_canvas_scale)] } { return 150.0 }
	return "$g_prefs(gui_canvas_scale)"
    } else {
	return $scale
    }
}

proc setCanvasRefPoint { canvas refpt } {
    global $canvas

    set i [lsearch [set $canvas] "refpt *"]
    if { $i >= 0 } {
	set $canvas [lreplace [set $canvas] $i $i "refpt {$refpt}"]
    } else {
	set $canvas [linsert [set $canvas] 1 "refpt {$refpt}"]
    }
}

proc getCanvasRefPoint { canvas } {
    global $canvas g_prefs DEFAULT_REFPT

    set entry [lrange [lsearch -inline [set $canvas] "refpt *"] 1 end]
    set altitude [string trim $entry \{\}]
    if { $altitude == "" } {
	if { ![info exists g_prefs(gui_canvas_refpt)] } {
	    return $DEFAULT_REFPT 
	}
	return "$g_prefs(gui_canvas_refpt)"
    } else {
	return $altitude
    }
}

# from http://wiki.tcl.tk/1415 (MAK)
proc canvasSee { hWnd items } {
    set box [eval $hWnd bbox $items]

    if {$box == ""} { return }

    if {[string match {} [$hWnd cget -scrollregion]] } {
        # People really should set -scrollregion you know...
        foreach {x y x1 y1} $box break

        set x [expr round(2.5 * ($x1+$x) / [winfo width $hWnd])]
        set y [expr round(2.5 * ($y1+$y) / [winfo height $hWnd])]

        $hWnd xview moveto 0
        $hWnd yview moveto 0
        $hWnd xview scroll $x units
        $hWnd yview scroll $y units
    } else {
        # If -scrollregion is set properly, use this
        foreach { x y x1 y1  } $box break
        foreach { top  btm   } [$hWnd yview] break
        foreach { left right } [$hWnd xview] break
        foreach { p q xmax ymax } [$hWnd cget -scrollregion] break

        set xpos [expr (($x1+$x) / 2.0) / $xmax - ($right-$left) / 2.0]
        set ypos [expr (($y1+$y) / 2.0) / $ymax - ($btm-$top)    / 2.0]

        $hWnd xview moveto $xpos
        $hWnd yview moveto $ypos
    }
}
