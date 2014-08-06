#
# Copyright 2007-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

#
# Copyright 2007 Petra Schilhard.
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


.menubar.tools.experimental add command -label "Topology partitioning..." -underline 9 -command "dialog";

#****h* gpgui/weight_file
# NAME & FUNCTION
#  weight_file -- holds the name of the file where the node weights are saved
#****
set WEIGHT_FILE "node_weights";
array set node_weights {};

#****f* gpgui.tcl/dialog
# NAME
#   dialog 
# SYNOPSIS
#   dialog
# FUNCTION
#   Procedure opens a new dialog with a text field for entering the number of parts
#   in which the graph is to be partition, and with the node and link weights, which can be
#   changed.  
#****
proc dialog { } {
#    package require BWidget
    global partition_list
    
    readNodeWeights;
	    
    set wi .popup
    toplevel $wi
    wm transient $wi .
    wm resizable $wi 0 0
    wm title $wi "Graph partition settings"
    
    #number of partitions parameter
    labelframe $wi.pnum -pady 0 -padx 4 
    frame $wi.pnum.l
    label $wi.pnum.l.p -text "Number of partitions:" -anchor w
    pack $wi.pnum.l.p -side top
    frame $wi.pnum.e -borderwidth 2
    entry $wi.pnum.e.p -bg white -width 10 -validate focus
    pack $wi.pnum.e.p -side top
    pack $wi.pnum.l $wi.pnum.e -side left
    pack $wi.pnum -side top -anchor w -fill both     
    
    #buttons for detail node and link weights
    labelframe $wi.weight -pady 4 -padx 4 -text "Weights"
    frame $wi.weight.wl
    label $wi.weight.l -text "Detailed:"
    button $wi.weight.wl.lns -text "Link weights" -command \
    "displayAllLinkWeights $wi"  

    frame $wi.weight.wn
    button $wi.weight.wn.nds -text "Nodes weights" -command \
    "displayAllNodeWeights $wi"    
    
    pack $wi.weight.l $wi.weight.wn.nds $wi.weight.wl.lns -side left
    pack $wi.weight.wn $wi.weight.wl  -side left
    
    #pack $wi.custom -side top -anchor w -fill both   
    pack $wi.weight -side top -anchor w -fill x
    
    #buttons Ok & Cancel   
    frame $wi.button -borderwidth 6
    button $wi.button.ok -text "OK" -command \
    "popupApply $wi"
    focus $wi.button.ok
    button $wi.button.cancel -text "Cancel" -command \
    "destroy $wi"
    pack $wi.button.cancel $wi.button.ok -side right
    pack $wi.button -side bottom
    
    return;   
    #grab .popup
}

#****f* gpgui.tcl/displayAllNodeWeights
# NAME
#   displayAllNodeWeights -- display all nodes weight
# SYNOPSIS
#   displayAllNodeWeights wi
# FUNCTION
#   Procedure reads for each node its weight and writes it onto
#   new window. The weight is first search in the node_list, and
#   if not found, read from the default values.
# INPUTS
#   *  wi -- parent window id
#****
proc displayAllNodeWeights {wi} {
    #package require BWidget
    global node_list;

    set nw .pop
    toplevel $nw
    wm transient $nw .
    wm resizable $nw 0 0
    wm title $nw "Node weights"
    #weights settings
    labelframe $nw.more -pady 4 -padx 4 -text "Node Weights"
    frame $nw.more.weights
    
    set i 1;
    set j 1;  
    #weights from the file
    foreach node $node_list {
	#read for each node its weight
	set wgt [getNodeWeight $node];
      
	label $nw.more.weights.$node -text "$node" -anchor w    
	spinbox $nw.more.weights.w$node -bg white -width 3 \
	    -validate focus -invcmd "focusAndFlash %W"
	$nw.more.weights.w$node insert 0 $wgt;
	$nw.more.weights.w$node configure \
	    -vcmd {checkIntRange %P 0 100} \
	    -from 0 -to 100 -increment 1
  
	grid $nw.more.weights.$node -row $i -column $j
	grid $nw.more.weights.w$node -row $i -column [expr {int($j+1)}];
    
	incr i;
	if {[expr {$i % 10}] == 0} then {
	    set j [expr {$j + 2}];
	    set i 1;
	}
    }
    pack $nw.more.weights -side top -anchor w
    pack $nw.more -side top -anchor w -fill x
  
    #buttons Apply & Cancel   
    frame $nw.button -borderwidth 6
    button $nw.button.apply -text "Apply" -command "applyNodeWeights $nw"
    focus $nw.button.apply
    button $nw.button.cancel -text "Cancel" -command "destroy $nw"
    pack $nw.button.cancel $nw.button.apply -side right
    pack $nw.button -side bottom 
}


