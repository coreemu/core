#
# Copyright 2005-2014 the Boeing Company.
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
# This work was supported in part by Croatian Ministry of Science
# and Technology through the research contract #IP-2003-143.
#

#****h* imunes/initgui.tcl
# NAME
#    initgui.tcl
# FUNCTION
#    Initialize GUI. Not included when operating in batch mode.
#****


#
# GUI-related global variables
#

#****v* initgui.tcl/global variables
# NAME
#    global variables
# FUNCTION
#    GUI-related global varibles
# 
#    * newlink -- helps when creating a new link. If there is no
#      link currently created, this value is set to an empty string.
#    * selectbox -- the value of the box representing all the selected items
#    * selected -- containes the list of node_id's of all selected nodes.
#    * newCanvas -- 
#
#    * animatephase -- starting dashoffset. With this value the effect of 
#      rotating line around selected itme is achived. 
#    * undolevel -- control variable for undo.
#    * redolevel -- control variable for redo.
#    * undolog -- control variable for saving all the past configurations.
#    * changed -- control variable for indicating that there something changed 
#      in active configuration.
#    * badentry -- control variable indicating that there has been a bad entry
#      in the text box.
#    * cursorstate -- control variable for animating cursor.
#    * clock_seconds -- control variable for animating cursor.
#    * oper_mode -- control variable reresenting operating mode, possible 
#      values are edit and exec.
#    * grid -- control variable representing grid distance. All new 
#      elements on the 
#      canvas are snaped to grid. Default value is 24.
#    * sizex -- X size of the canvas.
#    * sizey -- Y size of the canvas.
#    * curcanvas -- the value of the current canvas.
#    * autorearrange_enabled -- control variable indicating is 
#      autorearrange enabled.
#
#    * defLinkColor -- defines the default link color, default link color is set
#      to red.
#    * defLinkWidth -- defines the width of the link, default is 2.
#    * defEthBandwidth -- defines the ethernet bandwidth, default is set to 
#      100000000.
#    * defSerBandwidth -- defines the serail link bandwidth, default is 2048000.
#    * defSerDelay -- defines the serail link delay, default is 2500.
#    * showIfNames -- control variable for showing interface names, default is 1
#    * showIfIPaddrs -- control variable for showing interface IPv4 addresses, 
#      default is 1 (addresses are visible).
#    * showIfIPv6addrs -- control variable for showing interface IPv4 
#      addresses, default is 1 (addresses are visible).
#    * showNodeLabels -- control variable for showing node labels, default is 1.
#    * showLinkLabels -- control variable for showing link labels, default is 1.
#
#****


set newlink ""
set selectbox ""
set selected ""
newCanvas ""

set animatephase 0
set undolevel 0
set redolevel 0
set undolog(0) ""
set changed 0
set badentry 0
set cursorState 0
set clock_seconds 0
set oper_mode edit
set grid 24
set showGrid 1
set zoom 1.0
set curcanvas [lindex $canvas_list 0]
set autorearrange_enabled 0

set num_canvases $g_prefs(gui_num_canvases)
while { $num_canvases > 1 } { newCanvas ""; incr num_canvases -1 }

# resize Oval/Rectangle, "false" or direction: north/west/east/...
set resizemode false
set thruplotResize false

# dictionary that maps cursor style to resize mode
set cursorToResizemode [dict create top_left_corner lu] 
    dict set cursorToResizemode bottom_left_corner ld
    dict set cursorToResizemode left_side l
    dict set cursorToResizemode top_right_corner ru
    dict set cursorToResizemode bottom_right_corner rd
    dict set cursorToResizemode right_side r
    dict set cursorToResizemode top_side u
    dict set cursorToResizemode bottom_side d 

# dictionary that maps thruplot to color 
set thruPlotColor [dict create default blue]
set thruPlotDragStart false
set thruPlotCur null 

set curPlotLineColor blue
set curPlotFillColor "#7f9eee"
set curPlotBgColor "#EEEEFF"

# values for locking thruplot Max Height
set thruPlotMaxKBPS 10
set defThruPlotMaxKBPS 10

#
# Initialize a few variables to default values
#
set defLinkColor Red 
set defFillColor Gray
set defLinkWidth 2
set defEthBandwidth 0
set defSerBandwidth 2048000
set defSerDelay 2500

