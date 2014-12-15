#
# Copyright 2005-2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#

set g_imageFileTypes {{"images" {.gif}} {"images" {.jpg}} {"images" {.png}}
			{"images" {.bmp}} {"images" {.pcx}} {"images" {.tga}}
			{"images" {.tif}} {"images" {.ps}} {"images" {.ppm}}
			{"images" {.xbm}} {"All files"  {*}   }}

global execMode
if { $execMode == "interactive"} { 
    if { [catch { package require Img }] } {
	puts "warning: Tcl/Tk Img package not found"
	puts "  Thumbnails and other image types (JPG, PNG, etc.) will not be supported."
	puts "  Please install it with:"
	puts "    yum install tkimg   (RedHat/Fedora)"
	puts "    sudo apt-get install libtk-img   (Debian/Ubuntu)"
	puts "    pkg_add -r libimg   (FreeBSD)\n"
	set g_imageFileTypes {{"images" {.gif}} {"All files" {*} }}
    }
}

#
# Set the global systype variable using checkOS, if it hasn't been set yet
proc setSystype { } {
    global systype
    if { [info exists systype] } { return } ;# global already set
    set systype [lindex [checkOS] 0]
}

#
# Return a string identifying the operating system,
# and a string of verbose OS info (for user display)
proc checkOS {} {
	global tk_patchLevel tk_library
	set ret {}

	set tcl_ver [info patchlevel]
	set tcl_libpath [info library]
	if { [info exists tk_patchLevel] } {
	    set tk_ver $tk_patchLevel
	    set tk_libpath $tk_library
	} else {
	    set tk_ver 0
	    set tk_libpath 0
	}
	set os_name [exec uname]
	set os_ver [exec uname -r]

	set machine [exec uname -m]
	set kernel [exec uname -v]

        set x11 0  
  	catch { set x11 [winfo server .c] }

	set os_ident "$os_name $os_ver"
	lappend ret $os_ident

	set os_verbose "$os_ident on $machine\nkernel build $kernel\nTCL version $tcl_ver ($tcl_libpath)\nTk version $tk_ver ($tk_libpath)\nX11 server $x11\n"

	lappend ret $os_verbose
	return $ret
}

# search a .imn topology file for old statements, and upgrade them
proc upgradeOldConfig { cfg_ref } {
	global execMode
	# modify config directly!
	upvar 1 $cfg_ref cfg

	set msg "config line updated:"

	# s/circle/annotation/
	set match {circle circle([0-9]+) (.)(.)}
	set subs {annotation a\1 \2\3    type oval\3}
	set r [regsub -all $match $cfg $subs cfg]
	if { $r > 0 } { puts "$msg  circle -> oval annotation ($r)" }

	# s/label/annotation/
	set match {label lab([0-9]+) (.)(.)}
	set subs {annotation a1\1 \2\3    type text\3}
	set r2 [regsub -all $match $cfg $subs cfg]
	if { $r2 > 0 } { puts "$msg  label -> text annotation ($r2)" }

	# s/size/fontsize/
	set r3 0
	if { $r2 > 0 } {
	    set match {size ([0-9]+)}
	    set subs {fontsize \1}
	    set r3 [regsub -all $match $cfg $subs cfg]
	    if { $r3 > 0 } { puts "$msg  size -> fontsize ($r3)" }
	}

	# s/model quagga/model router/
	set match {    model quagga}
	set subs {    model router}
	set r4 [regsub -all $match $cfg $subs cfg]
	if { $r4 > 0 } { puts "$msg  model quagga -> model router ($r4)" }

	# s/type pc/type router\n    model PC/
	set match {    type pc}
	set subs "    type router\n    model PC"
	set r5 [regsub -all $match $cfg $subs cfg]
	if { $r5 > 0 } { puts "$msg  type pc -> model pc ($r5)" }

	# s/type host/type router\n    model host/
	set match {    type host}
	set subs "    type router\n    model host"
	set r6 [regsub -all $match $cfg $subs cfg]
	if { $r6 > 0 } { puts "$msg  type host -> model host ($r6)" }

	incr r [expr {$r2 + $r3 + $r4 + $r5 + $r6}]
	#puts "$cfg"
	set choice ""
	if { $execMode == "interactive" && $r > 0 } {
	    puts "$msg $r substitutions made"
	    set choice [tk_messageBox -type yesno -icon question -title "CORE" \
		-message "This configuration file contains old syntax, \
			would you like to upgrade it to the new format?"]
	}
	return $choice
}

# renumber n0 if it exists
proc upgradeConfigRemoveNode0 { } {
    global node_list
    set i [lsearch $node_list n0]
    if { $i < 0 } { return }

    set new [newObjectId node]
    puts "changing node n0 to $new"
    global $new n0
    set $new $n0
    renumberNodesIfcs n0 $new
    set node_list [lreplace $node_list $i $i]
    lappend node_list $new
}

