#
# Copyright 2005-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

array set left_tooltips {
	select	"selection tool"
	start	"start the session"
	link	"link tool"
	routers "network-layer virtual nodes"
	hubs	"link-layer nodes"
	bgobjs	"background annotation tools"
	routers0	"router"
	routers1	"host"
	routers2	"pc"
	hubs0	"ethernet hub"
	hubs1	"ethernet switch"
	hubs2	"wireless LAN"
	hubs3	"rj45 physical interface tool"
	hubs4	"tunnel tool"
	hubs5	"ktunnel tool"
	bgobjs0	"marker"
	bgobjs1	"oval"
	bgobjs2	"rectangle"
	bgobjs3	"text"
	stop	"stop the session"
	marker	"marker"
	mobility "add and remove static links"
	twonode	"run command from one node to another"
}

proc leftToolTip { w parent } {
    global left_tooltips g_prefs
    if { ! $g_prefs(gui_show_tooltips) } { return } ;# user has turned off ttips
    if { ![info exists left_tooltips($w)] } { return }
    balloon $parent.$w $left_tooltips($w)
}

#
# Show a sub-menu tooltip. This is called from a <<MenuSelect>> event.
proc leftToolTipSubMenu { w } {
    global left_tooltips g_prefs
    if { ! $g_prefs(gui_show_tooltips) } { return } ;# user has turned off ttips

    set index [$w index active]
    if { $index == "none" } { return }

    # fix window path for submenus
    if { [lindex [split $w .] end] == "menu" } {
	set newlen [expr {[string length $w] - 6}]
	set w [string range $w 0 $newlen]
    }
    # set ypos [$w yposition $index]
    set wmx [expr [winfo rootx $w] + ($index * 64)]
    set wmy [expr [winfo rooty $w]+int(1.5*[winfo height $w])]
    # puts "submenu: $index = $ypos"
    set submenu [lindex [split $w .] end]
    if { [info exists left_tooltips($submenu$index)] } {
	set caption $left_tooltips($submenu$index)
    } elseif { [info exists left_tooltips($w)] } {
	set caption $left_tooltips($w)
    } else {
	return
    }
    ::balloon::show2 $w $wmx $wmy $caption
}

proc floatingInfo3 { c node } {
    global zoom
#    if { $oper_mode != "exec" } {
#	return
#    }
    if { $node != "" } {
	# this floating info already exists
        if { [$c find withtag "floatinfo && $node"] != "" } {
	    return
        }
    } else {
	# popdown floating info
        $c delete -withtag floatinfo
	return
    }
    set coords [getNodeCoords $node]
    set x [expr {int([lindex $coords 0] * $zoom)}]
    set y [expr {int([lindex $coords 1] * $zoom)}]
    set w ""
    set wmx [expr [winfo rootx $c] + $x + 40]
    set wmy [expr [winfo rooty $c] + $y + 40]
# int(1.5*[winfo height $c])
    foreach n [$c find withtag "node && $node"] {
	::balloon::show2 $w $wmx $wmy "$node stuff"
    }
}

