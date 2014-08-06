#
# Copyright 2007-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

#
# Copyright 2007-2008 University of Zagreb, Croatia.
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

#****h* imunes/annotations.tcl
# NAME
#  annotations.tcl -- oval, rectangle, text, background, ...
# FUNCTION
#  This module is used for configuration/image annotations, such as oval, 
#  rectangle, text, background or some other.
#****

#****f* annotations.tcl/annotationConfig
# NAME
#   annotationConfig -- 
# SYNOPSIS
#   annotationConfig $canvas $target
# FUNCTION
#   . . .
# INPUTS
#   * canvas -- 
#   * target -- oval or rectangle object
#****

proc annotationConfig { c target } {
    switch -exact -- [nodeType $target] {
	oval {
	    popupAnnotationDialog $c $target "true"
	}
	rectangle {
	    popupAnnotationDialog $c $target "true"
	}
	text {
	    popupAnnotationDialog $c $target "true"
	}
	default {
	    puts "Unknown type [nodeType $target] for target $target"
	}
    }
    redrawAll
}


#****f* annotations.tcl/popupOvalDialog
# NAME
#   popupOvalDialog -- creates a new oval or modifies existing oval
# SYNOPSIS
#   popupOvalDialog $canvas $modify $color $label $lcolor
# FUNCTION
#   Called from:
#   - editor.tcl/button1-release when new oval is drawn 
#   - annotationConfig which is called from popupConfigDialog bound to 
#     Double-1 on various objects
#   - configureOval called from button3annotation procedure which creates
#     a menu for configuration and deletion (bound to 3 on oval, 
#     rectangle and text) 
# INPUTS
#   * canvas -- 
#   * modify -- create new oval "newoval" if modify=false or 
#     modify an existing oval "newoval" if modify=true
#   * color  -- oval color
#   * label  -- label text
#   * lcolor -- label (text) color
#****


#****f* annotations.tcl/destroyNewoval
# NAME
#   destroyNewoval -- helper for popupOvalDialog and popupOvalApply
# SYNOPSIS
#   destroyNewoval $canvas
# FUNCTION
#   . . .
# INPUTS
#   * canvas -- 
#****

proc destroyNewoval { c } {
    global newoval
    $c delete -withtags newoval
    set newoval ""
}


# oval/rectangle/text right-click menu

proc button3annotation { type c x y } {

    if { $type == "oval" } {
	set procname "Oval"
	set item [lindex [$c gettags {oval && current}] 1]
    } elseif { $type == "rectangle" } {
	set procname "Rectangle"
	set item [lindex [$c gettags {rectangle && current}] 1]
    } elseif { $type == "label" } {
	set procname "Label"
	set item [lindex [$c gettags {label && current}] 1]
    } elseif { $type == "text" } {
	set procname "Text"
	set item [lindex [$c gettags {text && current}] 1]
    } elseif { $type == "marker" } {
 	# erase markings
	$c delete -withtags {marker && current}
	return
    } else {
	# ???
	return
    }
    if { $item == "" } {
	return
    }
    set menutext "$type $item"

    .button3menu delete 0 end

    .button3menu add command -label "Configure $menutext" \
	-command "annotationConfig $c $item"
    .button3menu add command -label "Delete $menutext" \
	-command "deleteAnnotation $c $type $item"

    set x [winfo pointerx .]
    set y [winfo pointery .]
    tk_popup .button3menu $x $y
}


proc deleteAnnotation { c type target } {
    global changed annotation_list
    
    $c delete -withtags "$type && $target"
    $c delete -withtags "new$type"
    set i [lsearch -exact $annotation_list $target]
    set annotation_list [lreplace $annotation_list $i $i]
    set changed 1
    updateUndoLog
}


