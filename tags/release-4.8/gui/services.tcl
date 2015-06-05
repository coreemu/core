#
# Copyright 2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author:	Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
# GUI support for managing CORE node services.
#

#
# Popup a services configuration dialog box. Similar to popupCapabilityConfig
# but customized for configuring node services. This dialog has two uses:
# (1) selecting the default services for a node type (when session != ""), and
# (2) selecting/customizing services for a certain node
#
proc popupServicesConfig { channel node types values captions possible_values groups session } {
    global plugin_img_edit
    global g_service_ctls
    global g_sent_nodelink_definitions
    set wi .popupServicesConfig
    catch {destroy $wi}
    toplevel $wi

    # instead of using vals, the activated services are stored in this list
    set activated ""
    if { $session != "" } {
	global g_node_type_services_hint
	if { ![info exists g_node_type_services_hint] } {
	    set g_node_type_services_hint "router"
	}
	set title "Default services"
	set toptitle "Default services for node type $g_node_type_services_hint"
	set activated [getNodeTypeServices $g_node_type_services_hint]
	set parent .nodesConfig
    } else {
        set title "Node [getNodeName $node] ($node) services"
	set toptitle $title
	set activated [getNodeServices $node true]
	set parent .popup
    }
    if { ![winfo exists $parent] } {
	set parent "."
    }
    wm title $wi $title
    wm transient $wi $parent 

    label $wi.top -text $toptitle 
    pack $wi.top -side top -padx 4 -pady 4

    frame $wi.vals -relief raised -borderwidth 1

    set g_sent_nodelink_definitions 0 ;# only send node/link defs once
    set g_service_ctls {} ;# list of checkboxes

    set n 0
    set gn 0
    set lastgn -1
    foreach type $types {
	# group values into frames based on groups TLV
	set groupinfo [popupCapabilityConfigGroup $groups [expr {$n + 1}]]
	set gn [lindex $groupinfo 0]
	set groupcaption [lindex $groupinfo 1]
	if { $lastgn != $gn } {
	    labelframe $wi.vals.$gn -text $groupcaption \
	    		-borderwidth 1 -padx 4 -pady 4
	}
	frame $wi.vals.$gn.item$n
	if {$type != 11} { ;# boolean value
	    puts "warning: skipping service config [lindex $captions $n]"
	    incr n
	    continue
	}
	set servicename [lindex $captions $n]
	global $wi.vals.$gn.item$n.entval
	checkbutton $wi.vals.$gn.item$n.ent -width 12 -wraplength 90 \
	    -variable $wi.vals.$gn.item$n.entval -text $servicename \
	    -offrelief flat -indicatoron false -overrelief raised
	lappend g_service_ctls $wi.vals.$gn.item$n.ent

	if { [lsearch -exact $activated [lindex $captions $n]] == -1 } {
	    set value 0 ;# not in the activated list
	} else {
	    set value 1
	}
	set $wi.vals.$gn.item$n.entval $value
	if { $session == "" } {
	    set needcustom false
	    if { $n < [llength $possible_values] } {
		if { [lindex $possible_values $n] == 1 } { set needcustom true }
	    }
	    set btn $wi.vals.$gn.item$n.custom
	    button $btn -image $plugin_img_edit \
		    -command "customizeService $wi $node $servicename $btn"
	    setCustomButtonColor $btn $node $servicename $needcustom
	    pack $wi.vals.$gn.item$n.custom -side right -padx 4 -pady 4
	    # this causes the button for services that require customization to 
	    # turn yellow when the service is selected
	    $wi.vals.$gn.item$n.ent configure -command \
		"setCustomButtonColor $btn $node $servicename $needcustom"
	}
	pack $wi.vals.$gn.item$n.ent -side right -padx 4 -pady 4
	pack $wi.vals.$gn.item$n -side top -anchor e
	if { $lastgn != $gn } {
	    pack $wi.vals.$gn -side left -anchor n -fill both
	    set lastgn $gn
	}
	incr n
    }; # end foreach
    pack $wi.vals.$gn -side left -anchor n -fill both
    pack $wi.vals -side top -padx 4 -pady 4

    # Apply / Cancel buttons
    set apply_cmd "popupServicesConfigApply $wi $channel $node {$session}"
    set cancel_cmd "destroy $wi"
    frame $wi.btn
    button $wi.btn.apply -text "Apply" -command $apply_cmd
    button $wi.btn.def -text "Defaults" -command \
	"popupServicesConfigDefaults $wi $node {$types} {$captions} {$groups}"
    button $wi.btn.cancel -text "Cancel" -command $cancel_cmd
    set buttons [list $wi.btn.apply $wi.btn.cancel]
    if { $session == "" } {
	set buttons [linsert $buttons 1 $wi.btn.def]
    }
    foreach b $buttons { pack $b -side left -padx 4 -pady 4 }
    pack $wi.btn -side bottom
    bind $wi <Key-Return> $apply_cmd
    bind $wi <Key-Escape> $cancel_cmd
}