# update network-config blocks from old imn file configs
proc upgradeNetworkConfigToServices { } {
    global node_list

    # XXX this is a hack to populate zebra service values
    #     really, we should query for service config items...
    set vals "{('/usr/local/etc/quagga', '/var/run/quagga')}"
    set vals "$vals {('/usr/local/etc/quagga/Quagga.conf', 'quaggaboot.sh', '/usr/local/etc/quagga/vtysh.conf')}"
    set vals "$vals 35 {('sh quaggaboot.sh zebra',)} {('killall zebra',)} {} {}"
    set statvals "{} {('staticroutes.sh', )} 35 {('sh staticroutes.sh', )}"
    set statvals "$statvals {} {} {}"

    foreach node $node_list {
	#
	# build Quagga services config from network-config block
	#
	set ospfv2 [netconfFetchSection $node "router ospf"]
	set ospfv3 [netconfFetchSection $node "router ospf6"]
	set rip [netconfFetchSection $node "router rip"]
	set ripng [netconfFetchSection $node "router ripng"]
	set bgp [netconfFetchSection $node "router bgp"]
	if { $ospfv2 != "" || $ospfv3 != "" || $rip != "" || $ripng != "" } {
	    set cfg ""
	    set services "zebra vtysh IPForward"
	    foreach ifc [ifcList $node] {
		lappend cfg "interface $ifc"
		set ifccfg [netconfFetchSection $node "interface $ifc"]
                set cfg "$cfg $ifccfg"
		lappend cfg "!"
	    }
	    if { $ospfv2 != "" } {
		netconfClearSection $node "router ospf"
                lappend cfg "router ospf"; set cfg "$cfg $ospfv2 !"
		lappend services "OSPFv2"
	    }
	    if { $ospfv3 != "" } {
		netconfClearSection $node "router ospf6"
		lappend cfg "router ospf6"; set cfg "$cfg $ospfv3 !"
		lappend services "OSPFv3"
	    }
	    if { $rip != "" } {
		netconfClearSection $node "router rip"
		lappend cfg "router rip"; set cfg "$cfg $rip !"
		lappend services "RIP"
	    }
	    if { $ripng != "" } {
		netconfClearSection $node "router ripng"
		lappend cfg "router ripng"; set cfg "$cfg $ripng !"
		lappend services "RIPNG"
	    }
	    if { $bgp != "" } {
		netconfClearSection $node "router bgp"
                # AS number is lost here
		lappend cfg "router bgp"; set cfg "$cfg $bgp !"
		lappend services "BGP"
	    }
	    setCustomConfig $node "service:zebra" "zebra" $vals 0
	    set cfgname "/usr/local/etc/quagga/Quagga.conf"
	    setCustomConfig $node "service:zebra:$cfgname" $cfgname $cfg 0
	    set cfgname "/usr/local/etc/quagga/vtysh.conf"
	    setCustomConfig $node "service:zebra:$cfgname" $cfgname \
		"service integrated-vtysh-config" 0
            setNodeServices $node $services
	    puts "updating Quagga services on node $node"
	} ;# end quagga services
	#
	# convert static model to router 
	#
	if { [getNodeModel $node] == "static" } {
	    setNodeModel $node "router"
            setNodeServices $node "IPForward"
	    puts "changing model static to router on node $node"
	}
	#
	# convert static routes to a custom service
	#
	if { [getStatIPv4routes $node] != "" || \
	     [getStatIPv6routes $node] != "" } {
	    set cfg {}
	    lappend cfg "# custom static route service generated by util.tcl"
	    addStaticRoutesToConfig $node cfg
	    setStatIPv4routes $node ""; setStatIPv6routes $node "" ;# clear old
	    set cfgname "staticroutes.sh"
	    setCustomConfig $node "service:UserDefined" "UserDefined" \
	    	$statvals 0
            setCustomConfig $node "service:UserDefined:$cfgname" $cfgname $cfg 0
	    set services [getNodeServices $node true] 
	    lappend services "UserDefined"
            setNodeServices $node $services
	    puts "adding user-defined static routing service on node $node"
	} ;# end static services
    }
}

# get CPU usage from /proc/stat jiffies
proc getCPUUsage { } {
    global lastcpu

    if { [catch {set f [open "/proc/stat" r]} ] } {
	return ""; # unable to open /proc/stat
    }

    array set cpu {}
   
    while { [ gets $f line ] >= 0 } {
	set cpun [lindex $line 0]
	set user [lindex $line 1]; set nice [lindex $line 2]
	set sys  [lindex $line 3]; set idle [lindex $line 4]
	if { [string range $cpun 0 2] != "cpu" } { continue }
	set cpu($cpun) "$user $nice $sys $idle"
    }
    close $f
    if { ![info exists cpu(cpu)] } { return "" }

    set cpuusages ""
    foreach cpun [lsort -dictionary [array names cpu]] {
	if { ![info exists lastcpu($cpun)] } {
	    set lastcpu($cpun) "0 0 0 0"
	}
	set lu [lindex $lastcpu($cpun) 0]; set ln [lindex $lastcpu($cpun) 1]
	set ls [lindex $lastcpu($cpun) 2]; set li [lindex $lastcpu($cpun) 3]
	set u [lindex $cpu($cpun) 0]; set n [lindex $cpu($cpun) 1]
	set s [lindex $cpu($cpun) 2]; set i [lindex $cpu($cpun) 3]
	set lastcpu($cpun) "$u $n $s $i"

	set usage_time [expr {($u-$lu) + ($n-$ln) + ($s-$ls)}]
	set total_time [expr {$usage_time + ($i-$li)}]
	if { $total_time <= 0 } { 
	    set cpuusage "" ;# avoid div by zero
 	} else {
	    set cpuusage [expr { 100 * $usage_time / $total_time }]
	}
	lappend cpuusages $cpuusage
    }
    return $cpuusages 
}

# Node selection dialog display given message 'msg' with initial node selection
# set to the 'initsel' list, and calls the callback using the selected nodes
proc popupSelectNodes { msg initsel callback } {
    global node_list

    set wi .nodeselect
    catch {destroy $wi}
    toplevel $wi -takefocus 1
    wm resizable $wi 0 0
    wm title $wi "Select Nodes"
    grab $wi

    frame $wi.nodes -borderwidth 4

    if { $msg == "" } { set msg "Select one or more nodes:" }
    label $wi.nodes.label -text $msg
    frame $wi.nodes.fr
    listbox $wi.nodes.fr.nodelist -width 40 \
    	-listvariable node_list -yscrollcommand "$wi.nodes.fr.scroll set" \
	-activestyle dotbox -selectmode extended
    scrollbar $wi.nodes.fr.scroll -command "$wi.nodes.fr.nodelist yview" 
    pack $wi.nodes.fr.nodelist -fill both -expand true -side left
    pack $wi.nodes.fr.scroll -fill y -expand true -side left
    pack $wi.nodes.label $wi.nodes.fr -side top -padx 4 -pady 4 \
	-anchor w -fill both -expand true
    pack $wi.nodes -fill both -expand true -side top

    frame $wi.fbot -borderwidth 4
    button $wi.fbot.apply -text "OK" \
        -command "selectNodesHelper $wi {$callback}"
    button $wi.fbot.cancel -text "Cancel" -command "destroy $wi"
    pack $wi.fbot.cancel $wi.fbot.apply -side right -padx 4 -pady 4
    pack  $wi.fbot -side bottom

    #set n [$wi.nodes.fr.from get $i]
    #itemconfigure $i -foreground blue
    set idx 0
    foreach node $node_list {
	foreach sel $initsel {
	    if { $node == $sel } {
		$wi.nodes.fr.nodelist selection set $idx
		break
	    }
	}
	incr idx
    }
}

