#
# Copyright 2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author:	Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
# GUI support for node types and profiles.
#

global execMode
if { $execMode == "interactive" } {
    package require Ttk
}

# these are the default node types when nodes.conf does not exist
#      index {name normal-icon tiny-icon services type metadata}
array set g_node_types_default {
	1 {router router.gif router.gif {zebra OSPFv2 OSPFv3 vtysh IPForward} \
	    netns {built-in type for routing}}
	2 {host host.gif host.gif {DefaultRoute SSH} \
	    netns {built-in type for servers}}
	3 {PC pc.gif pc.gif {DefaultRoute} \
	    netns {built-in type for end hosts}}
	4 {mdr mdr.gif mdr.gif {zebra OSPFv3MDR vtysh IPForward} \
	    netns {built-in type for wireless routers}}
	5 {prouter router_green.gif router_green.gif \
	    {zebra OSPFv2 OSPFv3 vtysh IPForward} \
	    physical {built-in type for physical nodes}}
	6 {xen xen.gif xen.gif {zebra OSPFv2 OSPFv3 vtysh IPForward} \
	    xen {built-in type for Xen PVM domU router}}
}

# possible machine types for nodes
set MACHINE_TYPES "netns physical xen"

# array populated from nodes.conf file
array set g_node_types { }

#
# Load the nodes.conf file into the g_nodes array
#
proc loadNodesConf { } {
    global CONFDIR g_node_types g_node_types_default MACHINE_TYPES
    set confname "$CONFDIR/nodes.conf"
    if { [catch { set f [open $confname r] } ] } {
	puts "Creating a default $confname"
	unset g_node_types
	array set g_node_types [array get g_node_types_default]
	writeNodesConf
	return
    }

    array unset g_nodes

    while { [ gets $f line ] >= 0 } {
	if { [string range $line 0 0] == "#" } { continue } ;# skip comments

	# fix-up 5-element list to include node type
	if { [llength $line] == 2 } {
	    set idx [lindex $line 0]; set data [lindex $line 1]
	    if { [llength $data] == 5 } {
		set data [linsert $data 4 [lindex $MACHINE_TYPES 0]]
		set line [list $idx $data]
	    }
	}
	
	# load into array of nodes
	if { [catch {array set g_node_types $line} e] } {
	    puts "Error reading $confname line '$node': $e"
	}
    }
    close $f
    checkNodeTypes true
}

# look for missing default node types; exit if fatal flag is true; return a
# string for the first missing type
proc checkNodeTypes { fatal } {
    global g_node_types_default
    set names [getNodeTypeNames]
    foreach i [lsort [array names g_node_types_default]] {
	set name [lindex $g_node_types_default($i) 0]
	if { [lsearch -exact $names $name] < 0 } {
	    puts "error: missing built-in node type '$name'!"
	    puts "move your ~/.core/nodes.conf file to re-create the defaults"
	    if { $fatal } {
		exit 
	    } else {
		return $name
	    }

	}
	
    }
    return ""
}

#
# Write the nodes.conf file from the g_nodes array.
#
proc writeNodesConf { } {
    global CONFDIR g_node_types
    set confname "$CONFDIR/nodes.conf"
    if { [catch { set f [open "$confname" w] } ] } {
	puts "***Warning: could not write nodes file: $confname"
	return
    }

    set header "# nodes.conf: CORE node templates customization file."
    set header "$header\n# format: index {name normal-icon tiny-icon services"
    set header "$header type metadata}"
    puts $f $header
    foreach i [lsort -integer [array names g_node_types]] {
	puts $f "$i { [string trim $g_node_types($i)] }"
    }
    close $f
}

# return a list of names of node types
proc getNodeTypeNames {} {
    global g_node_types
    set names ""
    foreach i [lsort -integer [array names g_node_types]] {
	set node_type_data $g_node_types($i)
	set name [lindex $node_type_data 0]
	lappend names $name
    }
    return $names
}

proc isDefaultNodeType { nodetype } {
    global g_node_types_default

    foreach i [lsort [array names g_node_types_default]] {
	set name [lindex $g_node_types_default($i) 0]
	if { $nodetype == $name } { return true}
    }
    return false
}

