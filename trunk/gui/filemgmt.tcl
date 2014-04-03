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


##****h* imunes/filemgmt.tcl
# NAME
#  filemgmt.tcl -- file used for manipulation with files
# FUNCTION
#  This module is used for all file manipulations. In this file 
#  a file is read, a new file opened or existing file saved.
# NOTES
# variables:
# 
# currentFile
#    relative or absolute path to the current configuration file
# 
# fileTypes
#    types that will be displayed when opening new file 
#
# procedures used for loading and storing the configuration file:
#
# newFile 
#   - creates an empty project
#
# openFile
#   - loads configuration from currentFile   
#
# saveFile {selectedFile} 
#   - saves current configuration to a file named selectedFile 
#     unless the file name is an empty string
#
# fileOpenStartUp
#   - opens the file named as command line argument
# 
# fileNewDialogBox
#   - opens message box to optionally save the changes 
#
# fileOpenDialogBox
#   - opens dialog box for selecting a file to open
#
# fileSaveDialogBox
#   - opens dialog box for saving a file under new name if there is no
#     current file 
#****

set currentFile ""

set fileTypes {
    { "CORE scenario files" {.xml .imn} }
    { "CORE/IMUNES network configuration" {.imn} }
    { "EmulationScript XML files" {.xml} }
    { "All files" {*} }
}


#****f* filemgmt.tcl/newFile
# NAME
#   newFile -- new file
# SYNOPSIS
#   newFile
# FUNCTION
#   Loads an empty configuration, i.e. creates an empty project.
#****
proc newFile {} {
    global currentFile canvas_list curcanvas
    global g_prefs oper_mode showGrid systype
    global g_current_session g_view_locked

    if { [popupStopSessionPrompt]=="cancel" } {
	return
    }
    set showGrid 1
    set g_view_locked 0

    # flush daemon configuration
    if { [llength [findWlanNodes ""]] > 0 } {
	if { [lindex $systype 0] == "FreeBSD" } {
	    catch { exec ngctl config wlan_ctl: flush=all }
	}
    }
    loadCfg ""
    resetGlobalVars newfile
    set curcanvas [lindex $canvas_list 0]
    set num_canvases $g_prefs(gui_num_canvases)
    while { $num_canvases > 1 } { newCanvas ""; incr num_canvases -1 }
    switchCanvas none
    redrawAll
    set currentFile ""
    set emulp [getEmulPlugin "*"]
    set name [lindex $emulp 0]
    set sock [lindex $emulp 2]
    # reset node services info
    if { $sock != -1 && $sock != "" } { sendNodeTypeInfo $sock 1 }
    if { $oper_mode == "exec" } {
	setOperMode edit
	set g_current_session 0
    }
    # disconnect and get a new session number
    if { $name != "" } {
	pluginConnect $name disconnect 1
	pluginConnect $name connect 1
    }
    setGuiTitle ""
}


#****f* filemgmt.tcl/openFile
# NAME
#   openFile -- open file
# SYNOPSIS
#   openFile
# FUNCTION
#   Loads the configuration from the file named currentFile.
#****
proc openFile {} {
    global currentFile 
    global undolog activetool
    global canvas_list curcanvas systype
    global changed
    
    if { [lindex [file extension $currentFile] 0] == ".py" } {
	set flags 0x10 ;# status request flag
	sendRegMessage -1 $flags [list "exec" $currentFile]
	addFileToMrulist $currentFile
	return
    }
    if { [file extension $currentFile] == ".xml" } {
	setGuiTitle ""
	cleanupGUIState
	resetGlobalVars openfile
	xmlFileLoadSave "open" $currentFile
	addFileToMrulist $currentFile
	return
    }
    set fileName [file tail $currentFile]
    # flush daemon configuration
    if { [llength [findWlanNodes ""]] > 0 } {
	if { [lindex $systype 0] == "FreeBSD" } {
	    catch { exec ngctl config wlan_ctl: flush=all }
	}
    }
    set cfg ""
    if { [catch { set fileId [open $currentFile r] } err] } {
	puts "error opening file $currentFile: $err"
	return
    }
    if { [catch { foreach entry [read $fileId] { lappend cfg $entry; }} err] } {
    	puts "error reading config file $currentFile: $err"
	close $fileId
	return
    }
    close $fileId
    setGuiTitle ""
    loadCfg $cfg
    set curcanvas [lindex $canvas_list 0]
    switchCanvas none
    # already called from switchCanvas: redrawAll
    resetGlobalVars openfile
    set undolog(0) $cfg 
    set activetool select

    # remember opened files
    set changed 0
    addFileToMrulist $currentFile
}