proc drawOval {oval} {
    global $oval defOvalColor zoom curcanvas
    global defTextFontFamily defTextFontSize

    set coords [getNodeCoords $oval]
    if { [llength $coords] < 4 } {
	puts "Bad coordinates for oval $oval"
    	return
    }
    set x1 [expr {[lindex $coords 0] * $zoom}]
    set y1 [expr {[lindex $coords 1] * $zoom}]
    set x2 [expr {[lindex $coords 2] * $zoom}]
    set y2 [expr {[lindex $coords 3] * $zoom}]
    set color [lindex [lsearch -inline [set $oval] "color *"] 1]
    set label [lindex [lsearch -inline [set $oval] "label *"] 1]
    set lcolor [lindex [lsearch -inline [set $oval] "labelcolor *"] 1]
    set bordercolor [lindex [lsearch -inline [set $oval] "border *"] 1]
    set width [lindex [lsearch -inline [set $oval] "width *"] 1]
    set lx [expr $x1 + (($x2 - $x1) / 2)]
    set ly [expr ($y1 + 20)]

    if { $color == "" } { set color $defOvalColor }
    if { $lcolor == "" } { set lcolor black }
    if { $width == "" } { set width 0 }
    if { $bordercolor == "" } { set bordercolor black }

    # -outline red -stipple gray50
    set newoval [.c create oval $x1 $y1 $x2 $y2 \
	-fill $color -width $width -outline $bordercolor \
	-tags "oval $oval annotation"]
    .c raise $newoval background

    set fontfamily [lindex [lsearch -inline [set $oval] "fontfamily *"] 1]
    set fontsize [lindex [lsearch -inline [set $oval] "fontsize *"] 1]
    if { $fontfamily == "" } {
	set fontfamily $defTextFontFamily
    }
    if { $fontsize == "" } {
	set fontsize $defTextFontSize
    }
    set newfontsize $fontsize
    set font [list "$fontfamily" $fontsize]
    set effects [lindex [lsearch -inline [set $oval] "effects *"] 1]

    .c create text $lx $ly -tags "oval $oval annotation" -text $label \
	-justify center -font "$font $effects" -fill $lcolor

    setNodeCanvas $oval $curcanvas
    setType $oval "oval"
}


# Color helper for popupOvalDialog and popupLabelDialog
proc popupColor { type l settext } {
    # popup color selection dialog with current color
    if { $type == "fg" } {
	set initcolor [$l cget -fg]
    } else {
	set initcolor [$l cget -bg]
    }
    set newcolor [tk_chooseColor -initialcolor $initcolor]

    # set fg or bg of the "l" label control
    if { $newcolor == "" } {
	return
    }
    if { $settext == "true" } {
	$l configure -text $newcolor -$type $newcolor
    } else {
	$l configure -$type $newcolor
    }
}


#****f* annotations.tcl/roundRect
# NAME
#   roundRect -- Draw a rounded rectangle in the canvas.
#		Called from drawRect procedure
# SYNOPSIS
#   roundRect $w $x0 $y0 $x3 $y3 $radius $args
# FUNCTION
#   Creates a rounded rectangle as a smooth polygon in the canvas
#   and returns the canvas item number of the rounded rectangle.
# INPUTS
#   * w      -- Path name of the canvas
#   * x0, y0 -- Coordinates of the upper left corner, in pixels
#   * x3, y3 -- Coordinates of the lower right corner, in pixels
#   * radius -- Radius of the bend at the corners, in any form
#		acceptable to Tk_GetPixels
#   * args   -- Other args suitable to a 'polygon' item on the canvas
# Example:
#   roundRect .c 100 50 500 250 $rad -fill white -outline black -tags rectangle
#****

proc roundRect { w x0 y0 x3 y3 radius args } {

    set r [winfo pixels $w $radius]
    set d [expr { 2 * $r }]

    # Make sure that the radius of the curve is less than 3/8 size of the box

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
    lappend cmd $x0 $y0 $x1 $y0 $x2 $y0 $x3 $y0 $x3 $y1 $x3 $y2 
    lappend cmd $x3 $y3 $x2 $y3 $x1 $y3 $x0 $y3 $x0 $y2 $x0 $y1
    lappend cmd -smooth 1
    return [eval $cmd $args]
 }

