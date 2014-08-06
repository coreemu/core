#
# Copyright 2005-2013 the Boeing Company.
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

if {[lindex $argv 0] == "-b" || [lindex $argv 0] == "--batch"} {
    set argv [lrange $argv 1 end]
    set execMode batch
} elseif {[lindex $argv 0] == "-c" || [lindex $argv 0] == "--closebatch"} {
    set argv [lrange $argv 1 end]
    set execMode closebatch
} elseif {[lindex $argv 0] == "--addons"} {
    set argv [lrange $argv 1 end]
    set execMode addons
} else {
    set execMode interactive
}

set LIBDIR ""
set SBINDIR "/usr/local/sbin"
set CONFDIR "."
set CORE_DATA_DIR "."
set CORE_STATE_DIR "."
set CORE_START_DIR ""
set CORE_USER ""
if { [info exists env(LIBDIR)] } {
    set LIBDIR $env(LIBDIR)
}
if { [info exists env(SBINDIR)] } {
    set SBINDIR $env(SBINDIR)
}
if { [info exists env(CONFDIR)] } {
    set CONFDIR $env(CONFDIR)
}
if { [info exists env(CORE_DATA_DIR)] } {
    set CORE_DATA_DIR $env(CORE_DATA_DIR)
}
if { [info exists env(CORE_STATE_DIR)] } {
    set CORE_STATE_DIR $env(CORE_STATE_DIR)
}
if { [info exists env(CORE_START_DIR)] } {
    set CORE_START_DIR $env(CORE_START_DIR)
}
if { [info exists env(CORE_USER)] } {
    set CORE_USER $env(CORE_USER)
}

source "$LIBDIR/version.tcl"

source "$LIBDIR/linkcfg.tcl"
source "$LIBDIR/nodecfg.tcl"
source "$LIBDIR/ipv4.tcl"
source "$LIBDIR/ipv6.tcl"
source "$LIBDIR/cfgparse.tcl"
source "$LIBDIR/exec.tcl"
source "$LIBDIR/canvas.tcl"

source "$LIBDIR/editor.tcl"
source "$LIBDIR/annotations.tcl"

source "$LIBDIR/help.tcl"
source "$LIBDIR/filemgmt.tcl"

source "$LIBDIR/ns2imunes.tcl"


source "$LIBDIR/mobility.tcl"
source "$LIBDIR/api.tcl"
source "$LIBDIR/wlan.tcl"
source "$LIBDIR/wlanscript.tcl"
source "$LIBDIR/util.tcl"
source "$LIBDIR/plugins.tcl"
source "$LIBDIR/nodes.tcl"
source "$LIBDIR/services.tcl"
source "$LIBDIR/traffic.tcl"
source "$LIBDIR/exceptions.tcl"

#
# Global variables are initialized here
#
set node_list {}
set link_list {}
set annotation_list {}
set canvas_list {}
set eid e0
set plot_list {}
array set exec_servers {}
loadServersConf ;# populate exec_servers

# global vars
set showAPI 0
set mac_byte4 0
set mac_byte5 0
set g_mrulist {}
initDefaultPrefs
loadDotFile
loadPluginsConf
checkCommandLineAddressPort
autoConnectPlugins


#
# Initialization should be complete now, so let's start doing something...
#

if {$execMode == "interactive"} {
    # GUI-related files
    source "$LIBDIR/widget.tcl"
    source "$LIBDIR/tooltips.tcl"
    source "$LIBDIR/initgui.tcl"
    source "$LIBDIR/topogen.tcl"
    source "$LIBDIR/graph_partitioning.tcl"
    source "$LIBDIR/gpgui.tcl"
    source "$LIBDIR/debug.tcl"
    # Load all Tcl files from the addons directory
    foreach file [glob -nocomplain -directory "$LIBDIR/addons" *.tcl] {
	if { [catch { if { [file isfile $file ] } { source "$file"; } } e] } {
	    puts "*** Error loading addon file: $file"
	    puts "    $e"
	}
    }
    setOperMode edit
    fileOpenStartUp 
    foreach arg $argv {
        if { $arg == "--start" } {
	    global currentFile
	    if { [file extension $currentFile] == ".xml" } {
		after 100; update; # yield to other events so XML file
		after 100; update; # can be loaded and received
	    }
	    startStopButton "exec"; break;
	}
    }
# Boeing changed elseif to catch batch and else to output error
} elseif {$execMode == "batch"} {
    puts "batch execute $argv"
    set sock [lindex [getEmulPlugin "*"] 2]
    if { $sock == "" || $sock == "-1" || $sock == -1 } { exit.real; }
    if {$argv != ""} {
	global currentFile
	set currentFile [argAbsPathname $argv]
	set fileId [open $currentFile r]
	set cfg ""
	foreach entry [read $fileId] {
	    lappend cfg $entry
	}
	close $fileId
	after 100 {
	    loadCfg $cfg
	    deployCfgAPI $sock
	    puts "waiting to enter RUNTIME state..."
	}
	global vwaitdummy
	vwait vwaitdummy
    }
} elseif {$execMode == "closebatch"} {
	global g_session_choice
	set g_session_choice $argv
	puts "Attempting to close session $argv ..."
	global vwaitdummy
	vwait vwaitdummy
} elseif {$execMode == "addons"} {
    # pass control to included addons code
    foreach file [glob -nocomplain -directory "$LIBDIR/addons" *.tcl] {
	if { [file isfile $file ] } { source "$file"; }
    }
    global vwaitdummy
    vwait vwaitdummy
} else {
    puts "ERROR: execMode is not set in core.tcl"
}

