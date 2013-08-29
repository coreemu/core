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

#****f* graph_partitioning.tcl/writePartitions
# NAME
#   writePartitions -- write partitions
# SYNOPSIS
#   writePartitions node_weight
# FUNCTION
#   Procedure that writes for each node its partition.
# INPUTS
#   *  node_weight -- array of node weights
#****
proc writePartitions {node_weight} {
    global nparts;
    global node_list;
    global link_list;
    global split_list;
    global finalpartition;

    upvar $node_weight nweight;
  
    #counts how many nodes are in each partition
    array set nr_nodes_partition {};
    #sum up the weight of each partition
    array set weight_partition {}; 
 
    for {set i 0} {$i<$nparts} {incr i} {
	set nr_nodes_partition($i) 0;
	set weight_partition($i) 0;
    }

    set i 0;
    foreach node $node_list {
	#write to node its partition
	setPartition $node $finalpartition($i);
	incr nr_nodes_partition($finalpartition($i)) 1;
	incr weight_partition($finalpartition($i)) $nweight($i);
	incr i;
    }

    #disconnect for algorithm connected nodes
    foreach split $split_list {
	set node1 [lindex $split 0];
	set node2 [lindex $split 1];
	set linkToSplit [linkByPeers $node1 $node2];
	splitGUILink $linkToSplit ;
    }

    set outstr "";
    for {set i 0} {$i < $nparts} {incr i} {
	set outstr "p$i: $nr_nodes_partition($i) vertices with weight $weight_partition($i)";
	#puts [format %s $outstr];
    }
    
    redrawAll;
    updateUndoLog;
    tk_dialog .dialog1 "Graph partitioning output" "Done.\n" info 0 Dismiss;
}
 
#****f* graph_partitioning.tcl/setPartition
# NAME
#   setPartition -- set partition
# SYNOPSIS
#   setPartition $node $partition
# FUNCTION
#   Procedure searches the node for the information about
#   its partition, if found it replace the info, if not found
#   it adds the information to the node.
# INPUTS
#   *  node -- node id
#   *  partition -- partition of the node
#****
proc setPartition { node partition } {
    global $node;

    set p [lsearch [set $node] "partition *"];
    if { $p >= 0 } {
	set $node [lreplace [set $node] $p $p "partition p$partition"];
    } else {
 	set $node [linsert [set $node] end "partition p$partition"];
    }
}

#****f* graph_partitioning.tcl/getNodePartition
# NAME
#   getNodePartition -- get node partition
# SYNOPSIS
#   getNodePartition $node
# FUNCTION
#   Function searches for node's partition, and returns it
#   (or empty string if not found)
# INPUTS
#   *  node -- node id
# RESULT
#   * part -- the node's partition 
#****
proc getNodePartition { node } {
    global $node;
    set part [lindex [lsearch -inline [set $node] "partition *"] 1];
    return $part;
}

#****f* graph_partitioning.tcl/debug
# NAME
#   debug
# SYNOPSIS
#   debug $message
# FUNCTION
#   Prints the message to the stderr if enabled.
# INPUTS
#   *  message -- a messege to be printed
#****
proc debug { message } {
    global debug;
    if ![info exists debug(enabled)] {
	#do nothing
	return;
    }
    puts stderr $message;
}

#****f* graph_partitioning.tcl/graphPartition
# NAME
#   graphPartition -- graph partition
# SYNOPSIS
#   graphPartition $partNum
# FUNCTION
#   Procedure which prepares arrays for partitioning
#   algorithm, and starts the algorithm.
# INPUTS
#   *  partNum -- number of partitions
#****
proc graphPartition {partNum} {
    global node_list link_list finalpartition

    global nparts tpwgts max_nweight

    array set node_weight {};
    array set edge_weight {};
    array set node_neighbour {};
    array set edge_array {};
    array set tpwgts {};
    array set node_map {};

    puts "";
    #puts " Starting graph partitioning...";
    #puts "+------------------------------------------------+";
    #puts "";
  
    set start [clock clicks -milliseconds];

    #initialise the arrays for the algorithm
    set nparts $partNum;
    initNodes node_weight;
    set nvertices [array size node_weight];
    initNeighbours node_neighbour edge_array edge_weight;
  
    if {$nparts > $nvertices} then {
 	debug "Number of vertices should be greater then number of partitions.";
	displayErrorMessage "Number of vertices should be greater then number of partitions.";
	return;
    } elseif {$nparts < 2} {
	debug "Number of partition should be greater then 1.";
	displayErrorMessage "Number of partition should be greater then 1.";
	return;
    }

    #calculate tpwgts array
    for {set i 0} {$i < $nparts} {incr i} {
	set tpwgts($i) [expr {1.0 / (1.0 * $nparts)}];
    }   
  
    set t [time { recursiveBisection $nvertices node_weight node_neighbour edge_array edge_weight tpwgts $nparts 0 node_map; } 1];
    set microsec [lindex $t 0];
    puts "total time: [expr {$microsec * 0.000001}] sec";
    
    #compute cut
    set cut 0;
    for {set i 0} {$i < $nvertices} {incr i} {
	set id($i) 0;
	set ed($i) 0;

	set curr_partition $finalpartition($i);

	# calculates the sum of the edge weights of the adjacent vertices of i
	if {[info exists node_neighbour($i)]} then {
	    foreach ngb $node_neighbour($i) {
		if {$curr_partition == $finalpartition($ngb)} then {
		    # vertice in the same partition
		    incr id($i) 1;
		    #$edge_weight([getEdgeBetween $i $ngb edge_array]);
		} else {
		    # vertice in a different partition
		    incr ed($i) 1;
		    #$edge_weight([getEdgeBetween $i $ngb edge_array]);
		};#if-else
	    };#foreach

	    if {$ed($i) > 0 || [llength $node_neighbour($i)] == 0} then {
		#vanjski node, ili nema susjeda
		incr cut $ed($i);
	    }
	}
    }
    set cut [expr {$cut / 2}];
    puts "end cut: $cut";
  
    #save the partitions
    writePartitions node_weight;
  
    set end [clock clicks -milliseconds];
    puts [format "total elapsed time: %.6f s" [expr {($end - $start) * 0.001}]];
  
    puts "";
    puts " Done graph partitioning.";
    puts "+------------------------------------------------+";
    puts "";
}

#****f* graph_partitioning.tcl/initNodes
# NAME
#   initNodes
# SYNOPSIS
#   initNodes node_weight
# FUNCTION
#   Initialise the node_weight array.
# INPUTS
#   *  node_weight -- empty array of node weights
#****
proc initNodes {node_weight} {
    global node_list;
    upvar $node_weight nweight;
    
    set i 0;
    foreach node $node_list {
	#if the node is pseudo, remove it
	if {[nodeType $node] == "pseudo"} then {
	    mergePseudoLink $node 
	} else {
	    #seve node's weight into array
	    set nweight($i) [getNodeWeight $node];
	    incr i;
	}
    }   
}