proc drawRect {rectangle} {
    global $rectangle defRectColor zoom curcanvas
    global defTextFontFamily defTextFontSize

    set coords [getNodeCoords $rectangle]
    if {$coords == "" || [llength $coords] != 4 } {
	puts "Bad coordinates for rectangle $rectangle"
	return
    }

    set x1 [expr {[lindex $coords 0] * $zoom}]
    set y1 [expr {[lindex $coords 1] * $zoom}]
    set x2 [expr {[lindex $coords 2] * $zoom}]
    set y2 [expr {[lindex $coords 3] * $zoom}]
    set color [lindex [lsearch -inline [set $rectangle] "color *"] 1]
    set label [lindex [lsearch -inline [set $rectangle] "label *"] 1]
    set lcolor [lindex [lsearch -inline [set $rectangle] "labelcolor *"] 1]
    set bordercolor [lindex [lsearch -inline [set $rectangle] "border *"] 1]
    set width [lindex [lsearch -inline [set $rectangle] "width *"] 1]
    set rad [lindex [lsearch -inline [set $rectangle] "rad *"] 1]
    set lx [expr $x1 + (($x2 - $x1) / 2)]
    set ly [expr ($y1 + 20)]

    if { $color == "" } { set color $defRectColor }
    if { $lcolor == "" } { set lcolor black }
    if { $bordercolor == "" } { set bordercolor black }
    if { $width == "" } { set width 0 }
    # rounded-rectangle radius
    if { $rad == "" } { set rad 25 }

    # Boeing: allow borderless rectangles
    if { $width == 0 } {
    set newrect [roundRect .c $x1 $y1 $x2 $y2 $rad \
	-fill $color -tags "rectangle $rectangle annotation"]
    } else {
    # end Boeing
    set newrect [roundRect .c $x1 $y1 $x2 $y2 $rad \
	-fill $color -outline $bordercolor -width $width \
	-tags "rectangle $rectangle annotation"]
    .c raise $newrect background
    # Boeing
    }
    # end Boeing

    set fontfamily [lindex [lsearch -inline [set $rectangle] "fontfamily *"] 1]
    set fontsize [lindex [lsearch -inline [set $rectangle] "fontsize *"] 1]
    if { $fontfamily == "" } {
	set fontfamily $defTextFontFamily
    }
    if { $fontsize == "" } {
	set fontsize $defTextFontSize
    }
    set newfontsize $fontsize
    set font [list "$fontfamily" $fontsize]
    set effects [lindex [lsearch -inline [set $rectangle] "effects *"] 1]

    .c create text $lx $ly -tags "rectangle $rectangle annotation" \
	-text $label -justify center -font "$font $effects" -fill $lcolor

    setNodeCanvas $rectangle $curcanvas
    setType $rectangle "rectangle"
}