# return the image path name for the specified node type
# size should equal "tiny" or "normal"
proc getNodeTypeImage { type size } {
    global g_node_types CORE_DATA_DIR
    foreach i [lsort -integer [array names g_node_types]] {
	set node_type_data $g_node_types($i)
	if { [lindex $node_type_data 0] == $type } {
	    if { $size == "tiny" } {
		set imgf [lindex $node_type_data 2]
	    } else {
		set imgf [lindex $node_type_data 1]
	    }
	    # if the image has no path, assume it can be
	    # found in $CORE_DATA_DIR/icons/tiny
	    if { [string first "/" $imgf] < 0 } {
		set imgf "$CORE_DATA_DIR/icons/$size/$imgf"
	    }
	    return $imgf
	}
    }
    return ""
}

# return the index in the global array for the given node type
proc getNodeTypeIndex { type } {
    global g_node_types
    foreach i [lsort -integer [array names g_node_types]] {
	set node_type_data $g_node_types($i)
	if { [lindex $node_type_data 0] == $type } {
	    return $i
	}
    }
    return -1
}

# return the default services for this node type
proc getNodeTypeServices { type } {
    global g_node_types
    foreach i [lsort -integer [array names g_node_types]] {
	set node_type_data $g_node_types($i)
	if { [lindex $node_type_data 0] == $type } {
	    return [lindex $node_type_data 3]
	}
    }
    return ""
}

# return the machine type (e.g. netns, physical, xen) of the currently selected
# node type from the toolbar
proc getNodeTypeMachineType { type } {
    global MACHINE_TYPES g_node_types
    set default_machine_type [lindex $MACHINE_TYPES 0]
    set i [getNodeTypeIndex $type]
    if { $i < 0 } { return $default_machine_type }; # failsafe
    return [lindex $g_node_types($i) 4]
}

proc getNodeTypeProfile { type } {
    global g_node_types
    foreach i [lsort -integer [array names g_node_types]] {
	set node_type_data $g_node_types($i)
	if { [lindex $node_type_data 0] == $type } {
	    if {[llength $node_type_data] >= 7 } {
	        return [lindex $node_type_data 6]
	    }
	    break ;# profile may be empty
	}
    }
    return ""
}

# return the machine type (e.g. netns, physical, xen) of the currently selected
# node type from the toolbar
proc getNodeTypeMachineType { type } {
    global MACHINE_TYPES g_node_types
    set default_machine_type [lindex $MACHINE_TYPES 0]
    set i [getNodeTypeIndex $type]
    if { $i < 0 } { return $default_machine_type }; # failsafe
    return [lindex $g_node_types($i) 4]
}

# Helper for add/delete button next to a list/combo box; from is the text entry
# from which the value is copied, and to is the list/combo box where the value
# is inserted upon add
proc listboxAddDelHelper { cmd from to combo } {
    set current [$from get] ;# current text from entry or combo
    if { $combo } {
	set values [$to cget -values]
	set i [lsearch -exact $values $current]
    }

    if { $cmd == "add" } {
	if { $combo } {
	    if { $i != -1 } { return } ;# item already exists
	    lappend values $current
	    $to configure -values $values
	} else {
	    $to insert end $current
	}
    } elseif { $cmd == "del" } {
	if { $combo } {
	    # search combo box values for current text
	    if { $i == -1 } { return } ;# item doesn't exist
	    set values [lreplace $values $i $i]
	    $to configure -values $values
	} else {
	    set values [$to curselection]
	    if { $values == "" } { return } ;# no current selection
	    $to delete [lindex $values 0] ;# delete only first selected item
	}
	$from delete 0 end ;# clear text entry/combo on delete
    }
}

# helper to populate a text entry when a listbox selection has changed
proc listboxSelect { lb ent } {
    set i [$lb curselection]
    $ent delete 0 end
    if { $i == "" } { return }
    $ent insert 0 [$lb get $i]
}