#****f* graph_partitioning.tcl/mergePseudoLink
# NAME
#   mergePseudoLink -- merge pseudo link
# SYNOPSIS
#   mergePseudoLink $pnode
# FUNCTION
#   Removes pseudo connections.
# INPUTS
#   *  pnode -- pseudo node id
#****
proc mergePseudoLink { pnode } {
    global node_list;
    global split_list;
  
    foreach n $node_list {
	#get the links connecting the both pseudo node's
	set l1 [linkByPeers $pnode $n];
	if {$l1 != ""} then {
	    set l2 [getLinkMirror $l1];
	    #set peers1 [linkPeers $l1];
	    set peers2 [linkPeers $l2];

	    #get it's not-pseudo peers
	    #set n1 [lindex $peers1 0];
	    set n2 [lindex $peers2 0];

	    mergeLink $l1;
	    if {[lsearch $split_list "$n $n2"] < 0 && [lsearch $split_list "$n2 $n"] < 0} then {
		lappend split_list "$n $n2";
		break;
	    }
	}
    }
}  

#****f* graph_partitioning.tcl/initNeighbours
# NAME
#   initNeighbours
# SYNOPSIS
#   initNeighbours node_neighbour edge_array edge_weight
# FUNCTION
#   Initialise node_neighbour, edge_array and edge_weight array.
# INPUTS
#   *  node_neighbour -- empty array
#   *  edge_array -- empty array
#   *  edge_weight -- empty array 
#****
proc initNeighbours {node_neighbour edge_array edge_weight} {
    global node_list link_list

    upvar $edge_array earray;
    upvar $node_neighbour nneighbour;
    upvar $edge_weight eweight;

    for {set i 0} {$i < [llength $link_list]} {incr i} {
	#take the edge one after the other
	set edge [lindex $link_list $i];
	#read nodes incident to edge
	set peers [linkPeers $edge];
	set node1 [lindex $peers 0];
	set node2 [lindex $peers 1];
	#read node's index in the node_list
	set idx_n1 [lsearch $node_list $node1];
	set idx_n2 [lsearch $node_list $node2];
	#node1 is adjacent to node2
	lappend nneighbour($idx_n1) $idx_n2;
	lappend nneighbour($idx_n2) $idx_n1;
	set earray($i) "$idx_n1 $idx_n2";
	#calculate the link weight
	set eweight($i) [expr {[getLinkWeight $edge] / 100000}]; #!!!!!!s
    }
}

#****f* graph_partitioning.tcl/recursiveBisection
# NAME
#   recursiveBisection
# SYNOPSIS
#   recursiveBisection $nvertices node_weight node_neighbour 
#   edge_array edge_weight tpart_wgts $new_parts $part_nr up_map
# FUNCTION
#   Recursive starts coarsening, initial partitioning and uncoarsening. 
#   In each recursion it bisect the graph and recalculates arrays for each
#   part.
# INPUTS
#   *  nvertices -- number of vertices
#   *  node_weight -- array of node weights
#   *  node_neighbour -- array of node neighbours
#   *  edge_array -- array of edges
#   *  edge_weight -- array of edge weights
#   *  tpart_wgts -- array of each partition ratio of the graph
#   *  new_parts -- number to divide the graph
#   *  part_nr -- counts how deep the recursion is
#   *  up_map  -- 
#****
proc recursiveBisection {nvertices node_weight node_neighbour edge_array edge_weight tpart_wgts new_parts part_nr up_map} {
    global part_mincut;
    global finalpartition;
    global part_partition;

    upvar $node_weight nweight;
    upvar $node_neighbour nneighbour;
    upvar $edge_array earray;
    upvar $edge_weight eweight;
    upvar $tpart_wgts tpwgts;
    upvar $up_map upmap;

    array set tpwgts2 {};

    set nparts $new_parts;
    set cut 0;
    debug "recursiveBisection!!!!";
    debug "RB: nparts=$nparts";

    #calculate for each partition its wished weight
    set tvwgt [sum_array $nvertices nweight];
    set sum_tpwgt [sum_array [expr {$nparts / 2}] tpwgts];
    set tpwgts2(0) [expr {int ( ceil($tvwgt * $sum_tpwgt))}];
    set tp2 [expr {ceil($sum_tpwgt * $tvwgt)}];
    set tpwgts2(1) [expr {int($tvwgt - $tpwgts2(0))}];
    debug "RB: tvwgt=$tvwgt, tpwgts2(0)=$tpwgts2(0), tpwgts2(1)=$tpwgts2(1), sum_tpwgt=$sum_tpwgt";

    #start partitioning
    coarseGraph $nvertices nweight nneighbour earray eweight tpwgts2;
    #minimal cut
    set cut $part_mincut;
  
    #calculate for each vertex its right partition by adding to "0" and "1" partition a number
    for {set i 0} {$i < $nvertices} {incr i} {
	if {[array size upmap] > 0} {
	    set finalpartition($upmap($i)) [expr {$part_partition($i) + $part_nr}];
	} else {
	    set finalpartition($i) [expr {$part_partition($i) + $part_nr}];
	}
    }

    #when partition in more then 2 parts, divide the graph in 2 halfs (subgraph "0" and subgraph "1")
    if {$nparts > 2} then {
	array set snode_neighbour {};
	array set snode_weight {};
  	array set sedge_array {};
  	array set sedge_weight {};
	array set snode_map {};
	array set snode_map_help {}; #auxiliary variable

  	array set sn_vtxs {};
  	set sn_vtxs(0) 0;
  	set sn_vtxs(1) 0;

  	array set sn_edges {};
  	set sn_edges(0) 0;
  	set sn_edges(1) 0;

  	splitGraph $nvertices nneighbour nweight earray eweight snode_neighbour snode_weight sedge_array sedge_weight snode_map sn_vtxs sn_edges snode_map_help;

  	array set snode_neighbour0 {};
  	array set snode_weight0 {};
  	array set sedge_array0 {};
  	array set sedge_weight0 {};
  	array set snode_map0 {};

	array set snode_neighbour1 {};
  	array set snode_weight1 {};
  	array set sedge_array1 {};
  	array set sedge_weight1 {};
  	array set snode_map1 {};

	#save the node characteristics from both subgraphs in two different arrays
	
	for {set i 0} {$i < $sn_vtxs(0)} {incr i} {
	    if {[info exists snode_neighbour(0,$i)]} then {
		set snode_neighbour0($i) $snode_neighbour(0,$i);
	    }
	    if {[array size upmap] > 0} then {
		set snode_map0($i) $upmap($snode_map_help(0,$i));
	    } else {
		set snode_map0($i) $snode_map_help(0,$i); 
	    }
	    debug "snode_map0($i)=$snode_map0($i)";
	    set snode_weight0($i) $snode_weight(0,$i);
	}

	for {set i 0} {$i < $sn_vtxs(1)} {incr i} {
	    if {[info exists snode_neighbour(1,$i)]} then {
		set snode_neighbour1($i) $snode_neighbour(1,$i);
	    }
	    if {[array size upmap] > 0} then {
		set snode_map1($i) $upmap($snode_map_help(1,$i));
	    } else {
		set snode_map1($i) $snode_map_help(1,$i);
	    }
	    debug "snode_map1($i)=$snode_map1($i)";
	    set snode_weight1($i) $snode_weight(1,$i);
	}

	#save the link characteristics from both subgraphs in two different arrays
	
	for {set i 0} {$i < $sn_edges(0)} {incr i} {
	    set sedge_array0($i) $sedge_array(0,$i);
	    set sedge_weight0($i) $sedge_weight(0,$i);
  	}

	for {set i 0} {$i < $sn_edges(1)} {incr i} {
	    set sedge_array1($i) $sedge_array(1,$i);
	    set sedge_weight1($i) $sedge_weight(1,$i);
	}
    }
  
    #update the tpwgts (partition's ratio of the graph)
    mult_array 0 [expr {int($nparts / 2)}] tpwgts [expr {1 / $sum_tpwgt}];
    mult_array [expr {int($nparts / 2)}] $nparts tpwgts [expr {1.0 / (1.0 - $sum_tpwgt)}];
    set max [expr {int($nparts - $nparts / 2)}];

    for {set i 0} {$i < $max} {incr i} {
	set new_tpwgts($i) $tpwgts([expr {$i + int($nparts / 2)}]);
	debug " new_tpwgts($i)=$new_tpwgts($i)";
    }

    #call recursive itself
    if {$nparts > 3} then {
	#partition the first subgraph
	recursiveBisection $sn_vtxs(0) snode_weight0 snode_neighbour0 sedge_array0 sedge_weight0 tpwgts [expr {int($nparts / 2)}] $part_nr snode_map0;
	#partition the second subgraph
	recursiveBisection $sn_vtxs(1) snode_weight1 snode_neighbour1 sedge_array1 sedge_weight1 new_tpwgts [expr {int($nparts - $nparts / 2)}] [expr {int($part_nr + $nparts / 2)} ] snode_map1;
    } elseif {$nparts == 3} then {
	#partition the second subgraph
	recursiveBisection $sn_vtxs(1) snode_weight1 snode_neighbour1 sedge_array1 sedge_weight1 new_tpwgts [expr {int($nparts - $nparts / 2)}] [expr {int($part_nr + $nparts / 2)}] snode_map1;
    }
}