proc popupAnnotationDialog { c target modify } {
    global $target newrect newoval 
    global width rad fontfamily fontsize
    global defFillColor defTextColor defTextFontFamily defTextFontSize

    # do nothing, return, if coords are empty
    if { $target == 0 \
	    && [$c coords "$newrect"] == "" \
	    && [$c coords "$newoval"] == "" } {
	return
    }
    if { $target == 0 } {
	set width 0
	set rad 25
	set coords [$c bbox "$newrect"]
	if { [$c coords "$newrect"] == "" } {
	    set coords [$c bbox "$newoval"]
	    set annotationType "oval"
	} else {
	    set annotationType "rectangle"
	}
	set fontfamily ""
	set fontsize ""
	set effects ""
	set color ""
	set label ""
	set lcolor ""
	set bordercolor ""
    } else {
	set width [lindex [lsearch -inline [set $target] "width *"] 1]
	set rad [lindex [lsearch -inline [set $target] "rad *"] 1]
	set coords [$c bbox "$target"]
	set color [lindex [lsearch -inline [set $target] "color *"] 1]
	set fontfamily [lindex [lsearch -inline [set $target] "fontfamily *"] 1]
	set fontsize [lindex [lsearch -inline [set $target] "fontsize *"] 1]
	set effects [lindex [lsearch -inline [set $target] "effects *"] 1]

	set label [lindex [lsearch -inline [set $target] "label *"] 1]
	set lcolor [lindex [lsearch -inline [set $target] "labelcolor *"] 1]
	set bordercolor [lindex [lsearch -inline [set $target] "border *"] 1]
	set annotationType [nodeType $target]
    }

    if { $color == "" } {
	# Boeing: use default shape colors
	if { $annotationType == "oval" } {
	    global defOvalColor
	    set color $defOvalColor
	} elseif { $annotationType == "rectangle" } {
	    global defRectColor
	    set color $defRectColor
	} else {
	    set color $defFillColor
	}
    }
    if { $lcolor == "" } { set lcolor black }
    if { $bordercolor == "" } { set bordercolor black }
    if { $width == "" } { set width 0 }
    if { $rad == "" } { set rad 25 }
    if { $fontfamily == "" } { set fontfamily $defTextFontFamily }
    if { $fontsize == "" } { set fontsize $defTextFontSize }

    set textBold 0
    set textItalic 0
    set textUnderline 0
    if { [lsearch $effects bold ] != -1} {set textBold 1}
    if { [lsearch $effects italic ] != -1} {set textItalic 1}
    if { [lsearch $effects underline ] != -1} {set textUnderline 1}

    set x1 [lindex $coords 0] 
    set y1 [lindex $coords 1]
    set x2 [lindex $coords 2]
    set y2 [lindex $coords 3]
    set xx [expr {abs($x2 - $x1)}] 
    set yy [expr {abs($y2 - $y1)}] 
    if { $xx > $yy } {
	set maxrad [expr $yy * 3.0 / 8.0]
    } else {
	set maxrad [expr $xx * 3.0 / 8.0]
    }

    set wi .popup
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 0 0

    if { $modify == "true" } {
	set windowtitle "Configure $annotationType $target"
    } else {
	set windowtitle "Add a new $annotationType"
    }
    wm title $wi $windowtitle

    frame $wi.text -relief groove -bd 2
    frame $wi.text.lab
    label $wi.text.lab.name_label -text "Text for top of $annotationType:"
    entry $wi.text.lab.name -bg white -fg $lcolor -width 32 \
	-validate focus -invcmd "focusAndFlash %W"
    $wi.text.lab.name insert 0 $label
    pack $wi.text.lab.name_label $wi.text.lab.name -side left -anchor w \
	-padx 2 -pady 2 -fill x
    pack $wi.text.lab -side top -fill x

    frame $wi.text.format 

    set fontmenu [tk_optionMenu $wi.text.format.fontmenu fontfamily "$fontfamily"]
    set sizemenu [tk_optionMenu $wi.text.format.fontsize fontsize "$fontsize"]


    # color selection 
    if { $color == "" } {
	set color $defTextColor
    }
    button $wi.text.format.fg -text "Text color" -command \
	"popupColor fg $wi.text.lab.name false"
    checkbutton $wi.text.format.bold -text "Bold" -variable textBold \
	-command [list fontupdate $wi.text.lab.name bold]
    checkbutton $wi.text.format.italic -text "Italic" -variable textItalic \
	-command [list fontupdate $wi.text.lab.name italic]
    checkbutton $wi.text.format.underline -text "Underline" \
	-variable textUnderline \
	-command [list fontupdate $wi.text.lab.name underline]

    if {$textBold == 1} {	$wi.text.format.bold select
    } else {			$wi.text.format.bold deselect }
    if {$textItalic == 1} {	$wi.text.format.italic select
    } else {			$wi.text.format.italic deselect }
    if {$textUnderline == 1} {	$wi.text.format.underline select
    } else {			$wi.text.format.underline deselect }

    pack $wi.text.format.fontmenu \
	$wi.text.format.fontsize \
	$wi.text.format.fg \
	$wi.text.format.bold \
	$wi.text.format.italic \
	$wi.text.format.underline \
	-side left -pady 2

    pack $wi.text.format -side top -fill x

    pack $wi.text -side top -fill x

    fontupdate $wi.text.lab.name fontfamily $fontfamily
    fontupdate $wi.text.lab.name fontsize $fontsize

    $fontmenu delete 0
    foreach f [lsort -dictionary [font families]] {
	$fontmenu add radiobutton -value "$f" -label $f \
	    -variable fontfamily \
	    -command [list fontupdate $wi.text.lab.name fontfamily $f]
    }
 
    $sizemenu delete 0
    foreach f {8 9 10 11 12 14 16 18 20 22 24 26 28 36 48 72} {
	$sizemenu add radiobutton -value "$f" -label $f \
	    -variable fontsize \
	    -command [list fontupdate $wi.text.lab.name fontsize $f]
    }
 
if { "$annotationType" == "rectangle" || "$annotationType" == "oval" } {

    # fill color, border color
    frame $wi.colors -relief groove -bd 2
    # color selection controls
    label $wi.colors.label -text "Fill color:"

    label $wi.colors.color -text $color -width 8 \
	-bg $color -fg $lcolor
    button $wi.colors.bg -text "Color" -command \
	"popupColor bg $wi.colors.color true"
    pack $wi.colors.label $wi.colors.color $wi.colors.bg \
	-side left -padx 2 -pady 2 -anchor w -fill x
    pack $wi.colors -side top -fill x

    # border selection controls
    frame $wi.border -relief groove -bd 2
    label $wi.border.label -text "Border color:"
    label $wi.border.color -text $bordercolor -width 8 \
	-bg $color -fg $bordercolor
    label $wi.border.width_label -text "Border width:"
    set widthMenu [tk_optionMenu $wi.border.width width "$width"]
    $widthMenu delete 0
    foreach f {0 1 2 3 4 5 6 7 8 9 10} {
	$widthMenu add radiobutton -value $f -label $f \
	    -variable width
    }
    button $wi.border.fg -text "Color" -command \
	"popupColor fg $wi.border.color true"
    pack $wi.border.label $wi.border.color $wi.border.fg \
	$wi.border.width_label $wi.border.width \
	$wi.border.fg $wi.border.color $wi.border.label \
	-side left -padx 2 -pady 2 -anchor w -fill x
    pack $wi.border -side top -fill x

}

if { $annotationType == "rectangle" } {
    frame $wi.radius -relief groove -bd 2
    scale $wi.radius.rad -from 0 -to [expr int($maxrad)] \
	-length 400 -variable rad \
	-orient horizontal -label "Radius of the bend at the corners: " \
	-tickinterval [expr int($maxrad / 15) + 1] -showvalue true
    pack $wi.radius.rad -side left -padx 2 -pady 2 -anchor w -fill x
    pack $wi.radius -side top -fill x
}

    # Add new oval or modify old one?
    if { $modify == "true"  } {
	set cancelcmd "destroy $wi"
	set applytext "Modify $annotationType"
    } else {
	set cancelcmd "destroy $wi; destroyNewRect $c"
	set applytext "Add $annotationType"
    }
    
    frame $wi.butt -borderwidth 6
    button $wi.butt.apply -text $applytext -command "popupAnnotationApply $c $wi $target $annotationType"

    button $wi.butt.cancel -text "Cancel" -command $cancelcmd
    bind $wi <Key-Escape> "$cancelcmd" 
    bind $wi <Key-Return> "popupAnnotationApply $c $wi $target $annotationType"
    pack $wi.butt.cancel $wi.butt.apply -side right
    pack $wi.butt -side bottom

    after 100 {
	grab .popup
    }
    return
}