#
# Popup a profile configuration dialog box, using popupCapabilityConfig
#
proc popupNodeProfileConfig { channel node model types values captions bitmap possible_values groups session opaque } {
    global g_node_types

    set opaque_items [split $opaque :]
    if { [llength $opaque_items] != 2 } { 
	puts "warning: received unexpected opaque data in conf message!"
	return
    }
    set nodetype [lindex $opaque_items 1]
    # check if we already have config for this profile, replacing values
    set existing_values [getNodeTypeProfile $nodetype]
    if { $existing_values != "" } {
	if { [llength $existing_values] == [llength $values] } {
	    set values $existing_values
	} else { ;# this accommodates changes to models
	    puts "warning: discarding stale profile for $model from nodes.conf"
	}
    }

    popupCapabilityConfig $channel $node $model $types $values \
				$captions $bitmap $possible_values $groups
}

proc popupNodeProfileConfigApply { vals } {
    global g_node_types g_node_type_services_hint
    set type $g_node_type_services_hint
    set idx [getNodeTypeIndex $type]
    if { $idx < 0 } {
	puts "warning: skipping unknown node type $type"
    } else {
	set typedata $g_node_types($idx)
	if { [llength $typedata] < 7 } {
	    set typedata [linsert $typedata 6 $vals] ;# no profile in list
	} else {
	    set typedata [lreplace $typedata 6 6 $vals] ;# update the profile
	}
	array set g_node_types [list $idx $typedata]
    }
    # node type will be used in sendConfReplyMessage opaque data
    return "model:$type"
}

array set g_nodes_button_tooltips {
	add "add a new node type"
	save "apply changes to this node type"
	del "remove the selected node type"
	up "move the node type up in the list"
	down "move the selected node type down in the list"
}

# show the CORE Node Types configuration dialog
# this allows the user to define new node types having different names, icons,
# and default set of services
proc popupNodesConfig {} {
    global g_nodes_types g_nodes_button_tooltips MACHINE_TYPES g_machine_type
    global CORE_DATA_DIR

    set wi .nodesConfig
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 0 1
    wm title $wi "CORE Node Types"

    # list of nodes
    labelframe $wi.s -borderwidth 0 -text "Node Types"
    listbox $wi.s.nodes -selectmode single -height 5 -width 15 \
	-yscrollcommand "$wi.s.nodes_scroll set" -exportselection 0
    scrollbar $wi.s.nodes_scroll -command "$wi.s.nodes yview" 
    pack $wi.s.nodes $wi.s.nodes_scroll -fill y -side left
    pack $wi.s -padx 4 -pady 4 -fill both -side top -expand true

    # image button bar
    frame $wi.bbar
    set buttons "add save del"
    foreach b $buttons {
	# re-use images from the plugin dialog
	global plugin_img_$b
	button $wi.bbar.$b -image [set plugin_img_$b] \
                -command "nodesConfigHelper $wi $b"
        pack $wi.bbar.$b -side left
        balloon $wi.bbar.$b $g_nodes_button_tooltips($b)
    }
    pack $wi.bbar -padx 4 -pady 4 -fill x -side top

    # up/down buttons
    foreach b {up down} {
        set fn "$CORE_DATA_DIR/icons/tiny/arrow.${b}.gif"
        set img$b [image create photo -file $fn]
        button $wi.bbar.$b -image [set img${b}] \
                -command "nodesConfigHelper $wi $b"
	pack $wi.bbar.$b -side left
        balloon $wi.bbar.$b $g_nodes_button_tooltips($b)
    }

    # node type edit area
    frame $wi.s.edit -borderwidth 4
    frame $wi.s.edit.0
    label $wi.s.edit.0.namelab -text "Name"
    entry $wi.s.edit.0.name -bg white -width 20 
    pack $wi.s.edit.0.namelab $wi.s.edit.0.name -side left
    
    frame $wi.s.edit.1
    label $wi.s.edit.1.iconlab -text "Icon"
    entry $wi.s.edit.1.icon -bg white -width 25
    button $wi.s.edit.1.filebtn -text "..." \
	-command "nodesConfigImgDialog $wi $wi.s.edit.1.icon normal"
    pack $wi.s.edit.1.iconlab $wi.s.edit.1.icon $wi.s.edit.1.filebtn -side left
    bind $wi.s.edit.1.icon <KeyPress> "nodesConfigImg $wi"

    canvas $wi.s.edit.0.c -width 60 -height 60
    # -bg white
    pack $wi.s.edit.0.c -side right -padx 10
    bind $wi.s.edit.0.c <Button> \
	"nodesConfigImgDialog $wi $wi.s.edit.1.icon normal"

    frame $wi.s.edit.2
    label $wi.s.edit.2.icontlab -text "Icon (small)"
    entry $wi.s.edit.2.icont -bg white -width 20
    button $wi.s.edit.2.filebtn -text "..." \
	-command "nodesConfigImgDialog $wi $wi.s.edit.2.icont tiny"
    pack $wi.s.edit.2.icontlab $wi.s.edit.2.icont $wi.s.edit.2.filebtn \
	-side left

    frame $wi.s.edit.5
    label $wi.s.edit.5.metalab -text "Meta-data  "
    entry $wi.s.edit.5.meta -bg white -width 25
    pack $wi.s.edit.5.metalab $wi.s.edit.5.meta -side left

    frame $wi.s.edit.3
    set machinetypemenu [tk_optionMenu $wi.s.edit.3.type g_machine_type \
    			 [lindex $MACHINE_TYPES 0]]
    foreach t [lrange $MACHINE_TYPES 1 end] {
	$machinetypemenu add radiobutton -label $t -value $t \
		-variable g_machine_type \
		-command "nodesConfigMachineHelper $wi"
    }
    button $wi.s.edit.3.services -text "Services..." \
	-command "nodesConfigServices $wi services"
    button $wi.s.edit.3.config -text "Profile..." \
	-command "nodesConfigServices $wi profile"
    pack $wi.s.edit.3.type $wi.s.edit.3.services $wi.s.edit.3.config -side left

    pack $wi.s.edit.0 $wi.s.edit.1 $wi.s.edit.2 $wi.s.edit.5 \
	-side top -anchor w
	#-padx 4 -pady 4
    pack $wi.s.edit.3 -side top -padx 4 -pady 4 -anchor w
    pack $wi.s.edit -fill both -side right

    # populate the list
    nodesConfigRefreshList $wi
    bind $wi.s.nodes <<ListboxSelect>> "nodesConfigSelect $wi \"\""
    $wi.s.nodes selection set 0
    nodesConfigSelect $wi ""


    # close button 
    frame $wi.b -borderwidth 0
    button $wi.b.close -text "Close" -command "nodesConfigClose $wi"
    pack $wi.b.close -side right
    pack $wi.b -side bottom
}

