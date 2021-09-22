## 2021-09-17 CORE 7.5.2

* Installation
    * \#596 - fixes issue related to installing poetry by pinning version to 1.1.7
    * updates pipx installation to pinned version 0.16.4
* core-daemon
    * \#600 - fixes known vulnerability for pillow dependency by updating version

## 2021-04-15 CORE 7.5.1

* core-pygui
    * fixed issues creating and drawing custom nodes

## 2021-03-11 CORE 7.5.0

* core-daemon
    * fixed issue setting mobility loop value properly
    * fixed issue that some states would not properly remove session directories
    * \#560 - fixed issues with sdt integration for mobility movement and layer creation
* core-pygui
    * added multiple canvas support
    * added support to hide nodes and restore them visually
    * update to assign full netmasks to wireless connected nodes by default
    * update to display services and action controls for nodes during runtime
    * fixed issues with custom nodes
    * fixed issue auto assigning macs, avoiding duplication
    * fixed issue joining session with different netmasks
    * fixed issues when deleting a session from the sessions dialog
    * \#550 - fixed issue not sending all service customization data
* core-cli
    * added delete session command

## 2021-01-11 CORE 7.4.0

* Installation
    * fixed issue for automated install assuming ID_LIKE is always present in /etc/os-release
* gRPC API
    * fixed issue stopping session and not properly going to data collect state
    * fixed issue to have start session properly create a directory before configuration state
* core-pygui
    * fixed issue handling deletion of wired link to a switch
    * avoid saving edge metadata to xml when values are default
    * fixed issue editing node mac addresses
    * added support for configuring interface names
    * fixed issue with potential node names to allow hyphens and remove under bars
    * \#531 - fixed issue changing distributed nodes back to local
* core-daemon
    * fixed issue to properly handle deleting links from a network to network node
    * updated xml to support writing and reading link buffer configurations
    * reverted change and removed mac learning from wlan, due to promiscuous like behavior
    * fixed issue creating control interfaces when starting services
    * fixed deadlock issue when clearing a session using sdt
    * \#116 - fixed issue for wlans handling multiple mobility scripts at once
    * \#539 - fixed issue in udp tlv api

## 2020-12-02 CORE 7.3.0

* core-daemon
    * fixed issue where emane global configuration was not being sent to core-gui
    * updated controlnet names on host to be prefixed with ctrl
    * fixed RJ45 link shutdown from core-gui causing an error
    * fixed emane external transport xml generation
    * \#517 - update to account for radvd required directory
    * \#514 - support added for session specific environment files
    * \#529 - updated to configure netem limit based on delay or user specified, requires kernel 3.3+
* core-pygui
    * fixed issue drawing wlan/emane link options when it should not have
    * edge labels are now placed a set distance from nodes like original gui
    * link color/width are now saved to xml files
    * added support to configure buffer size for links
    * \#525 - added support for multiple wired links between the same nodes
    * \#526 - added option to hide/show links with 100% loss
* Documentation
    * \#527 - typo in service documentation
    * \#515 - added examples to docs for using EMANE features within a CORE context

## 2020-09-29 CORE 7.2.1

* core-daemon
    * fixed issue where shutting down sessions may not have removed session directories
    * fixed issue with multiple emane interfaces on the same node not getting the right configuration
* Installation
    * updated automated install to be a bit more robust for alternative distros
    * added force install type to try and leverage a redhat/debian like install
    * locked ospf mdr version installed to older commit to avoid issues with multiple interfaces on same node

## 2020-09-15 CORE 7.2.0

* Installation
    * locked down version of ospf-mdr installed in automated install
    * locked down version of emane to v1.2.5 in automated emane install
    * added option to install locally using the -l option
* core-daemon
    * improve error when retrieving services that do not exist, or failed to load
    * fixed issue with writing/reading emane node interface configurations to xml
    * fixed issue with not setting the emane model when creating a node
    * added common utility method for getting a emane node interface config id in core.utils
    * fixed issue running emane on more than one interface for a node
    * fixed issue validating paths when creating emane transport xml for a node
    * fixed issue avoiding multiple calls to shutdown, if already in shutdown state
* core-pygui
    * fixed issue configuring emane for a node interface
* gRPC API
    * added wrapper client that can provide type hinting and a simpler interface at core.api.grpc.clientw
    * fixed issue creating sessions that default to having a very large reference scale
    * fixed issue with GetSession returning control net nodes

## 2020-08-21 CORE 7.1.0

* Installation
    * added core-python script that gets installed to help globally reference the virtual environment
* gRPC API
    * GetSession will now return all configuration information for a session and the file it was opened from, if applicable
    * node update events will now include icon information
    * fixed issue with getting session throughputs for sessions with a high id
