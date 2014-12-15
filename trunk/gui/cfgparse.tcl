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
# This work was supported in part by the Croatian Ministry of Science
# and Technology through the research contract #IP-2003-143.
#

#****h* imunes/cfgparse.tcl
# NAME
#  cfgparse.tcl -- file used for parsing the configuration
# FUNCTION
#  This module is used for parsing the configuration, i.e. reading the 
#  configuration from a file or a string and writing the configuration 
#  to a file or a string. This module also contains a function for returning 
#  a new ID for nodes, links and canvases.
#****

#****f* nodecfg.tcl/dumpputs
# NAME
#   dumpputs -- puts a string to a file or a string configuration 
# SYNOPSIS
#   dumpputs $method $destination $string
# FUNCTION
#   Puts a sting to the file or appends the string configuration (used for 
#   undo functions), the choice depends on the value of method parameter.
# INPUTS
#   * method -- method used. Possiable values are file (if saving the string 
#   to the file) and string (if appending the string configuration)
#   * dest -- destination used. File_id for files, and string name for string 
#   configuration
#   * string -- the string that is inserted to a file or appended to the string
#   configuartion
#****

proc dumpputs {method dest string} {
    switch -exact -- $method {
	file {
	    puts $dest $string
	}
	string {
	    global $dest
	    append $dest "$string
"
	}
    }
}

#****f* nodecfg.tcl/dumpCfg
# NAME
#   dumpCfg -- puts the current configuraton to a file or a string 
# SYNOPSIS
#   dumpCfg $method $destination
# FUNCTION
#   Writes the working (current) configuration to a file or a string.
# INPUTS
#   * method -- used method. Possiable values are file (saving current congif
#   to the file) and string (saving current config in a string)
#   * dest -- destination used. File_id for files, and string name for string 
#   configurations
#****

proc dumpCfg {method dest} {
    global node_list plot_list link_list canvas_list annotation_list

    global g_comments
    if { [info exists g_comments] && $g_comments != "" } {
	dumpputs $method $dest "comments \{"
	foreach line [split $g_comments "\n"] { dumpputs $method $dest "$line" }
	dumpputs $method $dest "\}"
	dumpputs $method $dest ""
    }
    
    foreach node $node_list {
	global $node
	upvar 0 $node lnode
	dumpputs $method $dest "node $node \{"
	foreach element $lnode {
	    if { "[lindex $element 0]" == "network-config" } {
		dumpputs $method $dest "    network-config \{"
		foreach line [lindex $element 1] {
		    dumpputs $method $dest "	$line"
		}
		dumpputs $method $dest "    \}"
	    } elseif { "[lindex $element 0]" == "custom-config" } {
		dumpputs $method $dest "    custom-config \{"
		foreach line [lindex $element 1] {
		    if { $line != {} } {
			if { [catch {set str [lindex $line 0]} err] } {
				puts "error loading config: $err"
				puts "problem section: [lindex $element 0]"
				puts "problem line: $line"
				set str ""
			}
			if { $str == "config" } {
			    dumpputs $method $dest "	config \{"
			    foreach element [lindex $line 1] {
				dumpputs $method $dest "	$element"
			    }
			    dumpputs $method $dest "	\}"
			} else {
			    dumpputs $method $dest "	$line"
			}
		    }
		}
		dumpputs $method $dest "    \}"
	    } elseif { "[lindex $element 0]" == "ipsec-config" } { 
		dumpputs $method $dest "    ipsec-config \{"
		foreach line [lindex $element 1] {
		    if { $line != {} } {
			dumpputs $method $dest "	$line"
		    }
		}
		dumpputs $method $dest "    \}"
	    } elseif { "[lindex $element 0]" == "custom-pre-config-commands" } {
		#Boeing custom pre config commands
		dumpputs $method $dest "    custom-pre-config-commands \{"
		foreach line [lindex $element 1] {
		    dumpputs $method $dest "	$line"
		}
		dumpputs $method $dest "    \}"
	    } elseif { "[lindex $element 0]" == "custom-post-config-commands" } {
		#Boeing custom post config commands
		dumpputs $method $dest "    custom-post-config-commands \{"
		foreach line [lindex $element 1] {
		    dumpputs $method $dest "	$line"
		}
		dumpputs $method $dest "    \}"
	    } elseif { "[lindex $element 0]" == "ine-config" } {
	    # Boeing: INE config support
		dumpputs $method $dest "    ine-config \{"
		foreach line [lindex $element 1] {
		    dumpputs $method $dest "	$line"
		}
		dumpputs $method $dest "    \}"
	    # end Boeing
	    } else {
		dumpputs $method $dest "    $element"
            }
	}
	dumpputs $method $dest "\}"
	dumpputs $method $dest ""
    }

    foreach obj "link annotation canvas plot" {
	upvar 0 ${obj}_list obj_list
	foreach elem $obj_list {
	    global $elem
	    upvar 0 $elem lelem
	    dumpputs $method $dest "$obj $elem \{"
	    foreach element $lelem {
		dumpputs $method $dest "    $element"
	    }
	    dumpputs $method $dest "\}"
	    dumpputs $method $dest ""
	}
    }

    global g_traffic_flows
    if { [info exists g_traffic_flows] && [llength $g_traffic_flows] > 0 } {
	dumpputs $method $dest "traffic \{"
	foreach flow $g_traffic_flows {
	    dumpputs $method $dest "    $flow"
	}
	dumpputs $method $dest "\}"
	dumpputs $method $dest ""
    }

    global g_hook_scripts
    if { [info exists g_hook_scripts] && [llength $g_hook_scripts] > 0 } {
	foreach hook $g_hook_scripts {
	    set name [lindex $hook 0]
	    set state [lindex $hook 1]
	    set script [lindex $hook 2]
	    dumpputs $method $dest "hook $state:$name \{"
	    foreach line [split $script "\n"] {
	        dumpputs $method $dest "$line"
	    }
	    dumpputs $method $dest "\}"
	    dumpputs $method $dest ""
	}
    }

    dumpGlobalOptions $method $dest

    # session options
    dumpputs $method $dest "option session \{"
    foreach kv [getSessionOptionsList] { dumpputs $method $dest "    $kv" }
    dumpputs $method $dest "\}"
    dumpputs $method $dest ""
}