proc selectNodesHelper { wi callback } {
    set selected_indices [$wi.nodes.fr.nodelist curselection]
    set selected_nodes {}
    foreach idx $selected_indices {
	set node [$wi.nodes.fr.nodelist get $idx]
	lappend selected_nodes $node
    }
    destroy $wi
    lappend callback $selected_nodes
    eval $callback
}

# Boeing: node renumbering dialog
proc popupRenumberNodes { } {
    set wi .renumbernode
    catch {destroy $wi}
    toplevel $wi -takefocus 1
    wm transient $wi .
    wm resizable $wi 0 0
    wm title $wi "Renumber Nodes"
    grab $wi

    frame $wi.nodes -borderwidth 4

    frame $wi.nodes.left
    label $wi.nodes.left.label -text "Change this node:"
    frame $wi.nodes.left.fr
    listbox $wi.nodes.left.fr.from -selectmode single -width 20 \
    	-listvariable node_list -yscrollcommand "$wi.nodes.left.fr.scroll set" \
	-activestyle dotbox
    scrollbar $wi.nodes.left.fr.scroll -command "$wi.nodes.left.fr.from yview" 
    pack $wi.nodes.left.fr.from $wi.nodes.left.fr.scroll -fill y -side left
    pack $wi.nodes.left.label $wi.nodes.left.fr -side top -padx 4 -pady 4 \
	-anchor w
    pack $wi.nodes.left -side left
    bind $wi.nodes.left.fr.from <<ListboxSelect>> "selectRenumberNodes $wi from"

    frame $wi.nodes.right
    label $wi.nodes.right.label -text "to this node:"
    frame $wi.nodes.right.fr
    listbox $wi.nodes.right.fr.to -selectmode single -width 20 \
	-listvariable node_list -yscrollcommand "$wi.nodes.right.fr.scroll set"
    scrollbar $wi.nodes.right.fr.scroll -command "$wi.nodes.right.fr.to yview"
    pack $wi.nodes.right.fr.to $wi.nodes.right.fr.scroll -fill y -side left
    pack $wi.nodes.right.label $wi.nodes.right.fr -side top -padx 4 -pady 4 \
	-anchor w
    pack $wi.nodes.right -side left
    bind $wi.nodes.right.fr.to <<ListboxSelect>> "selectRenumberNodes $wi to"

    pack $wi.nodes -side top

    frame $wi.fbot -borderwidth 4
    button $wi.fbot.apply -text "Renumber Node" -command "renumberNodes $wi" \
	-state disabled
    button $wi.fbot.cancel -text "Close" -command "destroy $wi"
    pack $wi.fbot.cancel $wi.fbot.apply -side right -padx 4 -pady 4
    pack  $wi.fbot -side bottom

    #set n [$wi.nodes.left.fr.from get $i]
    #itemconfigure $i -foreground blue
}

# helper for highlighting nodes in the node renumbering list boxes
proc selectRenumberNodes { wi l } {
    global renumber_node_from renumber_node_to; # may be undefined
    if { $l == "to" } {
	set nlist $wi.nodes.right.fr.to
	set other "from"
    } else {
	set nlist $wi.nodes.left.fr.from
	set other "to"
    }
    if { [info exists renumber_node_$other] } { ;# do we have two selections?
	$wi.fbot.apply configure -state normal
    }
    set sel [$nlist curselection]
    if { [info exists renumber_node_${l}] } {; # color prev selected item black
	$nlist itemconfigure [set renumber_node_${l}] -foreground black
    }
    $nlist itemconfigure $sel -foreground blue; # highlight curr selection blue
    set renumber_node_${l} $sel; # this value is used by the apply button
}

# perform node renumbering, e.g. n1 becomes n3 and n3 is now n1
proc renumberNodes { wi } {
    global renumber_node_from renumber_node_to
    set from_idx $renumber_node_from
    set to_idx $renumber_node_to

    if { $from_idx < 0 || $to_idx < 0 } { return }
    set from [$wi.nodes.left.fr.from get $from_idx]
    set to [$wi.nodes.right.fr.to get $to_idx]
    set from_name [getNodeName $from]
    set to_name [getNodeName $to]

    set tmp [newObjectId node]

    global $to $from $tmp
    set $tmp [set $to]
    renumberNodesIfcs $to $tmp
    renumberNodesIfcs $from $to
    set $to [set $from]
    set $from [set $tmp]
    renumberNodesIfcs $tmp $from
    setNodeName $from $from_name
    setNodeName $to $to_name
    redrawAll
    destroy $wi
}

# helper to change interface-peers and links from one node to another
proc renumberNodesIfcs { from to } {
    foreach ifc [ifcList $from] {
	set peer [peerByIfc $from $ifc]
	set peerifc [ifcByPeer $peer $from]
	set link [linkByPeers $from $peer]
	global $peer $link
	# modify the peer to point to the new node
	set i [lsearch [set $peer] "interface-peer {$peerifc $from}"]
	set $peer [lreplace [set $peer] $i $i "interface-peer {$peerifc $to}"]
	# update the link variable with the new node
	if { [lindex [linkPeers $link] 0] == $from } {
	    set newnodes "nodes {$to $peer}"
	} else {
	    set newnodes "nodes {$peer $to}"
	}
	set $link [lreplace [set $link] 0 0 $newnodes]
    }
}