#****f* graph_partitioning.tcl/coarseGraph
# NAME
#   coarseGraph -- coarsening and uncoarsening
# SYNOPSIS
#   coarseGraph $nvertices node_weight node_neighbour edge_array edge_weight tpwgts2
# FUNCTION
#   Coarsening and uncoarsening phase. Procedure first recursivly coarse the graph. 
#   The coarsest graph is partitionend. In "backrolling" of recurson, the coarse 
#   graph is uncoarsen and refined.
# INPUTS
#   *  nvertices -- number of vertices
#   *  node_weight -- array of node weights
#   *  node_neighbour -- array of node neighbours
#   *  edge_array -- array of edges
#   *  edge_weight -- array of edge weights
#   *  tpwgts2 -- array of each partition size of the graph
#****
proc coarseGraph {nvertices node_weight node_neighbour edge_array edge_weight tpwgts2} {
    global nparts;
    global max_nweight;
    global COARSEN_TO;

    upvar  $node_weight nweight;
    upvar  $node_neighbour nneighbour;
    upvar  $edge_array earray;
    upvar  $edge_weight eweight;
    upvar  $tpwgts2 tpwgts;

    debug "MatchRm... $nvertices";
  
    array set cnweight {};
    array set nmap {};
    array set nmatch {};
  
    set matched "";
    set cnvertices 0;

    #permute the nodes
    set permList [makePermList $nvertices ];
    #array with random permuted nodes
    array set permArray $permList;
    set sum_nweight [sum_array $nvertices nweight];
    set max_nweight [expr {1.5 * $sum_nweight / 20}];

    #match the vertices
    for {set i 0} {[llength $matched] < $nvertices} {incr i} {
	set unmatched_node $permArray($i);

	if {[lsearch $matched $unmatched_node] == -1} then {
	    lappend matched $unmatched_node;
	    set matched_ngb 0;
	    set max_eweight 0;
	    debug "matched=$matched";

	    #node has an unmatched, passend neighbor, and is matched with it
	    if {$nvertices > $COARSEN_TO && [info exists nneighbour($unmatched_node)]} then {
		foreach ngb $nneighbour($unmatched_node) {
		    if {[lsearch $matched $ngb] == -1 && [expr {$nweight($i) + $nweight($ngb)}] < $max_nweight && $max_eweight < $eweight([getEdgeBetween $unmatched_node $ngb earray])} then {
			set matched_ngb 1;
			lappend matched $ngb;
			set max_eweight $eweight([getEdgeBetween $unmatched_node $ngb earray]);
			set nmatch($unmatched_node) $ngb;
			set nmatch($ngb) $unmatched_node;
			set nmap($unmatched_node) $cnvertices; #potrebno za uncoarse
			set nmap($ngb) $cnvertices; #potrebno za uncoarse
			set cnweight($cnvertices) [expr {$nweight($unmatched_node) + $nweight($ngb)}];
		    }
		}
	    }
	    #node is matched with itself
	    if {$matched_ngb == 0} then {
		set nmatch($unmatched_node) $unmatched_node;
		set nmap($unmatched_node) $cnvertices;
		set cnweight($cnvertices) $nweight($unmatched_node);
	    }
	    debug "nmap($unmatched_node)=$nmap($unmatched_node),$unmatched_node,$nmatch($unmatched_node) ";
	    incr cnvertices;
	}
    }

    array set cnneighbour {};
    set used_nodes  "";
    set cngb 0;
  
    #coarse graph
    for {set i 0} {[llength $used_nodes] < $cnvertices} {incr i} {
	set parent1 $i;
	set parent2 $nmatch($i);
	set cnode $nmap($parent1);

	if {[lsearch $used_nodes $cnode] > -1} {
	    continue;
	}
	lappend used_nodes $cnode;

	#save all neighbours from the 2 parent nodes to their coarse node
	set temp_ngb_list "";
	if {[info exists nneighbour($parent1)] && [info exists nneighbour($parent2)]} then {
	    # take all neighbours from "parent"-nodes
	    set all_neighbours [concat $nneighbour($parent1) $nneighbour($parent2)];
	    foreach ngb $all_neighbours {
		set ngb_map $nmap($ngb);
		#don't save duplicates
		if {$ngb_map == $cnode} then {
		     continue;
		}

		if {[lsearch $temp_ngb_list $ngb_map] == -1} then {
		    lappend temp_ngb_list $ngb_map;
		}
	    }

	    set cnneighbour($cnode)  $temp_ngb_list;
	}
    }
  
    ##############  EDGES	###############

    array set cearray {};
    set cnum_edges 0;

    #coarse edges
    for {set i 0} {$i < [array size earray]} {incr i} {
	set twin 0;
	set node1 [lindex $earray($i) 0];
	set node2 [lindex $earray($i) 1];
 
	set cnode1 $nmap($node1);
	set cnode2 $nmap($node2);
 
	if {$cnode1 == $cnode2} then {
	    #edge between two coarsed nodes disappears
	} else {
	    #check if the link already exists in coarsed graph
	    for {set j 0} {$j < [array size cearray]} {incr j} {
		if {$cearray($j) == "$cnode1 $cnode2" || $cearray($j) == "$cnode2 $cnode1"} then {
		    set twin 1;
		    #add the edge weight to the weight of coarsed edge
		    incr ceweight($j) $eweight($i);
		    break;
		}
	    }
	    #if its no double edge, make a new edge in coarsed graph
	    if {$twin == 0} then {
		set cearray($cnum_edges) "$cnode1 $cnode2";
		set ceweight($cnum_edges) $eweight($i);
		incr cnum_edges;
	    }
	}
    }
  
    #repeat coarsening
    if {$cnvertices > $COARSEN_TO && $nvertices > $cnvertices} {
	coarseGraph $cnvertices cnweight cnneighbour cearray ceweight tpwgts;
    } else {
	#enough coarsed, partition the coarsest graph
	makePartitions $cnvertices cnweight cnneighbour cearray ceweight tpwgts
    } 
    debug "match Over !!!";

    #balance, refine and uncoarse the graph
    balance $cnvertices cnneighbour cnweight cearray ceweight tpwgts 4;
    FMRefinement $cnvertices cnneighbour cnweight cearray ceweight tpwgts 4;
    project2waypartition $nvertices earray eweight nneighbour nmap nweight $cnvertices cnweight;
}	