#
# Save the selection of activated services with the node or in the g_node_types
# array when configuring node type defaults.
#
proc popupServicesConfigApply { wi channel node session } {
    set vals [getSelectedServices]

    # save default services for a node type into the g_node_types array
    if { $session != "" } {
	global g_node_types g_node_type_services_hint
	set type $g_node_type_services_hint
	set idx [getNodeTypeIndex $type]
	if { $idx < 0 } { 
	    puts "warning: skipping unknown node type $type"
	} else {
	    set typedata $g_node_types($idx)
	    set typedata [lreplace $typedata 3 3 $vals]
	    array set g_node_types [list $idx $typedata]
	}
    # save the services configured for a specific node
    } else {
	setNodeServices $node $vals
    }

    destroy $wi
}

# load the default set of services for this node type
proc popupServicesConfigDefaults { wi node types captions groups } {
    set type [getNodeModel $node]
    set defaults [getNodeTypeServices $type]
    for { set n 0 } { $n < [llength $types] } { incr n } {
	set groupinfo [popupCapabilityConfigGroup $groups [expr {$n + 1}]]
	set gn [lindex $groupinfo 0]

	set val 0
	set valname [lindex $captions $n]
	if { [lsearch $defaults $valname] != -1 } { set val 1 }
	global $wi.vals.$gn.item$n.entval
	set $wi.vals.$gn.item$n.entval $val
    }
}

