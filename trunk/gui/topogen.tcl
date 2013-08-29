#
# Copyright 2007-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#

#
# Copyright 2007-2008 University of Zagreb, Croatia.
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

# Boeing: refactor menus
set TOOLSMENUPATH .menubar.tools
set TOPOMENUPATH ${TOOLSMENUPATH}.t_g
menu $TOPOMENUPATH -tearoff 1
${TOOLSMENUPATH} add cascade -label "Topology generator" -underline 0 -menu ${TOPOMENUPATH}
# also throughout:
# s/.menubar.t_g/${TOPOMENUPATH}/g
# s///g
# end Boeing

set m ${TOPOMENUPATH}.random
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Random" -menu $m -underline 0 
foreach i [list 1 5 10 15 20 30 40 50 75 100] {
    set n $m.$i
    menu $n -tearoff 0
    $m add command -label "R($i)" -command "R \[newNodes $i\]"
}

set m ${TOPOMENUPATH}.grid
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Grid" -menu $m -underline 0 
foreach i [list 1 5 10 15 20 25 30 35 40 50 60 70 80 90 100] {
    set n $m.$i
    menu $n -tearoff 0
    $m add command -label "G($i)" -command "G \[newNodes $i\]"
}

set m ${TOPOMENUPATH}.gridc
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Connected Grid" -menu $m -underline 0 
    
for { set i 1 } { $i <= 10 } { incr i } {
    set n $m.$i
    menu $n -tearoff 0
    $m add cascade -label "$i x N" -menu $n -underline 0
    for { set j 1 } { $j <= 10 } { incr j } {
	$n add command -label "$i x $j" -command "Gchelper $i $j"
    }
}

set m ${TOPOMENUPATH}.chain
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Chain" -menu $m -underline 0 
for { set i 2 } { $i <= 24 } { incr i } {
    $m add command -label "P($i)" -command "P \[newNodes $i\]"
}
# Boeing
foreach i [list 32 64 128] {
    $m add command -label "P($i)" -command "P \[newNodes $i\]"
}
# end Boeing

set m ${TOPOMENUPATH}.star
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Star" -menu $m -underline 0 
for { set i 3 } { $i <= 25 } { incr i } {
    $m add command -label "S($i)" \
	-command "Kb \[newNodes 1\] \[newNodes [expr {$i - 1}]\]"
}

set m ${TOPOMENUPATH}.cycle
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Cycle" -menu $m -underline 0 
for { set i 3 } { $i <= 24 } { incr i } {
    $m add command -label "C($i)" -command "C \[newNodes $i\]"
}

set m ${TOPOMENUPATH}.wheel
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Wheel" -menu $m -underline 0 
for { set i 4 } { $i <= 25 } { incr i } {
    $m add command -label "W($i)" \
	-command "W \"\[newNodes 1\] \[newNodes [expr {$i - 1}]\]\""
}

set m ${TOPOMENUPATH}.cube
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Cube" -menu $m -underline 0 
for { set i 2 } { $i <= 6 } { incr i } {
    $m add command -label "Q($i)" \
	-command "Q \[newNodes [expr {int(pow(2,$i))}]\]"
}

set m ${TOPOMENUPATH}.clique
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Clique" -menu $m -underline 0 
for { set i 3 } { $i <= 24 } { incr i } {
    $m add command -label "K($i)" -command "K \[newNodes $i\]"
}

set m ${TOPOMENUPATH}.bipartite
menu $m -tearoff 0
${TOPOMENUPATH} add cascade -label "Bipartite" -menu $m -underline 0 
    
for { set i 1 } { $i <= 12 } { incr i } {
    set n $m.$i
    menu $n -tearoff 0
    $m add cascade -label "K($i,N)" -menu $n -underline 0
    for { set j $i } { $j <= [expr {24 - $i}] } { incr j } {
	$n add command -label "K($i,$j)" -command "Kbhelper $i $j"
    }
}


proc newNodes { n } {
    global curcanvas grid sizex sizey activetool activetoolp CORE_DATA_DIR
    global g_last_selected_node_type

    if { [lsearch {select start link bgobjs} $activetool] >= 0 } {
	set activetoolp ""
    }
    # some other tool is selected besides layer-2/3 nodes
    if { $activetoolp != "routers" && $activetoolp != "hubs" } {
	if { [info exists g_last_selected_node_type] && \
	     $g_last_selected_node_type != "" } {
	    set parent [lindex $g_last_selected_node_type 0]
	    set b [lindex $g_last_selected_node_type 1]
	    set imgf [lindex $g_last_selected_node_type 2]
	    popupMenuChoose $parent $b $imgf
	} else {
	    # select router by default (this properly sets some globals)
	    set icon "$CORE_DATA_DIR/icons/tiny/router.gif"
	    popupMenuChoose "routers" "router" $icon
        }
    }

    set v {}
    set r [expr {($n - 1) * (1 + 4 / $n) * $grid / 2}]
    set x0 [expr {$sizex / 2}]
    set y0 [expr {$sizey / 2}]
    set twopidivn [expr {acos(0) * 4 / $n}]

    set dy 32
    if { [lsearch {router rj45} $activetool] >= 0 } {
	set dy 28
    } elseif { [lsearch {hub lanswitch} $activetool] >= 0 } {
	set dy 24
    }

    for { set i 0 } { $i < $n } { incr i } {
	if { $activetoolp == "routers" } {
	    set new_node [newNode router]
	    setNodeModel $new_node $activetool
	} else {
	    set new_node [newNode $activetool]
	}
	set x [expr {$x0 + $r * cos($twopidivn * $i)}]
	set y [expr {$y0 - $r * sin($twopidivn * $i)}]
	setNodeCoords $new_node "$x $y"
	setNodeLabelCoords $new_node "$x [expr {$y + $dy}]"
	setNodeCanvas $new_node $curcanvas
	lappend v $new_node
    }

    return $v
}