#****f* gpgui.tcl/displayAllLinkWeights
# NAME
#   displayAllLinkWeights -- display all link weights
# SYNOPSIS
#   displayAllLinkWeights wi
# FUNCTION
#   Procedure reads for each link its characteristics and writes them
#   on the new window.   
# INPUTS
#   *  wi -- parent window id
#****
proc displayAllLinkWeights {wi} {
    # package require BWidget
    global link_list;

    set lw .pop
    toplevel $lw
    wm transient $lw .
    wm resizable $lw 0 0
    wm title $lw "Link weights"
    #weights settings
    labelframe $lw.more -pady 4 -padx 4 -text "Link Weights"
    frame $lw.more.weights
    
    set i 1;
    set j 1;  
    foreach link $link_list {

	label $lw.more.weights.$link -text "$link" -anchor w    
	#bandwidth
	label $lw.more.weights.bl$link -text "Bandwidth:" -anchor w
	spinbox $lw.more.weights.b$link -bg white -width 9 \
	    -validate focus -invcmd "focusAndFlash %W"
	$lw.more.weights.b$link insert 0 [getLinkBandwidth $link]
	$lw.more.weights.b$link configure \
	    -vcmd {checkIntRange %P 0 100000000} \
	    -from 0 -to 100000000 -increment 1000
	#delay
	label $lw.more.weights.dl$link -text "Delay:" -anchor w
	spinbox $lw.more.weights.d$link -bg white -width 9 \
	    -validate focus -invcmd "focusAndFlash %W"
	$lw.more.weights.d$link insert 0 [getLinkDelay $link]
	$lw.more.weights.d$link configure \
	    -vcmd {checkIntRange %P 0 100000000} \
	    -from 0 -to 100000000 -increment 5
	#BER
	label $lw.more.weights.rl$link -text "BER (1/N):" -anchor w
	spinbox $lw.more.weights.r$link -bg white -width 9 \
	    -validate focus -invcmd "focusAndFlash %W"
	$lw.more.weights.r$link insert 0 [getLinkBER $link]
	$lw.more.weights.r$link configure \
	    -vcmd {checkIntRange %P 0 10000000000000} \
	    -from 0 -to 10000000000000 -increment 1000
    
	grid $lw.more.weights.$link -row $i -column 1;
	grid $lw.more.weights.bl$link -row $i -column 2;
	grid $lw.more.weights.b$link -row $i -column 3;
	grid $lw.more.weights.dl$link -row $i -column 4;
	grid $lw.more.weights.d$link -row $i -column 5;
	grid $lw.more.weights.rl$link -row $i -column 6;
	grid $lw.more.weights.r$link -row $i -column 7;
    
	incr i;
    }
    pack $lw.more.weights -side top -anchor w
    pack $lw.more -side top -anchor w -fill x
  
    #buttons Apply & Cancel   
    frame $lw.button -borderwidth 6
    button $lw.button.apply -text "Apply" -command \
	"applyLinkWeights $lw"
    focus $lw.button.apply
    button $lw.button.cancel -text "Cancel" -command \
	"destroy $lw"
    pack $lw.button.cancel $lw.button.apply -side right
    pack $lw.button -side bottom 
}

#****f* gpgui.tcl/readNodeWeights
# NAME
#   readNodeWeights -- read node weights
# SYNOPSIS
#   readNodeWeights
# FUNCTION
#   Procedure reads from a file node weights and saves them
#   in array.
#****
proc readNodeWeights {} {
    global node_weights;
  
    #get the weight settings out of the file
    set file [openWeightFile "r"];
    # Boeing: attempt to recover with default weights
    if { $file == "" } {
	set i 0;
	while { $i < 6 } {
	    set node_weights($i) $i
	    incr i
	}
	return
    }
    # end Boeing
    
    set n [gets $file line];

    set i 0;
    while {[gets $file line] >= 0} {
	set node_weights($i) $line;
	incr i;
    }    
    close $file;
  
    if {$i != 6} then {
	puts stdout "Bad file $file.";
	return;
    }
}

#****f* gpgui.tcl/openWeightFile
# NAME
#   openWeightFile -- open weight file
# SYNOPSIS
#   openWeightFile $op
# FUNCTION
#   Function opens a file specified in WEIGHT_FILE constant,
#   and returns file descriptor.
# INPUTS
#   *  op -- operation "r" (for read) or "w" (for write)
# RESULT
#   * fileId -- file id
#****
proc openWeightFile { op } {
    global WEIGHT_FILE;
    if {[catch {open $WEIGHT_FILE $op} fileId]} then {
	puts stdout "graph_partitioning: Cannot open $WEIGHT_FILE.";
	return;
    } 
    return $fileId;
}

#****f* gpgui.tcl/applyNodeWeights
# NAME
#   applyNodeWeights -- apply node weights
# SYNOPSIS
#   applyNodeWeights nw
# FUNCTION
#   Procedure reads for each node its weight from the
#   window, and save it to the node_list.
# INPUTS
#   *  nw -- window id
#****
proc applyNodeWeights {nw} {
    global node_list;

    foreach node $node_list {
	writeWeightToNode $node [$nw.more.weights.w$node get];
    }
    destroy $nw;
}