set newoval ""
set defOvalColor #CFCFFF
set defOvalLabelFont "Arial 12"
set newrect ""
set defRectColor #C0C0FF
set defRectLabelFont "Arial 12"
set defTextFont "Arial 12"
set defTextFontFamily "Arial"
set defTextFontSize 12
set defTextColor #000000

set showIfNames 0
set showIfIPaddrs 1
set showIfIPv6addrs 1
set showNodeLabels 1
set showLinkLabels 1

set showBkgImage 0
set showAnnotations 1
set g_view_locked 0

set defSelectionColor #FEFFBA
set def_router_model router

set wlanLinkColors "#007000 #000070 #700000 #700070 #707070 #007070 #707000"
set g_twoNodeSelect "" ;# flag for editor.tcl:button1 when selecting two nodes

# assume displaying only 7 other distributed servers cpu usage
array set server_cpuusage {}
set cpu_palettes { black blue red yellow green magenta cyan white}


#
# Window / canvas setup section
#


wm minsize . 640 480
wm geometry . 1016x716-30+30
setGuiTitle ""
wm iconbitmap . @$CORE_DATA_DIR/icons/normal/core-icon.xbm
catch {
    set g_core_icon [image create photo -file \
    		     "$CORE_DATA_DIR/icons/normal/core-icon.png"]
    wm iconphoto . -default $g_core_icon
}

menu .menubar
. config -menu .menubar -bg white

.menubar add cascade -label File -underline 0 -menu .menubar.file
.menubar add cascade -label Edit -underline 0 -menu .menubar.edit
.menubar add cascade -label Canvas -underline 0 -menu .menubar.canvas
.menubar add cascade -label View -underline 0 -menu .menubar.view
.menubar add cascade -label Tools -underline 0 -menu .menubar.tools
.menubar add cascade -label Widgets -underline 0 -menu .menubar.widgets
.menubar add cascade -label Session -underline 0 -menu .menubar.session
.menubar add cascade -label Help -underline 0 -menu .menubar.help


#
# File
#
menu .menubar.file -tearoff 0

.menubar.file add command -label New -underline 0 \
  -accelerator "Ctrl+N" -command { fileNewDialogBox }
bind . <Control-n> "fileNewDialogBox"

.menubar.file add command -label "Open..." -underline 0 \
  -accelerator "Ctrl+O" -command { fileOpenDialogBox }
bind . <Control-o> "fileOpenDialogBox"

.menubar.file add command -label "Reload" -underline 0 \
  -command { openFile $currentFile } 

.menubar.file add command -label Save -underline 0 \
  -accelerator "Ctrl+S" -command { fileSaveDialogBox "" }
bind . <Control-s> "fileSaveDialogBox {}"

.menubar.file add command -label "Save As XML..." -underline 8 \
  -command { fileSaveDialogBox xml }

.menubar.file add command -label "Save As imn..." -underline 8 \
  -command { fileSaveDialogBox imn }

.menubar.file add separator
.menubar.file add command -label "Export Python script..." -command exportPython
.menubar.file add command -label "Execute XML or Python script..." \
	-command { execPython false }
.menubar.file add command -label "Execute Python script with options..." \
	-command { execPython true }

.menubar.file add separator
.menubar.file add command -label "Open current file in editor..." \
	-underline 21 -command { 
	global currentFile
	set ed [get_text_editor false]
	set t [get_term_prog false]
	if { [catch {eval exec $t "$ed $currentFile" & } err ] } {
	     puts "Error running editor '$ed' in terminal '$t': $err"
	     puts "Check the text editor setting under preferences."
	}
  }
