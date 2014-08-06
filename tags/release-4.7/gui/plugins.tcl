#
# Copyright 2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author:	Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
# Support for managing CORE plugins from the GUI.
#

# possible types of plugins, indicating messaging type
array set g_plugin_types {
	0 "none"
	1 "CORE API"
}

array set g_plugin_status_types {
	0 "disconnected"
	1 "connected"
}

# array index is "name"
#   0ip       1port 2type 3auto 4status 5capabilities 6sock
#   127.0.0.1 4038  1     0     1       (reglist)     -1
array set g_plugins_default {
	{"GUI"}
	{ 0 0 1 0 1 "gui=core" -1 }
	{"core-daemon"}
	{ 127.0.0.1 4038 1 1 0 "emul=core-daemon" -1 }
}
array set g_plugins {
	{"GUI"}
	{ 0 0 1 0 1 "gui=core" -1 }
}

# TODO: move all shared image resources to a centralized place
if { $execMode == "interactive" } {
set iconpath "$CORE_DATA_DIR/icons/tiny"
set plugin_img_add  [image create photo -file "$iconpath/document-new.gif"]
set plugin_img_edit [image create photo \
	-file "$iconpath/document-properties.gif"]
set plugin_img_save [image create photo -file "$iconpath/document-save.gif"]
set plugin_img_open [image create photo -file "$iconpath/fileopen.gif"]
set plugin_img_del  [image create photo -file "$iconpath/edit-delete.gif"]
set plugin_img_conn [image create photo -file "$iconpath/stock_connect.gif"]
set plugin_img_disc [image create photo -file "$iconpath/stock_disconnect.gif"]
set plugin_img_refr [image create photo -file "$iconpath/view-refresh.gif"]
set plugin_img_folder [image create photo -file "$iconpath/folder.gif"]
}

array set g_plugin_button_tooltips {
	add "add a new plugin"
	edit "edit the selected plugin" 
	del "remove the selected plugin"
	conn "connect to this plugin"
	disc "disconnect from this plugin"
	refr "refresh plugin data"
}

###############################################################################
#                    Plugins and Capabilities GUI functions                   #
###############################################################################

#
# Configure remote plugins. Popup a dialog box for editing the remote plugin
# list; results are stored in plugins.conf file.
#
proc popupPluginsConfig {} {
    global g_plugins g_plugin_types g_plugin_button_tooltips
    set wi .pluginConfig
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 0 1
    wm title $wi "CORE Plugins"

    # list of plugins
    labelframe $wi.s -borderwidth 0 -text "Plugins"
    listbox $wi.s.plugins -selectmode single -height 5 -width 50 \
	-yscrollcommand "$wi.s.plugins_scroll set" -exportselection 0
    scrollbar $wi.s.plugins_scroll -command "$wi.s.plugins yview" 
    pack $wi.s.plugins $wi.s.plugins_scroll -fill y -side left
    pack $wi.s -padx 4 -pady 4 -fill both -side top -expand true


    # image button bar
    frame $wi.bbar
    set buttons "add edit del conn refr"
    foreach b $buttons {
	global plugin_img_$b
	button $wi.bbar.$b -image [set plugin_img_$b]
        pack $wi.bbar.$b -side left
        balloon $wi.bbar.$b $g_plugin_button_tooltips($b)
    }
    pack $wi.bbar -padx 4 -pady 4 -fill x -side top
    $wi.bbar.add  configure -command "popupPluginsConfigEdit $wi new"
    $wi.bbar.edit configure -command "popupPluginsConfigEdit $wi edit"
    $wi.bbar.del  configure -command "pluginsConfigDelete $wi"
    $wi.bbar.conn configure -command "pluginsConfigConnect $wi"
    $wi.bbar.refr configure -command "pluginsConfigRefresh $wi"

    # plugin information
    labelframe $wi.si -borderwidth 0 -text "Plugin information"
    entry $wi.si.info -width 50
    pack $wi.si.info -fill x -side left
    pack $wi.si -padx 4 -pady 4 -fill x -side top

    # capabilities
    labelframe $wi.cap -borderwidth 0 -text "Capabilities"
    listbox $wi.cap.caps -selectmode single -height 5 -width 50 \
	-yscrollcommand "$wi.cap.caps_scroll set" -exportselection 0
    scrollbar $wi.cap.caps_scroll -command "$wi.cap.caps yview"
    pack $wi.cap.caps $wi.cap.caps_scroll -fill y -side left
    pack $wi.cap -padx 4 -pady 4 -fill both -side top -expand true

    # populate the list
    pluginsConfigRefreshList $wi
    bind $wi.s.plugins <<ListboxSelect>> "pluginsConfigSelect $wi"
    pluginsConfigSelect $wi

    # close button 
    frame $wi.b -borderwidth 0
    button $wi.b.save -text "Save" -command "writePluginsConf; destroy $wi"
    button $wi.b.cancel -text "Cancel" -command "destroy $wi"
    pack $wi.b.cancel $wi.b.save -side right
    pack $wi.b -side bottom

    # uncomment to make modal
#    after 100 {	catch { grab .pluginConfig } }
}

#
# Helper for pluginConfig when new/edit buttons are pressed.
#
proc popupPluginsConfigEdit { parent action } {
    global g_plugins g_plugin_types plugin_config_type plugin_config_autoconn

    set wi .pluginConfig.popup
    catch {destroy $wi}
    toplevel $wi

    wm transient $wi .pluginConfig
    wm resizable $wi 0 0
    if { $action == "new" } {
	set title "Add"
	set selected_idx -1
	set selected_name -1
    } else {
	set title "Edit"
	set selected_idx [$parent.s.plugins curselection]
	if { $selected_idx == "" } { destroy $wi; return }
	set selected_name [$parent.s.plugins get $selected_idx]
	set plugin_data $g_plugins("$selected_name")
    }
    # default values
    set plugin_config_type $g_plugin_types(1)
    set plugin_config_autoconn 0

    wm title $wi "$title Plugin"

    # controls for editing entries
    labelframe $wi.c -text "Plugin configuration"

    frame $wi.c.a -borderwidth 4
    label $wi.c.a.namelab -text "Name"
    entry $wi.c.a.name -bg white -width 35
    pack $wi.c.a.namelab $wi.c.a.name -side left
    pack $wi.c.a -fill x -side top

    frame $wi.c.b -borderwidth 4
    label $wi.c.b.typelab -text "Type"
    set plugin_types_list {}
    foreach type_num [lsort -dictionary [array names g_plugin_types]] {
	lappend plugin_types_list "$g_plugin_types($type_num)"
    }
    eval tk_optionMenu $wi.c.b.type plugin_config_type $plugin_types_list
    label $wi.c.b.iplab -text "IP"
    entry $wi.c.b.ip -bg white -width 15
    label $wi.c.b.portlab -text "port"
    entry $wi.c.b.port -bg white -width 10
    pack $wi.c.b.typelab $wi.c.b.type -side left
    pack $wi.c.b.iplab $wi.c.b.ip -side left
    pack $wi.c.b.portlab $wi.c.b.port -side left
    pack $wi.c.b -fill x -side top

    frame $wi.c.c -borderwidth 4
    checkbutton $wi.c.c.autoconn -variable plugin_config_autoconn -text \
	"Automatically connect to this plugin at startup"
    pack $wi.c.c.autoconn -side left
    pack $wi.c.c -fill x -side top

    pack $wi.c -fill x -side top

    frame $wi.btm
    button $wi.btm.ok -text "OK" \
	-command "popupPluginConfigEditApply $wi $selected_idx \"$selected_name\"; pluginsConfigRefreshList $parent; destroy $wi"
    button $wi.btm.cancel -text "Cancel" -command "destroy $wi"
    pack $wi.btm.cancel $wi.btm.ok -side right
    pack $wi.btm -fill x -side top

    # fill in values for editing
    if { $action != "new" } {
	$wi.c.a.name insert 0 $selected_name
	$wi.c.b.ip insert 0 [lindex $plugin_data 0]
	$wi.c.b.port insert 0 [lindex $plugin_data 1]
	if { [info exists g_plugin_types([lindex $plugin_data 2])] } {
	    set plugin_config_type $g_plugin_types([lindex $plugin_data 2])
	}
	set plugin_config_autoconn [lindex $plugin_data 3]
    }
}