* core-daemon
    * \#503 - EMANE networks will now work with mobility again
    * \#506 - fixed service dependency resolution issue
    * fixed issue sending hooks to core-gui when joining session
* core-pygui
    * fixed issues editing hooks
    * fixed issue with cpu usage when joining a session
    * fixed mac field not being disabled during runtime when configuring a node
    * removed unlimited button from link config dialog
    * fixed issue with copy/paste links and their options
    * fixed issue with adding nodes/links and editing links during runtime
    * updated open file dialog in config dialogs to open to ~/.coregui home directory
    * fixed issue double clicking sessions dialog in invalid areas
    * added display of asymmetric link options on links
    * fixed emane config dialog display
    * fixed issue saving backgrounds in xml files
    * added view toggle for wired/wireless links
    * node events will now update icons

## 2020-07-28 CORE 7.0.1

* Bugfixes
    * \#500 - fixed issue running node commands with shell=True
    * fixed issue for poetry based install not properly vetting requirements for dataclasses dependency

## 2020-07-23 CORE 7.0.0

* Breaking Changes
    * core.emudata and core.data combined and cleaned up into core.data
    * updates to consistently use mac instead of hwaddr/mac
    * \#468 - code related to adding/editing/deleting links cleaned up
    * \#469 - usages of per all changed to loss to be consistent
    * \#470 - variables with numbered names now use numbers directly
    * \#471 - node startup is no longer embedded within its constructor
    * \#472 - code updated to refer to interfaces consistently as iface
    * \#475 - code updates changing how ip addresses are stored on interfaces
    * \#476 - executables to check for moved into own module core.executables
    * \#486 - core will now install into its own python virtual environment managed by poetry
* core-daemon
    * updates to properly save/load distributed servers to xml
    * \#474 - added type hinting to all service files
    * \#478 - fixed typo in config service directory
    * \#479 - opening an xml file will now cycle through states like a normal session
    * \#480 - ovs configuration will now save/load from xml and display in guis
    * \#484 - changes to support adding emane links during runtime
* core-pygui
    * fixed issue not displaying services for the default group in service dialogs
    * fixed issue starting a session when the daemon is not present
    * fixed issue attempting to open terminals for invalid nodes
    * fixed issue syncing session location
    * fixed issue joining a session with mobility, not in runtime
    * added cpu usage monitor to status bar
    * emane configurations can now be seen during runtime
    * rj45 nodes can only have one link
    * disabling throughputs will clear labels
    * improvements to custom service copy
    * link options will now be drawn on as a label
    * updates to handle runtime link events
    * \#477 - added optional details pane for a quick view of node/link details
    * \#485 - pygui fixed observer widget for invalid nodes
    * \#496 - improved alert handling
* core-gui
    * \#493 - increased frame size to show all emane configuration options
* gRPC API
    * added set session user rpc
    * added cpu usage stream
    * interface objects returned from get_node will now provide node_id, net_id, and net2_id data
    * peer to peer nodes will not be included in get_session calls
    * pathloss events will now throw an error when nem id not found
    * \#481 - link rpc calls will broadcast out
    * \#496 - added alert rpc call
* Services
    * fixed issue reading files in security services
    * \#494 - add staticd to daemons list for frr services

## 2020-06-11 CORE 6.5.0
* Breaking Changes
    * CoreNode.newnetif - both parameters are required and now takes an InterfaceData object as its second parameter
    * CoreNetworkBase.linkconfig - now takes a LinkOptions parameter instead of a subset of some of the options (ie bandwidth, delay, etc)
    * \#453 - Session.add_node and Session.get_node now requires the node class you expect to create/retrieve
    * \#458 - rj45 cleanup to only inherit from one class
* Enhancements
    * fixed issues with handling bad commands for TLV execute messages
    * removed unused boot.sh from CoreNode types
    * added linkconfig to CoreNetworkBase and cleaned up function signature
    * emane position hook now saves geo position to node
    * emane pathloss support
    * core.emulator.emudata leveraged dataclass and type hinting
    * \#459 - updated transport type usage to an enum
    * \#460 - updated network policy type usage to an enum
* Python GUI Enhancements
    * fixed throughput events do not work for joined sessions
    * fixed exiting app with a toolbar picker showing
    * fixed issue with creating interfaces and reusing subnets after deletion
    * fixed issue with moving text shapes
    * fixed scaling with custom node selected
    * fixed toolbar state switching issues
    * enable/disable toolbar when running stop/start
    * marker config integrated into toolbar
    * improved color picker layout
    * shapes can now be moved while drawing shapes
    * added observers to toolbar in run mode