.menubar.file add command -label "Print..." -underline 0 \
  -command {
    set w .entry1
    catch {destroy $w}
    toplevel $w
    wm title $w "Printing options"
    wm iconname $w "Printing options"

    label $w.msg -wraplength 5i -justify left -text "Print command:"
    pack $w.msg -side top

    frame $w.buttons
    pack $w.buttons -side bottom -fill x -pady 2m
    button $w.buttons.print -text Print -command "printCanvas $w"
    button $w.buttons.cancel -text "Cancel" -command "destroy $w"
    pack $w.buttons.print $w.buttons.cancel -side left -expand 1

    entry $w.e1 -bg white
    $w.e1 insert 0 "lpr"
    pack $w.e1 -side top -pady 5 -padx 10 -fill x
}
.menubar.file add command -label "Save screenshot..." -command {
        global currentFile
	set initialfile [file tail $currentFile]
	# this chops off the .imn file extension
	set ext [file extension $initialfile]
	set extidx [expr {[string last $ext $initialfile] - 1}]
	if { $ext != "" && $extidx > 0 } {
	    set initialfile [string range $initialfile 0 $extidx]
	}
	if { $initialfile == "" } { set initialfile "untitled" }
	set fname [tk_getSaveFile -filetypes {{ "PostScript file" {.ps} }} \
		   -initialfile $initialfile -defaultextension .ps]
	if { $fname != "" } {
	    .c postscript -file $fname
	}
    }
.menubar.file add separator
set g_mru_index 15 ;# index of first MRU list item
foreach f $g_mrulist {
    .menubar.file add command -label "$f" -command "mrufile {$f}"
}
.menubar.file add separator
.menubar.file add command -label Quit -underline 0 -command { exit }

wm protocol . WM_DELETE_WINDOW exit

#
# Edit
#
menu .menubar.edit -tearoff 0
.menubar.edit add command -label "Undo" -underline 0 \
    -accelerator "Ctrl+Z" -command undo -state disabled
bind . <Control-z> undo
.menubar.edit add command -label "Redo" -underline 0 \
    -accelerator "Ctrl+Y" -command redo -state disabled
bind . <Control-y> redo
.menubar.edit add separator
.menubar.edit add command -label "Cut" -underline 2 \
    -accelerator "Ctrl+X" -command cutSelection
bind . <Control-x> cutSelection
.menubar.edit add command -label "Copy" -underline 0 \
    -accelerator "Ctrl+C" -command copySelection
bind . <Control-c> copySelection
bind . <Control-Insert> copySelection
.menubar.edit add command -label "Paste" -underline 0 \
    -accelerator "Ctrl+V" -command pasteSelection
bind . <Control-v> pasteSelection
bind . <Shift-Insert> copySelection
.menubar.edit add separator
.menubar.edit add command -label "Select all" \
    -accelerator "Ctrl+A" -command {
	foreach obj [.c find withtag node] {
	    selectNode .c $obj
	}
    }
bind . <Control-a> {
	foreach obj [.c find withtag node] {
	    selectNode .c $obj
	}
    }
.menubar.edit add command -label "Select adjacent" \
    -accelerator "Ctrl+J" -command selectAdjacent
bind . <Control-j> selectAdjacent

.menubar.edit add separator
.menubar.edit add command -label "Find..." -underline 0 -accelerator "Ctrl+F" \
    -command popupFind
bind . <Control-f> popupFind
.menubar.edit add command -label "Clear marker" -command clearMarker
.menubar.edit add command -label "Preferences..." -command popupPrefs

#
# Canvas
#
menu .menubar.canvas -tearoff 0
.menubar.canvas add command -label "New" -command {
    newCanvas ""
    switchCanvas last
    set changed 1
    updateUndoLog
}
.menubar.canvas add command -label "Manage..." -command {manageCanvasPopup 0 0}
.menubar.canvas add command -label "Delete" -command {
    if { [llength $canvas_list] == 1 } {
	 return
    }
    foreach obj [.c find withtag node] {
	selectNode .c $obj
    }
    deleteSelection
    set i [lsearch $canvas_list $curcanvas]
    set canvas_list [lreplace $canvas_list $i $i]
    set curcanvas [lindex $canvas_list $i]
    if { $curcanvas == "" } {
	set curcanvas [lindex $canvas_list end]
    }
    switchCanvas none
    set changed 1
    updateUndoLog
}
.menubar.canvas add separator
.menubar.canvas add command -label "Size/scale..." -command resizeCanvasPopup
# Boeing
.menubar.canvas add command -label "Wallpaper..." -command wallpaperPopup
# end Boeing
.menubar.canvas add separator
.menubar.canvas add command -label "Previous" -accelerator "PgUp" \
    -command { switchCanvas prev }