# helper for popupOvalDialog and popupOvalApply
proc destroyNewRect { c } {
    global newrect
    $c delete -withtags newrect
    set newrect ""
}


proc popupAnnotationApply { c wi target type } {
    global newrect newoval annotation_list
    global $target
    global changed
    global width rad
    global fontfamily fontsize textBold textItalic textUnderline

    # attributes
    set caption [string trim [$wi.text.lab.name get]]
    set labelcolor [$wi.text.lab.name cget -fg]
    set coords [$c coords "$target"]
    set iconcoords "iconcoords"

    if {"$type" == "rectangle" || "$type" == "oval" } {
	set color [$wi.colors.color cget -text]
	set bordercolor [$wi.border.color cget -text]
    }

    if { $target == 0 } {
	# Create a new annotation object
	set target [newObjectId annotation]
	global $target
	lappend annotation_list $target
	if {"$type" == "rectangle" } {
	    set coords [$c coords $newrect]
        } elseif { "$type" == "oval" } {
	    set coords [$c coords $newoval]
	}
    } else {
	set coords [getNodeCoords $target]
    }
    set $target {}
    lappend $iconcoords $coords
    lappend $target $iconcoords "label {$caption}" "labelcolor $labelcolor" \
	"fontfamily {$fontfamily}" "fontsize $fontsize"
    if {"$type" == "rectangle" || "$type" == "oval" } {
	lappend $target "color $color" "width $width" "border $bordercolor" 
    }
    if {"$type" == "rectangle" } {
	lappend $target "rad $rad"
    }

    set ef {}
    if {"$textBold" == 1}   { lappend ef bold} 
    if {"$textItalic" == 1} { lappend ef italic} 
    if {"$textUnderline" == 1}   { lappend ef underline} 
    if {"$ef" != ""} { lappend $target "effects {$ef}"}

    # draw it
    if { $type == "rectangle" } {
        drawRect $target
        destroyNewRect $c
    } elseif { $type == "oval" } {
        drawOval $target
        destroyNewoval $c
    } elseif { $type == "text" } {
        drawText $target
    }

    set changed 1
    updateUndoLog
    redrawAll
    destroy $wi 
}