proc addAddressesToConfig { node cfg_ref } {
    global $node systype

    upvar 1 $cfg_ref cfg

    foreach ifc [ifcList $node] {
	set addr [getIfcIPv4addr $node $ifc]
	set addr6 [getIfcIPv6addr $node $ifc]
	if {[lindex $systype 0] == "Linux" } { ;# Linux
	    if { $addr != "" } {
		lappend cfg "/usr/local/sbin/addip.sh $ifc $addr"
	    }
	    if { $addr6 != "" } {
		lappend cfg "/usr/local/sbin/addip.sh $ifc $addr6"
	    }
	} else {
	    if { $addr != "" } {
		lappend cfg "ifconfig $ifc inet $addr"
	    }
	    if { $addr6 != "" } {
		lappend cfg "ifconfig $ifc inet6 $addr6"
	    }
	}
    }

}

# support for legacy static routing config
# called by upgradeNetworkConfigToServices
proc addStaticRoutesToConfig { node cfg_ref } {
    global $node systype

    upvar 1 $cfg_ref cfg

    foreach statrte [getStatIPv4routes $node] {
    	if {[lindex $systype 0] == "Linux" } { ;# Linux
	    set net [lindex [split $statrte] 0]
	    set gw [lindex [split $statrte] 1]
	    lappend cfg "/sbin/ip -4 route add $net via $gw"
	} else { ;# FreeBSD
	    lappend cfg "route -q add -inet $statrte"
	}
    }

    foreach statrte [getStatIPv6routes $node] {
    	if { [lindex $systype 0] == "Linux" } { ;# Linux
	    set net [lindex [split $statrte] 0]
	    set gw [lindex [split $statrte] 1]
	    if { $net == "::/0" } { set net "default" }
	    lappend cfg "/sbin/ip -6 route add $net via $gw"
	} else { ;# FreeBSD
	    lappend cfg "route -q add -inet6 $statrte"
	}
    }

}

proc getServiceStartString { } {
    global systype

    setSystype

    if { [lindex $systype 0] == "Linux" } { ;# Linux
	return "/etc/init.d/core-daemon start"
    } else { ;# FreeBSD
	return "/usr/local/etc/rc.d/core onestart"
    }
}

proc popupBuildHostsFile { } {
    global node_list
    set wi .buildhostsdialog

    catch {destroy $wi}

    toplevel $wi
    wm transient $wi .
    wm resizable $wi 1 1
    wm title $wi "Build hosts File"

    # help text at top
    frame $wi.top
    set helptext "The entries below can be added to your /etc/hosts file.\n"
    set helptext "$helptext Use the append button to write it now."
    label $wi.top.help -text $helptext
    pack $wi.top.help -side top -fill both -expand true
    pack $wi.top -padx 4 -pady 4 -side top

    # text box 
    frame $wi.mid
    text $wi.mid.hosts -relief sunken -bd 2 \
	-yscrollcommand "$wi.mid.scroll set" -setgrid 1 -height 30 -undo 1 \
	-autosep 1 -background white
    scrollbar $wi.mid.scroll -command "$wi.mid.hosts yview"
    pack $wi.mid.hosts -side left -fill both -expand true
    pack $wi.mid.scroll -side right -fill y
    pack $wi.mid -side top -fill both -expand true

    $wi.mid.hosts insert end "### begin CORE auto-generated hosts entries\n"
    foreach node $node_list {
	set hostname [getNodeName $node]
	foreach ifc [ifcList $node] {
	    foreach addr [getIfcIPv4addr $node $ifc] {
		set ip [lindex [split $addr /] 0]
	        $wi.mid.hosts insert end "$ip		$hostname\n"
	    }
	}
    }
    $wi.mid.hosts insert end "### end CORE auto-generated hosts entries\n"

    # file selection
    frame $wi.fil
    entry $wi.fil.filename -width 30 -bg white
    button $wi.fil.filebtn -text "..." -command {
        set wi .buildhostsdialog
	set f [$wi.fil.filename get]
        set f [tk_getSaveFile -initialfile $f]
        if { $f != "" } {
	    $wi.fil.filename delete 0 end
	    $wi.fil.filename insert 0 $f
        }
    }
    pack $wi.fil.filename -expand true -fill x -side left
    pack $wi.fil.filebtn -side left
    pack $wi.fil -side top
    $wi.fil.filename insert 0 "/etc/hosts"

    # buttons on the bottom
    frame $wi.btm
    button $wi.btm.apply -text "Append file" -command {
        set wi .buildhostsdialog
	set hosts [string trim [$wi.mid.hosts get 0.0 end]]
	set filename [$wi.fil.filename get]
	set fileId [open $filename a] 
        puts $fileId $hosts
	close $fileId
	destroy $wi
    }
    button $wi.btm.cancel -text "Close" -command "destroy $wi"
    pack $wi.btm.apply $wi.btm.cancel -side left
    pack $wi.btm

    focus $wi.mid.hosts
}