# Draw a square gray box on the canvas at the given node's coordinates
# containing the given caption. This is used by the Observer Widgets.
proc floatingInfo { c node caption } {
    global zoom oper_mode

    if { $oper_mode != "exec" } {
	return
    }
    if { $node != "" } {
	# this floating info already exists
        if { [$c find withtag "floatinfo && $node"] != "" } {
	    return
        }
    } else {
	# popdown floating info
        $c delete -withtag floatinfo
	return
    }
    # this controls the rectangle padding
    set offset 5 

    set coords [getNodeCoords $node]
    set x [expr {15 + [lindex $coords 0] * $zoom}]
    set y [expr {10 + [lindex $coords 1] * $zoom}]

    # only one floatinfo visible at a time
    $c delete -withtag floatinfo

    # text
    set float [$c create text $x $y \
			-text $caption -font "fixed 8" \
			-tag "floatinfo $node" -justify left -anchor nw]
    $c bind $float <Leave> "anyLeave $c"
    # text size is variable, base rectangle size on bounding box
    set bbox [$c bbox $float]
    set x1 [expr { [lindex $bbox 0] - $offset}]
    set y1 [expr { [lindex $bbox 1] - $offset}]
    set x2 [expr { [lindex $bbox 2] + $offset}]
    set y2 [expr { [lindex $bbox 3] + $offset}]

    # shadow
    roundRect $c $x1 $y1 [expr $x2 + 1] [expr $y2 + 1] 10.0 -fill black \
	-tag "floatinfo $node"
    # rounded rectangle
    roundRect $c $x1 $y1 $x2 $y2 10.0 -fill gray -tag "floatinfo $node"

    # raise floatinfo above everything else
    $c raise $float

    # check if the rectangle is drawn off the canvas, slide it into view
    set r [.c cget -scrollregion]
    set minx [expr { [lindex $r 0] * [lindex [.c xview] 0] }]
    set maxx [expr { $minx + ([lindex $r 2] * [lindex [.c xview] 1]) }]
    set miny [expr { [lindex $r 1] * [lindex [.c yview] 0] }]
    set maxy [expr { $miny + ([lindex $r 3] * [lindex [.c yview] 1]) }]

    set dx 0; set dy 0
    if { $x2 > $maxx } {	;# slide left
	set dx [expr {$maxx - $x2}]
    } elseif { $x1 < $minx } {	;# slide right
	set dx [expr {$minx - $x1}]
    }
    if { $y2 > $maxy } {	;# slide up
	set dy [expr {$maxy - $y2}]
    } elseif { $y1 < $miny } { 	;# slide down
	set dy [expr {$miny - $y1}]
    }
    if { $dx != 0 || $dy != 0 } {
	after 550 "floatingInfoSlide $c $node $float $dx $dy 200"
    }
}

# slide the floating info box into view
# recursively calls self with decaying function
proc floatingInfoSlide { c node float dx dy delay } {
    #puts "floatingInfoSlide $c $node $dx $dy"
    if { [$c type $float] == "" } {
	return; # this particular floatinfo text no longer exists
    }

    # calculate a new x,y amount to slide the info box, decaying somewhat
    set movex [expr {$dx/3}]; set movey [expr {$dy/3}]

    $c move "floatinfo && $node" $movex $movey

    # calculate amount left to move
    set newdx [expr {$dx - $movex}]; set newdy [expr {$dy - $movey}]
    # slightly increasing delay slows down the sliding effect
    set delay [expr {int($delay * 1.1)}]

    # recursively call self with new parameters, if any movement is left
    if {$newdx != 0 || $newdy != 0} {
	after $delay "floatingInfoSlide $c $node $float $newdx $newdy $delay"
    }
}

# return the width and height (in characters) of the given caption
proc textCharSize { txt } {
    set width 0
    set height 0
    foreach line [split $txt "\n"] {
	set len [string length $line]
	if { $len > $width } { set width $len }
	incr height
    }
    return [list $width $height]
}
# end Boeing


# This is contributed code from http://wiki.tcl.tk/3060
namespace eval balloon {set last 0 ; namespace export balloon}

proc ::balloon::balloon {args} {
   variable last
   variable tips

   set numArgs [llength $args]
   if { $numArgs < 1 || $numArgs > 2 } {
        return -code error "wrong # args: should be \"balloon widget ?text?\"";
      }

   set w [lindex $args 0]
   if { ![winfo exists $w] } {
        return -code error "bad window path name \"$w\""
      }

   if { [winfo class $w] == "Toplevel" } {
        return -code error "cannot create tooltip for toplevel windows";
      }

   if { $numArgs == "1" } {
        if { [info exists tips($w)] } {
             return $tips($w);
           } else {
             return "";
           }
      }

   set text [lindex $args 1]

   if { $text == "" } {
        # turn off tooltip
        if { [set x [lsearch [bindtags $w] "Balloon"]] >= 0 } {
             bindtags $w [lreplace [bindtags $w] $x $x]
           }
        unset -nocomplain tips($w)
        trace remove command $w delete ::balloon::autoclear
        return;
      }

   # OK, set up a (new?) tooltip

   if { [lsearch [bindtags $w] "Balloon"] < 0 } {
        bindtags $w [linsert [bindtags $w] 0 "Balloon"]
      }

   if { [lsearch [trace info command $w] {delete ::balloon::autoclear}] < 0 } {
        trace add command $w delete ::balloon::autoclear
      }

   set tips($w) $text

 };# balloon::balloon

 proc ::balloon::show {w} {
    variable tips
    if { ![info exists tips($w)] } {return}
    if {[eval winfo containing [winfo pointerxy .]]!=$w} {return}
     set top "$w.balloon"
     catch {destroy $top}
     toplevel $top -bd 0 -bg black
     wm overrideredirect $top 1
     pack [message $top.txt -aspect 10000 -bg lightyellow -relief raised \
             -text $tips($w)]
     set wmx [winfo rootx $w]
     set wmy [expr [winfo rooty $w]+[winfo height $w]]
     wm geometry $top \
       [winfo reqwidth $top.txt]x[winfo reqheight $top.txt]+$wmx+$wmy
     raise $top
 };# balloon::show

 proc ::balloon::delay {} {
   variable last

   set then $last
   set last [clock seconds]
   if { [expr {$last - $then}] < 3} {
        return 50
      } else {
        return 1000
      }

 };# balloon::delay

 proc ::balloon::autoclear {old new op} {
   variable tips

   unset -nocomplain tips([namespace tail $old]);

 };# balloon::autoclear