#
# Popup a service customization dialog for a given service on a node
# The customize/edit button next to a service has been pressed
#
proc customizeService { wi node service btn } {
    global g_sent_nodelink_definitions
    global plugin_img_add plugin_img_del plugin_img_folder
    global plugin_img_open plugin_img_save
    global eventtypes
    set selected [getSelectedServices]
    # if service is not enabled, enable it here
    if { [lsearch -exact $selected $service] == -1 } {
	set i [string last ".custom" $btn]
	set entval [string replace $btn $i end ".entval"]
	global $entval
	set $entval 1
	lappend selected $service
    }

    # inform the CORE services about all nodes and links, so it can build
    # custom configurations for services
    if { $g_sent_nodelink_definitions == 0 } {
	set g_sent_nodelink_definitions 1
        set sock [lindex [getEmulPlugin $node] 2]
	sendEventMessage $sock $eventtypes(definition_state) -1 "" "" 0
        sendNodeLinkDefinitions $sock
    }

    set w .popupServicesCustomize
    catch {destroy $w}
    toplevel $w
    wm transient $w .popupServicesConfig   
    wm title $w "$service on node [getNodeName $node] ($node)"

    ttk::frame $w.top
    ttk::label $w.top.lab -text "$service service"

    ttk::frame $w.top.meta
    ttk::label $w.top.meta.lab -text "Meta-data"
    ttk::entry $w.top.meta.ent -width 40
    pack $w.top.lab -side top
    pack $w.top.meta.lab -side left -padx 4 -pady 4
    pack $w.top.meta.ent -fill x -side left -padx 4 -pady 4
    pack $w.top.meta -side top
    pack $w.top -side top -padx 4 -pady 4

    ttk::notebook $w.note
    pack $w.note -fill both -expand true -padx 4 -pady 4
    ttk::notebook::enableTraversal $w.note

    set enableapplycmd "$w.btn.apply configure -state normal"

    ### Custom ###
    # services may define custom popup configuration dialogs invoked here
    set custom_popup "popupServiceConfig_$service"
    if { [info commands $custom_popup] == $custom_popup } {
	$custom_popup $wi $w $node $service $btn
    }

    ### Files ###
    ttk::frame $w.note.files
    set fileshelp "Config files and scripts that are generated for this"
    set fileshelp "$fileshelp service."
    ttk::label $w.note.files.help -text $fileshelp
    pack $w.note.files.help -side top -anchor w -padx 4 -pady 4
    $w.note add $w.note.files -text "Files" -underline 0

    ttk::frame $w.note.files.name
    ttk::label $w.note.files.name.lab -text "File name:"
    set combo $w.note.files.name.combo
    ttk::combobox $combo -width 30
    set helpercmd "customizeServiceFileHelper $w"
    ttk::button $w.note.files.name.add -image $plugin_img_add \
	-command "listboxAddDelHelper add $combo $combo true; $helpercmd false"
    ttk::button $w.note.files.name.del -image $plugin_img_del \
	-command "listboxAddDelHelper del $combo $combo true; $helpercmd true"
    pack $w.note.files.name.lab -side left
    pack $w.note.files.name.combo -side left -fill x -expand true
    foreach c [list add del] {
	pack $w.note.files.name.$c -side left
    }
    pack $w.note.files.name -side top -anchor w -padx 4 -pady 4 -fill x

    # copy source file
    global g_service_configs_opt
    set g_service_configs_opt "use"
    set f ${w}.note.files.copy
    ttk::frame $f
    ttk::radiobutton $f.opt -text "Copy this source file: " \
	-value "copy" -variable g_service_configs_opt \
	-command "customizeServiceFileOpt $w copy true"
    ttk::entry $f.name -width 45
    ttk::button $f.btn -image $plugin_img_open -command \
	"customizeServiceFileOpt $w copy true; fileButtonPopup $f.name {}"
    pack $f.opt $f.name $f.btn -side left -anchor w 
    pack $f -side top -anchor w -padx 4 -pady 4 -fill x
    bind $f.btn <Button> "customizeServiceFileOpt $w copy true"

    # use file text
    set f ${w}.note.files.use
    ttk::frame $f
    ttk::radiobutton $f.opt -text "Use text below for file contents:" \
	-value "use" -variable g_service_configs_opt \
	-command "customizeServiceFileOpt $w use true"
    pack $f.opt -side left
    foreach c [list open save] {
	ttk::button $f.$c -image [set plugin_img_$c] -command \
	    "customizeServiceFileOpt $w use true; genericOpenSaveButtonPress $c $w.note.files.txt $w.note.files.name.combo"
        pack $f.$c -side left
    }
    pack $f -side top -anchor w -padx 4 -pady 4 -fill x

    text $w.note.files.txt -bg white -width 80 -height 10 \
	-yscrollcommand "$w.note.files.scroll set" -undo 1
    ttk::scrollbar $w.note.files.scroll -command "$w.note.files.txt yview"

    pack $w.note.files.txt -side left -fill both -expand true
    pack $w.note.files.scroll -side right -fill y
    bind $w.note.files.txt <KeyPress> $enableapplycmd

    global g_service_configs_tmp g_service_configs_last
    if { [info exists g_service_configs_tmp ] } {
	array unset g_service_configs_tmp
    }
    array set g_service_configs_tmp {}
    set g_service_configs_last ""
    bind $w.note.files.name.combo <<ComboboxSelected>> "$helpercmd true"
    bind $w.note.files.name.combo <KeyPress> $enableapplycmd

    ### Directories ###
    ttk::frame $w.note.dirs
    $w.note add $w.note.dirs -text "Directories" -underline 0
    set helptxt "Directories required by this service that are"
    set helptxt "$helptxt unique for each node."
    ttk::label $w.note.dirs.help -text $helptxt
    pack $w.note.dirs.help -side top -anchor w -padx 4 -pady 4

    ttk::treeview $w.note.dirs.tree -height 3 -selectmode browse
    $w.note.dirs.tree heading \#0 -text "Per-node directories"
    $w.note.dirs.tree insert {} end -id root -text "/" -open true \
 	-image $plugin_img_folder
    ttk::button $w.note.dirs.add -image $plugin_img_add \
	-command "customizeServiceDirectoryHelper $w add; $enableapplycmd"
    ttk::button $w.note.dirs.del -image $plugin_img_del \
	-command "customizeServiceDirectoryHelper $w del; $enableapplycmd"

    pack $w.note.dirs.tree -side top -fill both -expand true -padx 4 -pady 4
    pack $w.note.dirs.del $w.note.dirs.add -side right

    ### Startup/shutdown ###
    ttk::frame $w.note.ss
    $w.note add $w.note.ss -text "Startup/shutdown" -underline 0

    global g_service_startup_index
    set g_service_startup_index 50
    ttk::frame $w.note.ss.si
    ttk::label $w.note.ss.si.idxlab -text "Startup index:"
    ttk::entry $w.note.ss.si.idxval -width 5 \
	-textvariable g_service_startup_index
    ttk::scale $w.note.ss.si.idx -from 0 -to 100 -orient horizontal \
	-variable g_service_startup_index \
	-command "$enableapplycmd; scaleresolution 1 g_service_startup_index"
    pack $w.note.ss.si.idxlab $w.note.ss.si.idxval -side left -padx 4 -pady 4
    pack $w.note.ss.si.idx -side left -expand true -fill x -padx 4 -pady 4
    pack $w.note.ss.si -side top -padx 4 -pady 4 -fill x

    global g_service_startup_time
    set g_service_startup_time ""
    ttk::frame $w.note.ss.st
    ttk::label $w.note.ss.st.timelab -text "Start time:"
    ttk::entry $w.note.ss.st.timeval -width 5 \
	-textvariable g_service_startup_time
    set txt "(seconds after runtime; leave empty for default)"
    ttk::label $w.note.ss.st.help -text $txt 
    pack $w.note.ss.st.timelab $w.note.ss.st.timeval $w.note.ss.st.help \
	-side left -padx 4 -pady 4
    pack $w.note.ss.st -side top -padx 4 -pady 4 -fill x
    bind $w.note.ss.st.timeval <KeyPress> $enableapplycmd


    set captions "Startup Shutdown Validate"
    foreach c "up down val" {
	set fr $w.note.ss
	set caption [lindex $captions 0]
	set captions [lreplace $captions 0 0]
        entrylistbox $fr $c "$caption Commands" $enableapplycmd
    }

    set closecmd "destroy $w; setCustomButtonColor $btn $node $service false"

    ttk::frame $w.btn
    global g_customize_service_diff_only
    set g_customize_service_diff_only 1
    ttk::checkbutton $w.btn.diff -variable g_customize_service_diff_only \
    	-text "only store values that have changed from their defaults"
    ttk::button $w.btn.apply -text "Apply" -state disabled \
	-command "customizeServiceApply $w $node $service; $closecmd"
    ttk::button $w.btn.reset -text "Defaults" \
	-command "customizeServiceReset $w $node $service {$selected}; $w.btn.close configure -text Close"
    ttk::button $w.btn.copy -text "Copy..." \
	-command "customizeServiceCopy $node"
    ttk::button $w.btn.close -text "Cancel" -command $closecmd
    pack $w.btn.diff -side top
    pack $w.btn.apply $w.btn.reset $w.btn.copy $w.btn.close -side left
    pack $w.btn -side top -padx 4 -pady 4

    # populate dialog values
    customizeServiceRefresh $service "$w $node {$selected}"
}