proc topoGenDone { v } {
    global changed activetool

    set activetool select
    set changed 1
    updateUndoLog
    redrawAll
    selectNodes $v
}

#
# Chain
#
proc P { v } {
    .c config -cursor watch; update
    set n [llength $v]
    for { set i 0 } { $i < [expr {$n - 1}] } { incr i } {
	newLink [lindex $v $i] [lindex $v [expr {($i + 1) % $n}]]
    }
    topoGenDone $v
}

#
# Cycle
#
proc C { v } {
    .c config -cursor watch; update
    set n [llength $v]
    for { set i 0 } { $i < $n } { incr i } {
	newLink [lindex $v $i] [lindex $v [expr {($i + 1) % $n}]]
    }
    topoGenDone $v
}

#
# Wheel 
#
proc W { v } {
    .c config -cursor watch; update
    set n [llength $v]
    set vr [lindex $v 0]
    set vt "$v [lindex $v 1]"
    for { set i 1 } { $i < $n } { incr i } {
	newLink $vr [lindex $v $i]
	newLink [lindex $v $i] [lindex $vt [expr {$i + 1}]]
    }
    topoGenDone $v
}

#
# Cube
#
proc Q { v } {
    set n [llength $v]
    set order [expr int(log($n)/log(2))]
    for { set i 0 } { $i < $order } { incr i } {
	animateCursor
	set d [expr {int(pow(2, $i))}]
	for { set j 0 } { $j < $n } { incr j } {
	    if { [llength [ifcList [lindex $v $j]]] <= $i} {
		newLink [lindex $v $j] [lindex $v [expr {($j + $d) % $n}]]
	    }
	}
    }
    topoGenDone $v
}

#
# Clique
#
proc K { v } {
    set n [llength $v]
    for { set i 0 } { $i < [expr {$n - 1}] } { incr i } {
	animateCursor
	for { set j [expr {$i + 1}] } { $j < $n } {incr j } {
	    newLink [lindex $v $i] [lindex $v $j]
	}
    }
    topoGenDone $v
}

#
# Bipartite
#
proc Kb { v1 v2 } {
    set n1 [llength $v1]
    set n2 [llength $v2]
    for { set i 0 } { $i < $n1 } { incr i } {
	animateCursor
	for { set j 0 } { $j < $n2 } {incr j } {
	    newLink [lindex $v1 $i] [lindex $v2 $j]
	}
    }
    topoGenDone "$v1 $v2"
}

proc Kbhelper { n m } {
    set v [newNodes [expr $n + $m]]
    Kb [lrange $v 0 [expr $n -1]] [lrange $v $n end]
}

#
# Random
#
proc R { v } {
    global curcanvas
    set c .c
    set min 20
    set xmax [expr {[lindex [getCanvasSize $curcanvas] 0] - 2*$min}]
    set ymax [expr {[lindex [getCanvasSize $curcanvas] 1] - 2*$min}]

    expr { srand([clock clicks -milliseconds]) }

    .c config -cursor watch; update
    foreach node $v {
	set x [expr { int(rand() * $xmax) + $min} ]
	set y [expr { int(rand() * $ymax) + $min} ]
	setNodeCoords $node "$x $y"
	set dy 28
	setNodeLabelCoords $node "$x [expr {$y + $dy}]"
    }
    topoGenDone $v
}

#
# Grid
#
proc G { v } {
    global curcanvas
    set c .c
    set step 100
    set min 50
    set xmax [expr {[lindex [getCanvasSize $curcanvas] 0] - 2*$min}]
    set ymax [expr {[lindex [getCanvasSize $curcanvas] 1] - 2*$min}]

    .c config -cursor watch; update
    set x $min
    set y $min
    foreach node $v {
	if { $x >= $xmax } { ;# end of the row
	    set x $min
	    incr y $step
	    if { $y >= $ymax } {
		# xmax and ymax reached -- out of canvas space here!
		set y $ymax
	    }
        }
	setNodeCoords $node "$x $y"
	set dy 28 
	setNodeLabelCoords $node "$x [expr {$y + $dy}]"
	incr x $step
    }
    topoGenDone $v
}

#
# Connected Grid
#
proc Gc { v n m } {
    set step 100
    set dy 28 
    set y $step 

    set nodenum 0

    # m is number of rows
    for { set i 0 } { $i < $m } { incr i } {
	animateCursor
        set x 0 ;# start a new row
	# n is number of columns
	for { set j 0 } { $j < $n } {incr j } {
	    incr x $step
	    set node [lindex $v $nodenum]
	    setNodeCoords $node "$x $y"
	    setNodeLabelCoords $node "$x [expr {$y + $dy}]"
	    if { $x > $step } { ;# link each node with prev in row
	        set lastnode [lindex $v [expr {$nodenum - 1}]]
		newLink $lastnode $node
	    }
	    if { $y > $step } { ;# link each node with above in column
	        set lastnode [lindex $v [expr {$nodenum - $n}]]
		newLink $lastnode $node
	    }
	    incr nodenum 1 ;# on to the next column
	}
	incr y $step ;# on to the next row
    }
    topoGenDone $v
}

proc Gchelper { n m } {
    set v [newNodes [expr $n * $m]]
    Gc $v $n $m
}