* gRPC API
    * node events will now have geo positional data
    * node geo data is now returned in get_session and get_node calls
    * \#451 - added wlan link api to allow direct linking/unlinking of wireless links between nodes
    * \#462 - added streaming call for sending node position/geo changes
    * \#463 - added streaming call for emane pathloss events
* Bugfixes
    * \#454 - fixed issue creating docker nodes, but containers are now required to have networking tools
    * \#466 - fixed issue in python gui when xml file is loading nodes with no ip4 addresses

## 2020-05-11 CORE 6.4.0
* Enhancements
    * updates to core-route-monitor, allow specific session, configurable settings, and properly
      listen on all interfaces
    * install.sh now has a "-r" option to help with reinstalling from current branch and installing
      current python dependencies
    * \#202 - enable OSPFv2 fast convergence
    * \#178 - added comments to OVS service
* Python GUI Enhancements
    * added initial documentation to help support usage
    * supports drawing multiple links for wireless connections
    * supports differentiating wireless networks with different colored links
    * implemented unlink in node context menu to delete links to other nodes
    * implemented node run tool dialog
    * implemented find node dialog
    * implemented address configuration dialog
    * implemented mac configuration dialog
    * updated link address creation to more closely mimic prior behavior
    * updated configuration to use yaml class based configs
    * implemented auto grid layout for nodes
    * fixed drawn wlan ranges during configuration
* Bugfixes
    * no longer writes link option data for WLAN/EMANE links in XML
    * avoid configuring links for WLAN/EMANE link options in XML, due to them being written to XML prior
    * updates to allow building python docs again
    * \#431 - peer to peer node uplink link data was not using an enum properly due to code changes
    * \#432 - loading XML was not setting EMANE nodes model
    * \#435 - loading XML was not maintaining existing session options
    * \#448 - fixed issue sorting hooks being saved to XML

## 2020-04-13 CORE 6.3.0
* Features
    * \#424 - added FRR IS-IS service
* Enhancements
    * \#414 - update GUI OSPFv2 adjacency widget to work with FRR
    * \#416 - EMANE links can now be drawn for 80211 and RF Pipe models
    * \#418 #409 - code cleanup
    * \#425 - added route monitor script for SDT3D integration
    * a formal error will now be thrown when EMANE binding are not installed, but attempted to be used
    * node positions will now default to 0,0 to avoid GUI errors, when one is not provided
    * improved SDT3D integration, multiple link support and usage of custom layers
* Python GUI Enhancements
    * enabled edit menu delete
    * cleaned up node context menu and enabled delete
* Bugfixes
    * \#427 - fixed issue in default route service
    * \#426 - fixed issue reading ipsec template file
    * \#420 - fixed issue with TLV API udp handler
    * \#411 - allow wlan to be configured with 0 values
    * \#415 - general EMANE configuration was not being saved/loaded from XML

## 2020-03-16 CORE 6.2.0
* gRPC API
    * Added call to execute python script
* Enhancements
    * \#371 - improved coretk gui scaling
    * \#374 - display range visually for wlan in coretk gui, when configuring
    * \#377 - improved coretk error dialogs
    * \#379 - fixed issues with core converting between x,y and lon,lat for values that would cross utm zones
    * \#384 - sdt integration moved internally to core code allowing it to work for coretk gui as well
    * \#387 - coretk gui will now auto detect potential valid terminal and command to use for interacting with nodes during runtime
    * \#389 - coretk gui will now attempt to reconnect to daemon without need to restart
    * \#395 - coretk gui now has "save" and "save as" menu options
    * \#402 - coretk will now allow terminal preference to be directly edited
* Bugfixes
    * \#375 - fixed issues with emane event monitor handling data
    * \#381 - executing a python script will now wait until completion before looking to join a new session
    * \#391 - fixed configuring node ip addresses in coretk gui
    * \#392 - fixed coretk link display when addresses are cleared out
    * \#393 - coretk gui will properly clear marker annotations when switching sessions
    * \#396 - Docker and LXC nodes will now properly save to XML
    * \#406- WLAN bridge initialization was not ran when all nodes are disconnected

## 2020-02-20 CORE 6.1.0
* New
    * config services - these services leverage a proper template engine and have configurable parameters, given enough time may replace existing services
    * core-imn-to-xml - IMN to XML utility script
    * replaced internal code for determining ip/mac address with netaddr library
* Enhancements
    * added distributed package for built packages
    * made use of python type hinting for functions and their return values
    * updated Quagga zebra service to remove deprecated warning
* Removed
    * removed stale ns3 code