#****f* graph_partitioning.tcl/makePartitions
# NAME
#   makePartitions -- initial partitioning
# SYNOPSIS
#   makePartitions $nvertices node_weight node_neighbour edge_array edge_weight $tpwgts2
# FUNCTION
#   Initial partitioning of the coarsest graph.
# INPUTS
#   *  nvertices -- number of vertices
#   *  node_weight -- array of node weights
#   *  node_neighbour -- array of node neighbours
#   *  edge_array -- array of edges
#   *  edge_weight -- array of edge weights
#   *  tpwgts2 -- array of each partition size of the graph
#****
proc makePartitions {nvertices node_weight node_neighbour edge_array edge_weight tpwgts2} {
    global COARSEN_TO;
    global part_pwgts;
    global part_partition;
    global part_boundary;
    global part_id;
    global part_ed;
    global part_mincut;
  
    upvar $node_weight nweight;
    upvar $node_neighbour nneighbour;
    upvar $edge_array earray;
    upvar $edge_weight eweight;
    upvar $tpwgts2 tpwgts;

    #the sum of weight of all neighbours
    array set wsum_ngbs {};
    array set bestpartition {};
    array set part_partition {};
    array set visited {};
    array set part_ed {};
    array set part_id {};
  
    set part_mincut 0;

    #calculate the sum of all edge-weights in graph
    set wsum 1;
    for {set i 0} {$i < $nvertices} {incr i} {
	if {[info exists nneighbour($i)]} then {
	    foreach ngb $nneighbour($i) {
		set e [getEdgeBetween $i $ngb earray];
		incr wsum $eweight($e);
	    }
	}
	set bestpartitions($i) -1;
    }
    set bestcut $wsum;
  
    if {$nvertices <= $COARSEN_TO} then {
	set nbfs 4;
    } else {
	set nbfs 9;
    }

    while {$nbfs > 1} {
    	incr nbfs -1;
	set part_boundary "";
    	# set all vertices to partition 1, and for all vertices to not visited
    	for {set i 0} {$i < $nvertices} {incr i} {
	    set part_partition($i) 1;
      	    set visited($i) 0;
    	}

    	set part_pwgts(0) 0;
    	set part_pwgts(1) [expr {$tpwgts(0) + $tpwgts(1)}];

    	# Breadth - first algorithm
    	set queue {};
    	set start_node [expr {int(rand() * $nvertices)}];
    	set queue $start_node;
    	set visited($start_node) 1;

	while {1} {
	    #graph is disconnected
	    if {[llength $queue] == 0} {
		set more_left 0;
		for {set n 0} {$n < $nvertices} {incr n} {
		    if {$visited($n) == 0} then {
			set queue $n;
			set visited($n) 1;
			set more_left 1;
			break;
		    }
		}
		if {$more_left == 0} then {
		    debug "no more left!";
		    break;
		}
	    }
	    # take the first node from queue
	    set i [lindex $queue 0];
	    set queue [lreplace $queue 0 0];
		
	    if {$part_pwgts(0) > 0 && [expr {$part_pwgts(1) - $nweight($i)}] < $tpwgts(1)} then {
		debug "preveliko, dalje...";
		continue;
	    }
	    #change partition of i from 1 to 0
	    set part_partition($i) 0;
		
	    #update the partitions weight
	    set part_pwgts(0) [expr {$part_pwgts(0) + $nweight($i)}];
	    set part_pwgts(1) [expr {$part_pwgts(1) - $nweight($i)}];

	    #partition is bigger than it should be
	    if {$part_pwgts(1) <= $tpwgts(1)} then {
		debug "tpwgts(1)=$tpwgts(1)";
		break;
	    }
		
	    #search for the not visited neighbors, and attach them to the queue
	    if {[info exists nneighbour($i)]} then {
		foreach ngb $nneighbour($i) {			
		    if {$visited($ngb) == 0} {
			set visited($ngb) 1;
			lappend queue $ngb;
		    };#if
		};#foreach
	    }

	};#while

    
	array set pwgts2 {};
	set pwgts2(0) 0;
	set pwgts2(1) 0;
    
	#calculate ID and ED for each vertex
	for {set i 0} {$i < $nvertices} {incr i} {
	    set part_id($i) 0;
	    set part_ed($i) 0;

	    set curr_partition $part_partition($i);
	    incr pwgts2($curr_partition) $nweight($i);

	    # calculates the sum of the edge weights of the adjacent vertices of i
	    if {[info exists nneighbour($i)]} then {
		foreach ngb $nneighbour($i) {
		    if {$curr_partition == $part_partition($ngb)} then {
			# vertice in the same partition
			incr part_id($i) $eweight([getEdgeBetween $i $ngb earray]);
		    } else {
			# vertice in a different partition
			incr part_ed($i) $eweight([getEdgeBetween $i $ngb earray]);
		    };#if-else
		};#foreach

		if {$part_ed($i) > 0 || [llength $nneighbour($i)] == 0} then {
		    #vanjski node, ili nema susjeda
		    incr part_mincut $part_ed($i);
		    lappend part_boundary $i;	
		}
	    }
	}

	set part_mincut [expr {$part_mincut / 2}];
	set sum 0;
	debug "init part: part_mincut=$part_mincut";
	for {set k 0} {$k < $nvertices} {incr k} {
	    incr sum $nweight($k);
	}
	
	if {$pwgts2(0) + $pwgts2(1) != $sum} {
	    error "refine: partition weigth wrong!";
	}
    
	#balance the graph
	balance $nvertices nneighbour nweight earray eweight tpwgts 4;
	# edge - based FM refinement
	FMRefinement $nvertices nneighbour nweight earray eweight tpwgts 4;
    
	#save the partitions if better then current saved
	if {$bestcut > $part_mincut} then {
	    set bestcut $part_mincut;
	    set bestboundary $part_boundary;
	    set bestpwgts(0) $part_pwgts(0);
	    set bestpwgts(1) $part_pwgts(1);
	    for {set i 0} {$i < $nvertices} {incr i} {
		set bestpartitions($i) $part_partition($i); #save the best partitions
		set bestid($i) $part_id($i);
		set bested($i) $part_ed($i);
		
	    }
	    if {$part_mincut == 0} then {
		break;
	    }
	}
    }

    #save to globals the best found partitions
    set part_mincut $bestcut;
    set part_boundary $bestboundary;
    set part_pwgts(0) $bestpwgts(0);
    set part_pwgts(1) $bestpwgts(1);
    for {set i 0} {$i < $nvertices} {incr i} {
	set part_partition($i) $bestpartitions($i);
	set part_id($i) $bestid($i);
	set part_ed($i) $bested($i);
    }
}