proc nodesConfigRefreshList { wi } {
    global g_node_types

    set selected_idx [$wi.s.nodes curselection]

    $wi.s.nodes delete 0 end
    # this resets the g_node_types array so the indices match the listbox
    set idx 0
    foreach i [lsort -integer [array names g_node_types]] {
	incr idx
	set node_type_data $g_node_types($i)
	set name [lindex $node_type_data 0]
	$wi.s.nodes insert end $name
	if { $i != $idx } {
	    array unset g_node_types $i
	    array set g_node_types [list $idx $node_type_data]
	}
    }

    if { $selected_idx != "" } {
        $wi.s.nodes selection set $selected_idx
        nodesConfigSelect $wi ""
    }
}

# change a node type selection or save it to an array when cmd="save"
# this updates the edit controls with text from the array, or vice-versa
proc nodesConfigSelect { wi cmd } {
    global g_node_types g_machine_type

    set selected_idx [$wi.s.nodes curselection]
    if { $selected_idx == "" } { return }
   
    set idx [expr {$selected_idx + 1}]
    if { ![info exists g_node_types($idx)] } { return }

    set node_type_data $g_node_types($idx)

    if { [isDefaultNodeType [lindex $node_type_data 0]] } {
	set read_only disabled
    } else {
	set read_only normal
    }

    set i 0
    foreach item [list name icon icont meta] {
	if { $i == 3 } { incr i 2 } ;# skip services, type
	if { $cmd == "save" } { ;# save from controls
            set str [$wi.s.edit.$i.$item get]
	    set node_type_data [lreplace $node_type_data $i $i $str]
	} else { ;# write to the controls
	    $wi.s.edit.$i.$item configure -state normal
            $wi.s.edit.$i.$item delete 0 end
            $wi.s.edit.$i.$item insert 0 [lindex $node_type_data $i]
	    $wi.s.edit.$i.$item configure -state $read_only
	}
	incr i
    }

    if { $cmd == "save" } {
	set node_type_data [lreplace $node_type_data 4 4 $g_machine_type]
	array set g_node_types [list $idx $node_type_data]
	nodesConfigRefreshList $wi
    } else {
	set g_machine_type [lindex $node_type_data 4]
	nodesConfigImg $wi
    }
    nodesConfigMachineHelper $wi
}