# popup dialog with tree view for copying customized service configuration
# parameters from other nodes
proc customizeServiceCopy { cnode } {
    global node_list plugin_img_edit plugin_img_open

    set w .popupServicesCopy
    catch {destroy $w}
    toplevel $w
    wm transient $w .popupServicesCustomize
    wm title $w "Copy services to node [getNodeName $cnode] ($cnode)"

    ttk::frame $w.nodes
    ttk::treeview $w.nodes.tree -height 3 -selectmode extended
    $w.nodes.tree heading \#0 -text "Service configuration items"

    pack $w.nodes.tree -side top -fill both -expand true -padx 4 -pady 4
    pack $w.nodes -side top -anchor w -fill both -expand true

    ttk::frame $w.btn
    ttk::button $w.btn.apply -text "Copy" \
    	-command "customizeServiceCopyApply $w $cnode"
    ttk::button $w.btn.view -text "View" \
    	-command "customizeServiceCopyView $w $cnode"
    ttk::button $w.btn.close -text "Cancel" -command "destroy $w"
    pack $w.btn.apply $w.btn.view $w.btn.close -side left
    pack $w.btn -side top -padx 4 -pady 4
    set tree $w.nodes.tree

    foreach node $node_list {
	if { $node == $cnode } { continue }
	set customCfgList [getCustomConfig $node]
	foreach element $customCfgList {
	    set id [getConfig $element "custom-config-id"]
	    set parts [split $id :]
	    if { [lindex $parts 0] != "service" } { continue }
	    set s [lindex $parts 1]
	    # insert node into tree
	    if { ![$tree exists "$node"] } {
		set img [getCustomImage $node]
		if { $img == "" } {
		    set model [getNodeModel $node]
		    set img [getNodeTypeImage $model normal]
		}
		set img [file tail $img].5
		global [set img]
		set img [set [set img]]
		$tree insert {} end -id "$node" -text $node -open true \
			-image $img
	    }
	    # insert service name
	    if { ![$tree exists "$node:$s"] } {
		$tree insert $node end -id "$node:$s" -text $s -open true
	    }
	    # insert service elements
	    if { [llength $parts] == 3 } {
		set f [lindex $parts 2]
	        $tree insert "$node:$s" end -id "$node:$s:$f" -text $f \
			-image $plugin_img_open
	    } else {
		set cfg [getConfig $element "config"]
		foreach c $cfg {
		    if { [lindex [split $c =] 0] == "files" } { continue }
	            $tree insert "$node:$s" end -id "$node:$s:$c" -text $c \
		    	-image $plugin_img_edit
		}
	    }
	} ;# end foreach element
    }
}

# copy selected service configuration items from other nodes to the current
# customize dialog
proc customizeServiceCopyApply { w node } {
    global g_service_configs_tmp g_service_configs_last
    global g_service_startup_index g_service_startup_time 
    set tgt .popupServicesCustomize

    set tree $w.nodes.tree
    set sel [$tree selection]
    destroy $w

    foreach s $sel {
	set parts [split $s :]
	set node [lindex $parts 0]; set service [lindex $parts 1]
	set item [lindex $parts 2]
	# customized file 
	set f [getCustomService $node "$service:$item"]
	if { $f != "" } {
	    set filedata [join $f "\n"]
            array set g_service_configs_tmp [list $item $filedata]
	    set files [$tgt.note.files.name.combo cget -values]
	    if { [lsearch $files $item] < 0 } {
		lappend files $item
		$tgt.note.files.name.combo configure -values $files
	    }
	    if { $g_service_configs_last == $item } {
		customizeServiceFileDataSet $tgt $filedata
	    }
	# customized parameters
	} else {
	    set kv [splitKeyValue $item]
	    set key [lindex $kv 0]
	    set value [lindex $kv 1]
	    switch -exact -- $key {
		meta {
		    $tgt.top.meta.ent delete 0 end
		    $tgt.top.meta.ent insert end $value
		}
		dirs {
		    foreach dir [tupleStringToList $value] {
			set dir [string range $dir 1 end]
			treeviewInsert $tgt.note.dirs.tree root [split $dir "/"]
		    }
		}
		startidx {
	    	    set g_service_startup_index $value
		}
		cmdup -
		cmddown -
		cmdval {
		    set name [string range $key 3 end]
		    foreach cmd [tupleStringToList $value] {
			$tgt.note.ss.$name.cmds.list insert end $cmd
		    }
		}
		starttime {
		    set g_service_startup_time $value
		}
		default {
		    puts "warning: didn't copy '$key'"
		}
	    }
	}
    }

}

# view the customization for comparison with current node
proc customizeServiceCopyView { w node } {
    set tree $w.nodes.tree
    set sel [$tree selection]
    destroy $w

    set fn ""
    set filedata ""
    foreach s $sel {
	set parts [split $s :]
	set node [lindex $parts 0]; set service [lindex $parts 1]
	set item [lindex $parts 2]
	# customized file 
	set f [getCustomService $node "$service:$item"]
	if { $f != "" } {
	    set fn [file join "/tmp" "services.tmp-$node-[file tail $item]"]
	    set filedata [join $f "\n"]
	# customized parameters
	} else {
	    set kv [splitKeyValue $item]
	    set key [lindex $kv 0]
	    set value [lindex $kv 1]
	    set fn [file join "/tmp" "services.tmp-$node-$key"]
	    set filedata $value
	}
    }

    if { $fn == "" } { return }

    if { [catch { set f [open $fn w] } e] } {
	puts "error opening file: $fn\n ($e)"
	return
    }
    puts $f $filedata
    close $f

    popupFileView $fn
}