#
# helper to reset global state
#
proc resetGlobalVars { reason } {
    global undolevel redolevel

    set undolevel 0
    set redolevel 0
}


#****f* filemgmt.tcl/saveFile
# NAME
#   saveFile -- save file
# SYNOPSIS
#   saveFile $selectedFile
# FUNCTION
#   Loads the current configuration into the selectedFile file.
# INPUTS
#   * selectedFile -- the name of the file where current 
#   configuration is saved.
#****
proc saveFile { selectedFile } {
    global currentFile 
    global changed

    if { $selectedFile == ""} {
	return
    }
    set currentFile $selectedFile
    set fileName [file tail $currentFile]
    if { [file extension $selectedFile] == ".xml" } {
	xmlFileLoadSave save $selectedFile
    } elseif { [file extension $selectedFile] == ".py" } {
	set msg "Python script files cannot be saved by the GUI."
	set msg "$msg\nUse File > Export Python script... for export."
	tk_messageBox -type ok -icon warning -message $msg -title "Error"

    } else {
	set fileId [open $currentFile w]
	dumpCfg file $fileId
	close $fileId
    }
    setGuiTitle ""
    .bottom.textbox config -text "Saved $fileName"

    set changed 0
    # remember saved file
    addFileToMrulist $currentFile
}


#****f* filemgmt.tcl/fileOpenStartUp
# NAME
#   fileOpenStartUp -- file open in batch mode
# SYNOPSIS
#   fileOpenStartUp
# FUNCTION
#   Loads configuration from batch input file to the current 
#   configuration.
#****
proc fileOpenStartUp {} {
    global argv
    global currentFile

    # Boeing
    foreach arg $argv {
	if { $arg != "" && $arg != "--start" && $arg != "--batch" } {
	    set currentFile [argAbsPathname $arg]
	    openFile
	    break
	}
    }
    # end Boeing
}


#****f* filemgmt.tcl/fileNewDialogBox
# NAME
#   fileNewDialogBox -- save changes dialog box
# SYNOPSIS
#   fileNewDialogBox
# FUNCTION
#   Opens message box to optionally save the changes.
#****
proc fileNewDialogBox {} {
    global currentFile
    # Boeing: simplified using promptForSave procedure
    global changed
    set choice "yes"

    # Prompt for save if file was changed
    if  {$changed != 0 } {
	set choice [promptForSave]
    }
    
    if { $choice != "cancel"} {
	newFile
    }
}


#****f* filemgmt.tcl/fileOpenDialogBox
# NAME
#   fileOpenDialogBox -- open file dialog box
# SYNOPSIS
#   fileOpenDialogBox
# FUNCTION
#   Opens a open file dialog box.
#****
set fileDialogBox_initial 0; # static flag
proc fileOpenDialogBox {} {
    global currentFile fileTypes g_prefs fileDialogBox_initial

    # use default conf file path upon first run
    if { $fileDialogBox_initial == 0} {
	set fileDialogBox_initial 1
	set dir $g_prefs(default_conf_path)
        set selectedFile [tk_getOpenFile -filetypes $fileTypes -initialdir $dir]
    } else {
    # otherwise user may have changed dirs, do not use default conf path
        set selectedFile [tk_getOpenFile -filetypes $fileTypes]
    }
    if { $selectedFile != ""} {
	set currentFile $selectedFile
	openFile
    }
}