#****f* graph_partitioning.tcl/balance
# NAME
#   balance
# SYNOPSIS
#   balance $nvertices node_neighbour node_weight edge_array edge_weight tpart_wgts $npasses
# FUNCTION
#   Procedure swaps vertices between two partitions, to make the partitions balanced. 
#   The vertices from the bigger partition
#   are swapped to the smaller partition. After swapping, the ed and id arrays are
#   for all neighbor vertices updated.
# INPUTS
#   *  nvertices -- number of vertices
#   *  node_weight -- array of node weights
#   *  node_neighbour -- array of node neighbours
#   *  edge_array -- array of edges
#   *  edge_weight -- array of edge weights
#   *  tpart_wgts -- array of each partition size of the graph
#   *  npasses -- number of swap tries
#****
proc balance {nvertices node_neighbour node_weight edge_array edge_weight tpart_wgts npasses} {
    global part_pwgts;
    global part_partition;
    global part_boundary;
    global part_id;
    global part_ed;
    global part_mincut;
  
    upvar $node_neighbour nneighbour;
    upvar $node_weight nweight;
    upvar $edge_array earray;
    upvar $edge_weight eweight;
    upvar $tpart_wgts tpwgts;

    set move_from -1;
    set move_to -1;

    #there is no boundary nodes		  
    if {[llength $part_boundary] == 0} then {
	return;
    }

    # chose the the bigger partition to move from
    if {($tpwgts(0) - $part_pwgts(0)) < ($tpwgts(1) - $part_pwgts(1))} then {
	set move_from 0;
	set move_to 1;
    } else {
	set move_from 1;
	set move_to 0;
    }

    #prority queue
    array set queue {};

    #put all boundary nodes from move_from partition into queue
    for {set i 0} {$i < [llength $part_boundary]} {incr i} {
	set b [lindex $part_boundary $i];
	if {$part_partition($b) == $move_from} then {
	    set b_gain [expr {$part_ed($b) - $part_id($b)}];
	    push queue($move_from) "$b $b_gain";
	}
    }

    # set all vertices free to move
    for {set i 0} {$i < $nvertices} {incr i} {
	set moved($i) -1;
    }


    for {set pass 0} {$pass < $npasses} {incr pass} {
	# doesn't exists, if nodes are not connected 
	if {![info exists queue($move_from)]} then {
	    break;
	}

	# chose the node with the highest gain
	set hi_gain [pop queue($move_from)];
	if {$hi_gain == ""} {
	    debug "queue($move_from) empty.";
	    break;
	}
    
	#if the size of the partition, in which the node should be moved
	#is to small, dont move it
	if {$part_pwgts($move_to) + $nweight($hi_gain) > $tpwgts($move_to)}  then {
	    break;
	}

	#update partitions weight
	incr part_pwgts($move_from) [expr {-$nweight($hi_gain)}];
	incr part_pwgts($move_to) $nweight($hi_gain);
    
	set part_partition($hi_gain) $move_to;
 
	#all the "extern" links are now "intern", and umgekehrt
	set tmp $part_ed($hi_gain);
	set part_ed($hi_gain) $part_id($hi_gain);
	set part_id($hi_gain) $tmp;

	#if it's no more boundary node
	if {$part_ed($hi_gain) == 0} then {
	    #remove it from the bndy list
	    set bndy [lreplace $part_boundary [lsearch $part_boundary $hi_gain] [lsearch $part_boundary $hi_gain]];
	}

	#update part_id, part_ed values
	# go throught all neighbours of node "hi_gain"
	if {[info exists nneighbour($hi_gain)]} then {
	    foreach ngb $nneighbour($hi_gain) {
		set is_bnd_node  $part_ed($ngb); #if the value is > 0, it is a boundary node
		set edgeBetween [getEdgeBetween $hi_gain $ngb earray];
		if {$part_partition($ngb) == $move_to} then {
		    incr part_id($ngb) $eweight($edgeBetween);
		    incr part_ed($ngb) -$eweight($edgeBetween);
		} else {
		    incr part_ed($ngb) $eweight($edgeBetween);
		    incr part_id($ngb) -$eweight($edgeBetween);
		}
	
		if {$is_bnd_node > 0} then {
		    #node "ngb" is no longer an boundary node
		    if {$part_ed($ngb) == 0} then {
			#remove it from the boundary list
			set part_boundary [lreplace $part_boundary [lsearch $part_boundary $ngb] [lsearch $part_boundary $ngb]];
			if {$moved($ngb) == -1 && ($part_partition($ngb)==$move_from)} then {
			    #if not moved -> remove it from the queue
			    removeFromQueue queue($part_partition($ngb)) $ngb;
			}
		    } else {
			#if it wasn't been moved, update it in queue
			if {$moved($ngb) == -1 && ($part_partition($ngb) == $move_from)} then {
			    removeFromQueue queue($part_partition($ngb)) $ngb;
			    set new_gain [expr {$part_ed($ngb) - $part_id($ngb)}];
			    push queue($part_partition($ngb)) "$ngb $new_gain";
			}
		    }
		} else {
		    #puts "not boundary node: $ngb";
		    if {$part_ed($ngb) > 0} then {
			#new boundary node
			lappend part_boundary $ngb;
			#add it to the queue
			if {$moved($ngb) == -1} then {
			    push queue($part_partition($ngb)) "$ngb [expr {$part_ed($ngb) - $part_id($ngb)}]";
			}
		    }
		}
	    }
	}
    }
}