# helper for add/delete directories from treeview
proc customizeServiceDirectoryHelper { w cmd } {
    if { $cmd == "add" } {
	set dir [tk_chooseDirectory -mustexist false -initialdir "/" \
		-parent $w -title "Add a per-node directory"]
	if { $dir == "" } { return }
	set dir [string range $dir 1 end] ;# chop off leading slash
	treeviewInsert $w.note.dirs.tree root [split $dir "/"]
    } elseif { $cmd == "del" } {
	set s [$w.note.dirs.tree selection]
	if { $s == "root" } { return } ;# may not delete root
	$w.note.dirs.tree delete $s ;# delete the current selection
	set parents [lreplace [split $s /] end end]
	# delete all parents of the selected node if they do not have children
	while {[llength $parents] > 1} {
	    set parent [join $parents "/"]
	    if { [llength [$w.note.dirs.tree children $parent]] == 0 } {
		$w.note.dirs.tree delete $parent
	    }
	    set parents [lreplace $parents end end]
	}
    }
}

# helper for switching files based on combo box selection
proc customizeServiceFileHelper { w clear } {
    global g_service_configs_tmp g_service_configs_last
    # save old config to array
    set cfg [customizeServiceFileDataGet $w]
    if { [info exists g_service_configs_last] && \
	 $g_service_configs_last != "" } {
	array set g_service_configs_tmp [list $g_service_configs_last $cfg]
    }
    set cfgname [$w.note.files.name.combo get]
    set g_service_configs_last $cfgname

    # populate with new config
    if { $clear } {
	$w.note.files.txt delete 0.0 end
	$w.note.files.copy.name delete 0 end
	customizeServiceFileOpt $w "use" false
    }
    if { ![info exists g_service_configs_tmp($cfgname)] } {
	array set g_service_configs_tmp [list $cfgname ""]
    } else {
	set cfg $g_service_configs_tmp($cfgname)
	customizeServiceFileDataSet $w $cfg
    }
}

# helper to insert file contents into the text controls
proc customizeServiceFileDataSet { w cfg } {
    $w.note.files.txt delete 0.0 end
    $w.note.files.copy.name delete 0 end
    if { [string range $cfg 0 6] == "file://" } {
	customizeServiceFileOpt $w "copy" false
	set cfglines [split $cfg "\n"]
	set cfg [lindex $cfglines 0] ;# truncate any other lines
	$w.note.files.copy.name insert 0 [string range $cfg 7 end]
    } else {
	customizeServiceFileOpt $w "use" false
	$w.note.files.txt insert 0.0 $cfg
    }
}

# helper to get file contents from the text controls
proc customizeServiceFileDataGet { w } {
    global g_service_configs_opt
    if { $g_service_configs_opt == "use" } {
	set cfg [$w.note.files.txt get 0.0 end-1c]
    } elseif { $g_service_configs_opt == "copy" } {
	set cfg [$w.note.files.copy.name get]
	set cfg "file://$cfg"
    }
    return $cfg
}

# helper to set option mode to use/copy
proc customizeServiceFileOpt { w mode enable_apply } {
    global g_service_configs_opt
    set g_service_configs_opt $mode
    if { $mode == "copy" } {
	$w.note.files.txt configure -state disabled -bg gray
	$w.note.files.copy.name configure -state normal
    } else {
	$w.note.files.txt configure -state normal -bg white
	$w.note.files.copy.name configure -state disabled
    }
    if { $enable_apply } {
	$w.btn.apply configure -state normal
    }
}

# create a listbox with a text entry above it, with add/delete buttons and
# a scrollbar
proc entrylistbox { fr name caption extracmd} {
    global plugin_img_add plugin_img_del

    set c $name
    ttk::labelframe $fr.$name -text "$caption"

    ttk::frame $fr.$c.edit
    ttk::entry $fr.$c.edit.cmd -width 40
    ttk::button $fr.$c.edit.add -image $plugin_img_add \
        -command "listboxAddDelHelper add $fr.$c.edit.cmd $fr.$c.cmds.list false; $extracmd"
    ttk::button $fr.$c.edit.del -image $plugin_img_del \
        -command "listboxAddDelHelper del $fr.$c.edit.cmd $fr.$c.cmds.list false; $extracmd"
    pack $fr.$c.edit.cmd -side left -fill x -expand true
    pack $fr.$c.edit.add $fr.$c.edit.del -side left

    ttk::frame $fr.$c.cmds
    listbox $fr.$c.cmds.list -height 5 -width 50 \
        -yscrollcommand "$fr.$c.cmds.scroll set" -exportselection 0
    bind $fr.$c.cmds.list <<ListboxSelect>> "listboxSelect $fr.$c.cmds.list $fr.$c.edit.cmd"
    ttk::scrollbar $fr.$c.cmds.scroll -command "$fr.$c.cmds.list yview"
    pack $fr.$c.cmds.list  -side left -fill both -expand true
    pack $fr.$c.cmds.scroll -side left -fill y
        pack $fr.$c.edit $fr.$c.cmds -side top -anchor w -fill x
    pack $fr.$c -side top -fill x -expand true
}