# invoked when machine type is selected to enable/disable the profile button
proc nodesConfigMachineHelper { wi } {
    global g_machine_type g_plugins
    set cfgname "emul=$g_machine_type"
    # search plugin capabilities for support for this type of machine
    foreach p [array names g_plugins] {
	set caps [lindex $g_plugins($p) 5]
	if { [lsearch $caps $cfgname] != -1 } {
            $wi.s.edit.3.config configure -state normal
	    return
	}
    }
    $wi.s.edit.3.config configure -state disabled
}

# popup a file selection dialog for the icon filenames
proc nodesConfigImgDialog { wi ctl size } {
    global g_imageFileTypes CORE_DATA_DIR
    set dir "$CORE_DATA_DIR/icons/$size/"
    set f [tk_getOpenFile -initialdir $dir -filetypes $g_imageFileTypes ]
    if { [string first $dir $f] == 0 } {
	# chop off default path of $dir
	set f [string range $f [string length $dir] end]
    } 
    if { $f != "" } {
        $ctl delete 0 end
        $ctl insert 0 $f
	if { $size == "normal" } { nodesConfigImg $wi }
    }
}

# update the node icon preview
proc nodesConfigImg { wi } {
    global CORE_DATA_DIR

    set imgf [$wi.s.edit.1.icon get]
    set dir "$CORE_DATA_DIR/icons/normal/"
    # image has no path, assume it can be found in CORE_DATA_DIR
    if { [string first "/" $imgf] < 0 } { set imgf "$dir/$imgf" }

    set c $wi.s.edit.0.c
    set cw [lindex [$c configure -width] 4]
    set ch [lindex [$c configure -height] 4]
    $wi.s.edit.0.c delete "preview"
    if { [catch { set img [image create photo -file $imgf] } e] } {
	# puts "f=$imgf err=$e"
	set pad 5
	set x1 $pad; set y2 $pad
	set x2 [expr {$cw - $pad}]; set y1 [expr {$ch - $pad}]
	$c create line $x1 $y1 $x2 $y2 -fill red -width 3 -tags "preview"
    } else {
	set x [expr {$cw / 2}]; set y [expr {$ch / 2}]
	$c create image $x $y -image $img -tags "preview"
    }

}

# helper for adding, deleting, and rearranging (up/down) node types
proc nodesConfigHelper { wi cmd } {
    global g_node_types

    set ctl $wi.s.nodes
    set idx [$ctl curselection]
    if { $idx != "" } {
	set type [$ctl get $idx]
	set arridx [getNodeTypeIndex $type]
    } elseif { $cmd != "add" } { ;# must have item selected
	return
    }
    set newsel ""

    switch -exact -- $cmd {
	add {
	    set n 1
	    set types [getNodeTypeNames]
	    while { [lsearch $types "router$n"] != -1 } { incr n }
	    set newname "router$n"
	    set arridx [expr {[array size g_node_types] + 1}]
	    set newdata $g_node_types(1) ;# copy first item
	    set newdata [lreplace $newdata 0 0 $newname]
	    set newdata [lreplace $newdata 5 5 ""] ;# zero the meta-data
	    array set g_node_types [list $arridx $newdata]
	    set newsel [expr {$arridx - 1}] 
	}
	save {
	    nodesConfigSelect $wi save
	}
	del {
	    array unset g_node_types $arridx
	}
	up -
	down {
	    if {$cmd == "up" } { 
		if { $arridx < 2 } { return }
		set newidx [expr {$arridx - 1}] 
		set newsel [expr {$idx - 1}] 
	    } else {
		if { $idx >= [expr {[$ctl size] - 1}]} { return }
		set newidx [expr {$arridx + 1}]
		set newsel [expr {$idx + 1}] 
	    }
	    set newentry [lindex [array get g_node_types $arridx] 1]
	    set oldentry [lindex [array get g_node_types $newidx] 1]
	    if {$oldentry != ""} {
		array set g_node_types [list $arridx $oldentry] 
	    }
	    array set g_node_types [list $newidx $newentry]
	}
    }

    nodesConfigRefreshList $wi
    if { $newsel != "" } { 
	$ctl selection clear 0 end
	$ctl selection set $newsel
    }
    nodesConfigSelect $wi ""
}

