# Tutorial 6 - Improved Visuals

## Overview

This tutorial will cover changing the node icons, changing the background, and changing or hiding links.

## Files

Below is the list of files used for this tutorial.

* drone.png - icon for a drone
* demo.py - a mobility script for a node
* terrain.png - a background
* completed-scenario.xml - the scenario after making all changes below

## Running this Tutorial

This section will cover running this sample tutorial that develops a scenario file.

* Ensure that **/etc/core/core.conf** has **grpcaddress** set to **0.0.0.0**
* Make sure the **core-daemon** is running in a terminal
    ```shell
    sudop core-daemon
    ```
* In another terminal run the GUI
    ```shell
    core-gui
    ```

### Changing Node Icons

* Create three MDR nodes
   <p align="center">
     <img src="/core/static/tutorial6/create-nodes.png" width="80%">
   </p>
* Double click on each node for configuration, click the icon and set it to use the **drone.png** image
   <p align="center">
     <img src="/core/static/tutorial6/configure-icon.png" width="50%">
   </p>
* Use **Session -> Options** and set **Control Network 0** to **172.16.0.0./24**

### Linking Nodes to WLAN

* Add a WLAN Node
* Link the three prior MDR nodes to the WLAN node
   <p align="center">
     <img src="/core/static/tutorial6/linked-nodes.png" width="50%">
   </p>
* Click play to start the scenario
* Observe wireless links being created
   <p align="center">
     <img src="/core/static/tutorial6/wlan-links.png" width="50%">
   </p>
* Click stop to end the scenario
* Right click the WLAN node and select **Edit -> Hide**
* Now you can view the nodes in isolation
   <p align="center">
     <img src="/core/static/tutorial6/hidden-nodes.png" width="50%">
   </p>

### Changing Canvas Background

* Click **Canvas -> Wallpaper** to set the background to terrain.png
   <p align="center">
     <img src="/core/static/tutorial6/select-wallpaper.png" width="50%">
   </p>
* Click play to start the scenario again
* You now have a scenario with drone icons, terrain background, links displayed and hidden WLAN node
   <p align="center">
     <img src="/core/static/tutorial6/scenario-with-terrain.png" width="80%">
   </p>

## Adding Mobility

* Open and play the **completed-scenario.xml**
* Double click on **n1** and run the **demo.py** script
   ```shell
   # node id is first parameter, second is total nodes
   /opt/core/venv/bin/python demo.py 1 3
   ```
* Let it run to see the link break as the node 1 drone approches the right side
   <p align="center">
     <img src="/core/static/tutorial6/only-node1-moving.png" width="80%">
   </p>
* Repeat for other nodes, double click on **n2** and **n3** and run the demo.py script
   ```shell
   # n2
   /opt/core/venv/bin/python demo.py 2 3
   # n3
   /opt/core/venv/bin/python demo.py 3 3
   ```
* You can turn off wireless links via **View -> Wireless Links**
* Observe nodes moving in parallel tracks, when the far right is reached, the node will move down
  and then move to the left. When the far left is reached, the drone will move down and then move to the right.
   <p align="center">
     <img src="/core/static/tutorial6/scenario-with-motion.png" width="80%">
   </p>