#
# color the customize/edit button adjacent to each service checkbutton
#
proc setCustomButtonColor { btn node service needcustom } {
    set color lightgray ;# default button background color

    # color button yellow if enabled and customization is needed
    if { $needcustom } {
	# button $wi.vals.$gn.item$n.custom / value $wi.vals.$gn.item$n.entval
	set i [string last ".custom" $btn]
	set entval [string replace $btn $i end ".entval"]
	global $entval
	if { [set $entval] } {
	    set color yellow
	}
    }
    if { [getCustomService $node $service] != "" } {
	set color green
    }
    $btn configure -bg $color
}

proc scaleresolution { res var val } {
    set factor [expr {1 / $res}]
    set val [expr {int($val * $factor) / $factor}]
    global $var
    set $var $val
    return $val
}

# return a list of services that have been selected (checkbox is checked)
proc getSelectedServices { } {
    global g_service_ctls
    set selected {}
    foreach c $g_service_ctls {
	global $c
	set service [$c cget -text]
	set var [$c cget -variable]
	global $var
	if { [set $var] == 1 } { lappend selected $service }
    }
    return $selected
}

# send a config request message with the opaque field set to query for all
# service parameters; the opaque field is "service:s5,s2,s3,s4", where service
# s5 is being configured (parseConfMessage will invoke customizeServiceValues)
proc customizeServiceRefresh { var args } {
    set args [lindex $args 0]
    set w [lindex $args 0]
    set node [lindex $args 1]
    set services [lindex $args 2]

    # move service to the front of the list of services
    set i [lsearch $services $var]
    if { $i < 0 } {
	puts "error: service $var not found in '$services'"
	return
    } elseif { $i > 0 } {
	set services [lreplace $services $i $i]
	set services [linsert $services 0 $var]
    }

    # request service parameters from daemon
    set svcstr [join $services ","]
    set sock [lindex [getEmulPlugin $node] 2]
    sendConfRequestMessage $sock $node services 0x1 -1 "service:$svcstr"
    update
}

# this returns a list of values for the service s on node if a custom service
# configuration exists
proc getCustomService { node s } {
    set values [getCustomConfigByID $node "service:$s"]
    return $values
}

# this helper is invoked upon receiving the reply to the message sent from
# customizeServiceRefresh; it populates the dialog box fields
proc customizeServiceValues { node values services } {
    global plugin_img_folder

    set service [lindex $services 0]

    set w .popupServicesCustomize
    if { ![winfo exists $w] } {
	# apply config update without dialog box
	# this occurs when loading from XML or reconnecting to a session
        setCustomConfig $node "service:$service" $service $values 0
	return
    }

    global g_customize_service_values_orig
    set g_customize_service_values_orig $values

    # merge any custom values with defaults from message
    set custom_values [getCustomService $node $service]
    set i 0
    set has_keys [hasKeyValues $custom_values]
    foreach val $custom_values {
	if { $has_keys } {
	    set kv [splitKeyValue $val]
	    set key [lindex $kv 0]; set value [lindex $kv 1]
	    set values [setServiceValuesItem $values $key $value]
	} else {
	    set values [lreplace $values $i $i $val]
	}
	incr i
    }

    # populate meta-data
    set meta [getServiceValuesItem $values "meta" 6]
    $w.top.meta.ent delete 0 end
    $w.top.meta.ent insert end $meta

    # populate Files tab
    set files [tupleStringToList [getServiceValuesItem $values "files" 1]]
    set chosenfile [lindex $files 0] ;# auto-display first file from list
    $w.note.files.name.combo configure -values $files
    $w.note.files.name.combo delete 0 end
    if { $chosenfile != "" } {
	$w.note.files.name.combo insert 0 $chosenfile
    }
    global g_service_configs_last
    set g_service_configs_last $chosenfile

    # file data
    foreach f $files {
	set filedata [join [getCustomService $node "$service:$f"] "\n"]
	if { $filedata != "" } {
	    # use file contents from existing config
	    customizeServiceFile $node $f "service:$service" $filedata false
	} elseif { $f !=  "" } {
	    # request the file contents
	    set svcstr [join $services ","]
	    set sock [lindex [getEmulPlugin "*"] 2]
	    set opaque "service:$svcstr:$f"
	    # this causes customizeServiceFile to be invoked upon reply
	    sendConfRequestMessage $sock $node services 0x1 -1 $opaque
	}
    }

    # populate Directories tab
    set dirs [tupleStringToList [getServiceValuesItem $values "dirs" 0]]
    $w.note.dirs.tree delete root
    $w.note.dirs.tree insert {} end -id root -text "/" -open true \
	-image $plugin_img_folder
    foreach dir $dirs {
	set dir [string range $dir 1 end] ;# chop off leading slash
	treeviewInsert $w.note.dirs.tree root [split $dir "/"]
    }

    # populate Startup/shutdown tab
    set idx [getServiceValuesItem $values "startidx" 2]
    global g_service_startup_index
    set g_service_startup_index $idx

    set valuesidx 3
    foreach c "up down val" {
	set fr $w.note.ss
	$fr.$c.edit.cmd delete 0 end
	$fr.$c.cmds.list delete 0 end
	set value [getServiceValuesItem $values "cmd$c" $valuesidx]
	foreach cmd [tupleStringToList $value] {
	    if { $cmd != "" } { $fr.$c.cmds.list insert end $cmd }
	}
	incr valuesidx
    }

    set starttime [getServiceValuesItem $values "starttime" 6]
    global g_service_startup_time
    set g_service_startup_time $starttime

    # populate any custom service tab
    set service [lindex $services 0]
    set custom_vals_callback "popupServiceConfig_${service}_vals"
    if { [info commands $custom_vals_callback] == $custom_vals_callback } {
	$custom_vals_callback $node $values $services $w
    }

    $w.btn.apply configure -state disabled
}