proc dumpGlobalOptions { method dest } {
    global showIfNames showNodeLabels showLinkLabels
    global showIfIPaddrs showIfIPv6addrs
    global showBkgImage showGrid showAnnotations
    global showAPI
    global g_view_locked
    global g_traffic_start_opt
    global mac_addr_start

    dumpputs $method $dest "option global \{"
    if {$showIfNames == 0} { 
	dumpputs $method $dest "    interface_names no" 
    } else {
	dumpputs $method $dest "    interface_names yes" }
    if {$showIfIPaddrs == 0} { 
	dumpputs $method $dest "    ip_addresses no" 
    } else {
	dumpputs $method $dest "    ip_addresses yes" }
    if {$showIfIPv6addrs == 0} { 
	dumpputs $method $dest "    ipv6_addresses no" 
    } else {
	dumpputs $method $dest "    ipv6_addresses yes" }
    if {$showNodeLabels == 0} { 
	dumpputs $method $dest "    node_labels no" 
    } else {
	dumpputs $method $dest "    node_labels yes" }
    if {$showLinkLabels == 0} { 
	dumpputs $method $dest "    link_labels no" 
    } else {
	dumpputs $method $dest "    link_labels yes" }
    if {$showAPI == 0} {
	dumpputs $method $dest "    show_api no"
    } else {
	dumpputs $method $dest "    show_api yes" }
    if {$showBkgImage == 0} {
	dumpputs $method $dest "    background_images no"
    } else {
	dumpputs $method $dest "    background_images yes" }
    if {$showAnnotations == 0} {
	dumpputs $method $dest "    annotations no"
    } else {
	dumpputs $method $dest "    annotations yes" }
    if {$showGrid == 0} {
	dumpputs $method $dest "    grid no"
    } else {
	dumpputs $method $dest "    grid yes" }
    if {$g_view_locked == 1} {
	dumpputs $method $dest "    locked yes" }
    if { [info exists g_traffic_start_opt] } {
	dumpputs $method $dest "    traffic_start $g_traffic_start_opt"
    }
    if { [info exists mac_addr_start] && $mac_addr_start > 0 } {
	dumpputs $method $dest "    mac_address_start $mac_addr_start"
    }
    dumpputs $method $dest "\}"
    dumpputs $method $dest ""
}

# get the global options into a list of key=value pairs
proc getGlobalOptionList {} {
    global tmp
    set tmp ""
    dumpGlobalOptions string tmp ;# put "options global {items}" into tmp
    set items [lindex $tmp 2]
    return [listToKeyValues $items]
}