proc popupAddressConfig { } {
    global plugin_img_add plugin_img_del g_prefs
    set wi .addrconfig

    catch {destroy $wi}

    toplevel $wi
    wm transient $wi .
    wm resizable $wi 1 1
    wm title $wi "IP Addresses"

    # help text at top
    frame $wi.top
    set helptext "New interfaces are automatically assigned IP addresses from\n"
    set helptext "$helptext the range selected below."
    label $wi.top.help -text $helptext
    pack $wi.top.help -side top -fill both -expand true
    pack $wi.top -padx 4 -pady 4 -side top

    frame $wi.f
    foreach fam [list "IPv4" "IPv6"] {
	set faml [string tolower $fam]
	set f $wi.f.$faml
	labelframe $f -text "$fam"
	# list of address prefixes
	frame $f.l
	listbox $f.l.list -bg white -yscrollcommand "$f.l.scroll set" \
		-exportselection 0
	scrollbar $f.l.scroll -command "$f.l.list yview" -bd 1 -width 10
	pack $f.l.list $f.l.scroll -side left -fill y -expand true
	pack $f.l -side top -fill y -expand true
	# controls for editing list
	frame $f.edit
	entry $f.edit.addr -bg white -width 20
	button $f.edit.new -image $plugin_img_add \
	    -command "addressConfigHelper $wi $fam add"
	button $f.edit.del -image $plugin_img_del \
	    -command "addressConfigHelper $wi $fam del"
	pack $f.edit.addr $f.edit.new $f.edit.del -side left
	pack $f.edit -side top

        frame $f.butt
	label $f.butt.l -text "Remove $fam:"
	button $f.butt.delall -text "all" -command "delAddrs all $fam"
	button $f.butt.delsel -text "selected" -command "delAddrs sel $fam"
	pack $f.butt.l $f.butt.delall $f.butt.delsel -side left
	pack $f.butt -side top

	pack $f -side left

	# populate list and select appropriate entry
        if {![info exists g_prefs(gui_${faml}_addr)]} { setDefaultAddrs $faml }
	set idx -1; set i 0
	foreach addr $g_prefs(gui_${faml}_addrs) {
	    $f.l.list insert end $addr
	    if { $addr == $g_prefs(gui_${faml}_addr) } { set idx $i }
	    incr i
	}
	if { $idx < 0 } {
	    $f.l.list insert end $g_prefs(gui_${faml}_addr)
	    $f.l.list selection set end
	} else {
	    $f.l.list selection set $idx
	}
    } ;# end foreach fam
    pack $wi.f -side top

    # buttons on the bottom
    frame $wi.btm
    button $wi.btm.apply -text "OK" \
	-command "addressConfigHelper $wi \"\" apply"
    button $wi.btm.def -text "Defaults" \
	-command "setDefaultAddrs ipv4; setDefaultAddrs ipv6; destroy $wi; popupAddressConfig"
    button $wi.btm.cancel -text "Cancel" -command "destroy $wi"
    pack $wi.btm.apply $wi.btm.def $wi.btm.cancel -side left
    pack $wi.btm

    #focus $wi.mid.hosts
}

# listbox helper for adding and removing entries, and applying them
proc addressConfigHelper { wi fam cmd } {
    global g_prefs

    set f $wi.f.[string tolower $fam]
    switch -exact -- $cmd {
	add {
	    set addr [$f.edit.addr get]
	    $f.l.list insert end $addr
	}
	del {
	    set i [$f.l.list curselection]
	    if { $i == "" } { return }
	    $f.l.list delete $i
	}
	apply {
	    foreach fam [list "ipv4" "ipv6"] {
		set f $wi.f.$fam
		set i [$f.l.list curselection]
		if { $i == "" } { set i 0 }
		set addr [$f.l.list get $i]
		set addrs [$f.l.list get 0 end]
		array set g_prefs [list gui_${fam}_addr $addr]
		array set g_prefs [list gui_${fam}_addrs $addrs]
	    }
	    destroy $wi
	}
    }
}

# set the default addresses for automatic allocation in the g_prefs array 
# for the given address family
proc setDefaultAddrs { fam } {
    global g_prefs
    if { $fam == "ipv4" } {
	set addrs [getDefaultIPv4Addrs]
    } elseif { $fam == "ipv6" } {
	set addrs [getDefaultIPv6Addrs]
    } else {
	return
    }
    array set g_prefs [list gui_${fam}_addr [lindex $addrs 0]]
    array set g_prefs [list gui_${fam}_addrs $addrs]
}

proc popupMacAddressConfig { } {
    set wi .macaddrconfig
    global mac_addr_start

    catch {destroy $wi}

    toplevel $wi
    wm transient $wi .
    wm resizable $wi 1 1
    wm title $wi "MAC Addresses"

    # help text at top
    frame $wi.top
    set helptext "MAC addresses are automatically assigned starting with\n"
    set helptext "$helptext 00:00:00:aa:00:nn, where nn starts with the below"
    set helptext "$helptext value.\n You should change this value when tunneling" 
    set helptext "$helptext between \nemulations to prevent MAC address conflicts." 

    label $wi.top.help -text $helptext
    pack $wi.top.help -side top -fill both -expand true
    pack $wi.top -padx 4 -pady 4 -side top

    if { ![info exists mac_addr_start] } { set mac_addr_start 0 }
    frame $wi.f
    label $wi.f.maclab -text "Starting MAC number:"
    entry $wi.f.mac -width 5 -bg white -textvariable mac_addr_start
    pack $wi.f.maclab $wi.f.mac $wi.f -side left
    pack $wi.f -side top

    frame $wi.btm
    button $wi.btm.apply -text "close" -command "destroy $wi"
    pack $wi.btm.apply -side left
    pack $wi.btm

}

#
# Capture a window into an image
# Author: David Easton
#
proc captureWindow { win } {


   regexp {([0-9]*)x([0-9]*)\+([0-9]*)\+([0-9]*)} [winfo geometry $win] - w h x y

   # Make the base image based on the window
   set image [image create photo -format window -data $win]

   foreach child [winfo children $win] {
     captureWindowSub $child $image 0 0
   }

   return $image
}

proc captureWindowSub { win image px py } {

   if {![winfo ismapped $win]} {
     return
   }

   regexp {([0-9]*)x([0-9]*)\+([0-9]*)\+([0-9]*)} [winfo geometry $win] - w h x y

   incr px $x
   incr py $y

   # Make an image from this widget
   set tempImage [image create photo -format window -data $win]

   # Copy this image into place on the main image
   $image copy $tempImage -to $px $py
   image delete $tempImage

   foreach child [winfo children $win] {
     captureWindowSub $child $image $px $py
   }
}

proc writeCanvasThumbnail { c fn } {
    global execMode
    set r false
    if [ catch {
	set img [captureWindow $c]
	set imgthumb [image create photo]
	# resize image to height 100
	set w [image height $img]
	$imgthumb copy $img -subsample [expr { int($w / 100)} ]
	$imgthumb write $fn -format jpeg
	image delete $img
	image delete $imgthumb
	set r true
    } e ] {
	if { $execMode == "interactive" } {
	    puts "warning: failed to create canvas thumbnail"
	}
    }
    return $r
}