# Boeing
# this is a modified form of ::balloon::show but accepts 
# x,y coordinates and a caption for the tooltip
 proc ::balloon::show2 {w x y caption} {
    variable tips
#    if { ![info exists tips($w)] } {return}
     set top "$w.balloon"
     catch {destroy $top}
     toplevel $top -bd 0 -bg black
     wm overrideredirect $top 1
     pack [message $top.txt -aspect 10000 -bg lightyellow -relief raised \
             -text $caption]
     wm geometry $top \
       [winfo reqwidth $top.txt]x[winfo reqheight $top.txt]+$x+$y
     raise $top
 };# balloon::show2
# end Boeing

 namespace import ::balloon::balloon
 if {[catch { bind Balloon <Enter> {after [::balloon::delay] \
					  [list ::balloon::show %W]}} err]} {
    # DISPLAY variable probably not set!
    if { ![info exists tk_patchLevel] } { 
	puts ""
	puts -nonewline " Error initializing Tcl/Tk. Make sure that you are "
	puts "running CORE from X.org or" 
	puts " that you have X11 forwarding turned on (via SSH). "
	puts ""
    }
    exit.real
}
 bind Balloon <Leave> {destroy %W.balloon}

# This is contributed code from http://wiki.tcl.tk/1416
 #----------------------------------------------------------------------
 #
 # roundRect --
 #
 #       Draw a rounded rectangle in the canvas.
 #
 # Parameters:
 #       w - Path name of the canvas
 #       x0, y0 - Co-ordinates of the upper left corner, in pixels
 #       x3, y3 - Co-ordinates of the lower right corner, in pixels
 #       radius - Radius of the bend at the corners, in any form
 #                acceptable to Tk_GetPixels
 #       args - Other args suitable to a 'polygon' item on the canvas
 #
 # Results:
 #       Returns the canvas item number of the rounded rectangle.
 #
 # Side effects:
 #       Creates a rounded rectangle as a smooth polygon in the canvas.
 #
 #----------------------------------------------------------------------
 proc roundRect { w x0 y0 x3 y3 radius args } {

    set r [winfo pixels $w $radius]
    set d [expr { 2 * $r }]

    # Make sure that the radius of the curve is less than 3/8
    # size of the box!

    set maxr 0.75

    if { $d > $maxr * ( $x3 - $x0 ) } {
        set d [expr { $maxr * ( $x3 - $x0 ) }]
    }
    if { $d > $maxr * ( $y3 - $y0 ) } {
        set d [expr { $maxr * ( $y3 - $y0 ) }]
    }

    set x1 [expr { $x0 + $d }]
    set x2 [expr { $x3 - $d }]
    set y1 [expr { $y0 + $d }]
    set y2 [expr { $y3 - $d }]

    set cmd [list $w create polygon]
    lappend cmd $x0 $y0
    lappend cmd $x1 $y0
    lappend cmd $x2 $y0
    lappend cmd $x3 $y0
    lappend cmd $x3 $y1
    lappend cmd $x3 $y2
    lappend cmd $x3 $y3
    lappend cmd $x2 $y3
    lappend cmd $x1 $y3
    lappend cmd $x0 $y3
    lappend cmd $x0 $y2
    lappend cmd $x0 $y1
    lappend cmd -smooth 1
    return [eval $cmd $args]
}