proc setGlobalOption { field value } {
    global showIfNames showNodeLabels showLinkLabels
    global showIfIPaddrs showIfIPv6addrs
    global showBkgImage showGrid showAnnotations
    global showAPI
    global mac_addr_start 
    global g_traffic_start_opt
    global g_view_locked

    switch -exact -- $field {
	interface_names {
	    if { $value == "no" } {
		set showIfNames 0
	    } elseif { $value == "yes" } {
		set showIfNames 1
	    }
	}
	ip_addresses {
	    if { $value == "no" } {
		set showIfIPaddrs 0
	    } elseif { $value == "yes" } {
		set showIfIPaddrs 1
	    }
	}
	ipv6_addresses {
	    if { $value == "no" } {
		set showIfIPv6addrs 0
	    } elseif { $value == "yes" } {
		set showIfIPv6addrs 1
	    }
	}
	node_labels {
	    if { $value == "no" } {
		set showNodeLabels 0
	    } elseif { $value == "yes" } {
		set showNodeLabels 1
	    }
	}
	link_labels {
	    if { $value == "no" } {
		set showLinkLabels 0
	    } elseif { $value == "yes" } {
		set showLinkLabels 1
	    }
	}
	show_api {
	    if { $value == "no" } {
		set showAPI 0
	    } elseif { $value == "yes" } {
		set showAPI 1
	    }
	}
	background_images {
	    if { $value == "no" } {
		set showBkgImage 0
	    } elseif { $value == "yes" } {
		set showBkgImage 1
	    }
	}
	annotations {
	    if { $value == "no" } {
		set showAnnotations 0
	    } elseif { $value == "yes" } {
		set showAnnotations 1
	    }
	}
	grid {
	    if { $value == "no" } {
		set showGrid 0
	    } elseif { $value == "yes" } {
		set showGrid 1
	    }
	}
	locked {
	    if { $value == "yes" } {
		set g_view_locked 1
	    } else {
		set g_view_locked 0
	    }
	}
	mac_address_start {
	    set mac_addr_start  $value
	}
	traffic_start {
	    set g_traffic_start_opt $value
	}
    }
}

# reset global vars when opening a new file
proc cleanupGUIState {} {
    global node_list link_list plot_list canvas_list annotation_list
    global mac_addr_start g_comments
    global g_traffic_flows g_traffic_start_opt g_hook_scripts
    global g_view_locked

    set node_list {}
    set link_list {}
    set annotation_list {}
    set plot_list {}
    set canvas_list {}
    set g_traffic_flows ""
    set g_traffic_start_opt 0
    set g_hook_scripts ""
    set g_comments ""
    set g_view_locked 0
    resetSessionOptions
}

#****f* nodecfg.tcl/loadCfg
# NAME
#   loadCfg -- loads the current configuration.
# SYNOPSIS
#   loadCfg $cfg
# FUNCTION
#   Loads the configuration written in the cfg string to a current 
#   configuration. 
# INPUTS
#   * cfg -- string containing the new working configuration.
#****