# extract items from a list of values
# old-style values has an ordered list of values; idx determines key
# new-style values is a list of key=value pairs
proc getServiceValuesItem { values key idx } {
    # determine how to handle values
    set has_keys [hasKeyValues $values]
    if { $has_keys } {
        return [getKeyValue $key $values ""]
    } else {
	return [lindex $values $idx]
    }
}

# replace a "key=value" pair in a list, returning the list
proc setServiceValuesItem { values key value } {
    set i 0
    foreach v $values {
	set k [lindex [splitKeyValue $v] 0]
	if { $k == $key } { break }
	incr i
    }
    if { $i == [llength $values] } {
	puts "key not found '$key' in service values"
	return $values
    }
    return [lreplace $values $i $i "$key=$value"]
}

# this helper is invoked upon receiving a File Message in reply to the Config
# Message sent from customizeServiceRefresh; it populates the config file entry
proc customizeServiceFile { node name type data generated} {
    global g_service_configs_tmp g_service_configs_tmp_orig 
    global g_service_configs_last

    set w .popupServicesCustomize
    if { ![winfo exists $w] } {
	# apply file config update without dialog box
	# this occurs when loading from XML or reconnecting to a session
	# type should be e.g. "service:zebra"
	set data [split $data "\n"]
	setCustomConfig $node "$type:$name" $name $data 0
	return
    }

    # store file data in array
    array set g_service_configs_tmp [list $name $data]
    if { $generated } {
	array set g_service_configs_tmp_orig [list $name $data]
    } else {
	array set g_service_configs_tmp_orig [list $name ""]
    }

    # display file if currently selected
    if { $g_service_configs_last == $name } {
	customizeServiceFileDataSet $w $data
    }

    # invoke any custom service callback
    set service [string range $type 8 end] ;# assume already checked "service:"
    set custom_file_callback "popupServiceConfig_${service}_file"
    if { [info commands $custom_file_callback] == $custom_file_callback } {
	$custom_file_callback $node $name $data $w
    }
}

# helper to recursively add a directory path to a treeview
proc treeviewInsert { tree parent items } {
    # pop first item
    set item [lindex $items 0]
    set items [lreplace $items 0 0]
    set img [$tree item $parent -image] ;# adopt icon from parent
    if { ![$tree exists "$parent/$item"] } {
	$tree insert $parent end -id "$parent/$item" -text $item -open true \
		-image $img
    }

    if { [llength $items] > 0 } {
	treeviewInsert $tree "$parent/$item" $items
    }
}

# return all children that are leaf nodes in a tree
proc treeviewLeaves { tree parent } {
    set leaves ""
    set children [$tree children $parent]
    if { [llength $children] == 0 } {
	return $parent
    }
    foreach child $children {
	set leaves [concat $leaves [treeviewLeaves $tree $child]]
    }
    return $leaves
}