#****f* graph_partitioning.tcl/FMRefinement
# NAME
#   FMRefinement
# SYNOPSIS
#   FMRefinement $nvertices node_neighbour node_weight edge_array edge_weight tpart_wgt $npasses
# FUNCTION
#   Procedure swaps the vertices between two partition, to reduce the edge-cut.
# INPUTS
#   *  nvertices -- number of vertices
#   *  node_weight -- array of node weights
#   *  node_neighbour -- array of node neighbours
#   *  edge_array -- array of edges
#   *  edge_weight -- array of edge weights
#   *  tpart_wgts -- array of each partition size of the graph
#   *  npasses -- number of swap tries 
#****
proc FMRefinement {nvertices node_neighbour node_weight edge_array edge_weight tpart_wgt npasses} {
    global part_pwgts;
    global part_partition;
    global part_boundary;
    global part_id;
    global part_ed;
    global part_mincut;
  
    upvar $node_weight nweight;
    upvar $node_neighbour nneighbour;
    upvar $edge_array earray;
    upvar $edge_weight eweight;
    upvar $tpart_wgt tpwgts;

    array set queue {};
    array set bak_id {};
    array set bak_ed {};
    array set bak_part {};
    array set bak_pwgts {};

    set bak_bndy -1;
    set orig_diff [expr {abs ($tpwgts(0) - $part_pwgts(0))}];
    set avg1 [expr {($part_pwgts(0) + $part_pwgts(1)) / 20}];
    set avg2 [expr {2 * ($part_pwgts(0) + $part_pwgts(1)) / $nvertices}];
    if {$avg1 < $avg2} then {
	set avg_pwgt $avg1;
    } else {
	set avg_pwgt $avg2;
    }
	
    set swap_limit [expr {int(0.01 * $nvertices)}];
    if {$swap_limit < 15} then {
	set swap_limit 15;
    }

    #pamti najbolju kombinaciju
    set bak_bndy $part_boundary;
    for {set i 0} {$i < $nvertices} {incr i} {
	set bak_part($i) $part_partition($i);
	set bak_id($i) $part_id($i);
	set bak_ed($i) $part_ed($i);
    }
    set bak_pwgts(0) $part_pwgts(0);
    set bak_pwgts(1) $part_pwgts(1);

	
    # set all vertices free to move
    for {set i 0} {$i < $nvertices} {incr i} {
	set moved($i) -1;
    }

    for {set pass 0} {$pass < $npasses} {incr pass} {
	#set all variables to their's initial values
	set bndy $part_boundary;
	set newcut $part_mincut;
	set mincut $part_mincut;
	set min_diff [expr {abs ($tpwgts(0) - $part_pwgts(0))}];

	for {set i 0} {$i < 2} {incr i} {
	    set pwgts($i) $part_pwgts($i);
	    set queue($i) "";
	}

	for  {set i 0} {$i < $nvertices} {incr i} {
	    set part($i) $part_partition($i);
	    set id($i) $part_id($i);
	    set ed($i) $part_ed($i);
	}
		
	# insert boundary nodes in the priority queue
	set permList [makePermArray bndy];
	array set permArray $permList;
	set mincutorder -1;
	
	for {set i 0} {$i < [array size permArray]} {incr i} {
	    set node $permArray($i);
	    #calculate the node's gain
	    set node_gain [expr {$ed($node) - $id($node)}];
	    # push in the queue 0 or 1 (depends in which partition node is) the node and its gain
	    push queue($part($node)) "$node $node_gain";
	};#foreach

	# chose the best-gain move
	for {set nswaps 0} {$nswaps < $nvertices} {incr nswaps} {
	    debug "nswaps=$nswaps";
	    # chose the node from the bigger partition to move to the smaller
	    if {($tpwgts(0) - $pwgts(0)) < ($tpwgts(1) - $pwgts(1))} then {
		set move_from 0;
		set move_to 1;
	    } else {
		set move_from 1;
		set move_to 0;
	    }
	
	    # chose the node with the highest gain
	    set hi_gain [pop queue($move_from)];
	    if {$hi_gain == ""} {
		break;
	    }
	
	    # update the cut and partitions weight
	    set newcut [expr {$newcut - $ed($hi_gain) + $id($hi_gain)}];
	    incr pwgts($move_from) [expr {-$nweight($hi_gain)}];
	    incr pwgts($move_to) $nweight($hi_gain);
	
	    #check if the new cut better is than the old one
	    set new_diff [expr {abs ($tpwgts(0) - $pwgts(0))}];
	    if {($newcut < $mincut) && ($new_diff <= $orig_diff + $avg_pwgt) || 
		($newcut == $mincut) && ($new_diff < $min_diff)} then {
		set mincutorder $nswaps;
		set mincut $newcut;
		set min_diff $new_diff;
	    } elseif {$nswaps - $mincutorder > $swap_limit} {
		incr newcut [expr {$ed($hi_gain) - $id($hi_gain)}];
		incr pwgts($move_to) [expr {-$nweight($hi_gain)}];
		incr pwgts($move_from) $nweight($hi_gain);
		break;
	    }
	
	    #move node to the other partion
	    set part($hi_gain) $move_to;
	    set moved($hi_gain) $nswaps;
	    set swaps($nswaps) $hi_gain;

	    #all the "extern" links are now "intern", and reverse
	    set tmp $ed($hi_gain);
	    set ed($hi_gain) $id($hi_gain);
	    set id($hi_gain) $tmp;

	    #if it's no more boundary node
	    if {$ed($hi_gain) == 0} then {
		#remove it from the bndy list
		set bndy [lreplace $bndy [lsearch $bndy $hi_gain] [lsearch $bndy $hi_gain]];
	    }

	    #update ID, ED values
	    # go throught all neighbours of node "hi_gain"
	    if {[info exists nneighbour($hi_gain)]} then {
		foreach ngb $nneighbour($hi_gain) {
		    set is_bnd_node  $ed($ngb); #if the value is > 0, it is a boundary node
		    set edgeBetween [getEdgeBetween $hi_gain $ngb earray];
		    if {$part($ngb) == $move_to} then {
			incr id($ngb) $eweight($edgeBetween);
			incr ed($ngb) -$eweight($edgeBetween);
		    } else {
			incr ed($ngb) $eweight($edgeBetween);
			incr id($ngb) -$eweight($edgeBetween);
		    }
		    if {$is_bnd_node > 0} then {
			#node "ngb" is no longer an boundary node
			if {$ed($ngb) == 0} then {
			    #remove it from the boundary list
			    set bndy [lreplace $bndy [lsearch $bndy $ngb] [lsearch $bndy $ngb]];
			    if {$moved($ngb) == -1} then { 
				#if not moved -> remove it from the queue
				removeFromQueue queue($part($ngb)) $ngb;
			    }
			} else {
			    #if it wasn't been moved, update it in queue
			    if {$moved($ngb) == -1} then {
				removeFromQueue queue($part($ngb)) $ngb;
				set new_gain [expr {$ed($ngb) - $id($ngb)}];
				push queue($part($ngb)) "$ngb $new_gain";
			    }
			}
		    } else {
			#puts "not boundary node: $ngb";
			if {$ed($ngb) > 0} then { ;#new boundary node
			    lappend bndy $ngb;
			    #add it to the queue
			    if {$moved($ngb) == -1} then {
				push queue($part($ngb)) "$ngb [expr {$ed($ngb) - $id($ngb)}]";
			    }
			}
		    }
		}
	    }

	    if {$mincutorder > -1} then {
		set mincutorder -1;
		set mincut $newcut;
		set bak_bndy $bndy;
		for {set j 0} {$j < $nvertices} {incr j} {
		    set bak_id($j) $id($j);
		    set bak_ed($j) $ed($j);
		    set bak_part($j) $part($j);
		}
		set bak_pwgts(0) $pwgts(0);
		set bak_pwgts(1) $pwgts(1);		    
	    }
	};#inner loop
    };#outer loop

    #save the best partitions
    set part_mincut $mincut;
    set part_boundary $bak_bndy;
    for {set i 0} {$i < $nvertices} {incr i} {
	set part_partition($i) $bak_part($i);
	set part_id($i) $bak_id($i);
	set part_ed($i) $bak_ed($i);
    }
    set part_pwgts(0) $bak_pwgts(0);
    set part_pwgts(1) $bak_pwgts(1);
}