proc loadCfg { cfg } {
    global node_list plot_list link_list canvas_list annotation_list
    global g_traffic_flows g_traffic_start_opt g_hook_scripts
    global g_view_locked
    global g_comments

    # maximum coordinates
    set maxX 0
    set maxY 0
    set do_upgrade [upgradeOldConfig cfg]
    if { $do_upgrade == "no"} { return }

    # Cleanup first
    cleanupGUIState
    set class ""
    set object ""
    foreach entry $cfg {
	if {"$class" == ""} {
	    set class $entry
	    continue
	} elseif {"$object" == ""} {
	    set object $entry
	    if {"$class" == "node"} {
		lappend node_list $object
	    } elseif {"$class" == "link"} {
		lappend link_list $object
	    } elseif {"$class" == "canvas"} {
		lappend canvas_list $object
	    } elseif {"$class" == "plot"} {
		lappend plot_list $object
            } elseif {"$class" == "option"} {
		# do nothing
	    } elseif {"$class" == "traffic"} { ;# save traffic flows
		set g_traffic_flows [split [string trim $object] "\n"]
		set class ""; set object ""; continue
	    } elseif {"$class" == "script"} {
		# global_script (old config) becomes a runtime hook
		set name "runtime_hook.sh"
		set script [string trim $object]
		lappend g_hook_scripts [list $name 4 $script] ;# 4=RUNTIME_STATE
		set class ""; set object ""; continue
	    } elseif {"$class" == "hook"} {
		continue
	    } elseif {"$class" == "comments"} {
		set g_comments [string trim $object]
		set class ""; set object ""; continue
	    } elseif {"$class" == "annotation"} {
		lappend annotation_list $object
	    } else {
		puts "configuration parsing error: unknown object class $class"
		#exit 1
	    }
	    # create an empty global variable named object for most objects
	    global $object
	    set $object {}
	    continue
	} else {
	    set line [concat $entry]
	    # uses 'key=value' instead of 'key value'
	    if  { $object == "session" } {
		# 'key=value', values with space needs quoting 'key={space val}'
		setSessionOptions "" [split $line "\n"]
		set class ""
		set object ""
		continue
	    }
	    # extracts "field { value }"  elements from line
	    if { [catch { set tmp [llength $line] } e] } {
		puts "*** Error with line ('$e'):\n$line"
		puts "*** Line will be skipped. This is a Tcl limitation, "
		puts "*** consider using XML or fixing with whitespace."
		continue
	    }
	    while {[llength $line] >= 2} {
		set field [lindex $line 0]
		if {"$field" == ""} {
		    set line [lreplace $line 0 0]
		    continue
		}

		# consume first two list elements from line
		set value [lindex $line 1]
		set line [lreplace $line 0 1]
    
		if {"$class" == "node"} {
		    switch -exact -- $field {
			type {
			    lappend $object "type $value"
			}
			mirror {
			    lappend $object "mirror $value"
			}
			model {
			    lappend $object "model $value"
			}
			cpu {
			    lappend $object "cpu {$value}"
			}
			interface-peer {
			    lappend $object "interface-peer {$value}"
			}
			network-config {
			    set cfg ""
			    foreach zline [split $value {
}] {
				if { [string index "$zline" 0] == "	" } {
				    set zline [string replace "$zline" 0 0]
				}
				lappend cfg $zline
			    }
			    set cfg [lrange $cfg 1 [expr {[llength $cfg] - 2}]]
			    lappend $object "network-config {$cfg}"
			}
			custom-enabled {
			    lappend $object "custom-enabled $value"
			}
			custom-command {
			    lappend $object "custom-command {$value}"
			}
			custom-config {
			    set cfg ""
			    set have_config 0
			    set ccfg {}
			    foreach zline [split $value "\n"] {
				if { [string index "$zline" 0] == \
						"	" } {
				    # remove leading tab character
				    set zline [string replace "$zline" 0 0]
				}

				# flag for config lines
				if { $zline == "config \{" } {
				    set have_config 1
				# collect custom config lines into list
				} elseif { $have_config == 1 } {
				    lappend ccfg $zline
				# add non-config lines
				} else {
				    lappend cfg $zline
				}
  			    }
			    # chop off last brace in config { } block and add it
			    if { $have_config } {
				set ccfg [lrange $ccfg 0 \
					 [expr {[llength $ccfg] - 3}]]
				lappend cfg [list config $ccfg]
			    }
			    #set cfg [lrange $cfg 1 [expr {[llength $cfg] - 2}]]
			    lappend $object "custom-config {$cfg}"
			}
			ipsec-enabled {
			    lappend $object "ipsec-enabled $value"
			}
			ipsec-config {
			    set cfg ""
		
			    foreach zline [split $value {
}] {
				if { [string index "$zline" 0] == "	" } {
				    set zline [string replace "$zline" 0 0]
				}
				lappend cfg $zline
			    }
			    set cfg [lrange $cfg 1 [expr {[llength $cfg] - 2}]]
				lappend $object "ipsec-config {$cfg}"
			}
			iconcoords {
			    checkMaxCoords $value maxX maxY
			    lappend $object "iconcoords {$value}"
			}
			labelcoords {
			    checkMaxCoords $value maxX maxY
			    lappend $object "labelcoords {$value}"
			}
			canvas {
			    lappend $object "canvas $value"
			}
			hidden {
			    lappend $object "hidden $value"
			}
			/* {
			    set comment "$field $value"
			    foreach c $line {
				lappend comment $c
				# consume one element from line
				set line [lreplace $line 0 0]
				if { $c == "*/" } { break }
			    }
			    lappend $object "$comment"
			}

			custom-pre-config-commands {
			    # Boeing - custom pre config commands
			    set cfg ""
			    foreach zline [split $value {}] {
				if { [string index "$zline" 0] == "	" } {
				    set zline [string replace "$zline" 0 0]
				}
				lappend cfg $zline
			    }
			    set cfg [lrange $cfg 1 [expr [llength $cfg] - 2]]
			    lappend $object "custom-pre-config-commands {$cfg}"
		        }
			custom-post-config-commands {
			    # Boeing - custom post config commands
			    set cfg ""
			    foreach zline [split $value {}] {
				if { [string index "$zline" 0] == "	" } {
				    set zline [string replace "$zline" 0 0]
				}
				lappend cfg $zline
			    }
			    set cfg [lrange $cfg 1 [expr [llength $cfg] - 2]]
			    lappend $object "custom-post-config-commands {$cfg}"
		        }
			custom-image {
			    # Boeing - custom-image
			    lappend $object "custom-image $value"
		        }
			ine-config {
			    # Boeing - INE
			    set cfg ""
			    foreach zline [split $value {}] {
				if { [string index "$zline" 0] == "	" } {
				    set zline [string replace "$zline" 0 0]
				}
				lappend cfg $zline
			    }
			    set cfg [lrange $cfg 1 [expr [llength $cfg] - 2]]
			    lappend $object "ine-config {$cfg}"
			}
			tunnel-peer {
			    # Boeing - Span tunnels
			    lappend $object "tunnel-peer {$value}"
		        }
			range {
			    # Boeing - WLAN range
			    lappend $object "range $value"
			}
			bandwidth {
			    # Boeing - WLAN bandwidth
			    lappend $object "bandwidth $value"
			}
			cli-enabled {
			    puts "Warning: cli-enabled setting is deprecated"
			}
			delay {
			    # Boeing - WLAN delay
			    lappend $object "delay $value"
			}
			ber {
			    # Boeing - WLAN BER
			    lappend $object "ber $value"
			}
			location {
			    # Boeing - node location
			    lappend $object "location $value"
			}
			os {
			    # Boeing - node OS
			    # just ignore it, set at runtime
			}
			services {
			    lappend $object "services {$value}"
			}

			default {
			    # Boeing - added warning
			    puts -nonewline "config file warning: unknown confi"
			    puts "guration item '$field' ignored for $object"
			}
		    }
		} elseif {"$class" == "plot"} {
		    switch -exact -- $field {
		  	name {
			    lappend $object "name $value"
			}	
			height {
			    lappend $object "height $value"
			}
 			width {
			    lappend $object "width $value"
			}
			x {
			    lappend $object "x $value"
			}
			y {
			    lappend $object "y $value"
			}
 			color {	
			    lappend $object "color $value"
			} 
 		    } 
                } elseif {"$class" == "link"} {
		    switch -exact -- $field {
			nodes {
			    lappend $object "nodes {$value}"
			}
			mirror {
			    lappend $object "mirror $value"
			}
			bandwidth -
			delay -
			ber -
			duplicate -
			jitter {
			    if { [llength $value] > 1 } { ;# down/up-stream
				lappend $object "$field {$value}"
			    } else {
				lappend $object "$field $value"
			    }
			}
			color {
			    lappend $object "color $value"
			}
			width {
			    lappend $object "width $value"
			}
			default {
			    # this enables opaque data to be stored along with
			    # each link (any key is stored)
			    lappend $object "$field $value"
			    # Boeing - added warning
			    #puts -nonewline "config file warning: unknown conf"
			    #puts "iguration item '$field' ignored for $object"
			}
		    }
		} elseif {"$class" == "canvas"} {
		    switch -exact -- $field {
			name {
			    lappend $object "name {$value}"
			}
			size {
			    lappend $object "size {$value}"
			}
			bkgImage {
			    lappend $object "wallpaper {$value}"
			}
			wallpaper {
			    lappend $object "wallpaper {$value}"
			}
			wallpaper-style {
			    lappend $object "wallpaper-style {$value}"
			}
			scale {
			    lappend $object "scale {$value}"
			}
			refpt {
			    lappend $object "refpt {$value}"
			}
		    }
		} elseif {"$class" == "option"} {
		    setGlobalOption $field $value
		} elseif {"$class" == "annotation"} {
		    switch -exact -- $field {
			type {
			    lappend $object "type $value"
			}
			iconcoords {
			    lappend $object "iconcoords {$value}"
			}
			color {
			    lappend $object "color $value"
			}
			border {
			    lappend $object "border $value"
			}
			label {
			    lappend $object "label {$value}"
			}
			labelcolor {
			    lappend $object "labelcolor $value"
			}
			size {
			    lappend $object "size $value"
			}
			canvas {
			    lappend $object "canvas $value"
			}
			font {
			    lappend $object "font {$value}"
			}
			fontfamily {
			    lappend $object "fontfamily {$value}"
			}
			fontsize {
			    lappend $object "fontsize {$value}"
			}
			effects {
			    lappend $object "effects {$value}"
			}
			width {
			    lappend $object "width $value"
			}
			rad {
			    lappend $object "rad $value"
			}
		    } ;# end switch
		} elseif {"$class" == "hook"} {
		    set state_name [split $object :]
		    if { [llength $state_name] != 2 } {
			puts "invalid hook in config file"
			continue
		    }
		    set state [lindex $state_name 0]
		    set name [lindex $state_name 1]
		    set lines [split $entry "\n"]
		    set lines [lreplace $lines 0 0] ;# chop extra newline
		    set lines [join $lines "\n"]
		    set hook [list $name $state $lines]
		    lappend g_hook_scripts $hook
		    set line "" ;# exit this while loop
		} ;#endif class
	    }
	}
	set class ""
	set object ""
    }

    #
    # Hack for comaptibility with old format files (no canvases)
    #
    if { $canvas_list == "" } {
	set curcanvas [newCanvas ""]
	foreach node $node_list {
	    setNodeCanvas $node $curcanvas
	}
    }


    # auto resize canvas
    set curcanvas [lindex $canvas_list 0]
    set newX 0
    set newY 0
    if { $maxX > [lindex [getCanvasSize $curcanvas] 0] } {
	set newX [expr {$maxX + 50}]
    }
    if { $maxY > [lindex [getCanvasSize $curcanvas] 1] } {
	set newY [expr {$maxY + 50}]
    }
    if { $newX > 0 || $newY > 0 } {
    	if { $newX == 0 } { set newX [lindex [getCanvasSize $curcanvas] 0] }
    	if { $newY == 0 } { set newY [lindex [getCanvasSize $curcanvas] 1] }
	setCanvasSize $curcanvas $newX $newY
    }

    # extra upgrade steps
    if { $do_upgrade == "yes" } {
	upgradeNetworkConfigToServices
    }
    upgradeConfigRemoveNode0
    upgradeConfigServices
    upgradeWlanConfigs
}