bind . <Prior> { switchCanvas prev }
.menubar.canvas add command -label "Next" -accelerator "PgDown" \
    -command { switchCanvas next }
bind . <Next> { switchCanvas next }
.menubar.canvas add command -label "First" -accelerator "Home" \
    -command { switchCanvas first }
bind . <Home> { switchCanvas first }
.menubar.canvas add command -label "Last" -accelerator "End" \
    -command { switchCanvas last }
bind . <End> { switchCanvas last }


#
# Tools
#
menu .menubar.tools -tearoff 0
.menubar.tools add checkbutton -label "Auto rearrange all" -underline 0 \
    -command { rearrange all }
.menubar.tools add checkbutton -label "Auto rearrange selected" -underline 0 \
    -command { rearrange selected }
.menubar.tools add separator
.menubar.tools add command -label "Align to grid" -underline 0 \
    -command { align2grid }
.menubar.tools add separator
.menubar.tools add command -label "Traffic..." -command popupTrafficDialog
# Boeing
#
.menubar.tools add command -label "IP addresses..." -underline 0 \
	-command { popupAddressConfig }
.menubar.tools add command -label "MAC addresses..." -underline 0 \
	-command { popupMacAddressConfig }
.menubar.tools add command -label "Build hosts file..." -underline 0 \
	-command { popupBuildHostsFile }
.menubar.tools add command -label "Renumber nodes..." -underline 0 \
	-command { popupRenumberNodes }
menu .menubar.tools.experimental
.menubar.tools add cascade -label "Experimental" \
	-menu .menubar.tools.experimental
.menubar.tools.experimental add command -label "Plugins..." \
	-underline 0 -command "popupPluginsConfig"
.menubar.tools.experimental add command -label "ns2imunes converter..." \
    -underline 0 -command {
    	toplevel .ns2im-dialog
    	wm transient .ns2im-dialog .
	wm title .ns2im-dialog "ns2imunes converter"
    
	set f1 [frame .ns2im-dialog.entry1]
	set f2 [frame .ns2im-dialog.buttons]
    
	label $f1.l -text "ns2 file:"
	entry $f1.e -width 25 -textvariable ns2srcfile
	button $f1.b -text "Browse" -width 8 \
	    -command {
		set srcfile [tk_getOpenFile -parent .ns2im-dialog \
		    -initialfile $ns2srcfile]
		$f1.e delete 0 end
		$f1.e insert 0 "$srcfile"
	}    
	button $f2.b1 -text "OK" -command {
	    ns2im $srcfile
	    destroy .ns2im-dialog
	}
	button $f2.b2 -text "Cancel" -command { destroy .ns2im-dialog}
    
	pack $f1.b $f1.e -side right
	pack $f1.l -side right -fill x -expand true
	pack $f2.b1 -side left -expand true -anchor e
	pack $f2.b2 -side left -expand true -anchor w
	pack $f1  $f2 -fill x
    }

# Widgets
#
init_widget_menu
# end Boeing


#
# View
#
menu .menubar.view -tearoff 1
menu .menubar.view.show -tearoff 1
.menubar.view add cascade -label "Show" -menu .menubar.view.show

.menubar.view.show add command -label "All" -underline 5 -command {
	set showIfNames 1
	set showIfIPaddrs 1
	set showIfIPv6addrs 1
	set showNodeLabels 1
	set showLinkLabels 1
	redrawAllLinks
	foreach object [.c find withtag linklabel] {
	    .c itemconfigure $object -state normal
	}
    }
.menubar.view.show add command -label "None" -underline 6 -command {
	set showIfNames 0
	set showIfIPaddrs 0
	set showIfIPv6addrs 0
	set showNodeLabels 0
	set showLinkLabels 0
	redrawAllLinks
	foreach object [.c find withtag linklabel] {
	    .c itemconfigure $object -state hidden
	}
    }
.menubar.view.show add separator

.menubar.view.show add checkbutton -label "Interface Names" \
    -underline 5 -variable showIfNames \
    -command { redrawAllLinks }
.menubar.view.show add checkbutton -label "IPv4 Addresses " \
    -underline 8 -variable showIfIPaddrs \
    -command { redrawAllLinks }
.menubar.view.show add checkbutton -label "IPv6 Addresses " \
    -underline 8 -variable showIfIPv6addrs \
    -command { redrawAllLinks }