# apply button pressed on customizeService dialog
proc customizeServiceApply { w node service } {
    global g_customize_service_diff_only

    catch { $w.btn.apply configure -state disabled }

    set values ""

    # Directories
    set dirs ""
    set dirstmp [treeviewLeaves $w.note.dirs.tree root]
    foreach dir $dirstmp {
	set dir [string replace $dir 0 3] ;# chop off "root" prefix
	if { $dir == "" } { continue }
	lappend dirs $dir
    }
    lappend values "dirs=[listToTupleString $dirs]"

    # Files
    set files [$w.note.files.name.combo cget -values]
    lappend values "files=[listToTupleString $files]"

    # Startup index
    global g_service_startup_index
    lappend values "startidx=$g_service_startup_index"

    # Startup/shutdown commands
    foreach c "up down val" {
	set cmds [$w.note.ss.$c.cmds.list get 0 end]
	lappend values "cmd$c=[listToTupleString $cmds]"
    }

    # meta
    lappend values "meta=[$w.top.meta.ent get]"

    # start time
    global g_service_startup_time
    lappend values "starttime=$g_service_startup_time"

    # remove any existing config files for this service
    #   this prevents duplicates when files are renamed/deleted
    set cfgs [getCustomConfig $node]
    foreach cfg $cfgs {
	set cid [lindex [lsearch -inline $cfg "custom-config-id *"] 1]
	set len [expr {[string length "service:$service:"] - 1}]
	if { [string range $cid 0 $len] == "service:$service:" } {
	    setCustomConfig $node $cid "" "" 1
	}
    }

    # save config files (that have changed)
    set trimmed_files {}
    global g_service_configs_tmp g_service_configs_tmp_orig
    global g_service_configs_last
    set cfg [customizeServiceFileDataGet $w]
    array set g_service_configs_tmp [list $g_service_configs_last $cfg]
    foreach cfgname $files {
	if { ![info exists g_service_configs_tmp($cfgname)] } {
	    puts "missing config for file '$cfgname'"
	    continue
	}
	if { [info exists g_service_configs_tmp_orig($cfgname)] } {
	    if { $g_service_configs_tmp_orig($cfgname) == \
		 $g_service_configs_tmp($cfgname) } {
		# file has not changed
		if { $g_customize_service_diff_only } { continue }
	    }
	}
	set cfg [split $g_service_configs_tmp($cfgname) "\n"]
	setCustomConfig $node "service:$service:$cfgname" $cfgname $cfg 0
	lappend trimmed_files $cfgname
    }


    # store only values that have changed from the defaults
    set trimmed {}
    global g_customize_service_values_orig
    for {set i 0} {$i < [llength $values]} {incr i} {
	set value_orig [lindex $g_customize_service_values_orig $i]
	set value_orig [tupleStringToList $value_orig]
	set value_new [tupleStringToList [lindex $values $i]]
	if { $i == 1 } {
	    # when a file has changed, store all filenames whether or not
	    # the name(s) have changed
	    if { [llength $trimmed_files] > 0 } {
		lappend trimmed [lindex $values 1]
	    }
	    continue
	}
	if {$value_orig != $value_new} {
	    lappend trimmed [lindex $values $i]
	}
    }
    if { $g_customize_service_diff_only } {
	set values $trimmed
    }
    unset g_customize_service_values_orig

    # save values without config file
    setCustomConfig $node "service:$service" $service $values 0

    array unset g_service_configs_tmp
    array unset g_service_configs_tmp_orig
    unset g_service_configs_last

    #  may want to apply here, if some config validation is implemented or
    #  runtime applying of service customization
    #  otherwise this is not necessary due to config being sent upon startup
    #  also more logic would be needed for using the reset button
    #set sock [lindex [getEmulPlugin $node] 2]
    #set types [string repeat "10 " [llength $values]]
    #sendConfReplyMessage $sock $node services $types $values "service:$service"
}

#
# reset button is pressed on customizeService dialog
#
proc customizeServiceReset { w node service services } {
    set cfgnames [$w.note.files.name.combo cget -values]
    setCustomConfig $node "service:$service" "" "" 1
    foreach cfgname $cfgnames {
	setCustomConfig $node "service:$service:$cfgname" "" "" 1
    }

    customizeServiceRefresh $service [list $w $node $services]
}

# check for old service configs in all nodes
proc upgradeConfigServices {} {
    global node_list
    foreach node $node_list {
	upgradeNodeConfigService $node
	upgradeCustomPostConfigCommands $node
    }
}

# provide backwards-compatibility with changes to services fields here
proc upgradeNodeConfigService { node } {
    set OLD_NUM_FIELDS 7
    set cfgs [getCustomConfig $node]
    foreach cfg $cfgs {
	set cid [lindex [lsearch -inline $cfg "custom-config-id service:*"] 1]
	# skip configs that are not a service definition ("service:name")
	if { [llength [split $cid :]] != 2 } { continue }

	set values [getConfig $cfg config]
        if { [llength $values] != [expr {$OLD_NUM_FIELDS-1}] } { continue }

	# update from 6 service fields to 7 when introducing validate commands
	set service [lindex [split $cid :] 1]
	#puts -nonewline "note: updating service $service on $node with empty "
	#puts "validation commands"
	set values [linsert $values end-1 {}]
	setCustomConfig $node "service:$service" $service $values 0
    }
}

proc upgradeCustomPostConfigCommands { node } {
    set cfg [getCustomPostConfigCommands $node]
    setCustomPostConfigCommands $node {}
    if { $cfg == "" } { return }
    set cfgname "custom-post-config-commands.sh"
    set values "{files=('$cfgname', )} startidx=35 {cmdup=('sh $cfgname', )}"
    setCustomConfig $node "service:UserDefined" "UserDefined" $values 0
    setCustomConfig $node "service:UserDefined:$cfgname" $cfgname $cfg 0
    set services [getNodeServices $node true]
    lappend services "UserDefined"
    setNodeServices $node $services
    puts "adding user-defined custom-post-config-commands.sh service for $node"

}

# populate services menu when right-clicking on a node at runtime
proc addServicesRightClickMenu { m node } {
    $m add cascade -label "Services" -menu $m.services

    set i 0
    set services [getNodeServices $node true]
    foreach s $services {
	set childmenu $m.services.s$i
	incr i
	destroy $childmenu
	menu $childmenu -tearoff 0
	$m.services add cascade -label $s -menu $childmenu
	foreach cmd "start stop restart validate" {
	    $childmenu add command -label $cmd \
		-command "sendServiceCmd $node $s $cmd"
	}
    }
}

proc sendServiceCmd { node service cmd } {
    global eventtypes

    set plugin [lindex [getEmulPlugin "*"] 0]
    set sock [pluginConnect $plugin connect true]

    if { $cmd == "validate" } { set cmd "pause" }
    set type $eventtypes(event_$cmd)
    set nodenum [string range $node 1 end]
    set name "service:$service"
    set data ""

    sendEventMessage $sock $type $nodenum $name $data 0
}