#****f* nodecfg.tcl/newObjectId
# NAME
#   newObjectId -- new object Id 
# SYNOPSIS
#   set obj_id [newObjectId $type]
# FUNCTION
#   Returns the Id for a new object of the defined type. Supported types
#   are node, link and canvas. The Id is in the form $mark$number. $mark is the 
#   first letter of the given type and $number is the first available number to
#   that can be used for id. 
# INPUTS
#   * type -- the type of the new object. Can be node, link or canvas.
# RESULT
#   * obj_id -- object Id in the form $mark$number. $mark is the 
#   first letter of the given type and $number is the first available number to
#   that can be used for id. 
#****

proc newObjectId { type } {
    global node_list link_list annotation_list canvas_list

    set mark [string range [set type] 0 0]
    set id 1 ;# start numbering at 1, not 0
    while {[lsearch [set [set type]_list] "$mark$id"]  != -1} {
	incr id
    }
    return $mark$id
}



# Boeing: pick a new link id for temporary newlinks
proc newlinkId { } {
    global link_list
    set id [newObjectId link]
    set mark "l"
    set id 0

    # alllinks contains a list of all existing and new links
    set alllinks $link_list
    foreach newlink [.c find withtag "newlink"] {
    	set newlinkname [lindex [.c gettags $newlink] 1]
    	lappend alllinks $newlinkname
    }

    while {[lsearch $alllinks "$mark$id"] != -1 } {
	incr id
    }
    return $mark$id
}