.menubar.view.show add checkbutton -label "Node Labels" \
    -underline 5 -variable showNodeLabels -command {
    foreach object [.c find withtag nodelabel] {
	if { $showNodeLabels } {
	    .c itemconfigure $object -state normal
	} else {
	    .c itemconfigure $object -state hidden
	}
    }
}
.menubar.view.show add checkbutton -label "Link Labels" \
    -underline 5 -variable showLinkLabels -command {
    foreach object [.c find withtag linklabel] {
	if { $showLinkLabels } {
	    .c itemconfigure $object -state normal
	} else {
	    .c itemconfigure $object -state hidden
	}
    }
}
# .menubar.view.show add checkbutton -label "Background Image" \
#     -underline 5 -variable showBkgImage \
#     -command { redrawAll }
.menubar.view.show add checkbutton -label "Annotations" \
    -underline 5 -variable showAnnotations -command redrawAll
.menubar.view.show add checkbutton -label "Grid" \
    -underline 5 -variable showGrid -command redrawAll
.menubar.view.show add checkbutton -label "API Messages" \
    -underline 5 -variable showAPI

.menubar.view add command -label "Show hidden nodes" \
    -command {
	global node_list
	foreach node $node_list { setNodeHidden $node 0 }
	redrawAll
    }
.menubar.view add checkbutton -label "Locked" -variable g_view_locked
.menubar.view add command -label "3D GUI..." -command {
    global g_prefs
    set gui ""
    set guipref ""
    if { [info exists g_prefs(gui_3d_path)] } {
	set guipref $g_prefs(gui_3d_path)
	set gui [auto_execok $guipref]
    }
    if { $gui == "" } {
	set msg "The 3D GUI command was not valid ('$guipref').\n"
	set msg "$msg Make sure that SDT3D is installed and that an appropriate"
	set msg "$msg launch script is configured under preferences."
	tk_messageBox -type ok -icon warning -message $msg -title "Error"
    } else {
	if { [catch { exec $gui & }] } {
	    puts "Error with 3D GUI command '$gui'."
	}
	statline "3D GUI command executed: $gui"
    }
    setSessionOption "enablesdt" 1 1
}
.menubar.view add separator
.menubar.view add command -label "Zoom In" -accelerator "+" \
    -command "zoom up"
bind . "+" "zoom up"
.menubar.view add command -label "Zoom Out" -accelerator "-" \
     -command "zoom down"
bind . "-" "zoom down"


#
# Session
#
menu .menubar.session -tearoff 1
.menubar.session add command -label "Stop" -underline 1 \
	-command "setOperMode edit"
.menubar.session add command -label "Change sessions..." \
	-underline 0 -command "requestSessions"
.menubar.session add separator
.menubar.session add command -label "Node types..." -underline 0 \
	-command "popupNodesConfig"
.menubar.session add command -label "Comments..." -underline 0 \
	-command "popupCommentsConfig"
.menubar.session add command -label "Hooks..." -underline 0 \
	-command "popupHooksConfig"
.menubar.session add command -label "Reset node positions" -underline 0 \
	-command "resetAllNodeCoords reset"
.menubar.session add command -label "Emulation servers..." \
	-underline 0 -command "configRemoteServers"
.menubar.session add command -label "Options..." \
	-underline 0 -command "sendConfRequestMessage -1 0 session 0x1 -1 \"\""


#
# Help
#
menu .menubar.help -tearoff 0
.menubar.help add command -label "Online manual (www)" -command \
  "_launchBrowser http://downloads.pf.itd.nrl.navy.mil/docs/core/core-html/"
.menubar.help add command -label "CORE website (www)" -command \
  "_launchBrowser http://www.nrl.navy.mil/itd/ncs/products/core"
.menubar.help add command -label "Mailing list (www)" -command \
  "_launchBrowser http://pf.itd.nrl.navy.mil/mailman/listinfo/core-users"
.menubar.help add command -label "About" -command popupAbout

