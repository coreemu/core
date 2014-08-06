#
# Copyright 2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author:	Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
# This is a separate "addons" file because it is closely tied to Python
# service definition for the IPsec service.
#

#
# Helper dialog for configuring the IPsec service
#
proc popupServiceConfig_IPsec { parent w node service btn } {
    global plugin_img_add plugin_img_del plugin_img_edit

    set f $w.note.ipsec
    ttk::frame $f
    set h "This IPsec service helper will assist with building an ipsec.sh file"
    set h "$h (located on the Files tab).\nThe IPsec service builds ESP"
    set h "$h tunnels between the specified peers using the racoon IKEv2"
    set h "$h\nkeying daemon. You need to provide keys and the addresses of"
    set h "$h peers, along with the\nsubnets to tunnel."
    ttk::label $f.help -text $h
    pack $f.help -side top -anchor w -padx 4 -pady 4
    $w.note add $f -text "IPsec" -underline 0

    global g_ipsec_key_dir g_ipsec_key_name
    set g_ipsec_key_dir "/etc/core/keys"
    set g_ipsec_key_name "ipsec1"
    ttk::labelframe $f.keys -text "Keys"

    ttk::frame $f.keys.dir
    ttk::label $f.keys.dir.lab -text "Key directory:"
    ttk::entry $f.keys.dir.ent -width 40 -textvariable g_ipsec_key_dir
    ttk::button $f.keys.dir.btn -width 5 -text "..." -command {
        set f .popupServicesCustomize.note.ipsec
	set d [$f.keys.dir.ent get]
	set d [tk_chooseDirectory -initialdir $d -title "Key directory"]
	if { $d != "" } {
	    $f.keys.dir.ent delete 0 end
	    $f.keys.dir.ent insert 0 $d
	}
    }
    pack $f.keys.dir.lab $f.keys.dir.ent $f.keys.dir.btn \
	-side left -padx 4 -pady 4
    pack $f.keys.dir -side top -anchor w

    ttk::frame $f.keys.name
    ttk::label $f.keys.name.lab -text "Key base name:"
    ttk::entry $f.keys.name.ent -width 10 -textvariable g_ipsec_key_name
    pack $f.keys.name.lab $f.keys.name.ent -side left -padx 4 -pady 4
    pack $f.keys.name -side top -anchor w

    set h "The (name).pem x509 certificate and (name).key RSA private key need"
    set h "$h to exist in the\nspecified directory. These can be generated"
    set h "$h using the openssl tool. Also, a ca-cert.pem\nfile should exist"
    set h "$h in the key directory for the CA that issued the certs."
    ttk::label $f.keys.help -text $h
    pack $f.keys.help -side top -anchor w -padx 4 -pady 4

    pack $f.keys -side top -pady 4 -pady 4 -expand true -fill x

    ttk::labelframe $f.t -text "IPsec Tunnel Endpoints"
    set h "(1) Define tunnel endpoints (select peer node using the button"
    set h "$h, then select address from the list)"
    ttk::label $f.t.lab1 -text $h 
    pack $f.t.lab1 -side top -anchor w -padx 4 -pady 4
    ttk::frame $f.t.ep
    ttk::label $f.t.ep.lab1 -text "Local:"
    ttk::combobox $f.t.ep.combo1 -width 12
    pack $f.t.ep.lab1 $f.t.ep.combo1 -side left -padx 4 -pady 4
    populateComboWithIPs $f.t.ep.combo1 $node

    global g_twoNodeSelect g_twoNodeSelectCallback
    set g_twoNodeSelect ""
    set g_twoNodeSelectCallback selectTwoNodeIPsecCallback

    set h "Choose a node by clicking it on the canvas"
    set h "$h or\nby selecting it from the list below."
    ttk::label $f.t.ep.lab2 -text "Peer node:"
    ttk::checkbutton $f.t.ep.node -text " (none) " -variable g_twoNodeSelect \
 	-onvalue "$f.t.ep.node" -style Toolbutton \
	-command "popupSelectNodes {$h} {} selectNodesIPsecCallback"

    ttk::label $f.t.ep.lab3 -text "Peer:"
    ttk::combobox $f.t.ep.combo2 -width 12
    ttk::button $f.t.ep.add -text "Add Endpoint" -image $plugin_img_add \
	-compound left -command "ipsecTreeHelper $f ep"
    pack $f.t.ep.lab2 $f.t.ep.node $f.t.ep.lab3 $f.t.ep.combo2 \
    	$f.t.ep.add -side left -padx 4 -pady 4
    pack $f.t.ep -side top -anchor w

    set h "(2) Select endpoints below and add the subnets to be encrypted" 
    ttk::label $f.t.lab2 -text $h
    pack $f.t.lab2 -side top -anchor w -padx 4 -pady 4

    ttk::frame $f.t.sub
    ttk::label $f.t.sub.lab1 -text "Local subnet:"
    ttk::combobox $f.t.sub.combo1 -width 12
    ttk::label $f.t.sub.lab2 -text "Remote subnet:"
    ttk::combobox $f.t.sub.combo2 -width 12
    ttk::button $f.t.sub.add -text "Add Subnet" -image $plugin_img_add \
	-compound left -command "ipsecTreeHelper $f sub"
    pack $f.t.sub.lab1 $f.t.sub.combo1 $f.t.sub.lab2 $f.t.sub.combo2 \
    	$f.t.sub.add -side left -padx 5 -pady 4
    pack $f.t.sub -side top -anchor w

    global node_list
    set net_list [ipv4SubnetList $node_list]
    $f.t.sub.combo1 configure -values $net_list
    $f.t.sub.combo2 configure -values $net_list
   
    ttk::treeview $f.t.tree -height 5 -selectmode browse -show tree

    pack $f.t.tree -side top -padx 4 -pady 4 -fill both
    pack $f.t -side top -expand true -fill both

    ttk::frame $f.bottom
    ttk::button $f.bottom.del -image $plugin_img_del \
	-command "ipsecTreeHelper $f del"
    ttk::button $f.bottom.gen -text "Generate ipsec.sh" \
	-image $plugin_img_edit -compound left -command "generateIPsecScript $w"
    pack $f.bottom.del $f.bottom.gen -side left -padx 4 -pady 4
    pack $f.bottom -side top
}