# Boeing: helper fn to determine canvas size during load
proc checkMaxCoords { str maxXp maxYp } {
    upvar 1 $maxXp maxX
    upvar 1 $maxYp maxY
    set x [lindex $str 0]
    set y [lindex $str 1]
    if { $x > $maxX } {
	set maxX $x
    }
    if { $y > $maxY } {
	set maxY $y
    }
    if { [llength $str] == 4 } {
	set x [lindex $str 2]
	set y [lindex $str 3]
	if { $x > $maxX } {
	    set maxX $x
	}
	if { $y > $maxY } {
	    set maxY $y
	}
    }
}

# Boeing: pick a router for OSPF
proc newRouterId { type node } {
    set mark [string range [set type] 0 0]
    for { set id 0 } { $node != "$mark$id" } { incr id } {
    }
    return "0.0.0.${id}"
}
# end Boeing

# Boeing: load servers.conf file into exec_servers array
proc loadServersConf { } {
    global CONFDIR exec_servers DEFAULT_API_PORT
    set confname "$CONFDIR/servers.conf"
    if { [catch { set f [open "$confname" r] } ] } {
	puts "Creating a default $confname" 
	if { [catch { set f [open "$confname" w+] } ] } {
	    puts "***Warning: could not create a default $confname file."
	    return
	}
	puts $f "core1 192.168.0.2 $DEFAULT_API_PORT"
	puts $f "core2 192.168.0.3 $DEFAULT_API_PORT"
	close $f
    	if { [catch { set f [open "$confname" r] } ] } {
	    return
	}
    }

    array unset exec_servers

    while { [ gets $f line ] >= 0 } {
	if { [string range $line 0 0] == "#" } { continue } ;# skip comments
	set l [split $line] ;# parse fields separated by whitespace
	set name [lindex $l 0]
	set ip   [lindex $l 1]
	set port [lindex $l 2]
	set sock -1
	if { $name == "" } { continue } ;# blank name
	# load array of servers
	array set exec_servers [list $name [list $ip $port $sock]]
    }
    close $f
}
# end Boeing