#
# Left-side toolbar
#
frame .left
pack .left -side left -fill y
# Boeing: create images now, buttons in setOperMode
#foreach b {select delete link hub lanswitch router host pc rj45} {
foreach b {select } {
    set imgf "$CORE_DATA_DIR/icons/tiny/$b.gif"
    set image [image create photo -file $imgf]
    radiobutton .left.$b -indicatoron 0 \
	-variable activetool -value $b -selectcolor $defSelectionColor \
	-width 32 -height 32 -image $image \
	-command "popupMenuChoose \"\" $b $imgf"
    pack .left.$b -side top
    leftToolTip $b .left
}
foreach b {hub lanswitch router host pc rj45 \
	   tunnel wlan oval text antenna } {
    set $b [image create photo -file "$CORE_DATA_DIR/icons/normal/$b.gif"]
    createScaledImages $b
}
set activetool_prev select
set markersize 5
set markercolor black
# end Boeing changes
set pseudo [image create photo]
set text [image create photo]


. configure -background #808080
frame .grid
frame .hframe
frame .vframe
set c [canvas .c -bd 0 -relief sunken -highlightthickness 0\
	-background gray \
	-xscrollcommand ".hframe.scroll set" \
	-yscrollcommand ".vframe.scroll set"]

canvas .hframe.t -width 300 -height 18 -bd 0 -highlightthickness 0 \
	-background gray \
	-xscrollcommand ".hframe.ts set"
bind .hframe.t <1> {
    set canvas [lindex [.hframe.t gettags current] 1]
    if { $canvas != "" && $canvas != $curcanvas } {
	set curcanvas $canvas
	switchCanvas none
    }
}
bind .hframe.t <Double-1> {
    set canvas [lindex [.hframe.t gettags current] 1]
    if { $canvas != "" } {
	if { $canvas != $curcanvas } {
	    set curcanvas $canvas
	    switchCanvas none
	} else {
	    manageCanvasPopup %X %Y
	}
    }
}
scrollbar .hframe.scroll -orient horiz -command "$c xview" \
	-bd 1 -width 14
scrollbar .vframe.scroll -command "$c yview" \
	-bd 1 -width 14
scrollbar .hframe.ts -orient horiz -command ".hframe.t xview" \
	-bd 1 -width 14
pack .hframe.ts .hframe.t -side left -padx 0 -pady 0
pack .hframe.scroll -side left -padx 0 -pady 0 -fill both -expand true
pack .vframe.scroll -side top -padx 0 -pady 0 -fill both -expand true
pack .grid -expand yes -fill both -padx 1 -pady 1
grid rowconfig .grid 0 -weight 1 -minsize 0
grid columnconfig .grid 0 -weight 1 -minsize 0
grid .c -in .grid -row 0 -column 0 \
	-rowspan 1 -columnspan 1 -sticky news
grid .vframe -in .grid -row 0 -column 1 \
	-rowspan 1 -columnspan 1 -sticky news
grid .hframe -in .grid -row 1 -column 0 \
	-rowspan 1 -columnspan 1 -sticky news

frame .bottom
pack .bottom -side bottom -fill x
label .bottom.textbox -relief sunken -bd 1 -anchor w -width 999
label .bottom.zoom -relief sunken -bd 1 -anchor w -width 10
label .bottom.cpu_load -relief sunken -bd 1 -anchor w -width 9
label .bottom.mbuf -relief sunken -bd 1 -anchor w -width 9 
label .bottom.indicators -relief sunken -bd 1 -anchor w -width 5
pack .bottom.indicators .bottom.mbuf .bottom.cpu_load \
    .bottom.zoom .bottom.textbox -side right -padx 0 -fill both


#
# Event bindings and procedures for main canvas:
#
$c bind node <Any-Enter> "+nodeEnter $c"
$c bind nodelabel <Any-Enter> "nodeEnter $c"
$c bind link <Any-Enter> "linkEnter $c"
$c bind linklabel <Any-Enter> "linkEnter $c"
$c bind node <Any-Leave> "anyLeave $c"
$c bind nodelabel <Any-Leave> "anyLeave $c"
$c bind link <Any-Leave> "anyLeave $c"
$c bind linklabel <Any-Leave> "anyLeave $c"
$c bind node <Double-1> "popupConfigDialog $c"
$c bind nodelabel <Double-1> "popupConfigDialog $c"
$c bind grid <Double-1> "double1onGrid $c %x %y"
$c bind link <Double-1> "popupConfigDialog $c"
$c bind linklabel <Double-1> "popupConfigDialog $c"
$c bind node <3> "button3node $c %x %y \"\""
$c bind oval <Double-1> "popupConfigDialog $c"
$c bind rectangle <Double-1> "popupConfigDialog $c"
$c bind text <Double-1> "popupConfigDialog $c"
$c bind text <KeyPress> "textInsert $c %A"
$c bind text <Return> "textInsert $c \\n"
$c bind node <3> "button3node $c %x %y \"\""
$c bind nodelabel <3> "button3node $c %x %y \"\""
$c bind link <3> "button3link $c %x %y"
$c bind linklabel <3> "button3link $c %x %y"