# contributed code from CL from http://wiki.tcl.tk/557 fetched 6/11/10
proc _launchBrowser url {
      global tcl_platform

    # It *is* generally a mistake to switch on $tcl_platform(os), particularly
    # in comparison to $tcl_platform(platform).  For now, let's just regard it
    # as a stylistic variation subject to debate.
      switch $tcl_platform(os) {
	Darwin {
	  set command [list open $url]
	}
	HP-UX -
	Linux  -
	SunOS {
	  foreach executable {firefox mozilla netscape iexplorer opera lynx
		       w3m links epiphany galeon konqueror mosaic amaya
		       browsex elinks} {
	    set executable [auto_execok $executable]
	    if [string length $executable] {
    # Do you want to mess with -remote?  How about other browsers?
	      set command [list $executable $url &]
	      break
	    }
	  }
	}
	{Windows 95} -
	{Windows NT} {
	  set command "[auto_execok start] {} [list $url]"
	}
      }
      if [info exists command] {
	if [catch {eval exec $command } err] {
	  tk_messageBox -icon error -message "error '$err' with '$command'"
	}
      } else {
	tk_messageBox -icon error -message \
	  "Please tell CL that ($tcl_platform(os), $tcl_platform(platform)) is not yet ready for browsing."
      }
}

# helper for registering a callback with a tk_optionMenu variable, when a user
# clicks on the menu and changes the value; if the global variable var is
# cleared, this callback is cancelled 
# NOTE: when closing the window that calls this, ensure that var is cleared
proc tkOptionMenuCallback { ctl var cb args } {
    if { ![winfo exists $ctl] } { return }
    global $var
    tkwait variable $var
    # cancel callback when var is cleared
    if { [set $var] == "" } { return }
    # here is a hack to remove the outer list
    if {[llength $args] == 1} { set args [lindex $args 0] }
    $cb [set $var] $args

    tkOptionMenuCallback $ctl $var $cb $args
}

# split a string on commas, while respecting single quote "'" quoting
# items should be in single quotes which are omitted from the resulting list
#    e.g. 'foo', 'ba\'r', 'baz' ==> {foo, ba'r, baz}
proc safeCommaSplit { str } {
    set item ""
    set r []
    set inquotes false
    for {set i 0} {$i < [string length $str]} {incr i} {
	set c [string index $str $i]
	if { $c == "'" } {
	    # check for escaped quote and skip it
	    if { $i > 0 && [string index $str [expr $i-1]] == "\\" } {
		set item "$item$c"
		continue
	    }
	    if { !$inquotes } {
		set inquotes true ;# begin quoted block
	    } else {
		set inquotes false ;# end quoted block
	    }
	    continue
	}
	if { $c == "," && !$inquotes } { ;# comma outside quoted block
	    lappend r $item
	    set item ""
	    continue
	}
	set item "$item$c"
    }
    if { $item != "" } { lappend r $item } ;# last item in list
    return $r
}