# helper for services button
proc nodesConfigServices { wi services_or_profile } {
    global g_node_type_services_hint g_current_session g_machine_type
    set idx [$wi.s.nodes curselection]
    if { $idx == "" } { return }

    set g_node_type_services_hint [$wi.s.nodes get $idx]
    # use the default emulation plugin - not associated with any node
    set sock [lindex [getEmulPlugin "*"] 2]
    # node number 0 is sent, but these services are not associated with a node
    if { $services_or_profile == "profile" } {
	set services_or_profile $g_machine_type ;# address the e.g. "xen" model
	set opaque "$g_machine_type:$g_node_type_services_hint"
    } else {
	set opaque ""
    }
    sendConfRequestMessage $sock -1 $services_or_profile 0x1 -1 $opaque 
}

# helper for when close button is pressed
proc nodesConfigClose { wi } {
    set missing [checkNodeTypes false]
    if { $missing != "" } {
	set msg "Missing default node type '$missing'!"
	set msg "$msg\nChanging the name of a default node type is not"
	set msg "$msg allowed."
	tk_messageBox -icon error -title "Error" -message $msg
	return
    }
    writeNodesConf
    drawToolbarSubmenu "routers" [getNodeTypeNames]
    setLeftTooltips "routers" [getNodeTypeNames]
    destroy $wi
}

# set the submenu tooltips stored in the left_tooltips array
# needs to be invoked whenever the name of a user-defined node type changes
# key = "routers", names = [getNodeTypeNames]  for node types
proc setLeftTooltips { key names } {
    global left_tooltips
    for {set i 0 } { $i < [llength $names] } { incr i } {
	if { $key != "routers" && [info exists left_tooltips($key$i)] } {
	    continue; # skip built-in buttons already defined
	}
	array set left_tooltips [list $key$i [lindex $names $i]]
    }
    if { $key == "routers" } {
	array set left_tooltips [list $key$i "edit node types"]
    }
}

# Helper for open/save buttons
# cmd is open or save; ctldata is the text control having the file data;
# ctlinitfn is the control having the initial filename
proc genericOpenSaveButtonPress { cmd ctldata ctlinitfn } {
    # get initial filename from ctlinitfn
    set fn [file tail [$ctlinitfn get]]

    if { $cmd == "save" } {
	set title "Save File Text"
	set fn [tk_getSaveFile -title $title -initialfile $fn -parent $ctldata]
	set mode "w"
	set action "writing"
    } else {
	set title "Load File Text"
	set fn [tk_getOpenFile -title $title -initialfile $fn -parent $ctldata]
	set mode "r"
	set action "loading"
    }

    # user presses cancel
    if { $fn == "" } { return }

    set r "retry"
    while { $r == "retry" } {
	if { [catch { set f [open $fn $mode] } e] } {
	    set r [tk_messageBox -type retrycancel -title "Error" \
		    -message "Error $action file $fn: $e"]
	} else {
	    set r ""
	}

    }
    if { $r == "cancel" } { return }

    if { $cmd == "save" } {
	puts $f [$ctldata get 0.0 end-1c]
    } else {
	$ctldata delete 0.0 end
	while { [gets $f line] >= 0 } {
	    $ctldata insert end "$line\n"
	}
    }
    close $f
}

#
# built-in node types
#
proc rj45.layer {}      { return LINK }
proc lanswitch.layer {} { return LINK }
proc hub.layer {}       { return LINK }
proc tunnel.layer {}    { return LINK }
proc wlan.layer {}      { return LINK }
proc router.layer {}    { return NETWORK }
proc router.shellcmd { n } { return "vtysh" }

# load the nodes.conf file when this file is loaded
loadNodesConf