proc selectmarkEnter {c x y} {
    set isThruplot false

    if {$c == ".c"} {
        set obj [lindex [$c gettags current] 1]
        set type [nodeType $obj]
        if {$type != "oval" && $type != "rectangle"} { return }
    } else { 
        set obj $c
        set c .c 
        set isThruplot true
    }
    set bbox [$c bbox $obj]
    
    set x1 [lindex $bbox 0]
    set y1 [lindex $bbox 1]
    set x2 [lindex $bbox 2]
    set y2 [lindex $bbox 3]
  
    if {$isThruplot == true} {
        set x [expr $x+$x1]
        set y [expr $y+$y1] 

    } 
    set l 0 ;# left
    set r 0 ;# right
    set u 0 ;# up
    set d 0 ;# down

    set x [$c canvasx $x]
    set y [$c canvasy $y]

    if { $x < [expr $x1+($x2-$x1)/8.0]} { set l 1 }
    if { $x > [expr $x2-($x2-$x1)/8.0]} { set r 1 }
    if { $y < [expr $y1+($y2-$y1)/8.0]} { set u 1 }
    if { $y > [expr $y2-($y2-$y1)/8.0]} { set d 1 }

    if {$l==1} {
	if {$u==1} { 
	    $c config -cursor top_left_corner
	} elseif {$d==1} { 
	    $c config -cursor bottom_left_corner
	} else { 
	    $c config -cursor left_side
	} 
    } elseif {$r==1} {
	if {$u==1} { 
	    $c config -cursor top_right_corner
	} elseif {$d==1} { 
	    $c config -cursor bottom_right_corner
	} else { 
	    $c config -cursor right_side
	} 
    } elseif {$u==1} { 
	$c config -cursor top_side
    } elseif {$d==1} {
	$c config -cursor bottom_side
    } else {
	$c config -cursor left_ptr
    }
}