* CORETK GUI
    * added logging
    * improved error dialog
    * properly use global ipv6 addresses for nodes
    * disable proxy usage by default, flag available to enable
* gRPC API
    * add_link - now returns created interface information
    * set_node_service - can now set files and directories to properly replicate previous usage
    * get_emane_event_channel - return information related to the currently used emane event channel
* Bugfixes
    * fixed session SDT functionality back to working order, due to python3 changes
    * avoid shutting down services for nodes that are not up
    * EMANE bypass model options will now display properly in GUIs
    * XML scenarios will now properly read in custom node icons
    * \#372 - fixed mobility waypoint comparisons
    * \#370 - fixed radvd service
    * \#368 - updated frr services to properly start staticd when needed
    * \#358 - fixed systemd service install path
    * \#350 - fixed frr babel wireless configuration
    * \#354 - updated frr to reset interfaces to properly take configurations

## 2020-01-01 CORE 6.0.0
* New
    * beta release of the python based tk GUI, use **coretk-gui** to try it out, plan will be to eventually sunset the old GUI once this is good enough
        * this GUI will allow us to provide enhancements and a consistent python dev environment for developers
* Major Changes
    * python3.6+ support only, due  to python2 EOL https://pyfound.blogspot.com/2019/12/python-2-sunset.html
    * distributed sessions now leverages the fabric library for sending remote SSH commands
* Enhancements
    * changed usage of bridge-utils to using ip based bridge commands due to deprecation
    * installation.sh script to help automate a standard make install or dev install
    * when sessions are created without an id they will now always start from 1 and return the next unused id
    * gRPC is now running by default
* Session API
    * removed **create_emane_network** and **create_wlan_network** to help force using **add_node** for all cases
    * removed **session.master** as it was only used for previous distributed sessions
    * updated **add_node** to allow providing a custom class for node creation
* gRPC API
    * added get all services configurations
    * added get all wlan configurations
    * added start/stop session calls, provides more freedom for startup and shutdown logic
    * session events now have a session id to help differentiate which session they are coming from
    * throughput events now require a session id and responses include session id for differentiating data
    * session events can now be subscribed to with a subset of events or all
    * emane model config data now include interface ids properly
    * sessions returned from get sessions call may include file names when created from xml
    * when opening an xml the session can now be started or not
    * edit node will now broadcast the edit for others to listen to
    * all config responses will now be in the form of a mapped value of key to ConfigOption, or a list of these when retrieving all, sometimes the config response may be wrapped in a different message to include other metadata
* Bugfixes
    * \#311 - initialize ebtables chains for wlan networks only
    * \#312 - removed sudo from init script
    * \#313 - check if interface exists before flushing, previously would log an exception that didn't matter
    * \#314 - node locations stored as floats instead of ints to avoid mobility calculations due to loss of precision
    * \#321 - python installation path will be based on distr ibution/python building it
    * emane options xml parsing didn't properly take into account the **emane_prefix** configuration
    * updates services that checked for ipv4/ipv6 addresses to not fail for valid ipv6 addresses with a decimal
* Documentation
    * updated NRL links to new GitHub locations
    * updates for distributed session
    * updates to dev guide
    * updates to examples LXD/Docker setup
    * updates to FRR service documentation
    * gRPC get node service file will not throw an exception when node doesn't exist

## 2019-10-12 CORE 5.5.2
* gRPC
    * Added emane_link API for linking/unlinking EMANE nodes within the GUI
* Bugfixes
    * Fixed python3 issues when configuring WLAN nodes
    * Fixed issue due to refactoring when running distributed
    * Fixed issue when running python script from GUI

## 2019-10-09 CORE 5.5.1
* Bugfix
    * Fixed issue with 5.5.0 refactoring causing issues in python2.
    * Fixed python3 issues with NRL services

## 2019-10-03 CORE 5.5.0
* Documentation
    * updated dependencies for building OSPF MDR on installation page
    * added python/pip instruction on installation page
    * added ethtool dependency for CORE
* GUI
    * removed experimental OVS node to avoid confusion and issues related to using it
* Daemon
    * fixed core-daemon --ovs flag back to working order for running CORE using OVS bridges instead of Linux bridges
    * updated requirements.txt to refer to configparser 4.0.2, due to 4.0.1 removal by developers
    * update to fail fast for dependent executables that are not found within PATH
    * update to not load services that fail during service.on_load and move on
* Build
    * fixed issue with configure script when using option flags
    * python install path will use the native install path for AM_PATH_PYTHON, instead of coercing to python3
* Issues
    * \#271 - OVS node error in GUI
    * \#291 - configparser 4.0.1 issue
    * \#290 - python3 path issue when building

