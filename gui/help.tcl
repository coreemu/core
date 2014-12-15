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
# and Technology through the research contracts #IP-2003-143 and #IP-2004-154.
#

#****h* imunes/help.tcl
# NAME
#  help.tcl -- file used for help infromation
# FUNCTION
#  This file is considered to contain all the help information.
#  Currently it contains only copyright information.
#****

set copyright {

Copyright 2004-2008 University of Zagreb, Croatia.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY AUTHOR AND CONTRIBUTORS ``AS IS'' AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.  IN NO EVENT SHALL AUTHOR OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.

This work was supported in part by Croatian Ministry of Science and
Technology through the research contracts #IP-2003-143 and #IP-2004-154.

}

proc popupAbout {} {
    global CORE_DATA_DIR CORE_VERSION CORE_VERSION_DATE copyright

    set w .about
    catch {destroy $w}
    toplevel $w
    wm transient $w .
    wm title $w "About CORE"

    set fn "$CORE_DATA_DIR/icons/normal/core-logo-275x75.gif"
    set core_logo [image create photo -file $fn]
    canvas .about.logo -width 275 -height 75
   pack .about.logo -side top -anchor n -padx 4 -pady 4
    .about.logo create image 137 37 -image $core_logo
    # version info
    label .about.text1 -text "CORE version $CORE_VERSION ($CORE_VERSION_DATE)" \
    			-foreground #500000 -padx 5 -pady 10
    label .about.text2 -text "Copyright (c)2005-2013\
    		the Boeing Company. See the LICENSE file included in this\
		distribution."
    pack .about.text1 -side top -anchor n -padx 4 -pady 4

    # OS info
    set os_info [lindex [checkOS] 1]
    label .about.text3 -justify left -text "$os_info"

    set txt4 "Portions of the GUI are derived from IMUNES having the following" 
    set txt4 "$txt4 license and copyright:"
    label .about.text4 -text $txt4
    pack .about.text2 .about.text3 .about.text4 -side top -anchor w \
		-padx 4 -pady 4


    # IMUNES info
    frame .about.fr
    text .about.fr.text -bg white -height 10 -wrap word -setgrid 1 \
	-highlightthickness 0 -pady 2 -padx 3 \
	-yscrollcommand ".about.fr.scroll set"
    scrollbar .about.fr.scroll -command ".about.fr.text yview" -bd 1 -width 10
    pack .about.fr.text .about.fr.scroll -side left -anchor w -fill both
    pack .about.fr -side top -anchor w -expand true -padx 4 -pady 4
    .about.fr.text insert 1.0 "$copyright"

    # OK button
    button .about.ok -text "OK" -command "destroy .about"
    pack .about.ok  -side bottom -anchor center -padx 4 -pady 4

    after 100 {
	grab .about
    }
}