#
# Callback invoked when receiving configuration values
# from a Configuration Message; this service helper depends on the ipsec.sh
# file, not the other configuration values.
#
#proc popupServiceConfig_IPsec_vals { node values services w } {
#}

#
# Callback invoked when receiving service file data from a File Message
proc popupServiceConfig_IPsec_file { node name data w } {
    if { $name == "ipsec.sh" } {
	readIPsecScript $w
    }
}

# helper to insert all of a node's IP addresses into a combo
proc populateComboWithIPs { combo node } {
    set ip_list [ipv4List $node 0]
    $combo configure -values $ip_list
    $combo delete 0 end
    $combo insert 0 [lindex $ip_list 0]
}

# called from editor.tcl:button1 when user clicks on a node
# search for IP address and populate
proc selectTwoNodeIPsecCallback {} {
    set w .popupServicesCustomize
    set f $w.note.ipsec
    
    if { ![winfo exists $w] } { return }; # user has closed window
    catch {destroy .nodeselect}

    set node [string trim [$f.t.ep.node cget -text]]
    if { [set node] == "(none)" } { set node "" }

    # populate peer interface combo with list of IPs
    populateComboWithIPs $f.t.ep.combo2 $node
}

# called from popupSelectNodes dialog when a node selection has been made
proc selectNodesIPsecCallback { nodes } {
    global g_twoNodeSelect
    set w .popupServicesCustomize
    set f $w.note.ipsec

    set g_twoNodeSelect ""
    set node [lindex $nodes 0]
    if { $node == "" } {
	$f.t.ep.node configure -text "(none)"
	return
    }
    $f.t.ep.node configure -text " $node "

    # populate peer interface combo with list of IPs
    populateComboWithIPs $f.t.ep.combo2 $node
}

# helper to manipulate tree; cmd is "del", "ep" or "sub"
proc ipsecTreeHelper { f cmd } {

    if { $cmd == "del" } {
	set sel [$f.t.tree selection]
	$f.t.tree delete $sel
	return
    }

    # add endpoint (ep) or subnet (sub)
    set l [string trim [$f.t.$cmd.combo1 get]]
    set p [string trim [$f.t.$cmd.combo2 get]]
    if { $l == "" || $p == "" } {
	if { $cmd == "ep" } {
	    set h "tunnel interface addresses"
	} else {
	    set h "subnet addresses"
	}
	tk_messageBox -type ok -icon warning -message \
	    "You need to select local and peer $h."
	return
    }

    if { $cmd == "ep" } {
        set item [$f.t.tree insert {} end -text "$l <--> $p" -open true]
	$f.t.tree selection set $item
    } elseif { $cmd == "sub" } {
	set parent [$f.t.tree selection]
	if { $parent == "" } {
	    tk_messageBox -type ok -icon warning -message \
	        "You need to first select endpoints, then configure their subnets."
	    return
	}
	if { [$f.t.tree parent $parent] != {} } {
	    set parent [$f.t.tree parent $parent]
	}
	$f.t.tree insert $parent end -text "$l <===> $p"
    }
}

