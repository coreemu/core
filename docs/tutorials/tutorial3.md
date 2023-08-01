# Tutorial 3 - Basic Mobility

## Overview

This tutorial will cover using a 3 node scenario in CORE with basic mobility.
Mobility can be provided from a NS2 file or by including mobility commands in a gRPC script.

## Files

Below is the list of files used for this tutorial.

* movements1.txt - a NS2 mobility input file
* scenario.xml - 3 node CORE xml scenario file  (wireless)
* scenario.py - 3 node CORE gRPC python script (wireless)
* printout.py - event listener

## Running with XML file using NS2 Movement

This section will cover running this sample tutorial using the XML scenario
file, leveraging an NS2 file for mobility.

* Make sure the **core-daemon** is running a terminal
   ```shell
   sudop core-daemon
   ```
* In another terminal run the GUI
   ```shell
   core-gui
   ```
* Observe the format of the N2 file, cat movements1.txt. Note that this file was manually developed.
   ```shell
   $node_(1) set X_ 208.1
   $node_(1) set Y_ 211.05
   $node_(1) set Z_ 0
   $ns_ at 0.0 "$node_(1) setdest 208.1 211.05 0.00"
   $node_(2) set X_ 393.1
   $node_(2) set Y_ 223.05
   $node_(2) set Z_ 0
   $ns_ at 0.0 "$node_(2) setdest 393.1 223.05 0.00"
   $node_(4) set X_ 499.1
   $node_(4) set Y_ 186.05
   $node_(4) set Z_ 0
   $ns_ at 0.0 "$node_(4) setdest 499.1 186.05 0.00"
   $ns_ at 1.0 "$node_(1) setdest 190.1 225.05 0.00"
   $ns_ at 1.0 "$node_(2) setdest 393.1 225.05 0.00"
   $ns_ at 1.0 "$node_(4) setdest 515.1 186.05 0.00"
   $ns_ at 2.0 "$node_(1) setdest 175.1 250.05 0.00"
   $ns_ at 2.0 "$node_(2) setdest 393.1 250.05 0.00"
   $ns_ at 2.0 "$node_(4) setdest 530.1 186.05 0.00"
   $ns_ at 3.0 "$node_(1) setdest 160.1 275.05 0.00"
   $ns_ at 3.0 "$node_(2) setdest 393.1 275.05 0.00"
   $ns_ at 3.0 "$node_(4) setdest 530.1 186.05 0.00"
   $ns_ at 4.0 "$node_(1) setdest 160.1 300.05 0.00"
   $ns_ at 4.0 "$node_(2) setdest 393.1 300.05 0.00"
   $ns_ at 4.0 "$node_(4) setdest 550.1 186.05 0.00"
   $ns_ at 5.0 "$node_(1) setdest 160.1 275.05 0.00"
   $ns_ at 5.0 "$node_(2) setdest 393.1 275.05 0.00"
   $ns_ at 5.0 "$node_(4) setdest 530.1 186.05 0.00"
   $ns_ at 6.0 "$node_(1) setdest 175.1 250.05 0.00"
   $ns_ at 6.0 "$node_(2) setdest 393.1 250.05 0.00"
   $ns_ at 6.0 "$node_(4) setdest 515.1 186.05 0.00"
   $ns_ at 7.0 "$node_(1) setdest 190.1 225.05 0.00"
   $ns_ at 7.0 "$node_(2) setdest 393.1 225.05 0.00"
   $ns_ at 7.0 "$node_(4) setdest 499.1 186.05 0.00"
   ```
* In the GUI menu bar select **File->Open...**, and select this tutorials **scenario.xml** file
* You can now click play to start the session
* Select the play button on the Mobility Player to start mobility
* Observe movement of the nodes
* Note that OSPF routing protocol is included in the scenario to build routing table so that routes to other nodes are
  known and when the routes are discovered, ping will work

<p align="center">
  <img src="/core/static/tutorial3/motion_from_ns2_file.png" width="80%" >
</p>

## Running with the gRPC Script

This section covers using a gRPC script to create and provide scenario movement.

* Make sure the **core-daemon** is running a terminal
   ```shell
   sudop core-daemon
   ```
* From another terminal run the **scenario.py** script
   ```shell
   /opt/core/venv/bin/python scenario.py
   ```
* In another terminal run the GUI
    ```shell
    core-gui
    ```
* In the GUI dialog box select the session and click connect
* You will now have joined the already running scenario
* In the terminal running the **scenario.py**, hit a key to start motion
   <p align="center">
     <img src="/core/static/tutorial3/mobility-script.png" width="80%" >
   </p>
* Observe the link between **n3** and **n4** is shown and then as motion continues the link breaks
   <p align="center">
     <img src="/core/static/tutorial3/motion_continued_breaks_link.png" width="80%" >
   </p>

## Running the Chat App Software

This section covers using one of the above 2 scenarios to run software within
the nodes.

* In the GUI double click on **n4**, this will bring up a terminal for this node
* in the **n4** terminal, run the server
   ```shell
   export PATH=$PATH:/usr/local/bin
   chatapp-server
   ```
* In the GUI double click on **n2**, this will bring up a terminal for this node
* In the **n2** terminal, run the client
   ```shell
   export PATH=$PATH:/usr/local/bin
   chatapp-client -a 10.0.0.4
   ```
* This will result in **n2** connecting to the server
* In the **n2** terminal, type a message at the client prompt and hit enter
   ```shell
   >>hello world
   ```
* Observe that text typed at client then appears in the server terminal
   ```shell
   chat server listening on: :9001
   [server] 10.0.0.2:53684 joining
   [10.0.0.2:53684] hello world
   ```

## Running Mobility from a Node

This section provides an example for running a script within a node, that
leverages a control network in CORE for issuing mobility using the gRPC
API.

* Edit the following line in **/etc/core/core.conf**
   ```shell
   grpcaddress = 0.0.0.0
   ```
* Start the scenario from the **scenario.xml**
* From the GUI open **Session -> Options** and set **Control Network** to **172.16.0.0/24**
* Click to play the scenario
* Double click on **n2** to get a terminal window
* From the terminal window for **n2**, run the script
   ```shell
   /opt/core/venv/bin/python move-node2.py
   ```
* Observe that node 2 moves and continues to move

<p align="center">
  <img src="/core/static/tutorial3/move-n2.png" width="80%" >
</p>