## 2019-09-23 CORE 5.4.0
* Documentation
    * Updates to documentation dev guide
* Improvements
    * Added support for Pipenv for development
    * Added configuration to leverage pre-commit during development
    * Added configuration to leverage isort, black, and flake8 during development
    * Added Github Actions to help verify pull requests in the same way as pre-commit
* Issues
    * \#279 - WLAN configuration does not get set by default
    * \#272 - error installing python package futures==3.2.0
* Pull Requests
    * \#275 - Disable MAC learning on WLAN
    * \#281 - Bumped jackson version on corefx

## 2019-07-05 CORE 5.3.1
* Documentation
    * Updates to provide more information regarding several of the included services
* Issues
    * \#252 - fixed changing wlan configurations during runtime
    * \#256 - fixed mobility waypoint comparison for python3
    * \#174 - turn tx/rx checksums off by default as they will never be valid for virtual interfaces
    * \#259 - fixes for distributed EMANE
    * \#260 - fixed issue with how execfile was being used due to it not existing within python3

## 2019-06-10 CORE 5.3.0
* Enhancements
    * python 2 / 3 support
    * added new API using [gRPC](https://grpc.io/)
    * --grpc --grpc-port --grpc-address flags added to core-daemon
    * core.api.grpc.client.CoreGrpcClient, provides a convenience wrapper for leveraging the API
* Docs
    * Updates to installation instructions for latest changes
* Services
    * Added FRR service
* EMANE
    * Added EMANE prefix configuration when looking for emane model manifest files
    * requires configuring **emane_prefix** in /etc/core/core.conf
* Cleanup
    * Refactoring of the core python package structure, trying to help provide better organization and
  logical groupings
* Issues
    * \#246 - Fixed network to network link handling when reading xml files
    * \#236 - Fixed storing/reading of link configuration values within xml files
    * \#170 - FRR Service
    * \#155 - EMANE path configuration
    * \#233 - Python 3 support
    * \#245 - Fixed bidirectional link configurations when reading from xml files
    * \#208 - gRPC API
    * Fixed link configuration dup handling when loaded from xml files

## 2019-06-07 CORE 5.2.2
* Enhancements:
    * adds back in core-daemon udp support for coresendmsg, people may have depended on previously for certain scenarios
* Bug Fixes:
    * fixes issue in GUI that would prevent moving nodes during mobility scenarios

## 2019-03-25 CORE 5.2.1
* Packaging:
    * documentation no longer builds by default, must use configure flag
    * added configure flag to allow only building vcmd
    * sphinx will no long be required when not building documentation
* Services:
    * Added source NAT service
    * Fixed DHCP service for Ubuntu 18.04
* BUGFIXES:
    * \#188 - properly remove session on delete TLV API call
    * \#192 - updated default gnome terminal command for nodes to be Ubuntu 18.04 compatible
    * \#193 - updates to service validation, will retry on failure and better exception logging
    * \#195 - TLV link message data fix
    * \#196 - fix to avoid clearing out default services
    * \#197 - removed wireless_link_all API from EmuSession
    * \#216 - updated default WLAN bandwidth to 54Mbps
    * \#223 - fix to saving RJ45 to session XML files

## 2018-05-22 CORE 5.1
* DAEMON:
    * removed and cleared out code that is either legacy or no longer supported (Xen, BSD, Kernel patching, RPM/DEB
 specific files)
    * default nodes are now set in the node map
    * moved ns3 and netns directories to the top of the repo
    * changes to make use of fpm as the tool for building packages
    * removed usage of logzero to avoid dependency issues for built packages
    * removed daemon addons directory
    * added CoreEmu to core.emulator.coreemu to help begin serving as the basis for a more formal API for scripting
 and creating new external APIs out of
    * cleaned up logging, moved more logging to DEBUG from INFO, tried to mold INFO message to be more simple and
 informative
    * EMANE 1.0.1-1.21 supported
    * updates to leverage EMANE python bindings for dynamically parsing phy/mac manifest files
    * example custom EMANE model lives under /usr/share/core/examples/myemane/examplemodel.py
    * EMANE TDMA model now supports an option to start a TDMA schedule when running
    * fixed issues with coresendmsg script due to code refactoring
    * added make target for generating documentation "make doc"
    * Python 2.7+ is now required
    * ns3 is no longer bundled by default, but will be produced as a separate package for installation
* GUI:
    * updated broken help links in GUI Help->About
* Packaging:
    * fixed PYTHON_PATH to PYTHONPATH in sysv script
    * added make command to leverage FPM as the tool for creating deb/rpm packages going forward, there is documentation
 within README.md to try it out
* TEST:
    * fixed some broken tests
    * new test cases based on CoreEmu usage
* BUGFIXES:
    * \#142 - duplication of custom services
    * \#136 - sphinx-apidoc command not found
    * \#137 - make command fails when using distclean

## 2017-09-01 CORE 5.0
* DEVELOPMENT:
    * support for editorconfig to help standardize development across IDEs, from the defined configuration file
    * support for sonarqube analysis, from the defined configuration file
* DAEMON:
    * code cleanup and improvements to adhere to coding standards (SonarQube)
    * leverage "logzero" module to make easy usage of the standard logging module
    * improvements to documentation across the code base
    * initial work to separate the dependence on TCP API messaging from the core library (easier core scripting)
    * beta support for running core in Open vSwitch mode, leveraging Open vSwitch bridges, instead of Linux bridges
* SERVICES:
    * added Ryu SDN controller service
    * added Open vSwitch service
* TEST:
    * added unit/integration tests to support validating changes going forward
* BUGFIXES:
    * merged pull requests for: #115, #110, #109, #107, #106, #105, #103, #102, #101, #96

## 2015-06-05 CORE 4.8
* EMANE:
    * support for EMANE 0.9.2
    * run emane in each container when using EMANE 0.9.2
    * support using separate control networks for EMANE OTA and event traffic
* GUI:
    * fixed an issue where the adjacency widget lines pointed to old node positions
    * fixed an issue where not all EMANE 0.9.x IEEE 802.11 MAC parameter were configurable
    * fixed an issue related to running python scripts from the GUI when using tcl/tk version 8.6
    * improved batch mode execution to display the check emulation light status
    * improved managing multiple sessions
    * improved support for using multiple canvases
    * added a reload option to the file menu to revert back to a saved scenario
* DAEMON:
    * support exporting scenarios in NRL Network Modeling Framework 1.0 XML format
    * support importing scenarios in NRL Network Modeling Framework 1.0 XML format
    * support exporting the deployed scenario state in NRL NMF XML 1.0 format
    * improved EMANE post-startup processing to better synchronize distributed emulations
    * improved how addresses are assigned to tun/tap devices
    * added support for python state-change callbacks
* SERVICES:
    * added mgen sink and mgen actor services
    * added oslrv2 and olsr.org services
    * added a docker service
* BUILD:
    * improved the install/uninstall process
    * improved debian and rpm packaging
* BUGFIXES:
    * updated the http service for ubuntu 14.04
    * improved included examples
    * shortened the length of network interface names
    * improved how the core system service manages running the core daemon
    * fixed an issues related to applying session configuration setting
    * improved detecting when a distributed emulation is already running
    * improved documentation

## 2014-08-06 CORE 4.7
* EMANE:
    * support for EMANE 0.9.1
    * fix error when using Comm Effect model with loss/duplicate string values
    * enable flow control in virtual transport if enabled in the MAC model
    * fix bug #150 where EMANE event service/address port were not used
* GUI:
    * support Tcl/Tk 8.6 when available
    * added --(a)ddress and --(p)ort arguments to core-gui command-line
    * added File > Execute XML or Python script... option
    * added File > Execute Python script with options... menu item
    * when executing Python script from GUI, run in background thread, wait for
    RUNTIME state
    * enter RUNTIME state when start button pressed with empty canvas
    * added support for asymmetric link effects
    * support link delays up to 274 seconds (netem maximum)
    * allow runtime changes of WLAN link effects
* DAEMON:
    * set NODE_NAME, NODE_NUMBER, SESSION_SHORT in default vnoded environment
    * changed host device naming to use veth, tap prefixes; b.n.SS for bridges
    * allow parsing XML files into live running session
    * enable link effects between hub/switch and hub/switch connections
    * update MDR service to use broadcast interfaces for non-WLAN links
    * allow node class to be specified when initializing XML parser
    * save and parse canvas origin (reference point) and scale in MP XML
    * up/down control script session option
    * fix hash calculation used to determine GRE tunnel keys
    * use shell script to detach SMF on startup
    * added NRL services for mgen sink and nrlolsrv2
    * use SDT URL session option
    * added core-manage tool for addons to add/remove/check services, models,
    and custom node types
* API:
    * implement local flag in Execute Message for running host commands
    * jitter changed to 64-bit value to align with delay in Link Message
    * added unidirectional link flag TLV to Link Message
    * added reconfigure event type for re-generating service config files
    * return errors in API with failed services
* BUGFIXES:
    * fix HTTP service running under Ubuntu
    * fixed the following bugs: #150, 169, 188, 220, 225, 230, 231, 242, 244,
    247, 248, 250, 251

## 2013-09-25 CORE 4.6
* NOTE: cored is now core-daemon, and core is now core-gui (for Debian acceptance)
* NOTE: /etc/init.d/core is now /etc/init.d/core-daemon (for insserv compatibility)
* EMANE:
    * don't start EMANE locally if no local NEMs
    * EMANE poststartup() to re-transmit location events during initialization
    * added debug port to EMANE options
    * added a basic EMANE 802.11 CORE Python script example
    * expose transport XML block generation to EmaneModels
    * expose NEM entry to the EmaneModel so it can be overridden by a model
    * add the control interface bridge prior to starting EMANE, as some models may
    * depend on the controlnet functionality
    * added EMANE model to CORE converter
    * parse lat/long/alt from node messages, for moving nodes using command-line
    * fix bug #196 incorrect distance when traversing UTM zones
* GUI:
    * added Cut, Copy, and Paste options to the Edit menu
    * paste will copy selected services and take care of node and interface
    *  renumbering
    * implement Edit > Find dialog for searching nodes and links
    * when copying existing file for a service, perform string replacement of:
    *  "~", "%SESSION%", "%SESSION_DIR%", "%SESSION_USER%", "%NODE%", "%NODENAME%"
    * use CORE_DATA_DIR insteadof LIBDIR
    * fix Adjacency Widget to work with OSPFv2 only networks
* BUILD:
    * build/packaging improvements for inclusion on Debian
    * fix error when running scenario with a mobility script in batch mode
    * include Linux kernel patches for 3.8
    * renamed core-cleanup.sh to core-cleanup for Debian conformance
    * don't always generate man pages from Makefile; new manpages for
  coresendmsg and core-daemon
* BUGFIXES:
    * don't auto-assign IPv4/IPv6 addresses when none received in Link Messages (session reconnect)
    * fixed lock view
    * fix GUI spinbox errors for Tk 8.5.8 (RHEL/CentOS 6.2)
    * fix broker node count for distributed session entering the RUNTIME state when
    *  (non-EMANE) WLANs or GreTapBridges are involved;
    * fix "file exists" error message when distributed session number is re-used
    *  and servers file is written
    * fix bug #194 configuration dialog too long, make dialog scrollable/resizable
    * allow float values for loss and duplicates percent
    * fix the following bugs: 166, 172, 177, 178, 192, 194, 196, 201, 202,
  205, 206, 210, 212, 213, 214, 221

## 2013-04-13 CORE 4.5
* GUI:
    * improved behavior when starting GUI without daemon, or using File New after connection with daemon is lost
    * fix various GUI issues when reconnecting to a session
    * support 3D GUI via output to SDT3D
    * added "Execute Python script..." entry to the File Menu
    * support user-defined terminal program instead of hard-coded xterm
    * added session options for "enable RJ45s", "preserve session dir"
    * added buttons to the IP Addresses dialog for removing all/selected IPv4/IPv6
    * allow sessions with multiple canvases to enter RUNTIME state
    * added "--addons" startup mode to pass control to code included from addons dir
    * added "Locked" entry to View menu to prevent moving items
    * use currently selected node type when invoking a topology generator
    * updated throughput plots with resizing, color picker, plot labels, locked scales, and save/load plot
  configuration with imn file
    * improved session dialog
* EMANE:
    * EMANE 0.8.1 support with backwards-compatibility for 0.7.4
    * extend CommEffect model to generate CommEffect events upon receipt of Link Messages having link effects
* Services:
    * updated FTP service with root directory for anonymous users
    * added HTTP, PCAP, BIRD, RADVD, and Babel services
    * support copying existing files instead of always generating them
    * added "Services..." entry to node right-click menu
    * added "View" button for side-by-side comparison when copying customized config files
    * updated Quagga daemons to wait for zebra.vty VTY file before starting
* General:
    * XML import and export
    * renamed "cored.py" to "cored", "coresendmsg.py" to "coresendmsg"
    * code reorganization and clean-up
    * updated XML export to write NetworkPlan, MotionPlan, and ServicePlan within a Scenario tag, added new
  "Save As XML..." File menu entry
    * added script_start/pause/stop options to Ns2ScriptedMobility
    * "python" source sub-directory renamed to "daemon"
    * added "cored -e" option to execute a Python script, adding its session to the active sessions list, allowing for
  GUI connection
    * support comma-separated list for custom_services_dir in core.conf file
    * updated kernel patches for Linux kernel 3.5
    * support RFC 6164-style IPv6 /127 addressing
* ns-3:
    * integrate ns-3 node location between CORE and ns-3 simulation
    * added ns-3 random walk mobility example
    * updated ns-3 Wifi example to allow GUI connection and moving of nodes
* fixed the following bugs: 54, 103, 111, 136, 145, 153, 157, 160, 161, 162, 164, 165, 168, 170, 171, 173, 174, 176,
184, 190, 193

## 2012-09-25 CORE 4.4
* GUI:
    * real-time bandwidth plotting tool
    * added Wireshark and tshark right-click menu items
    * X,Y coordinates shown in the status bar
    * updated GUI attribute option to link messages for changing color/width/dash
    * added sample IPsec and VPN scenarios, how many nodes script
    * added jitter parameter to WLANs
    * renamed Experiment menu to Session menu, added session options
    * use 'key=value' configuration for services, EMANE models, WLAN models, etc.
    * save only service values that have been customized
    * copy service parameters from one customized service to another
    * right-click menu to start/stop/restart each service
* EMANE:
    * EMANE 0.7.4 support
    * added support for EMANE CommEffect model and Comm Effect controller GUI
    * added support for EMANE Raw Transport when using RJ45 devices
* Services:
    * improved service customization; allow a service to define custom Tcl tab
    * added vtysh.conf for Quagga service to support 'write mem'
    * support scheduled events and services that start N seconds after runtime
    * added UCARP service
* Documentation:
    * converted the CORE manual to reStructuredText using Sphinx; added Python docs
* General:
    * Python code reorganization
    * improved cored.py thread locking
    * merged xen branch into trunk
    * added an event queue to a session with notion of time zero
    * added UDP support to cored.py
    * use UDP by default in coresendmsg.py; added '-H' option to print examples
    * enter a bash shell by default when running vcmd with no arguments
    * fixes to distributed emulation entering runtime state
    * write 'nodes' file upon session startup
    * make session number and other attributes available in environment
    * support /etc/core/environment and ~/.core/environment files
    * added Ns2ScriptedMobility model to Python, removed from the GUI
    * namespace nodes mount a private /sys
    * fixed the following bugs: 80, 81, 84, 99, 104, 109, 110, 122, 124, 131, 133, 134, 135, 137, 140, 143, 144, 146,
  147, 151, 154, 155

## 2012-03-07 CORE 4.3
* EMANE 0.7.2 and 0.7.3 support
* hook scripts: customize actions at any of six different session states
* Check Emulation Light (CEL) exception feedback system
* added FTP and XORP services, and service validate commands
* services can flag when customization is required
* Python classes to support ns-3 simulation experiments
* write state, node X,Y position, and servers to pycore session dir
* removed over 9,000 lines of unused GUI code
* performance monitoring script
* batch mode improvements and --closebatch option
* export session to EmulationScript XML files
* basic range model moved from GUI to Python, supports 3D coordinates
* improved WLAN dialog with tabs
* added PhysicalNode class for joining real nodes with emulated networks
* fixed the following bugs: 50, 75, 76, 79, 82, 83, 85, 86, 89, 90, 92, 94, 96, 98, 100, 112, 113, 116, 119, 120

## 2011-08-19 CORE 4.2
* EMANE 0.7.1 support
    * support for Bypass model, Universal PHY, logging, realtime
* configurable MAC addresses
* control interfaces (backchannel between node and host)
* service customization dialog improved (tabbed)
* new testing scripts for MDR and EMANE performance testing
* improved upgrading of old imn files
* new coresendmsg.py utility (deprecates libcoreapi and coreapisend)
* new security services, custom service becomes UserDefined
* new services and Python scripting chapters in manual
* fixes to distributed emulation, linking tunnels/RJ45s with WLANs/hubs/switches
* fixed the following bugs: 18, 32, 34, 38, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 52, 53, 55, 57, 58, 60, 62, 64,
65, 66, 68, 71, 72, 74

## 2011-01-05 CORE 4.1
* new icons for toolbars and nodes
* node services introduced, node models deprecated
* customizable node types
* traffic flow editor with MGEN support
* user configs moved from /etc/core/`*` to ~/.core/
* allocate addresses from custom IPv4/IPv6 prefixes
* distributed emulation using GRE tunnels
* FreeBSD 8.1 now uses cored.py
* EMANE 0.6.4 support
* numerous bugfixes

## 2010-08-17 CORE 4.0
* Python framework with Linux network namespace (netns) support (Linux netns is now the primary supported platform)
* ability to close the GUI and later reconnect to a running session (netns only)
* EMANE integration (netns only)
* new topology generators, host file generator
* user-editable Observer Widgets
* use of /etc/core instead of /usr/local/etc/core
* various bugfixes

## 2009-09-15 CORE 3.5

## 2009-06-23 CORE 3.4

## 2009-03-11 CORE 3.3