# update an ipsec.sh file that was generated by the IPsec service
proc generateIPsecScript { w } {
    #puts "generateIPsecScript $w..."
    set cfg [$w.note.files.txt get 0.0 end-1c]
    set newcfg ""

    #
    # Gather data for a new config
    #
    set f $w.note.ipsec
    set keydir [$f.keys.dir.ent get]
    set keyname [$f.keys.name.ent get]

    set tunnelhosts ""
    set subnet_list ""
    set ti 0
    set th_items [$f.t.tree children {}]
    foreach th $th_items {
	set ep [$f.t.tree item $th -text]
	set i [string first " " $ep]
	# replace " <--> " with "AND"
	set ep [string replace $ep $i $i+5 "AND"]
	# build a list e.g.:
	#   tunnelhosts="172.16.0.1AND172.16.0.2 172.16.0.1AND172.16.2.1"
	lappend tunnelhosts $ep

	set subnets ""
	foreach subnet_item [$f.t.tree children $th] {
	     set sn [$f.t.tree item $subnet_item -text]
	     set i [string first " " $sn]
	     # replace " <===> " with "AND"
	     set sn [string replace $sn $i $i+6 "AND"]
	     lappend subnets $sn
	}
	incr ti
	set subnetstxt [join $subnets " "]
	# build a list e.g.:
	#   T2="172.16.4.0/24AND172.16.5.0/24 172.16.4.0/24AND172.16.6.0/24"
	set subnets "T$ti=\"$subnetstxt\""
	lappend subnet_list $subnets
    }

    #
    # Perform replacements in existing ipsec.sh file.
    #
    set have_subnets 0
    foreach line [split $cfg "\n"] {
	if { [string range $line 0 6] == "keydir=" } {
	    set line "keydir=$keydir"
	} elseif { [string range $line 0 8] == "certname=" } {
	    set line "certname=$keyname"
	} elseif { [string range $line 0 11] == "tunnelhosts=" } {
	    set tunnelhosts [join $tunnelhosts " "]
	    set line "tunnelhosts=\"$tunnelhosts\""
	} elseif { [string range $line 0 0] == "T" && \
	           [string is digit [string range $line 1 1]] } {
	    if { $have_subnets } {
		continue ;# skip this line
	    } else {
		set line [join $subnet_list "\n"]
		set have_subnets 1
	    }
	}
	lappend newcfg $line
    }
    $w.note.files.txt delete 0.0 end
    $w.note.files.txt insert 0.0 [join $newcfg "\n"]
    $w.note select $w.note.files
    $w.btn.apply configure -state normal
}

proc readIPsecScript { w } {
    set cfg [$w.note.files.txt get 0.0 end-1c]

    set f $w.note.ipsec
    $f.keys.dir.ent delete 0 end
    $f.keys.name.ent delete 0 end
    $f.t.tree delete [$f.t.tree children {}]

    set ti 1
    foreach line [split $cfg "\n"] {
	if { [string range $line 0 6] == "keydir=" } {
	    $f.keys.dir.ent insert 0 [string range $line 7 end]
	} elseif { [string range $line 0 8] == "certname=" } {
	    $f.keys.name.ent insert 0 [string range $line 9 end]
	} elseif { [string range $line 0 11] == "tunnelhosts=" } {
	    set tunnelhosts [string range $line 13 end-1]
	    set ti 0
	    foreach ep [split $tunnelhosts " "] {
		incr ti
		set i [string first "AND" $ep]
		set ep [string replace $ep $i $i+2 " <--> "]
		$f.t.tree insert {} end -id "T$ti" -text "$ep" -open true
	    }
	} elseif { [string range $line 0 0] == "T" && \
	           [string is digit [string range $line 1 1]] } {
	    set i [string first "=" $line]
	    set ti [string range $line 0 $i-1]
	    set subnets [split [string range $line $i+2 end-1] " "]
	    foreach sn $subnets {
		set i [string first "AND" $sn]
		set sn [string replace $sn $i $i+2 " <===> "]
		if { [catch {$f.t.tree insert $ti end -text "$sn"} e] } {
		    puts "IPsec service ignoring line '$ti='"
		}
	    }
	}
    }
}