proc selectmarkLeave {c x y} {
    global thruplotResize
    .bottom.textbox config -text {}
   
    # cursor options for thruplot resize 
    if {$thruplotResize == true} {

    } else {
        # no resize update cursor
        $c config -cursor left_ptr
    }
}


proc textEnter { c x y } {
    global annotation_list
    global curcanvas

    set object [newObjectId annotation]
    set newtext [$c create text $x $y -text "" \
	-anchor w -justify left -tags "text $object annotation"]

    set coords [$c coords "text && $object"]
    set iconcoords "iconcoords"

    global $object
    set $object {}
    setType $object "text"
    lappend $iconcoords $coords
    lappend $object $iconcoords
    lappend $object "label {}"
    setNodeCanvas $object $curcanvas

    lappend annotation_list $object
    popupAnnotationDialog $c $object "false"
}


proc drawText {text} {
    global $text defTextColor defTextFont defTextFontFamily defTextFontSize
    global zoom curcanvas newfontsize

    set coords [getNodeCoords $text]
    if { [llength $coords] < 2 } {
	puts "Bad coordinates for text $text"
    	return
    }
    set x [expr {[lindex $coords 0] * $zoom}]
    set y [expr {[lindex $coords 1] * $zoom}]
    set color [lindex [lsearch -inline [set $text] "labelcolor *"] 1]
    if { $color == "" } {
	set color $defTextColor
    }
    set label [lindex [lsearch -inline [set $text] "label *"] 1]
    set fontfamily [lindex [lsearch -inline [set $text] "fontfamily *"] 1]
    set fontsize [lindex [lsearch -inline [set $text] "fontsize *"] 1]
    if { $fontfamily == "" } {
	set fontfamily $defTextFontFamily
    }
    if { $fontsize == "" } {
	set fontsize $defTextFontSize
    }
    set newfontsize $fontsize
    set font [list "$fontfamily" $fontsize]
    set effects [lindex [lsearch -inline [set $text] "effects *"] 1]
    set newtext [.c create text $x $y -text $label -anchor w \
	-font "$font $effects" -justify left -fill $color \
	-tags "text $text annotation"]

    .c addtag text withtag $newtext
    .c raise $text background
    setNodeCanvas $text $curcanvas
    setType $text "text"
}


proc fontupdate { label type args} {
    global fontfamily fontsize
    global textBold textItalic textUnderline

    if {"$textBold" == 1} {set bold "bold"} else {set bold {} }
    if {"$textItalic"} {set italic "italic"} else {set italic {} }
    if {"$textUnderline"} {set underline "underline"} else {set underline {} }
    switch $type {
	fontsize {
	    set fontsize $args
	}
	fontfamily {
	    set fontfamily "$args"
	}
    }
    set f [list "$fontfamily" $fontsize]
    lappend f "$bold $italic $underline"
    $label configure -font "$f"
}


proc drawAnnotation { obj } {
    switch -exact -- [nodeType $obj] {
	oval {
	    drawOval $obj
	}
	rectangle {
	    drawRect $obj
	}
	text {
	    drawText $obj
	}
    }
}

# shift annotation coordinates by dx, dy; does not redraw the annotation
proc moveAnnotation { obj dx dy } {
    set coords [getNodeCoords $obj]
    lassign $coords x1 y1 x2 y2
    set pt1 "[expr {$x1 + $dx}] [expr {$y1 + $dy}]"
    if { [nodeType $obj] == "text" } {
	# shift one point
	setNodeCoords $obj $pt1
    } else { ;# oval/rectangle
	# shift two points
	set pt2 "[expr {$x2 + $dx}] [expr {$y2 + $dy}]"
	setNodeCoords $obj "$pt1 $pt2"
    }
}