#****f* filemgmt.tcl/fileSaveDialogBox
# NAME
#   fileSaveDialogBox -- save file dialog box
# SYNOPSIS
#   fileSaveDialogBox
# FUNCTION
#   Opens dialog box for saving a file under new name if there is no
#   current file.
#****
proc fileSaveDialogBox { prompt } {
    global currentFile fileTypes g_prefs fileDialogBox_initial


    # save without prompting
    if { $prompt == "" && $currentFile != "" } {
	saveFile $currentFile
	return "yes"
    }

    if { $prompt == "" } { set prompt "imn" } ;# File->Save w/no file yet
    set ft [lrange $fileTypes 1 end]
    if { $prompt == "xml" } { ;# swap imn/xml file types
	set imn [lindex $ft 0]
	set ft [lreplace $ft 0 0]
	set ft [linsert $ft 1 $imn]
    }
   
    set dir ""
    # use default conf file path upon first run
    if { $fileDialogBox_initial == 0} {
	set fileDialogBox_initial 1
	set dir $g_prefs(default_conf_path)
    }
    set initf "untitled"
    if { $currentFile != "" } {
	set dir [file dirname $currentFile]
	set initf [file tail $currentFile]
	if { [file extension $initf] != $prompt } { ;# update file extension
	    set initf "[file rootname $initf].$prompt"
	}
    }

    if { $dir == "" } {
	set selectedFile [tk_getSaveFile -filetypes $ft -initialfile $initf]
    } else {
	set selectedFile [tk_getSaveFile -filetypes $ft -initialfile $initf \
				-initialdir $dir]
    }
    if { $selectedFile == "" } {
	return "cancel"
    }
    saveFile $selectedFile
    return "yes"
}


#****f* filemgmt.tcl/relpath
# NAME
#   relpath -- return background image filename relative to configuration file
# SYNOPSIS
#   relpath bkgImageFilename
# FUNCTION
#   Returns relative pathname
#
#***
#####
# Some examples
# puts [relpath /root/imunes/labos.imn /root/EXAMPLES/labos.gif]
# ../EXAMPLES/labos.gif
# puts [relpath /root/EXAMPLES/labos.imn /root/EXAMPLES/labos.gif]
# ./labos.gif

proc relpath {target} {
    global currentFile
    set basedir $currentFile
    # Try and make a relative path to a target file/dir from base directory
    set bparts [file split [file normalize $basedir]]
    set tparts [file split [file normalize $target]]

    if {[lindex $bparts 0] eq [lindex $tparts 0]} {
	# If the first part doesn't match - there is no good relative path
	set blen [expr {[llength $bparts] - 1}]
	set tlen [llength $tparts]
	for {set i 1} {$i < $blen && $i < $tlen} {incr i} {
	    if {[lindex $bparts $i] ne [lindex $tparts $i]} { break }
	}
	set path [lrange $tparts $i end]
	for {} {$i < $blen} {incr i} {
	    set path [linsert $path 0 ..]
	}
	# Full name:
	# [file normalize [join $path [file separator]]]
	# Relative file name:
	return [join $path [file separator]]
    }
    return $target
}


# read user preferences from ~/.core/prefs.conf file
proc loadDotFile {} {
    global CONFDIR g_mrulist g_prefs

    set isfile 0
    if {[catch {set dotfile [open "$CONFDIR/prefs.conf" r]} ]} return
    close $dotfile
 
    if {[catch { source "$CONFDIR/prefs.conf" }]} {
	puts "The $CONFDIR/prefs.conf preferences file is invalid, ignoring it."
	#file delete "~/.core"
	return
    }
}

# save user preferences to ~/.core/prefs.conf config file
proc savePrefsFile { } {
    global CONFDIR g_mrulist g_prefs CORE_VERSION
    if {[catch {set dotfile [open "$CONFDIR/prefs.conf" w]} ]} {
	puts "Unable to save preferences to $CONFDIR/prefs.conf"
	return
    }

    # header
    puts $dotfile "# CORE ${CORE_VERSION} GUI preference file"
 
    # save the most-recently-used file list
    puts $dotfile "set g_mrulist \"$g_mrulist\""

    # save preferences
    puts $dotfile "array set g_prefs {"
    foreach pref [lsort -dict [array names g_prefs]] {
	set value $g_prefs($pref)
        set tabs "\t\t"
	if { [string length $pref] >= 16 } { set tabs "\t" }
	puts $dotfile "\t$pref$tabs\"$value\""
    }
    puts $dotfile "}"
    close $dotfile
}

# helper for most-recently-used file list menu items
proc mrufile { f args } {
    global currentFile
    set currentFile [string trim "$f $args"]
    openFile
}