# convert a string in the Python tuple format into a TCL list
proc tupleStringToList { str } {
    set str [string trim $str] ;# remove whitespace
    set str [string trim $str "()"] ;# remove (...)
    set quotedlist [safeCommaSplit $str] ;# [split $str ","] doesn't work here
    set r ""
    foreach item $quotedlist {
	set item [string trim $item] ;# remove whitespace
	# un-escape double and single quotes
	set item [string map {\\\" \"} $item]
	set item [string map {\\' '} $item]
	if { $item != "" } { lappend r $item }
    }
    return $r
}

# convert a TCL list to the Python tuple format
proc listToTupleString { l } {
    if { [llength $l] == 0 } { return {} } ;# don't return empty tuples "()"
    set str "("
    foreach item $l {
	# escape double and single quotes
	set item [string map {\" \\\"} $item]
	set item [string map {' \\'} $item]
	# enclose each item in single quotes
	set str "$str'$item', "
    }
    set str "$str)"
    return $str
}

proc exportPython { } {
    global node_list link_list

    foreach n $node_list {
        set name [getNodeName $n]
	set xy [getNodeCoords $n]
	puts "    $name = session.addobj(cls = pycore.nodes.class, name=\"$name\")"
	puts "    $name.setposition(x=[lindex $xy 0],y=[lindex $xy 1])"
    }

    foreach l $link_list {
	set lnode1 [lindex [linkPeers $l] 0]
	set lnode2 [lindex [linkPeers $l] 1]
	set ifc1 [ifcByPeer $lnode1 $lnode2]
	set ifc2 [ifcByPeer $lnode2 $lnode1]
	set net "ptpnet"
	if { [[typemodel $lnode1].layer] == "LINK" } {
	    set net [getNodeName $lnode1]
	}
	if { [[typemodel $lnode2].layer] == "LINK" } {
	    set net [getNodeName $lnode2]
	}
	if { [[typemodel $lnode1].layer] == "NETWORK" } {
	    set ipv4 [getIfcIPv4addr $lnode1 $ifc1]
	    set if1n [ifcNameToNum $ifc1]
	    puts -nonewline "    [getNodeName $lnode1].newnetif(net=$net, "
	    puts "addrlist=\[\"$ipv4\"\], ifindex=$if1n)"
	}
	if { [[typemodel $lnode2].layer] == "NETWORK" } {
	    set ipv4 [getIfcIPv4addr $lnode2 $ifc2]
	    set if2n [ifcNameToNum $ifc2]
	    puts -nonewline "    [getNodeName $lnode2].newnetif(net=$net, "
	    puts "addrlist=\[\"$ipv4\"\], ifindex=$if2n)"
	}

    }
}

proc execPythonFile { filename } {
    set flags 0x10 ;# status request flag
    sendRegMessage -1 $flags [list "exec" $filename]
    addFileToMrulist $filename

    tk_messageBox -type ok -message "Executed Python script '$filename'"
}

# ask the daemon to execute the selected file
proc execPython { with_options } {
    global fileDialogBox_initial g_prefs
    set ft {{ "CORE XML or Python scripts" {.py .xml} } { "All files" {*}}}

    if { $fileDialogBox_initial == 0 } {
	set fileDialogBox_initial 1
	set dir $g_prefs(default_conf_path)
        set fn [tk_getOpenFile -filetypes $ft -initialdir $dir]
    } else {
        set fn [tk_getOpenFile -filetypes $ft]
    }
    if { $fn == "" } { return }
    if { $with_options } {
	set prompt "Append any command-line options for running the Python"
	set prompt "$prompt script:"
	set fn [tk_inputBox "Python Script Options" $prompt $fn . 50]
	if { $fn == "" } { return }
    }

    execPythonFile $fn
}

# open a dialog that prompts the user with a text entry
# this is a blocking dialog that returns "" for cancel, or the entry text for OK
proc tk_inputBox { title prompt default_text parent width} {
    set w .input_box
    catch {destroy $w}
    toplevel $w

    global g_input_box_btn_state
    set g_input_box_btn_state 0
    global g_input_box_text
    set g_input_box_text $default_text

    wm title $w $title
    wm transient $w $parent
    wm attributes $w -type dialog

    ttk::frame $w.f
    ttk::label $w.f.top -text $prompt
    ttk::entry $w.f.ent -width $width -textvariable g_input_box_text
    pack $w.f.top $w.f.ent -side top -padx 4 -pady 4
    pack $w.f -side top

    ttk::frame $w.btn
    ttk::button $w.btn.ok -text "OK" -command {
        global g_input_box_btn_state
        set g_input_box_btn_state 1
    }
    ttk::button $w.btn.cancel -text "Cancel" -command {
	global g_input_box_text
        global g_input_box_btn_state
	set g_input_box_text ""
        set g_input_box_btn_state 2
    }
    pack $w.btn.ok $w.btn.cancel -side left -padx 4 -pady 4
    pack $w.btn -side top

    vwait g_input_box_btn_state
    destroy $w
    return $g_input_box_text
}

# from Practical Programming in Tcl and Tk, page 190
proc Call_Trace {{file stdout}} {
    puts $file "*** Tcl Call Trace:"
    for {set x [expr [info level]-1]} {$x > 0} {incr x -1} {
	puts $file "  $x: [info level $x]"
    }
}

# toggle a boolean variable
proc toggle { v } {
     upvar 1 $v var
     set var [expr {!$var}]
}

# return the name of the text editor to use
# - the preference g_prefs(gui_text_editor) overrides any default
# - if want_default is specified, first return EDITOR environment variable,
#   then find the first in the list of editors that exists on the system
set EDITORS "vim emacs gedit nano vi"
proc get_text_editor { want_default } {
    global g_prefs env EDITORS
    set ed ""
    if { [info exists env(EDITOR)] } {
	set ed $env(EDITOR)
    }
    if { !$want_default && [info exists g_prefs(gui_text_editor)] } {
	set edpref $g_prefs(gui_text_editor)
	# preference can be EDITOR, to use environment variable EDITOR
	if { $edpref == "EDITOR" } {
	    set edpref $ed
	}
	if { $edpref != "" } {
	    return $edpref
	}
	# fall through since environment variable or pref not set
    }

    # first use any EDITOR variable
    if { $ed != "" } {
	if { $want_default } {
	    return "EDITOR"
	} else {
	    return $ed 
	}
    }
    # return the first installed editor from EDITORS global
    foreach ed $EDITORS {
	if { [auto_execok $ed] != "" } {
	    return $ed
	}
    }
    # none of the editors were found, just return the first one
    return [lindex $EDITORS 0]
}

# return the name of the terminal program to use
# - the preference g_prefs(gui_term_prog) overrides any default
# - if want_default is specified, first return COLORTERM or TERM environment
#   variable, then find the first in the list of terminals that exists on the
#   system
set TERMS "{gnome-terminal -x} {lxterminal -e} {konsole -e} {xterm -e}"
set TERMS "$TERMS {aterm -e} {eterm -e} {rxvt -e} {xfce4-terminal -e}"

proc get_term_prog { want_default } {
    global g_prefs env TERMS
    # initialize term = COLORTERM or TERM environment variables
    set term ""
    if { [info exists env(COLORTERM)] } {
	if { ![string is integer $env(COLORTERM) ] } {
	    # under OpenSUSE, COLORTERM=1
	    set term [auto_execok $env(COLORTERM)]
	}
    }
    if { $term == "" && [info exists env(TERM)] } {
	set term [auto_execok $env(TERM)]
    }
    if { $term != "" } {
	set arg "-e"
	# gnome-terminal has problem w/subsequent arguments after -e, needs -x
	if { [file tail $term] == "gnome-terminal" } { set arg "-x" }
	set term "$term $arg"
    }

    if { !$want_default && [info exists g_prefs(gui_term_prog)] } {
	set termpref $g_prefs(gui_term_prog)
	# preference can be TERM, to adopt environment variable TERM
	if { $termpref == "TERM" } {
	    set termpref $term
	}
	if { $termpref != "" } {
	    return $termpref ;# pre-configured preference or expanded TERM
	}
	# fall through since environment variable or preference not set
    }

    # first use any TERM variable
    if { $term != "" } {
	if { $want_default } {
	    return "TERM"
	} else {
	    return $term
	}
    }
    # return the first installed terminal from TERMS global
    foreach term $TERMS {
	if { [auto_execok [lindex $term 0]] != "" } {
	    return $term
	}
    }
    # none of the terminals were found, just return the first one
    return [lindex $TERMS 0]
}

# short session ID used by Python daemon for interface names
proc shortSessionID { sid } {
    set ssid [ expr { ($sid >> 8) ^ ($sid & ((1<<8) - 1)) } ]
    return [format "%x" $ssid]
}


proc delAddrs { mode fam } {
    global node_list
    if { $mode == "all" } {
	delAddrsFromNodes $fam $node_list
    } else {
	set msg "Remove all $fam addresses from these nodes:"
	popupSelectNodes $msg "" "delAddrsFromNodes $fam"
    }
}

proc delAddrsFromNodes { fam nodes } {
    foreach node $nodes {
	foreach ifc [ifcList $node] {
	    if { $fam == "IPv4" } {
	        setIfcIPv4addr $node $ifc ""
	    } elseif { $fam == "IPv6" } {
	        setIfcIPv6addr $node $ifc ""
	    }
	}
    }
    redrawAll
}

# fix for Tcl/Tk 8.5.8 and lower which doesn't have ttk::spinbox
#    set spinbox [getspinbox]
#    $spinbox $var -justify right -width 10 ...
# 
proc getspinbox {} {
    if { [info command ttk::spinbox] == "" } {
	return spinbox
    } else {
	return ttk::spinbox
    }
}

# find dialog for searching for nodes and links
proc popupFind {} {
    set msg "find"
    set initsel ""
    set callback ""
    global node_list

    set w .find
    catch {destroy $w}
    toplevel $w -takefocus 1
    wm transient $w .
    wm title $w "Find"

    ttk::frame $w.find -borderwidth 4
    ttk::label $w.find.lab -text "Find:"
    ttk::entry $w.find.text -width 40
    pack $w.find.lab -side left
    pack $w.find.text -side left -fill x -expand 1
    pack $w.find -fill x -side top -padx 4 -pady 4
    bind $w.find.text <Key-Return> "findButton $w"

    ttk::frame $w.mid
    ttk::treeview $w.mid.tree -columns {number name location details} \
	-show headings -yscroll "$w.mid.vsb set" -xscroll "$w.mid.hsb set"
    ttk::scrollbar $w.mid.vsb -orient vertical -command "$w.mid.tree yview"
    ttk::scrollbar $w.mid.hsb -orient horizontal -command "$w.mid.tree xview"
    pack $w.mid -side top -fill both -expand true -padx 4 -pady 4
    grid $w.mid.tree $w.mid.vsb -in $w.mid -sticky nsew
    grid $w.mid.hsb -in $w.mid -sticky nsew
    grid column $w.mid 0 -weight 1
    grid row $w.mid 0 -weight 1

    bind $w.mid.tree <<TreeviewSelect>> "findTreeSelect $w.mid.tree"

    set closecmd "drawNodeCircle {} {} {} {} findhi; destroy $w"
    bind $w.find.text <Key-Escape> $closecmd
    bind $w <Key-Escape> $closecmd

    ttk::frame $w.fbot -borderwidth 4
    ttk::button $w.fbot.find -text "Find" -command "findButton $w"
    ttk::button $w.fbot.close -text "Close" -command $closecmd
    pack $w.fbot.find $w.fbot.close -side left -padx 4 -pady 4
    pack $w.fbot -side bottom

    findTreeHeader $w.mid.tree
    focus $w.find.text
}

# helper for find button, implements searching of nodes, links, and node names
# TODO: search IPv4/IPv6/MAC addresses, services, annotations, EMANE configs?
proc findButton { w } {
    global node_list link_list
    set terms [$w.find.text get]
    set tree $w.mid.tree

    findTreeHeader $tree
    . config -cursor watch; update
    set first ""
    set nodename_list ""
    foreach n $node_list { lappend nodename_list [getNodeName $n] }

    foreach search [list node nodename link] {
	set ${search}_results [lsearch -nocase -all -glob \
	    [set ${search}_list] "*$terms*"]
        # populate results
        foreach result [set ${search}_results] {
	    if { $result == -1 } { continue }
	    set search_list ${search}_list
	    if { ${search} == "nodename" } { set search_list node_list }
	    set obj [lindex [set $search_list] $result]
	    if { $first == "" } { set first $obj }

	    set num $obj
	    if { $search == "link" } {
		set peers [linkPeers $obj]
		set name "[lindex $peers 0]-[lindex $peers 1]"
		set coords [getNodeCoords [lindex $peers 0]]
		set details [getLinkBandwidthString $obj]
		set details "$details [getLinkDelayString $obj]"
	    } else {
		set name [getNodeName $obj]
		set coords [getNodeCoords $obj]
		set details [ipv4List $obj false]
		set details "$details [ipv6List $obj false]"
	    }
	    set coords "<[lindex $coords 0], [lindex $coords 1]>"
	    if { ![$tree exists $obj] } {
		$tree insert {} end -id $obj \
	    	    -values [list $num $name $coords $details]
	    }
	}
    }

    if { $first == "" } {
	$tree insert {} end -id none -values [list "" "" "" "no results found"]
    } else {
	$tree selection set $first 
    }

    . config -cursor left_ptr
}

# helper clears treeview and populates column header row
proc findTreeHeader { tree } {
    $tree delete [$tree children {}]
    set widths {75 75 125 350}; set i 0
    foreach col {number name location details} {
	$tree heading $col -text $col
	set width [lindex $widths $i]; incr i
	$tree column $col -width $width
    }
    drawNodeCircle "" "" "" "" findhi
}

# helper handles treeview selection changes in the Find dialog
proc findTreeSelect { ctl } {
    global curcanvas
    drawNodeCircle "" "" "" "" findhi
    set obj [$ctl selection]
    if { $obj == "none" } { return }

    if { [string range $obj 0 0] == "l" } {
	lassign [linkPeers $obj] node node2
    } else {
	set node $obj
	set node2 ""
    }

    # highlight node(s) and reposition canvas view so items are visible
    set target_canvas [getNodeCanvas $node]
    if { $target_canvas != $curcanvas } {
	set curcanvas $target_canvas
	switchCanvas none
    }
    drawNodeCircle $node 30 red findhi ""
    if { $node2 != "" } { drawNodeCircle $node2 30 red findhi "" }
    canvasSee .c $node
}


