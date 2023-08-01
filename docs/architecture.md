# CORE Architecture

## Main Components

* core-daemon
    * Manages emulated sessions of nodes and links for a given network
    * Nodes are created using Linux namespaces
    * Links are created using Linux bridges and virtual ethernet peers
    * Packets sent over links are manipulated using traffic control
    * Provides gRPC API
* core-gui
    * GUI and daemon communicate over gRPC API
    * Drag and drop creation for nodes and links
    * Can launch terminals for emulated nodes in running sessions
    * Can save/open scenario files to recreate previous sessions
* vnoded
    * Command line utility for creating CORE node namespaces
* vcmd
    * Command line utility for sending shell commands to nodes

![](static/architecture.png)

## Sessions

CORE can create and run multiple emulated sessions at once, below is an
overview of the states a session will transition between during typical
GUI interactions.

![](static/workflow.png)

## How Does it Work?

The CORE framework runs on Linux and uses Linux namespacing for creating
node containers. These nodes are linked together using Linux bridging and
virtual interfaces. CORE sessions are a set of nodes and links operating
together for a specific purpose.

### Linux

Linux network namespaces (also known as netns) is the primary
technique used by CORE. Most recent Linux distributions have
namespaces-enabled kernels out of the box. Each namespace has its own process
environment and private network stack. Network namespaces share the same
filesystem in CORE.

CORE combines these namespaces with Linux Ethernet bridging to form networks.
Link characteristics are applied using Linux Netem queuing disciplines.
Nftables provides Ethernet frame filtering on Linux bridges. Wireless networks are
emulated by controlling which interfaces can send and receive with nftables
rules.

## Open Source Project and Resources

CORE has been released by Boeing to the open source community under the BSD
license. If you find CORE useful for your work, please contribute back to the
project. Contributions can be as simple as reporting a bug, dropping a line of
encouragement, or can also include submitting patches or maintaining aspects
of the tool.