# add filename to the most-recently-used file list
# if it exists already, remove it from the list, add to the front; also limit
# the length of this list; if no file specified, erase the list
proc addFileToMrulist { f } {
    global g_mrulist g_prefs
    set MRUI 14 ;# index of MRU list -- update when adding to File menu!

    set oldlength [llength $g_mrulist]
    set maxlength $g_prefs(num_recent)
    if { $maxlength < 1 } { set maxlength 4 }
    set existing [lsearch $g_mrulist $f]
    if { $existing > -1 } {
        set g_mrulist [lreplace $g_mrulist $existing $existing]
    }

    # clear the MRU list menu
    if { $oldlength > 0 } {
	set end_of_menu [.menubar.file index end]
	.menubar.file delete $MRUI [expr {$end_of_menu - 2}]
    }
    if { $f == "" } { ;# used to reset MRU list
	set g_mrulist {}
	return
    }

    set g_mrulist [linsert $g_mrulist 0 "$f"]
    set g_mrulist [lrange $g_mrulist 0 [expr {$maxlength - 1}]]

    set i $MRUI
    foreach f $g_mrulist {
    	.menubar.file insert $i command -label "$f" -command "mrufile $f"
	incr i 1
    }
}

# prompt to terminate experiment
proc popupStopSessionPrompt { } {
    global oper_mode

    if { ![info exists oper_mode] || $oper_mode != "exec" } {
	return "no"
    }
    set choice [tk_messageBox -type yesnocancel -default yes \
		-message "Stop the running session?" -icon question]
    if { $choice == "yes" } {
	setOperMode edit
    }
    return $choice
}

# Boeing: cleanup on exit
rename exit exit.real
proc exit {} {
    global changed g_prefs systype oper_mode

    if { ![info exists oper_mode] } { ;# batch mode
	exit.real
    }

    if { [popupStopSessionPrompt]=="cancel" } {
	return
    }
    # Flush daemon configuration
    if { [lindex $systype 0] == "FreeBSD" } {
	catch { exec ngctl config wlan_ctl: flush=all }
    }
    # Prompt for save if file was changed
    if  { $changed != 0 && [promptForSave] == "cancel" } {
	return
    }
    # save window size and position
    set geo [wm geometry .]
    if { $g_prefs(gui_save_pos) } {
	set split_idx [string first "-" $geo]
	incr split_idx
	set pos [string range $geo $split_idx end]
	array set g_prefs "gui_window_pos $pos"
    } else {
	array unset g_prefs gui_window_pos
    }
    if { $g_prefs(gui_save_size) } {
	set split_idx [string first "-" $geo]
	incr split_idx -1
	set size [string range $geo 0 $split_idx]
	array set g_prefs "gui_window_size $size"
    } else {
	array unset g_prefs gui_window_size
    }

    # save user preferences
    savePrefsFile
    
    exit.real
}

# returns yes/no/cancel
proc promptForSave {} {
    set choice [tk_messageBox -type yesnocancel -default yes \
	    -message "File changed: Save?" -icon question ]

    if { $choice == "yes" } {
	# choice becomes cancel or yes
	set choice [fileSaveDialogBox true]
    }
    return $choice
}

# allow filenames in .imn files to contain special variables CORE_DATA_DIR
# (formerly LIBDIR for icons) and CONFDIR
# convert relative pathname to absolute using imn filename
proc absPathname { f } {
    global CORE_DATA_DIR CONFDIR currentFile
    if { $f == "" } { return $f }
    regsub -all {\$LIBDIR} $f $CORE_DATA_DIR f
    regsub -all {\$CORE_DATA_DIR} $f $CORE_DATA_DIR f
    regsub -all {\$CONFDIR} $f $CONFDIR f
    if { [file pathtype $f] == "relative" && $currentFile != "" } {
	set abspath [list [file dirname $currentFile] $f]
	set f [join $abspath [file separator]]
    }
    return $f
}

# convert relative path passed in as program argument to absolute path
proc argAbsPathname { f } {
    global CORE_START_DIR
    if { $f != "" && $CORE_START_DIR != "" && \
	 [file pathtype $f] == "relative" } {
	set abspath [list $CORE_START_DIR $f]
	set f [join $abspath [file separator]]
    }
    return $f
}

# set the main CORE GUI window title
proc setGuiTitle { txt } {
    global currentFile g_current_session
    set hn [info hostname] ;# may want to limit string length to 8 here
    set fn [file tail $currentFile]
    set sid $g_current_session

    global execMode
    if { $execMode != "interactive"} { return } ; # batch mode

    if {$sid == 0} { set sid "" } else { set sid "${sid} " }

    if { $txt == "" } {
	wm title . "CORE (${sid}on $hn) $fn"
    } else {
	wm title . "CORE $txt"
    }
}