#
# Helper for .pluginConfig.popup dialog when apply button is pressed.
# selected_idx = -1 indicates adding a new entry
#
proc popupPluginConfigEditApply { wi selected_idx selected_name } {
    global g_plugins g_plugin_types plugin_config_type plugin_config_autoconn
   
    # get values from the dialog 
    set name "\"[string trim [$wi.c.a.name get]]\""
    set ip   [string trim [$wi.c.b.ip get]]
    set port [string trim [$wi.c.b.port get]]
    set type $plugin_config_type
    set typenum -1
    foreach t [array names g_plugin_types] {
	if { $g_plugin_types($t) == "$type" } { set typenum $t; break; }
    }
    if { $typenum == -1 } { set typenum 1 }
    set status 0
    set cap ""
    set sock -1
    set ac $plugin_config_autoconn

    # replace (replace items 0-3, preserve 4-6)
    if { $selected_idx != -1 } {
	if { ![info exists g_plugins("$selected_name")] } { return }
	set plugin_data $g_plugins("$selected_name")
	set status [lindex $plugin_data 4]
	set cap    [lindex $plugin_data 5]
	set sock   [lindex $plugin_data 6]
	if { $name != $selected_name } { ;# name change
	    array unset g_plugins "\"$selected_name\""
	}
    }
  
    # manipulate the g_plugins array 
    set plugin_data [list $ip $port $typenum $ac $status $cap $sock]
    array set g_plugins [list $name $plugin_data]
}

