# Tutorial 7 - EMANE

## Overview

This tutorial will cover basic usage and some concepts one may want to
use or leverage when working with and creating EMANE based networks.

<p align="center">
  <img src="/core/static/tutorial7/scenario.png" width="75%">
</p>

For more detailed information on EMANE see the following:

* [EMANE in CORE](../emane.md)
* [EMANE Wiki](https://github.com/adjacentlink/emane/wiki)

## Files

Below is a list of the files used for this tutorial.

* 2 node EMANE ieee80211abg scenario
    * scenario.xml
    * scenario.py
* 2 node EMANE ieee80211abg scenario, with **n2** running the "Chat App Server" service
    * scenario_service.xml
    * scenario_service.py

## Running this Tutorial

This section covers interactions that can be carried out for this scenario.

Our scenario has the following nodes and addresses:

* emane1 - no address, this is a representative node for the EMANE network
* n2 - 10.0.0.1
* n3 - 10.0.0.2

All usages below assume a clean scenario start.

### Using Ping

Using the command line utility **ping** can be a good way to verify connectivity
between nodes in CORE.

* Make sure the CORE daemon is running a terminal, if not already
    ``` shell
    sudop core-daemon
    ```
* In another terminal run the GUI
    ``` shell
    core-gui
    ```
* In the GUI menu bar select **File->Open...**, then navigate to and select **scenario.xml**
   <p align="center">
     <img src="/core/static/tutorial-common/running-open.png" width="75%">
   </p>
* You can now click on the **Start Session** button to run the scenario
   <p align="center">
     <img src="/core/static/tutorial7/scenario.png" width="75%">
   </p>
* Open a terminal on **n2** by double clicking it in the GUI
* Run the following in **n2** terminal
    ``` shell
    ping -c 3 10.0.0.2
    ```
* You should see the following output
    ``` shell
    PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
    64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=7.93 ms
    64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=3.07 ms
    64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=3.05 ms

    --- 10.0.0.2 ping statistics ---
    3 packets transmitted, 3 received, 0% packet loss, time 2000ms
    rtt min/avg/max/mdev = 3.049/4.685/7.932/2.295 ms
    ```

### Using Tcpdump

Using **tcpdump** can be very beneficial for examining a network. You can verify
traffic being sent/received among many other uses.

* Make sure the CORE daemon is running a terminal, if not already
    ``` shell
    sudop core-daemon
    ```
* In another terminal run the GUI
    ``` shell
    core-gui
    ```
* In the GUI menu bar select **File->Open...**, then navigate to and select **scenario.xml**
   <p align="center">
     <img src="/core/static/tutorial-common/running-open.png" width="75%">
   </p>
* You can now click on the **Start Session** button to run the scenario
   <p align="center">
     <img src="/core/static/tutorial7/scenario.png" width="75%">
   </p>
* Open a terminal on **n2** by double clicking it in the GUI
* Open a terminal on **n3** by double clicking it in the GUI
* Run the following in **n3** terminal
    ``` shell
    tcpdump -lenni eth0
    ```
* Run the following in **n2** terminal
    ``` shell
    ping -c 1 10.0.0.2
    ```
* You should see the following in **n2** terminal
    ``` shell
    tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
    listening on eth0, link-type EN10MB (Ethernet), snapshot length 262144 bytes
    14:56:25.414283 02:02:00:00:00:01 > 02:02:00:00:00:02, ethertype IPv4 (0x0800), length 98: 10.0.0.1 > 10.0.0.2: ICMP echo request, id 64832, seq 1, length 64
    14:56:25.414303 02:02:00:00:00:02 > 02:02:00:00:00:01, ethertype IPv4 (0x0800), length 98: 10.0.0.2 > 10.0.0.1: ICMP echo reply, id 64832, seq 1, length 64
    ```

### Running Software

We will now leverage the installed Chat App software to stand up a server and client
within the nodes of our scenario.

* Make sure the CORE daemon is running a terminal, if not already
    ``` shell
    sudop core-daemon
    ```
* In another terminal run the GUI
    ``` shell
    core-gui
    ```
* In the GUI menu bar select **File->Open...**, then navigate to and select **scenario.xml**
   <p align="center">
     <img src="/core/static/tutorial-common/running-open.png" width="75%">
   </p>
* You can now click on the **Start Session** button to run the scenario
   <p align="center">
     <img src="/core/static/tutorial7/scenario.png" width="75%">
   </p>
* Open a terminal on **n2** by double clicking it in the GUI
* Run the following in **n2** terminal
    ``` shell
    export PATH=$PATH:/usr/local/bin
    chatapp-server
    ```
* Open a terminal on **n3** by double clicking it in the GUI
* Run the following in **n3** terminal
    ``` shell
    export PATH=$PATH:/usr/local/bin
    chatapp-client -a 10.0.0.1
    ```
* You will see the following output in **n1** terminal
    ``` shell
    chat server listening on: :9001
    [server] 10.0.0.1:44362 joining
    ```
* Type the following in **n2** terminal and hit enter
    ``` shell
    hello world
    ```
* You will see the following output in **n1** terminal
    ``` shell
    chat server listening on: :9001
    [server] 10.0.0.2:44362 joining
    [10.0.0.2:44362] hello world
    ```

### Tailing a Log

In this case we are using the service based scenario. This will automatically start
and run the Chat App Server on **n2** and log to a file. This case will demonstrate
using `tail -f` to observe the output of running software.

* Make sure the CORE daemon is running a terminal, if not already
    ``` shell
    sudop core-daemon
    ```
* In another terminal run the GUI
    ``` shell
    core-gui
    ```
* In the GUI menu bar select **File->Open...**, then navigate to and select **scenario_service.xml**
   <p align="center">
     <img src="/core/static/tutorial-common/running-open.png" width="75%">
   </p>
* You can now click on the **Start Session** button to run the scenario
   <p align="center">
     <img src="/core/static/tutorial7/scenario.png" width="75%">
   </p>
* Open a terminal on **n2** by double clicking it in the GUI
* Run the following in **n2** terminal
    ``` shell
    tail -f chatapp.log
    ```
* Open a terminal on **n3** by double clicking it in the GUI
* Run the following in **n3** terminal
    ``` shell
    export PATH=$PATH:/usr/local/bin
    chatapp-client -a 10.0.0.1
    ```
* You will see the following output in **n2** terminal
    ``` shell
    chat server listening on: :9001
    [server] 10.0.0.2:44362 joining
    ```
* Type the following in **n3** terminal and hit enter
    ``` shell
    hello world
    ```
* You will see the following output in **n2** terminal
    ``` shell
    chat server listening on: :9001
    [server] 10.0.0.2:44362 joining
    [10.0.0.2:44362] hello world
    ```

## Advanced Topics

This section will cover some high level topics and examples for running and
using EMANE in CORE. You can find more detailed tutorials and examples at
the [EMANE Tutorial](https://github.com/adjacentlink/emane-tutorial/wiki).

!!! note

    Every topic below assumes CORE, EMANE, and OSPF MDR have been installed.

    Scenario files to support the EMANE topics below will be found in
    the GUI default directory for opening XML files.

| Topic                                   | Model   | Description                                               |
|-----------------------------------------|---------|-----------------------------------------------------------|
| [XML Files](../emane/files.md)          | RF Pipe | Overview of generated XML files used to drive EMANE       |
| [GPSD](../emane/gpsd.md)                | RF Pipe | Overview of running and integrating gpsd with EMANE       |
| [Precomputed](../emane/precomputed.md)  | RF Pipe | Overview of using the precomputed propagation model       |
| [EEL](../emane/eel.md)                  | RF Pipe | Overview of using the Emulation Event Log (EEL) Generator |
| [Antenna Profiles](../emane/antenna.md) | RF Pipe | Overview of using antenna profiles in EMANE               |

--8<-- "tutorials/common/grpc.md"