# Boeing: write servers.conf file from exec_servers array
proc writeServersConf { } {
    global CONFDIR exec_servers
    set confname "$CONFDIR/servers.conf"
    if { [catch { set f [open "$confname" w] } ] } {
	puts "***Warning: could not write servers file: $confname"
	return
    }

    set header "# servers.conf: list of CORE emulation servers for running"
    set header "$header remotely."
    puts $f $header
    foreach server [lsort -dictionary [array names exec_servers]] {
	set ip   [lindex $exec_servers($server) 0]
	set port [lindex $exec_servers($server) 1]
	puts $f "$server $ip $port"
    }
    close $f
}
# end Boeing

# display the preferences dialog
proc popupPrefs {} {
    global EDITORS TERMS

    set wi .core_prefs
    catch { destroy $wi }
    toplevel $wi

    wm transient $wi .
    wm resizable $wi 0 0
    wm title $wi "Preferences"

    global g_prefs g_prefs_old
    array set g_prefs_old [array get g_prefs]

    #
    # Paths
    #
    labelframe $wi.dirs -borderwidth 4 -text "Paths" -relief raised
    frame $wi.dirs.conf
    label $wi.dirs.conf.label -text "Default configuration file path:"
    entry $wi.dirs.conf.entry -bg white -width 40 \
	-textvariable g_prefs(default_conf_path)
    pack $wi.dirs.conf.label $wi.dirs.conf.entry -side left
    pack $wi.dirs.conf -side top -anchor w -padx 4 -pady 4

    frame $wi.dirs.mru
    label $wi.dirs.mru.label -text "Number of recent files to remember:"
    entry $wi.dirs.mru.num -bg white -width 3 \
	-textvariable g_prefs(num_recent)
    button $wi.dirs.mru.clear -text "Clear recent files" \
	-command "addFileToMrulist \"\""
    pack $wi.dirs.mru.label $wi.dirs.mru.num $wi.dirs.mru.clear -side left
    pack $wi.dirs.mru -side top -anchor w -padx 4 -pady 4
    
    pack $wi.dirs -side top -fill x

    #
    # Window
    #
    labelframe $wi.win -borderwidth 4 -text "GUI Window" -relief raised
    frame $wi.win.win
    checkbutton $wi.win.win.savepos -text "remember window position" \
	-variable g_prefs(gui_save_pos)
    checkbutton $wi.win.win.savesiz -text "remember window size" \
	-variable g_prefs(gui_save_size)
    pack $wi.win.win.savepos $wi.win.win.savesiz -side left -anchor w -padx 4
    pack $wi.win.win -side top -anchor w -padx 4 -pady 4
 
    frame $wi.win.a
    checkbutton $wi.win.a.snaptogrid -text "snap to grid" \
	-variable g_prefs(gui_snap_grid)
    checkbutton $wi.win.a.showtooltips -text "show tooltips" \
	-variable g_prefs(gui_show_tooltips)
    pack $wi.win.a.snaptogrid $wi.win.a.showtooltips \
	-side left -anchor w -padx 4
    pack $wi.win.a -side top -anchor w -padx 4 -pady 4

    frame $wi.win.canv
    label $wi.win.canv.label -text "Default canvas size:"
    entry $wi.win.canv.x -bg white -width 5 -textvariable g_prefs(gui_canvas_x)
    entry $wi.win.canv.y -bg white -width 5 -textvariable g_prefs(gui_canvas_y)
    label $wi.win.canv.label2 -text "Default # of canvases:"
    entry $wi.win.canv.num -bg white -width 5 \
	-textvariable g_prefs(gui_num_canvases)
    pack $wi.win.canv.label $wi.win.canv.x $wi.win.canv.y \
	$wi.win.canv.label2 $wi.win.canv.num \
	-side left -anchor w -padx 4
    pack $wi.win.canv -side top -anchor w -padx 4 -pady 4
    pack $wi.win -side top -fill x

    #
    # Programs
    #
    labelframe $wi.pr -borderwidth 4 -text "Programs" -relief raised

    frame $wi.pr.editor
    label $wi.pr.editor.label -text "Text editor:"
    set editors [linsert $EDITORS 0 "EDITOR"]
    ttk::combobox $wi.pr.editor.combo -width 10 -exportselection 0 \
    	-values $editors -textvariable g_prefs(gui_text_editor)
    label $wi.pr.editor.label2 -text "Terminal program:"
    set terms [linsert $TERMS 0 "TERM"]
    ttk::combobox $wi.pr.editor.combo2 -width 20 -exportselection 0 \
    	-values $terms -textvariable g_prefs(gui_term_prog)
    pack $wi.pr.editor.label $wi.pr.editor.combo -padx 4 -pady 4 -side left
    pack $wi.pr.editor.label2 $wi.pr.editor.combo2 -padx 4 -pady 4 -side left
    pack $wi.pr.editor -side top -anchor w -padx 4 -pady 4

    frame $wi.pr.3d
    label $wi.pr.3d.label -text "3D GUI command:"
    entry $wi.pr.3d.entry -bg white -width 40 -textvariable g_prefs(gui_3d_path)
    pack $wi.pr.3d.label $wi.pr.3d.entry -side left -padx 4 -pady 4
    pack $wi.pr.3d -side top -anchor w -padx 4 -pady 4

    pack $wi.pr -side top -fill x

    #
    # Buttons at the bottom
    #
    frame $wi.bot -borderwidth 0
    button $wi.bot.apply -text "Save" -command "savePrefsFile; destroy $wi"
    button $wi.bot.defaults -text "Load defaults" -command initDefaultPrefs
    button $wi.bot.cancel -text "Cancel" -command {
	global g_prefs g_prefs_old
	array set g_prefs [array get g_prefs_old]
	destroy .core_prefs
    }
    pack $wi.bot.cancel $wi.bot.defaults $wi.bot.apply -side right
    pack $wi.bot -side bottom -fill x
    after 100 {
    	catch { grab .core_prefs }
    }
}

# initialize preferences array with default values
proc initDefaultPrefs {} {
    global g_prefs CONFDIR SBINDIR DEFAULT_REFPT tcl_platform

    # variable expansions must be done here
    array set g_prefs [list default_conf_path	"$CONFDIR/configs"]
    array set g_prefs [list gui_canvas_refpt	"$DEFAULT_REFPT"]
    if { $tcl_platform(os) == "FreeBSD" } { set shell "/usr/local/bin/bash"
    } else { set shell "bash" }
    array set g_prefs [list shell $shell] 
    array set g_prefs [list gui_text_editor	[get_text_editor true]]
    array set g_prefs [list gui_term_prog	[get_term_prog true]]
    setDefaultAddrs ipv4
    setDefaultAddrs ipv6
    # preferences will be reordered alphabetically
    array set g_prefs {
	num_recent		4
	log_path		"/tmp/core_logs"
	gui_save_pos		0
	gui_save_size		0
	gui_snap_grid		0
	gui_show_tooltips	1
	gui_canvas_x		1000
	gui_canvas_y		750
	gui_canvas_scale	150.0
	gui_num_canvases	1
	gui_3d_path		"/usr/local/bin/sdt3d.sh"
    }
    # add new preferences above; keep this at the end of the file
}