#****f* graph_partitioning.tcl/project2waypartition
# NAME
#   project2waypartition
# SYNOPSIS
#   project2waypartition $nvertices edge_array edge_weight node_neighbour node_map node_weight cnv $cnvw
# FUNCTION
#   The partitions from the coarserer graph propagates one level up.
# INPUTS
#   *  nvertices -- number of vertices
#   *  node_weight -- array of node weights
#   *  node_neighbour -- array of node neighbours
#   *  edge_array -- array of edges
#   *  edge_weight -- array of edge weights
#   *  node_map -- array with mappings of nodes from parent to child (coarse) graph
#   *  cnv -- number of vertices in coarse graph
#   *  cnvw -- array of node weights in coarse graph
#****
proc project2waypartition {nvertices edge_array edge_weight node_neighbour node_map node_weight cnv cnvw} {
    global part_pwgts;
    global part_mincut;
    global part_partition;
    global part_id;
    global part_ed;
    global part_boundary;
  
    upvar $cnvw cnw;
    upvar $node_weight nweight;
    upvar $edge_array earray;
    upvar $edge_weight eweight;
    upvar $node_neighbour nneighbour;
    upvar $node_map nmap;

    array set part_ed {};
    array set part_id {};
    set part_boundary "";
    array set pwgts2 {};
	
    #sum the weight of nodes in finer graph	
    set n 0; set p 0;
    for {set i 0} {$i < $nvertices} {incr i} {
	incr n $nweight($i);
    }
    #sum the weight of nodes in coarsed graph
    for {set i 0} {$i < $cnv} {incr i} {
	incr p $cnw($i);
    }

    #get partition for each vertex in finer graph
    for {set i 0} {$i < $nvertices} {incr i} {
	set cnode $nmap($i); #get the node in coarsed graph which corresponse to the node in finer graph
	set partition($i) $part_partition($cnode); #get it's partition too
	set part_ed($i) 0;
	set part_id($i) 0;
	set pwgts2(0) 0;
	set pwgts2(1) 0;
    }

    #calculate ID and ED
    for {set i 0} {$i < $nvertices} {incr i} {
	if {![info exists nneighbour($i)] || [llength $nneighbour($i)] == 0} then {
	    lappend part_boundary $i;
	} else {
	    foreach ngb $nneighbour($i) {
		if {$partition($ngb) == $partition($i)} then {
		    incr part_id($i) $eweight([getEdgeBetween $i $ngb earray]); #mogu uzeti stare tezine - posto iste
		    #incr id($ngb) $eweight([...]);
		} else {
		    incr part_ed($i) $eweight([getEdgeBetween $i $ngb earray]);
		    #incr ed($ngb) $eweight([...]);
		}
	    };#foreach

	    if {[expr $part_ed($i) > 0 || [llength $nneighbour($i)] == 0]} then {
		lappend part_boundary $i;
	    }
	}
	set part_partition($i) $partition($i);
	incr pwgts2($partition($i)) $nweight($i);
    };#for   
}

#****f* graph_partitioning.tcl/splitGraph
# NAME
#   splitGraph
# SYNOPSIS
#   splitGraph $nvertices node_neighbour node_weight edge_array edge_weight snode_neighbour snode_weight sedge_array sedge_weight snode_map sn_vtxs sn_edges snode_map_help
# FUNCTION
#   Divides the graph into two parts, one with nodes in partition 0 and the other with
#   the nodes in the partition 1.
# INPUTS
#   *  nvertices -- number of vertices
#   *  node_weight -- array of node weights
#   *  node_neighbour -- array of node neighbours
#   *  edge_array -- array of edges
#   *  edge_weight -- array of edge weights
#   *  snode_weight -- array of node weights of the split graph
#   *  snode_neighbour -- array of node neighbours of the split graph
#   *  sedge_array -- array of edges of the split graph
#   *  sedge_weight -- array of edge weights of the split graph
#   *  snode_map -- array with mappings of nodes from parent to child (coarse) graph
#   *  sn_vtxs -- number of vertices of the split graph
#   *  sn_edges -- number of edges of the split graph
#   *  snode_map_help -- help variable, needed for later connecting, in this procedure disconnected graphs
#****
proc splitGraph {nvertices node_neighbour node_weight edge_array edge_weight snode_neighbour snode_weight sedge_array sedge_weight snode_map sn_vtxs sn_edges snode_map_help} {
    global part_partition;

    upvar $node_neighbour nneighbour;
    upvar $node_weight nweight;
    upvar $edge_array earray;
    upvar $edge_weight eweight;
    upvar $snode_neighbour snneighbour;
    upvar $snode_weight snweight;
    upvar $sedge_array searray;
    upvar $sedge_weight seweight;
    upvar $snode_map snmap;
    upvar $snode_map_help snmap_h;
    upvar $sn_vtxs snvtxs;
    upvar $sn_edges snedges;

    array set sum_np {};
    set sum_np(0) 0;
    set sum_np(1) 0;

    array set auxn {};
    array set auxw {};

    #sets variables needed later for connecting the splited graph
    for {set i 0} {$i < $nvertices} {incr i} {
	set p $part_partition($i);
	set snmap($p,$i) $snvtxs($p);
	set snmap_h($p,$snvtxs($p)) $i;
	incr snvtxs($p);
    }

    #split the graph
    for {set i 0} {$i < $nvertices} {incr i} {
	set p_i $part_partition($i);
	set s_i $snmap($p_i,$i);
	set sum 0;

	if {[info exists nneighbour($i)]} then {
	    foreach ngb $nneighbour($i) {
		set p $part_partition($ngb);
		if {$p == $p_i} then {
		    set twin 0;
		    set sngb $snmap($p_i,$ngb);
		    lappend snneighbour($p_i,$s_i) $sngb; 
		    for {set a 0} {$a < $snedges($p_i)} {incr a} {
			if {$searray($p_i,$a) == "$s_i $sngb" || $searray($p_i,$a) == "$sngb $s_i"} then {
			    set twin 1;
			    break;
			}
		    }
		    if {$twin == 0} then {
			set searray($p_i,$snedges($p_i)) "$s_i $sngb";
			set seweight($p_i,$snedges($p_i)) $eweight([getEdgeBetween $i $ngb earray]);
			incr snedges($p_i);
		    }
		    incr sum $nweight($ngb);
		} else {
		    incr sum [expr {-$nweight($ngb)}]
		}
	    };#foreach
	}
	set snweight($p_i,$s_i) $nweight($i);
	set sadjwgtsum($p_i,$s_i)) $sum;
    }
}