#
# Helper to refresh the list of plugins. Called from various places.
#
proc pluginsConfigRefreshList { wi } {
    global g_plugins

    set selected_idx [$wi.s.plugins curselection]

    $wi.s.plugins delete 0 end
    foreach plugin [lsort -dictionary [array names g_plugins]] {
	$wi.s.plugins insert end [string trim $plugin \"]
    }
    if { $selected_idx != "" } {
	$wi.s.plugins selection set $selected_idx
	pluginsConfigSelect $wi
    }
}

#
# Helper to populate the plugin info and capabilities frame.
#
proc pluginsConfigRefreshInfo { wi plugin_data } {
    global g_plugin_types g_plugin_status_types
    set ip   [lindex $plugin_data 0]
    set port [lindex $plugin_data 1]
    set tnum [lindex $plugin_data 2]
    set ac   [lindex $plugin_data 3]
    set snum [lindex $plugin_data 4]
    set caps [lindex $plugin_data 5]
    set sock [lindex $plugin_data 6]

    set type $g_plugin_types($tnum)
    set stat $g_plugin_status_types($snum)

    # plugin information text
    set txt "($type)://$ip:$port  status=$stat"
    $wi.si.info delete 0 end
    $wi.si.info insert 0 $txt

    # update the connect/disconnect button
    set c "conn"
    if { $snum == 1 } { set c "disc" }
    global plugin_img_$c
    $wi.bbar.conn configure -image [set plugin_img_$c]

    # capabilities list
    $wi.cap.caps delete 0 end
    foreach cap $caps {
	addPluginCapToListbox $wi.cap.caps $cap end
    }
}

#
# Helper for adding a capability to the given listbox control.
#
proc addPluginCapToListbox { listb cap idx } {
    global regtxttypes

    set cap [split $cap =]
    set captype [lindex $cap 0]
    set capname [lindex $cap 1]
    if { ![info exists regtxttypes($captype)] } {
	set txt "Unknown($captype)"
    } else {
	set txt $regtxttypes($captype)
    }
    $listb insert $idx "$txt - $capname"
}

#
# Helper for pluginConfig dialog when plugin list items are selected.
#
proc pluginsConfigSelect { wi } {
    global g_plugins g_plugin_types g_plugin_status_types regtxttypes
    # initialize the default state
    set buttons "edit del conn refr"
    set buttons_state disabled
    set name ""

    if { ![winfo exists $wi.s.plugins] } { return }

    set selected_idx [$wi.s.plugins curselection]
    if { $selected_idx != "" } {
	set buttons_state normal
	set name "\"[$wi.s.plugins get $selected_idx]\""
    }
    
    # enable or disable the editing/control buttons
    if { $name == "\"GUI\"" } {
        # this program is the GUI, you cannot change this connection
	set buttons_state disabled
	global plugin_img_disc
	$wi.bbar.conn configure -image $plugin_img_disc
    }
    foreach b $buttons { $wi.bbar.$b configure -state $buttons_state }

    # fill in plugin info frame
    if { [info exists g_plugins($name)] } {
	set plugin_data $g_plugins($name)
	pluginsConfigRefreshInfo $wi $plugin_data
    }
}

#
# Helper for pluginConfig dialog when delete button is pressed.
#
proc pluginsConfigDelete { wi } {
    global g_plugins

    set selected_idx [$wi.s.plugins curselection]
    if { $selected_idx == "" } { return }
    set name "\"[$wi.s.plugins get $selected_idx]\""

    set title "Delete CORE plugin"
    set msg "Are you sure you want to delete the plugin $name?"
    set choice [tk_messageBox -type yesno -default no -icon warning \
				-title $title -message $msg]
    if { $choice == "yes" } {
	array unset g_plugins $name
	pluginsConfigRefreshList $wi
    }
}

#
# Helper for pluginConfig dialog when connect button is pressed.
#
proc pluginsConfigConnect { wi } {
    global g_plugins g_plugin_types

    set selected_idx [$wi.s.plugins curselection]
    if { $selected_idx == "" } { return }
    set name "\"[$wi.s.plugins get $selected_idx]\""
    pluginConnect $name toggle true
}

#
# Helper for pluginConfig dialog when refresh button is pressed.
#
proc pluginsConfigRefresh { wi } {
    set selected_idx [$wi.s.plugins curselection]
    if { $selected_idx == "" } { return }
    set name "\"[$wi.s.plugins get $selected_idx]\""
    pluginRefresh $name
}

#
# Helper called from api.tcl when register message is parsed.
#
proc pluginsConfigRefreshCallback { } {
    global execMode
    if { $execMode != "interactive"} { return } ; # batch mode

    # callback if CORE Plugins window is open, refresh it...
    if { [winfo exists .pluginConfig] } {
	pluginsConfigRefreshList .pluginConfig
    }
    # callback if CORE WLAN window is open, refresh it...
    if { [winfo exists .pluginCapConfig] } {
	pluginsCapConfigRefreshList .pluginCapConfig
    }
}

#
# Dialog to assign capabilities from plugin to WLAN.
#
proc popupPluginsCapConfig { wlan parent } {
    global g_plugins CORE_DATA_DIR g_cap_in_use

    set wi .pluginCapConfig
    catch {destroy $wi}
    toplevel $wi
    wm transient $parent . 
    wm title $wi "Available Plugins"

    # update dialog
    if { [winfo exists $parent.mod.plugins.coreapi] } {
	global mobmodel
	set mobmodel "coreapi"
    }

    # active plugins
    set name [getNodeName $wlan]
    labelframe $wi.active -text "Active capabilities for $name" -borderwidth 0
    listbox $wi.active.plugins -selectmode single -width 55 -height 5 \
	-yscrollcommand "$wi.active.scroll set" -exportselection 0
    scrollbar $wi.active.scroll -command "$wi.active.plugins yview"
    pack $wi.active.plugins -fill both -side left 
    pack $wi.active.scroll -fill y -side left
    pack $wi.active -side top -fill both -expand true -padx 4 -pady 4

    # buttons
    frame $wi.mid
    foreach b {up down} {
	set fn "$CORE_DATA_DIR/icons/tiny/arrow.${b}.gif"
	set img$b [image create photo -file $fn]
	if { $b == "up" } { set endis "Enable" } else { set endis "Disable" }
	button $wi.mid.$b -image [set img${b}] \
		-text "$endis" -compound left \
		-command "popupPluginsCapConfigHelper $wi $b $wlan"
	pack $wi.mid.$b -side left -pady 2 -fill y
    }
    button $wi.mid.conf -text "Configure..." \
	-command "popupPluginsCapConfigHelper $wi config $wlan"
    button $wi.mid.plugins -text "Manage plugins..." \
	-command "popupPluginsConfig; after 100 { catch {grab .pluginConfig } }"
    pack $wi.mid.conf $wi.mid.plugins -side left -pady 2
    pack $wi.mid -side top -fill x -expand true -padx 4 -pady 4

    # available plugins
    labelframe $wi.avail -text "Available capabilities" -borderwidth 0
    listbox $wi.avail.plugins -selectmode single -width 55 -height 5 \
	-yscrollcommand "$wi.avail.scroll set" -exportselection 0
    scrollbar $wi.avail.scroll -command "$wi.avail.plugins yview"
    pack $wi.avail.plugins -fill both -side left 
    pack $wi.avail.scroll -fill y -side left
    pack $wi.avail -side top -fill both -expand true -padx 4 -pady 4

    bind $wi.active.plugins <Double-Button-1> \
    	"popupPluginsCapConfigHelper $wi down $wlan"
    bind $wi.avail.plugins <Double-Button-1> \
    	"popupPluginsCapConfigHelper $wi up $wlan"

    # this reads from the existing wlan config
    if { $g_cap_in_use == "" } { 
	set g_cap_in_use [getCapabilities $wlan "mobmodel"]
    }

    # populate the plugins list
    pluginsCapConfigRefreshList $wi
    $wi.active.plugins selection set 0

    # OK button
    set cancel_cmd "destroy $wi"
    frame $wi.btn
    button $wi.btn.cancel -text "OK" -command $cancel_cmd
    pack $wi.btn.cancel -side left -padx 4 -pady 4
    pack $wi.btn -side bottom
    bind $wi <Key-Return> $cancel_cmd
    bind $wi <Key-Escape> $cancel_cmd

    # grab the window due to interactions with node configuration dialog
    after 100 {
	grab .pluginCapConfig
	raise .pluginCapConfig
    }
}

#
# Up/down/configure buttons helper.
#
proc popupPluginsCapConfigHelper { wi cmd wlan} {
    global g_cap_in_use g_cap_in_use_set

    if { $cmd == "up" } {
	set l $wi.avail.plugins
	set l2 $wi.active.plugins
    } else {
	set l $wi.active.plugins
	set l2 $wi.avail.plugins
    }
    set selected_idx [$l curselection]
    if { $selected_idx == "" } { return } ;# nothing was selected

    if { $cmd == "config" } { ;# configure button pressed
	set capstr [$l get $selected_idx]
	set cap [string trim [lindex [split $capstr -] 1]]
	if { $cap == "" } { return } ;# error
	set plch [pluginChannelByCap $cap]
	set plugin [lindex $plch 0]
	set channel [lindex $plch 1]
	set flags 0x1 ;# request - a response to this message is requested
	set netid -1 ;# no netid because node not necessarily instantiated
	set opaque "" ;# unused
	set channel [pluginConnect $plugin connect 1]
	if { $cap == "location" } {
	    # hack to map location capabilities with canvas size/scale dialog
	    resizeCanvasPopup 
	    return
	}
	if { $channel != -1 && $channel != "" } {
	    sendConfRequestMessage $channel $wlan $cap $flags $netid $opaque 
	}
	return
    } else { ;# up/down enable/disable button preseed
	set capstr [$l get $selected_idx]
	$l delete $selected_idx $selected_idx
	$l2 insert end $capstr
	$l2 selection set end 
	# put the capabilities from the active list into the g_cap_in_use list
	#  this list will be read in wlanConfigDialogHelper when Apply pressed
	set g_cap_in_use {}
	set g_cap_in_use_set 1
	foreach capstr [$wi.active.plugins get 0 end] {
	    set cap [string trim [lindex [split $capstr -] 1]]
	    lappend g_cap_in_use $cap	
	}
    }
}

#
# Send a configure message to request a capabilities configuration parameters.
#
proc configCap { node models } {
    set plch [pluginChannelByCap [lindex $models 0]]
    set plugin [lindex $plch 0]
    set channel [lindex $plch 1]
    set flags 0x1 ;# request - a response to this message is requested
    set netid -1 ;# no netid because node not necessarily instantiated
    set opaque "" ;# unused
    set channel [pluginConnect $plugin connect 1]
    if { $channel != -1 && $channel != "" } {
	sendConfRequestMessage $channel $node $models $flags $netid $opaque 
    }
}

#
# Refresh the capabilities in-use and available listboxes.
#
proc pluginsCapConfigRefreshList { wi } {
    # global list of capabilities in use for the current config dialog
    # (this is global because parseRegMessage does not know which WLAN is being
    #  configured)
    global g_cap_in_use

    # clear the listboxes
    $wi.avail.plugins delete 0 end
    $wi.active.plugins delete 0 end

    # refresh the listboxes
    set caplist [getPluginsCapList]
    foreach cap $caplist {
	set captype [lindex [split $cap =] 0]
	set capname [lindex [split $cap =] 1]
	# skip CORE daemons
	if { [lsearch -exact "openvz core-daemon" $capname] != -1 } { continue }
	# skip gui, exec, util capabilities
	if { [lsearch -exact "gui exec util" $captype] != -1 } { continue }
	# add capability to active or available lists
	if { [lsearch -exact $g_cap_in_use $capname] < 0 } {
	    addPluginCapToListbox $wi.avail.plugins $cap end
	} else {
	    addPluginCapToListbox $wi.active.plugins $cap end
	}
    }
}

#
# Helper to convert a capability name to a text title,
# e.g. emane_rfpipe -> rfpipe
#
proc capTitle { cap } {
    if { [string range $cap 0 5] == "emane_" } {
	return [string range $cap 6 end]
    }
    return $cap
}

#
# Popup a capability configuration dialog box.
# This is used for these dynamic dialogs:
#  Session options
#  EMANE options
#  EMANE model options, per-WLAN/per-interface
#  node profile (Xen machine type)
#
proc popupCapabilityConfig { channel wlan model types values captions bmp possible_values groups } {
    global node_list g_node_type_services_hint g_popupcap_keys g_prefs
    set wi .popupCapabilityConfig
    catch {destroy $wi}
    toplevel $wi
    set modelname [capTitle $model]
    wm transient $wi . 
    wm title $wi "$modelname configuration"

    array unset g_popupcap_keys ;# hint for supporting key=value w/apply button

    set titletxt "$modelname"
    set customcfg ""
    if { [lsearch $node_list $wlan] != -1 } {
	set titletxt "node $wlan $titletxt"
	# check for existing saved parameters in custom-config
	set customcfg [getCapabilityConfig $wlan $model]
    } else {
	set titletxt "$titletxt parameters"
    }
    ttk::label $wi.top -text "$titletxt"
    pack $wi.top -side top -padx 4 -pady 4
    if { $model == "emane" } {
	# EMANE global config uses node None, but is saved with minEmaneNode
	set wlan [minEmaneNode]
	if { $wlan == "" } {
	    # WLAN configure dialog but "Apply" hasn't been pressed yet
	    # so there is no EMANE node in node_list
	    if { [winfo exists .popup.butt.apply] } {
		# grab the currently configured WLAN ID
		set wlan [lindex [.popup.butt.apply cget -command] 3]
	    }
	}
	if { $wlan != "" } {
	    set customcfg [getCapabilityConfig $wlan $model]
	} else {
	    puts "*** Error: emane config with no EMANE nodes!"
	}
    }

    if { $customcfg != "" } {
	set cfg [lindex [lindex $customcfg 2] 1]
    } else { 
	set cfg ""
    }
    # session options stored in array, not custom-config
    if { $model == "session" } { set cfg [getSessionOptionsList] }


    ttk::notebook $wi.vals
    pack $wi.vals -fill both -expand true -padx 4 -pady 4
    ttk::notebook::enableTraversal $wi.vals

    set n 0
    set gn 0
    set lastgn -1
    foreach type $types {
	set kv [splitKeyValue [lindex $values $n]]
	set key [lindex $kv 0]
	set value [lindex $kv 1]

	if { $cfg != "" } { ;# possibly use existing config value
	    if { $key == "" } { ;# support old "value" format 
	        set value [lindex $cfg $n]
	    } else {
		set value [getKeyValue $key $cfg $value]
	    }
	}
	array set g_popupcap_keys [list $n $key] ;# remember key for apply

	if {$type == 1 || $type == 5} {set w 4}
	if {$type == 2 || $type == 6} {set w 8}
	if {$type == 3 || $type == 7 || $type == 9} {set w 8}
	if {$type == 4 || $type == 8 || $type == 10} {set w 16}

	# group values into frames based on groups TLV
	set groupinfo [popupCapabilityConfigGroup $groups [expr {$n + 1}]]
	set gn [lindex $groupinfo 0]
	set groupcaption [lindex $groupinfo 1]
	if { $lastgn != $gn } {
	    ttk::frame $wi.vals.$gn 
	    $wi.vals add $wi.vals.$gn -text $groupcaption -underline 0
	    set lastgn $gn
	}
	set fr $wi.vals.$gn.item$n
	ttk::frame $fr
	if {$type == 11} { ;# boolean value
	    global $fr.entval $fr.entvalhint
	    set optcmd [list tk_optionMenu $fr.ent \
	                $fr.entval]
	    if { [lindex $possible_values $n] != "" } {
		set possible [lindex $possible_values $n]
		set opts [split $possible ,]
	    } else {
		set opts [list True False]
	    }
	    set optcmd "$optcmd $opts"
	    eval $optcmd
	    set $fr.entval [lindex $opts 0]
	    # store the first value so we know how to interpret the option menu
	    # value later as 0 or 1 instead of the text labels
	    set $fr.entvalhint [lindex $opts 0]
	    if { $value == "0" } {
		set $fr.entval [lindex $opts 1]
	    }
	} else {
	    # dropdown control
	    if { [lindex $possible_values $n] != "" } {
	        global $fr.entval
	        set optcmd [list tk_optionMenu $fr.ent \
	                    $fr.entval]
		set possible [lindex $possible_values $n]
		set opts [split $possible ,]
		set optcmd [concat $optcmd $opts]
	        eval $optcmd
	        set $fr.entval [lindex $opts 0]
		for { set i 0 } { $i < [llength $opts] } { incr i } {
		    set opt [lindex $opts $i]
		    set optval [lindex [split $opt] 0]
		    if { $value == $optval } {
	        	set $fr.entval $opt
			break
		    }
		}
	    # plain old text entry
	    } else {
                ttk::entry $fr.ent -width $w -justify right
	        $fr.ent insert 0 $value
	    }
        }
	ttk::label $fr.lab -text "[lindex $captions $n]"
	# file browse button "..."
	if { [winfo class $fr.ent] == "TEntry" && \
	     [string first "file" "[lindex $captions $n]"] > -1 } {
	    ttk::button $fr.browse -width 5 -text "..." \
		-command "fileButtonPopup $fr.ent $g_prefs(default_conf_path)"
	    pack $fr.browse $fr.ent $fr.lab -side right -padx 4 -pady 4
	} else {
	    pack $fr.ent $fr.lab -side right -padx 4 -pady 4
	}
	pack $fr -side top -anchor e
	incr n
    }; # end foreach

    if { $bmp != "" && [file exists $bmp] } {
	if { [string range $bmp end-2 end] == "gif" } {
	    set bitmap [image create photo -file $bmp]
	} else {
	    set bitmap [image create bitmap -file $bmp]
	}
	ttk::label $wi.bitmap -image $bitmap
	pack $wi.bitmap -side top -padx 4 -pady 4
    } elseif { $bmp != "" } {
	puts "bitmap not found: $bmp"
    }

    # TODO: any captions beyond count

    # Apply / Cancel buttons
    set apply_cmd \
       "popupCapabilityConfigApply $wi $channel $wlan $model {$types} {$groups}"
    set cancel_cmd "destroy $wi"
    ttk::frame $wi.btn
    ttk::button $wi.btn.apply -text "Apply" -command $apply_cmd
    ttk::button $wi.btn.cancel -text "Cancel" -command $cancel_cmd
    pack $wi.btn.apply $wi.btn.cancel -side left -padx 4 -pady 4
    pack $wi.btn -side bottom
    bind $wi <Key-Return> $apply_cmd
    bind $wi <Key-Escape> $cancel_cmd

    after 100 {
	grab .popupCapabilityConfig
	raise .popupCapabilityConfig
    }
}

# Helper to retrieve the group number and caption for the current item based
# on the list from the groups TLV.
#
proc popupCapabilityConfigGroup { groups n } {
    set num 0
    set caption ""
    # groups are in the form caption:a-b
    # the caption is optional
    foreach group $groups {
	set i [string first ":" $group]
	# here it is possible that i = -1, and caption will become ""
	set caption [string range $group 0 $i]
	if { [string index $caption end] == ":" } {
	    # remove the ":" character
	    set caption [string replace $caption end end]
	}
	incr i
	set groupitems [split [string range $group $i end] -]
	set a [lindex $groupitems 0]
	set b [lindex $groupitems 1]
	# check if the current item belongs to this group
	if { $n >= $a && $n <= $b } {
	    return [list $num $caption]
	}
	incr num
    }
    return [list $num $caption]
}

# apply button for Wireless model configuration dialog
proc popupCapabilityConfigApply { wi channel wlan model types groups } {
    global node_list MACHINE_TYPES g_popupcap_keys

    set n 0
    set vals {}
    foreach type $types {
	set groupinfo [popupCapabilityConfigGroup $groups [expr {$n + 1}]]
	set gn [lindex $groupinfo 0]
	if { ![winfo exists $wi.vals.$gn.item$n.ent] } {
	    puts "warning: missing dialog value $n for $model"
	    continue
	}
	if { [catch { set val [$wi.vals.$gn.item$n.ent get] }] } {
	    if { $type == 11 } {
		# convert textual value from tk_optionMenu to boolean 0/1
		# using hint
	        global $wi.vals.$gn.item$n.entval $wi.vals.$gn.item$n.entvalhint
		if { [set $wi.vals.$gn.item$n.entval] == \
		     [set $wi.vals.$gn.item$n.entvalhint] } {
		    set val 1 ;# true
		} else {
		    set val 0 ;# false
		}
	    } else {
		# convert textual dropdown value to numeric using first word
		# e.g. "0 11 Mbps" has a value of 0
		global $wi.vals.$gn.item$n.entval
		set selectedopt [set $wi.vals.$gn.item$n.entval]
		set val [lindex $selectedopt 0]
	    }
	}
	if { $g_popupcap_keys($n) != "" } {
	    set val [join [list $g_popupcap_keys($n) $val] =] ;# key=value
	}
	lappend vals $val
    	incr n
    }

    set opaque ""
    # node doesn't exist, we are changing the node type or session options
    if { [lsearch $node_list $wlan] == -1 } {
	if { [lsearch -exact $MACHINE_TYPES $model] != -1 } {
	    set opaque [popupNodeProfileConfigApply $vals]
	} elseif { $model == "session" } {
	    setSessionOptions $types $vals
	} elseif { $model == "emane" } {
	    set minemane [minEmaneNode]
	    setCustomConfig $minemane $model $types $vals 0
	}
    # overload the use of custom-config: store each external model config here
    } else {
	setCustomConfig $wlan $model $types $vals 0
    }

    destroy $wi
    sendConfReplyMessage $channel $wlan $model $types $vals $opaque
}

#
# Popup a session configuration dialog box.
#
proc popupSessionConfig { channel sessionids sessionnames sessionfiles nodecounts sessiondates thumbs opaque } {
    catch { package require Img }
    global g_current_session node_list currentFile
    global plugin_img_add plugin_img_del plugin_img_open

    set wi .popupSessionConfig
    catch {destroy $wi}
    toplevel $wi
    wm transient $wi . 
    wm title $wi "CORE Sessions"

    ttk::frame $wi.top
    set txt "Below is a list of active CORE sessions."
    set txt "$txt Double-click to connect to an existing session."
    set txt "$txt Usually, only sessions in the RUNTIME state persist in the"
    set txt "$txt daemon, except for the one you may be currently editing."
    ttk::label $wi.msg -wraplength 4i -justify left -anchor n \
	-padding {10 2 20 6} -text $txt
    #pack $wi.msg -fill x
    canvas $wi.preview -background white -relief sunken -bd 2 \
	-width 100 -height 100
    pack $wi.top -fill both -expand 1
    grid $wi.msg $wi.preview -in $wi.top -padx 4 -pady 4

    # tree view -- list of sessions
    set cols {sid name nc fn dt}
    ttk::frame $wi.container
    # TODO: allow multiple selections (-selectmode extended) for shutting down
    #       multiple sessions
    ttk::treeview $wi.tree -columns $cols -show headings \
	-selectmode browse -height 5 \
	-yscroll "$wi.vsb set" -xscroll "$wi.hsb set"
    ttk::scrollbar $wi.vsb -orient vertical -command "$wi.tree yview"
    ttk::scrollbar $wi.hsb -orient horizontal -command "$wi.tree xview"
    pack $wi.container -fill both -expand 1
    grid $wi.tree $wi.vsb -in $wi.container -sticky nsew
    grid $wi.hsb -in $wi.container -sticky nsew
    grid column $wi.container 0 -weight 1
    grid row $wi.container 0 -weight 1

    array set thumbnails {}
    # populate headers
    set font [ttk::style lookup [$wi.tree cget -style] -font]
    foreach col $cols name {ID Name {Node Count} Filename Date} {
	$wi.tree heading $col -text $name
	$wi.tree column $col -width [font measure $font $name]
    }
    # populate tree items
    foreach sid $sessionids name $sessionnames fn $sessionfiles nc $nodecounts dt $sessiondates th $thumbs {
	if {$sid == $g_current_session} {
	    set nc [llength $node_list]
	    set fn [file tail $currentFile]
	    set dt "(current session)"
	}
	array set thumbnails [list $sid $th]
	$wi.tree insert {} end -values [list $sid $name $nc $fn $dt] \
		-tags "sess"
	foreach col {sid name nc fn dt} {
	    set len [font measure $font "[set $col]  "]
	    if { [$wi.tree column $col -width] < $len } {
		$wi.tree column $col -width $len
	    }
	}
    }

    # buttons - new connect shutdown cancel
    set close_cmd "destroy $wi"
    set conn_cmd "sessionConfig connect $wi $channel; $close_cmd"
    set shut_cmd "sessionConfig shutdown $wi $channel; $close_cmd"
    set new_cmd  "sessionConfig new $wi $channel; $close_cmd"

    ttk::frame $wi.btn
    ttk::separator $wi.btn.sep
    grid $wi.btn.sep -columnspan 4 -row 0 -sticky ew -pady 2
    ttk::button $wi.btn.cancel -text "Cancel" -command $close_cmd
    ttk::button $wi.btn.shut -text "Shutdown" -image $plugin_img_del \
	-compound left -command $shut_cmd
    ttk::button $wi.btn.conn -text "Connect" -image $plugin_img_open \
	-compound left -command $conn_cmd
    ttk::button $wi.btn.new -text "New" -image $plugin_img_add \
	-compound left -command $new_cmd
    grid $wi.btn.new $wi.btn.conn $wi.btn.shut $wi.btn.cancel -padx 4 -pady 4
    grid columnconfigure $wi 0 -weight 1
    pack $wi.btn -side bottom -fill x
    
    bind $wi <Key-Return> $conn_cmd
    bind $wi <Key-Escape> $close_cmd
    bind $wi.tree <<TreeviewSelect>> "sessionConfigSelect $wi {$thumbs}"
    bind $wi.tree <Double-1> "$conn_cmd; break"
}

# update the preview thumbnail when a session has been clicked
proc sessionConfigSelect { wi thumbs } {
    set item [$wi.tree selection]
    set i [$wi.tree index $item]
    set thumb [lindex $thumbs $i]
    set thumbimg [image create photo -file $thumb]
    set w [image width $thumbimg]; set h [image height $thumbimg]
    $wi.preview delete -withtags "thumbnail"
    $wi.preview create image [expr $w / 2] [expr $h / 2] -image $thumbimg \
	-tags "thumbnail"
}

# send Session API message to connect or shutdown a session
proc sessionConfig { cmd wi channel } {
    global g_current_session

    # sid = 0 is new session, or the session number of an existing session
    set sid 0
    set fn ""
    foreach item [$wi.tree selection] {
	array set vals [$wi.tree set $item]
	set sid $vals(sid)
	set fn $vals(fn)
	break; # TODO: loop on multiple selection for shutdown
    }
    if { $sid == $g_current_session } {
	return
    }
    if { $cmd == "new" } {
	set cmd "connect"
	set sid 0
    }
    connectShutdownSession $cmd $channel $sid $fn
}

# switch sessions or shutdown the specified session
# sid=0 indicates switching to a new session (disconnect from old and start a
# new file)
proc connectShutdownSession { cmd channel sid fn } {
    global g_current_session CORE_USER currentFile

    switch -exact -- $cmd {
	connect {
	    newFile
	    # start a new session and return
	    if { $sid == 0 } {
		return
	    } else {
		set g_current_session $sid
	    }
	    # connect to an existing session
	    set currentFile $fn
	    setOperMode exec connect
	    set flags 0x11 ;# add flag, status req flag
	}
	shutdown {
	    if { $sid == 0 } { return }
	    set flags 0x2 ;# delete flag
	}
    }

    set name ""
    set f ""
    set nodecount ""
    set thumb ""
    set user $CORE_USER
    sendSessionMessage $channel $flags $sid $name $f $nodecount $thumb $user
}

proc requestSessions {} {
    global g_session_dialog_hint
    set channel [lindex [getEmulPlugin "*"] 2]
    set flags 0x10 ;# status request flag
    set sid "0"
    set name ""
    set f ""
    set nodecount ""
    set thumb ""
    set user ""
    set g_session_dialog_hint 1 ;# show session dialog upon response
    sendSessionMessage $channel $flags $sid $name $f $nodecount $thumb $user
}

###############################################################################
#                  Plugins and Capabilities helper functions                  #
###############################################################################

#
# Given a channel, return the plugin associated with it.
#
proc pluginByChannel { sock } {
    global g_plugins
    foreach plugin [array names g_plugins] {
	set plugin_data $g_plugins($plugin)
	if { [lindex $plugin_data 6] == $sock } {
	    return $plugin
	}
    }
    return ""
}

#
# Given a capability, return the plugin/socket associated with it.
#
proc pluginChannelByCap { cap } {
    global g_plugins
    foreach plugin [array names g_plugins] {
	set plugin_data $g_plugins($plugin)
	set caps [lindex $plugin_data 5]
	set sock [lindex $plugin_data 6]
	if { [lsearch $caps "*=$cap"] > -1 } {
	    return [list $plugin $sock]
	}
    }
    return "" ;# not found
}

#
# Return a list of all known capabilities from all plugins.
#
proc getPluginsCapList { } {
    global g_plugins
    set r {}

    foreach p_name [lsort -dictionary [array names g_plugins]] {
	set p $g_plugins($p_name)
	set p_caps [lindex $p 5]
	foreach cap $p_caps { lappend r $cap }
    }
    return $r
}

#
# Set the list of capabilities for a plugin.
#
proc setPluginCapList { plugin caps } {
    global g_plugins

    if { ![info exists g_plugins($plugin)] } {
	return -1 ;# unknown plugin
    }
    set plugin_data $g_plugins($plugin)
    set plugin_data [lreplace $plugin_data 5 5 $caps] 
    array set g_plugins [list $plugin $plugin_data]
    return 0
}


#
# Get the configuration for a capability associated with a node.
#
proc getCapabilityConfig { node model } {
    # check for existing saved parameters in custom-config
    set customCfgList [getCustomConfig $node]
    foreach element $customCfgList {
	set cid [lindex [lsearch -inline $element "custom-config-id *"] 1]
	if { $cid == $model } {
	    if { [lindex $element 0] == {} } {;# remove empty first elemnt
		set element [lreplace $element 0 0]
	    }
	    return $element
	}
    }
    return ""
}

#
# Return a list of active capabilities for a node.
#
proc getCapabilities { node section } {
    # for wlan, the capabilities are stored in the "mobmodel" section
    set cfg [split [netconfFetchSection $node $section]]
    set r {}
    if { [lindex $cfg 0] == "coreapi" } {
	# list of active capabilities
	set r [join [join [lreplace $cfg 0 0]]]
    }
    return $r
}

#
# Return the first <plugin,capname,sock> that provides emulation capability.
#
proc getEmulPlugin { node } {
    # TODO: in the future, may associate certain nodes with certain plugins
    global g_plugins
    foreach p_name [lsort -dictionary [array names g_plugins]] {
	set p $g_plugins($p_name)
	set p_caps [lindex $p 5]
	set sock [lindex $p 6]
	foreach cap $p_caps {
	    set captype [lindex [split $cap =] 0]
	    set capname [lindex [split $cap =] 1]
	    if { $captype == "emul" } {
		return [list $p_name $capname $sock]
	    }
	}
    }
    return ""
}

#
# Automatically connect to plugins whose auto-connect=1 on startup
#
proc autoConnectPlugins { } {
    global g_plugins
    foreach plugin [lsort -dictionary [array names g_plugins]] {
	set plugin_data $g_plugins($plugin)
	set ac [lindex $plugin_data 3]
	set status [lindex $plugin_data 4]
	if { $ac == 1 && $status == 0 } {
	    set server [lindex $plugin_data 0]
	    set port [lindex $plugin_data 1]
	    pluginConnect $plugin connect 0
	}
    }
}

#
#
# Connect to a plugin using its configured ip/port and set its sock member.
# The cmd parameter can be connect, disconnect, or toggle.
# The retry parameter is passed to openAPIChannel for prompting the user to
# retry the connection. Returns the channel.
#
proc pluginConnect { name cmd retry } {
    global g_plugins
    if { $name == "" } { set name \"core-daemon\" }
    if { ![info exists g_plugins($name)] } { 
	puts "pluginConnect error: $name does not exist!"
	return -1
    }

    set plugin_data $g_plugins($name)
    set ip     [lindex $plugin_data 0]
    set port   [lindex $plugin_data 1]
    set type   [lindex $plugin_data 2]
    set ac     [lindex $plugin_data 3]
    set snum   [lindex $plugin_data 4]
    set cap    [lindex $plugin_data 5]
    set sock   [lindex $plugin_data 6]

    set do_refresh false

    switch -exact -- $type {
    0 { ;# none
	puts "Warning: plugin type 0 '$g_plugin_types(0)' cannot be connected."
    }
    1 { ;# CORE API
	if { $cmd == "toggle" } {
	    if { $snum == 0 } {
		set cmd connect 
	    } elseif { $snum == 1 } {
		set cmd disconnect
	    }
	}
	# connect, disconnect, or do nothing
	if { $cmd == "connect" && $snum != 1} {
	    puts -nonewline "Connecting to $name ($ip:$port)..."
	    flush stdout
	    set sock [openAPIChannel $ip $port $retry]
	    if { "$sock" <= -1 } { return -1 };# user pressed cancel
	    set snum 1 ;# status connected
	    set do_refresh true
	} elseif { $cmd == "disconnect" && $snum == 1 } {
	    if { "$sock" != -1 } {
		catch { flush $sock }
		close $sock
		pluginChannelClosed $sock
		return -1
	    }
	    set snum 0 ;# status disconnected
	} else {
	    return $sock; # do nothing, already (dis)connected
	}
    }
    default {
	puts "Warning: don't know how to connect to plugin type $type."
	return $sock;
    }
    }; # end switch

    # update the g_plugins array
    set plugin_data [list $ip $port $type $ac $snum $cap $sock]
    array set g_plugins [list $name $plugin_data]
    if { $do_refresh } { pluginRefresh $name }
    return $sock
}

#
# Refresh a connected plugin by sending a register message.
#
proc pluginRefresh { plugin } {
    global g_plugins DEFAULT_GUI_REG

    if { ![info exists g_plugins($plugin)] } { return }

    set plugin_data $g_plugins($plugin)
    set type   [lindex $plugin_data 2]
    set status [lindex $plugin_data 4]
    set sock   [lindex $plugin_data 6]

    switch -exact -- $type {
    0 { ;# none
	puts "Warning: plugin type 0 '$g_plugin_types(0)' cannot be refreshed."
    }
    1 { ;# CORE API
	if { "$status" != 1 } {
	    puts -nonewline "Plugin $plugin is disconnected and cannot be "
	    puts "refreshed."
	    return
	}
	sendRegMessage $sock 0 $DEFAULT_GUI_REG
    }
    default {
	if { [info exists g_plugin_type($type)] } {
	    set txt $g_plugin_types($type)
	} else {
	    set txt "unknown"
	}
	puts "Warning: plugin type $type '$txt' cannot be refreshed."
	return
    }
    }; # end switch
}

#
# Update the sock member of a plugin when its channel has been closed.
#
proc pluginChannelClosed { sock } {
    global g_plugins
    set plugin [pluginByChannel $sock] 
    if { $plugin == "" } { return } ;# channel not found
    set plugin_data $g_plugins($plugin)
    set plugin_data [lreplace $plugin_data 6 6 -1]; # sock = -1
    set plugin_data [lreplace $plugin_data 4 4 0]; # status = 0 disconnected
    array set g_plugins [list $plugin $plugin_data]
    set ip [lindex $plugin_data 0]
    set port [lindex $plugin_data 1]
    puts "Connection to $plugin ($ip:$port) closed."
    if { $plugin == "\"core-daemon\"" } {
	global g_current_session
	set g_current_session 0
	setGuiTitle ""
    }
}

#
# Load the plugins.conf file into the g_plugins array
#
proc loadPluginsConf { } {
    global CONFDIR g_plugins g_plugins_default
    set confname "$CONFDIR/plugins.conf"
    if { [catch { set f [open $confname r] } ] } {
	puts "Creating a default $confname"
	unset g_plugins
	array set g_plugins [array get g_plugins_default]
	writePluginsConf
	return
    }

    array unset g_plugins

    while { [ gets $f line ] >= 0 } {
	if { [string range $line 0 0] == "#" } { continue } ;# skip comments
	set l [split $line ,] ;# parse fields separated by commas
	set plugin [lindex $l 0]
	set plugin_data [lindex $l 1]

	# update legacy daemon names - may be removed in the future
	if { $plugin == {"cored.py"} || $plugin == {"cored"} } {
	    set plugin {"core-daemon"}
	}

	if { $plugin == "" } { continue } ;# blank name
	# special entry: GUI (entry for this program) cannot be modified
	if { $plugin == "GUI" || $plugin == {"GUI"} } {
	    set plugin_data $g_plugins_default($plugin)
	} else {
	    set plugin_data [lreplace $plugin_data 4 4 0]; # force status=0
	    set plugin_data [lreplace $plugin_data 6 6 -1]; # force sock=-1
        }
	# load into array of plugins
	if { [catch {array set g_plugins [list $plugin $plugin_data]} e] } {
	    puts "Error reading plugin line '$plugin': $e"
	}
    }
    close $f
}

#
# Write the plugins.conf file from the g_plugins array.
#
proc writePluginsConf { } {
    global CONFDIR g_plugins
    set confname "$CONFDIR/plugins.conf"
    if { [catch { set f [open "$confname" w] } ] } {
	puts "***Warning: could not write plugins file: $confname"
	return
    }

    set header "# plugins.conf: CORE Plugins customization file."
    puts $f $header
    foreach plugin [lsort -dictionary [array names g_plugins]] {
	set plugin_data $g_plugins($plugin)
	set plugin_data [lreplace $plugin_data 4 4 0]; # force status=0
	set plugin_data [lreplace $plugin_data 6 6 -1]; # force sock=-1
	puts $f "$plugin, $plugin_data"
    }
    close $f
}

#
# Perform capability initialization when a plugin capability has been configured
# for a node. This is called during node instantiation.
#
proc pluginCapsInitialize { node config_name } {
    global eid ngnodeidmap

    set active_caps [getCapabilities $node $config_name]
    foreach cap $active_caps {
	set plugin_sock [pluginChannelByCap $cap]
	set plugin [lindex $plugin_sock 0]
	set sock [lindex $plugin_sock 1]
	if { $sock == "" || $sock == -1 } {
	    puts "Warning: plugin $plugin with capability $cap is not connected"
	    continue
	}
	# update any config
	# this updates a custom config that may have been loaded from a file
	set customcfg [getCapabilityConfig $node $cap]
	if { $customcfg != "" } { ;# push existing config
	    set vals [lindex [lindex $customcfg 2] 1]
	    set types [lindex [lindex $customcfg 1] 1]
	    if { [string is digit [lindex $types 0]] } {;# protect against
		# older conf -- remove in the future
		sendConfReplyMessage $sock $node $cap $types $vals ""
	    }
	}
	# update ID mapping
	# this is required to associate a model with a node when the
	# configure button has not been pressed yet (i.e. customcfg == "")
	sendConfRequestMessage $sock $node $cap 0x2 -1 ""

	# for link-layer nodes, find capability config on connected interfaces
	if { [[typemodel $node].layer] == "LINK" } {
	    foreach ifc [ifcList $node] {
		set peer [peerByIfc $node $ifc]
		set ifccfg [getCapabilityConfig $peer $cap]
		if { $ifccfg == "" } { continue }
		set vals [lindex [lindex $ifccfg 2] 1]
		set types [lindex [lindex $ifccfg 1] 1]
		sendConfReplyMessage $sock $peer $cap $types $vals ""
	    }
	    # send global EMANE options if configured for WLANs
	    set emanecfg [getCapabilityConfig $node "emane"]
	    if { $emanecfg != "" } { ;# push existing config
		set vals [lindex [lindex $emanecfg 2] 1]
		set types [lindex [lindex $emanecfg 1] 1]
		sendConfReplyMessage $sock -1 "emane" $types $vals ""
	    }
	}
    } ;# end foreach cap

}

#
# Perform capability de-initialization. This is called during node destruction.
#
proc pluginCapsDeinitialize { node config_name } {
    global eid ngnodeidmap

    set socks {}

    # Get a list of active plugin sockets
    set active_caps [getCapabilities $node $config_name]
    foreach cap $active_caps {
	set plugin_sock [pluginChannelByCap $cap]
	set sock [lindex $plugin_sock 1]
	if { $sock == "" || $sock == -1 } {
	    continue
	}
	if { [lsearch -exact $socks $sock] == -1 } {
	    lappend socks $sock
	}
    }

    # Send config message with reset flag to flush the plugin.
    foreach sock $socks {
	sendConfRequestMessage $sock $node "all" 0x3 -1 ""
    }
}

# empty the session config array when loading a new scenario
proc resetSessionOptions {} {
    global g_session_options
    array unset g_session_options
    array set g_session_options ""
}

# apply button pressed for session config (types is currently unused)
proc setSessionOptions { types vals } {
    global g_session_options
    foreach kv $vals {
	set kvs [splitKeyValue $kv]
	if {[llength $kvs] < 2} {
	    puts "error with session option: $kv"
	    continue
	}
	set key [string trim [lindex $kvs 0]]
	set value [lindex $kvs 1]
        array set g_session_options [list $key $value]
    }
}

# return list of key=value pairs from the session options array
proc getSessionOptionsList {} {
    global g_session_options
    set values ""
    foreach key [lsort [array names g_session_options]] {
	set val [join [list $key $g_session_options($key)] =]
	lappend values $val ;# append key=value
    }
    return $values
}

proc getSessionOption { key defaultval } {
    set opts [getSessionOptionsList]
    return [getKeyValue $key $opts $defaultval]
}

proc setSessionOption { key value notify } {
    global g_session_options
    array set g_session_options [list $key $value]
    if { $notify } { sendSessionOptions -1 }
}

# split value input whether it has 'key=value' format or just 'value'
# return a list of the key (if any) and value.
proc splitKeyValue { keyvalue } {
    set key ""
    set value ""

    set kv [split $keyvalue =]
    if { [llength $kv] > 1 } { ;# "key=value" format
	set key [lindex $kv 0]
	set value [join [lrange $kv 1 end] =]
    } else { ;# "value" format
	set value $keyvalue
    }
    return [list $key $value]
}

# extract a value from cfg matching the given key, or return supplied default
proc getKeyValue { key cfg defaultval } {
    set i [lsearch $cfg "$key=*"]
    if {$i < 0 } { ;# key not present in cfg
	return $defaultval
    } else { ;# key found in cfg
	set kv [splitKeyValue [lindex $cfg $i]]
	return [lindex $kv 1]
    }
}

# returns true if the supplied values list contains "key=value" strings
proc hasKeyValues { values } {
    if { $values == "" } { return false }
    foreach v $values {
	if { [string first = $v 1] < 0 } { ;# look for '=' separator
	    return false
	}
    }
    return true
}

# turn list of "key value key value..." into list of "key=value key=value..."
proc listToKeyValues { keyvalues } {
    set r ""
    set key ""
    foreach item $keyvalues {
	if { $key == "" } {
	    set key $item
	} else {
	    set value $item
	    lappend r "$key=$value"
	    set key ""
	}
    }
    return $r
}

# parse command-line parameters for address/port to connect with
proc checkCommandLineAddressPort {} {
    global argv g_plugins
    set addr ""; set port ""
    set addri [lsearch -regexp $argv "(^\[-\]\[-\]address$|^\[-\]a$)"]
    #set addri [lsearch -exact $argv "--address"]
    if { $addri > -1 } {
	set argv [lreplace $argv $addri $addri]
	set addr [lindex $argv $addri]
	if { ![checkIPv4Addr $addr] } {
	    puts "error: invalid address '$addr'"; exit;
	}
	set argv [lreplace $argv $addri $addri]
    }

    #set porti [lsearch -exact $argv "--port"]
    set porti [lsearch -regexp $argv "(^\[-\]\[-\]port$|^\[-\]p$)"]
    if { $porti > -1 } {
	set argv [lreplace $argv $porti $porti]
	set port [lindex $argv $porti]
	if { $port == "" || ![string is integer $port] || $port > 65535 } {
	    puts "error: invalid port '$port'"; exit;
	}
	set argv [lreplace $argv $porti $porti]
    }
    # update the auto-connect plugin (core-daemon entry)
    if { $addri > -1 || $porti > -1 } {
	set key [lindex [getEmulPlugin "*"] 0]
	set plugin_data $g_plugins($key)
	if { $addri > -1 } { set plugin_data [lreplace $plugin_data 0 0 $addr] }
	if { $porti > -1 } { set plugin_data [lreplace $plugin_data 1 1 $port] }
        array set g_plugins [list $key $plugin_data]
    }
}