$c bind oval <3> "button3annotation oval $c %x %y"
$c bind rectangle <3> "button3annotation rectangle $c %x %y"
$c bind text <3> "button3annotation text $c %x %y"

$c bind selectmark <Any-Enter> "selectmarkEnter $c %x %y"
$c bind selectmark <Any-Leave> "selectmarkLeave $c %x %y"

bind $c <1> "button1 $c %x %y none"
bind $c <Control-Button-1> "button1 $c %x %y ctrl"
bind $c <B1-Motion> "button1-motion $c %x %y"
bind $c <B1-ButtonRelease> "button1-release $c %x %y"
bind . <Delete> deleteSelection
bind .menubar <Destroy> {setOperMode edit}

# Scrolling and panning support
bind $c <2> "$c scan mark %x %y"
bind $c <B2-Motion> "$c scan dragto %x %y 1"
bind $c <4> "$c yview scroll -1 units"
bind $c <5> "$c yview scroll 1 units"
bind . <Right> ".c xview scroll 1 units"
bind . <Left> ".c xview scroll -1 units"
bind . <Down> ".c yview scroll 1 units"
bind . <Up> ".c yview scroll -1 units"

# Escape to Select mode
bind . <Key-Escape> "set activetool select"

$c bind node <Shift-Button-3> "button3node $c %x %y shift"
$c bind node <Control-Button-3> "button3node $c %x %y ctrl"
$c bind marker <3> "button3annotation marker $c %x %y"
bind .bottom.zoom <1> "zoom up"
bind .bottom.zoom <3> "zoom down"
bind .bottom.indicators <1> "popupExceptions"

#
# Popup-menu hierarchy
#
menu .button3menu -tearoff 0
menu .button3menu.connect -tearoff 0
menu .button3menu.assign -tearoff 0
menu .button3menu.moveto -tearoff 0
menu .button3menu.shell -tearoff 0
menu .button3menu.services -tearoff 0
menu .button3menu.ethereal -tearoff 0
menu .button3menu.tcpdump -tearoff 0
menu .button3menu.tshark -tearoff 0
menu .button3menu.wireshark -tearoff 0
menu .button3menu.tunnel -tearoff 0
menu .button3menu.color -tearoff 0

#
# Restore window position
#
if { ( [info exists g_prefs(gui_save_pos)]  && $g_prefs(gui_save_pos) ) || \
     ( [info exists g_prefs(gui_save_size)] && $g_prefs(gui_save_size) ) } {
    set newgeo ""
    if { [info exists g_prefs(gui_save_size)] && $g_prefs(gui_save_size) && \
	 [info exists g_prefs(gui_window_size)] } {
	set newgeo "$g_prefs(gui_window_size)"
    }
    if { [info exists g_prefs(gui_save_pos)] && $g_prefs(gui_save_pos) && \
	 [info exists g_prefs(gui_window_pos] } {
	set newgeo "${newgeo}-$g_prefs(gui_window_pos)"
    }
    if { $newgeo != "" } { wm geometry . $newgeo }
}

#
# Invisible pseudo links
#
set invisible -1
bind . <Control-i> {
    global invisible
    set invisible [expr $invisible * -1]
    redrawAll
}

#
# Don't show hidden files by default under Linux
#
catch { tk_getOpenFile foo bar }
set ::tk::dialog::file::showHiddenVar 0
set ::tk::dialog::file::showHiddenBtn 1

#
# Done with initialization, draw an empty canvas
#
switchCanvas first

focus -force . 

#
# Fire up the animation loop - used basically for selectbox
#
animate