#****f* graph_partitioning.tcl/sum_array
# NAME
#   sum_array
# SYNOPSIS
#   sum_array $end arr
# FUNCTION
#   Function sum the elements from the array.
# INPUTS
#   *  end -- until what index to sum
#   *  arr -- array of numbers
# RESULT
#   * sum -- the sum of first "end" numbers
#****
proc sum_array {end arr} {
    upvar 1 $arr a;
    set sum 0.0;

    for {set i 0} {$i < $end} {incr i} {
	set sum [expr {$sum + $a($i)}];
    }

    return $sum;
}

#****f* graph_partitioning.tcl/mult_array
# NAME
#   mult_array
# SYNOPSIS
#   mult_array $start $end arr $prod
# FUNCTION
#   Procedure multiplyes the elements between start and end position in the array
#   with the number prod
# INPUTS
#   *  start -- the position in array from where to start multipling
#   *  end -- the position in array until which to multiply
#   *  arr -- array 
#   *  prod -- 
# RESULT
#   * 
#****
proc mult_array {start end arr prod} {
    upvar 1 $arr a;
    for {set i $start} {$i < $end} {incr i} {
	set a($i) [expr {$a($i) * $prod }];
    }
}

#****f* graph_partitioning.tcl/makePermList
# NAME
#   makePermList -- make permuted list
# SYNOPSIS
#   makePermList $num
# FUNCTION
#   Function makes a new list with num elements, and randomizes the list.
# INPUTS
#   *  num -- number of elements in list
# RESULT
#   * list -- permuted list
#****
proc makePermList {num} {
    array set permList "";

    for {set i 0} {$i < $num} {incr i} {
	set permList($i) $i;
    }

    if {$num > 4} {
  	for {set i 0} {$i < $num} {incr i 16} {
	    set rand1 [expr {int(rand() * ($num -  4))}]
	    set rand2 [expr {int(rand() * ($num -  4))}]
    
	    swap permList $rand1 $rand2;
	    swap permList [expr $rand1+1] [expr $rand2+1];
	    swap permList [expr $rand1+2] [expr $rand2+2];
	    swap permList [expr $rand1+3] [expr $rand2+3];
  	}
    }
  
    return [array get permList];
}

#****f* graph_partitioning.tcl/makePermArray
# NAME
#   makePermArray -- make permuted array
# SYNOPSIS
#   makePermArray arr
# FUNCTION
#   Function randomizes the elements in the array.
# INPUTS
#   *  arr -- array to randomize
# RESULT
#   *  list -- permuted list
#****
proc makePermArray {arr} {
    upvar $arr a;
    array set permList "";
    set a_size [llength $a];
    for {set i 0} {$i < $a_size} {incr i} {
	set permList($i) [lindex $a $i];
    }

    if {$a_size > 4} {
  	for {set i 0} {$i < $a_size} {incr i 16} {
	    set rand1 [expr {int(rand() * ($a_size -  4))}]
	    set rand2 [expr {int(rand() * ($a_size -  4))}]
    
	    swap permList $rand1 $rand2;
	    swap permList [expr $rand1+1] [expr $rand2+1];
	    swap permList [expr $rand1+2] [expr $rand2+2];
	    swap permList [expr $rand1+3] [expr $rand2+3];
  	}
    }
  
    return [array get permList];
}

#****f* graph_partitioning.tcl/swap
# NAME
#   swap
# SYNOPSIS
#   swap permArray $idx1 $idx2
# FUNCTION
#   Procedure swapps two elements in the array.
# INPUTS
#   *  permList -- array
#   *  idx1 -- index of the first element
#   *  idx2 -- index of the second element
#****
proc swap {permArray idx1 idx2} {
    upvar $permArray rarray;

    set temp $rarray($idx1);
    set rarray($idx1) $rarray($idx2);
    set rarray($idx2) $temp;
}

#****f* graph_partitioning.tcl/getEdgeBetween
# NAME
#   getEdgeBetween -- get edge between
# SYNOPSIS
#   getEdgeBetween $node1 $node2 edge_array
# FUNCTION
#   Function searches for an edge connecting the two nodes.
# INPUTS
#   *  node1 -- first node id
#   *  node2 -- second node id
#   *  edge_array -- array of edges
# RESULT
#   * i -- index of the edge connecting the nodes, or null
#****
proc getEdgeBetween {node1 node2 edge_array} {
    upvar $edge_array earray;
    for {set i 0} {$i < [array size earray]} {incr i} {
	if {$earray($i) == "$node1 $node2" || $earray($i) == "$node2 $node1"} then {
	    return $i;
	}
    }
}

#****f* graph_partitioning.tcl/push
# NAME
#   push
# SYNOPSIS
#   push
# FUNCTION
#   Alias for the command lappend.
#****
interp alias {} push {} lappend

#****f* graph_partitioning.tcl/pop
# NAME
#   pop
# SYNOPSIS
#   pop queue
# FUNCTION
#   Returns the element from the queue with the highest priority.
# INPUTS
#   *  queue_name -- array
# RESULT
#   * hi_elem -- element from the array
#****
proc pop {queue_name} {
    upvar 1 $queue_name queue;

    #sort items after priority
    set queue [lsort -integer -decreasing -index 1 $queue];
    set hi_ [lindex $queue 0];
    set hi_elem [lindex $hi_ 0];
    set queue [lrange $queue 1 end];
    return $hi_elem;
}

#****f* graph_partitioning.tcl/removeFromQueue
# NAME
#   removeFromQueue -- remove from the queue
# SYNOPSIS
#   removeFromQueue queue_name $node
# FUNCTION
#   Removes the node from the queue.
# INPUTS
#   *  queue_name -- array
#   *  node -- node id
#****
proc removeFromQueue {queue_name node } {
    upvar 1 $queue_name queue;
	
    foreach q $queue {
	set n [lindex $q 0];
	if {$n == $node} then {
	    set node_idx [lsearch $queue $q];
	    set queue [lreplace $queue $node_idx $node_idx];
	}
    }
}


############ GLOBALS

set debug 0;
array set tpwgts {};
set nparts 0;
set finalcut 0;
set COARSEN_TO 20;
array set pwgts {};
set minPartWeight 0;
set split_list "";
array set finalpartition {};
set part_boundary "";
array set part_partition {};
array set part_id {};
array set part_ed {};
array set part_pwgts {};
set part_mincut 0;