#****f* gpgui.tcl/applyLinkWeights
# NAME
#   applyLinkWeights -- apply link weights
# SYNOPSIS
#   applyLinkWeights lw
# FUNCTION
#   Procedure reads for each link its characteristics from the
#   window, and change theirs values in program.
# INPUTS
#   *  lw -- window id
#****
proc applyLinkWeights {lw} {
    global link_list;

    foreach link $link_list {
	setLinkBandwidth $link [$lw.more.weights.b$link get];
	setLinkDelay $link [$lw.more.weights.d$link get];
	setLinkBER $link [$lw.more.weights.r$link get];
    }
    destroy $lw;
}

#****f* gpgui.tcl/writeWeightToNode
# NAME
#   writeWeightToNode -- write weight to node
# SYNOPSIS
#   writeWeightToNode $node $weight
# FUNCTION
#   Procedure writes the weight to the node.
# INPUTS
#   *  node -- node id
#   *  weight -- weight of the node
#****
proc writeWeightToNode {node weight} {
    global $node;

    set p [lsearch [set $node] "weight *"];
    if { $p >= 0 } {
	set $node [lreplace [set $node] $p $p "weight $weight"];
    } else {
	set $node [linsert [set $node] end "weight $weight"];
    }
}


#****f* gpgui.tcl/getNodeWeight
# NAME
#   getNodeWeight -- get node weight
# SYNOPSIS
#   getNodeWeight $node
# FUNCTION
#   Function searches the node for the information
#   about its weight. If the weight is found, it is
#   returned, and if it is not found, an empty string is
#   returned.
# INPUTS
#   *  node -- node id
# RESULT
#   * wgt -- weight of the node
#****
proc getNodeWeight {node} {
    global $node;
    global node_weights;
  
    set wgt [lindex [lsearch -inline [set $node] "weight *"] 1];

    if {$wgt == ""} then {
	switch -exact -- [nodeType $node] {
	    pc {
		set wgt $node_weights(0);
	    }
	    host {
		set wgt $node_weights(1);
	    }
	    router {
		set wgt $node_weights(2);
	    }
	    lanswitch {
		set wgt $node_weights(3);
	    }
	    hub {
		set wgt $node_weights(4);
	    }
	    rj45 {
		set wgt $node_weights(5);
	    }      
	    default {
		set wgt 0;
	    }
	}	
    }
    return $wgt;
}

#****f* gpgui.tcl/changeDefaultWeights
# NAME
#   changeDefaultWeights -- change default weights
# SYNOPSIS
#   changeDefaultWeights wi
# FUNCTION
#   Procedure opens a file with node weights, and writes
#   in it the weight for each group of nodes (pc,router,...).  
# INPUTS
#   *  wi -- window id, parent window
#****
#save node weights to the file
proc changeDefaultWeights {wi} {
    global node_weights;
    set file [openWeightFile "w"]; 
    
    set node_weights(0) [$wi.weight.pcs get];
    set node_weights(1) [$wi.weight.hosts get];
    set node_weights(2) [$wi.weight.routers get];
    set node_weights(3) [$wi.weight.switchs get];
    set node_weights(4) [$wi.weight.hubs get];
    set node_weights(5) [$wi.weight.rj45s get];
	
    debug $file [format "%d %d %d %d %d %d" $node_weights(0) $node_weights(1) $node_weights(2) $node_weights(3) $]node_weights(4) $node_weights(5);
    close $file; 
    destroy $wi; 
}


#****f* gpgui.tcl/popupApply
# NAME
#   popupApply -- popup apply
# SYNOPSIS
#   popupApply wi
# FUNCTION
#   Procedure saves for each node its weight in node_list.
# INPUTS
#   *  wi -- window id
#****
proc popupApply { wi } {
    global node_list;
    set partNum [$wi.pnum.e.p get]
    
    foreach node $node_list {
	#read for each node its weight
	set wgt [getNodeWeight $node];  
	#write it to the node_list
	writeWeightToNode $node $wgt
    }
    
    destroy $wi
    #graphPartition $partNum;
    test_partitioning $partNum;
}

#****f* gpgui.tcl/displayErrorMessage
# NAME
#   displayErrorMessage -- display error message
# SYNOPSIS
#   displayErrorMessage $message
# FUNCTION
#   Procedure writes a message to the screen as a popup dialog.
# INPUTS
#   *  message -- message to be writen
#****
proc displayErrorMessage { message } {
    tk_dialog .dialog1 "Graph partitioning" $message info 0 Dismiss;
}

#****f* gpgui.tcl/getLinkWeight
# NAME
#   getLinkWeight -- calculate link weight
# SYNOPSIS
#   getLinkWeight $link
# FUNCTION
#   Function calculates for each link its weight from its characteristics.
# INPUTS
#   *  link -- link id
# RESULT
#   * weight -- weight of the link
#****
proc getLinkWeight {link} {
    set bndw [getLinkBandwidth $link];
    set dly [getLinkDelay $link];
    set ber [getLinkBER $link];
    set dup [getLinkDup $link];
    set weight [expr {$bndw}];

    return $weight;
}


proc test_partitioning {partNum} {

#    foreach n {2 4 8 16 32 64 128 256 512} {
#	if {$n > $partNum} then {
#	    break;
#	}
#	for {set i 0} {$i < 3} {incr i} {
#	    puts "i=$i, n=$n";
	    graphPartition $partNum;
#	}
#    }
}
