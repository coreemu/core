# CORE Documentation

## Introduction

CORE (Common Open Research Emulator) is a tool for building virtual networks. As an emulator, CORE builds a representation of a real computer network that runs in real time, as opposed to simulation, where abstract models are used. The live-running emulation can be connected to physical networks and routers.  It provides an environment for running real applications and protocols, taking advantage of virtualization provided by the Linux operating system.

CORE is typically used for network and protocol research, demonstrations, application and platform testing, evaluating networking scenarios, security studies, and increasing the size of physical test networks.

#### Key Features
* Efficient and scalable
* Runs applications and protocols without modification
* Drag and drop GUI
* Highly customizable

## Topics

* [Architecture](architecture.md)
* [Installation](install.md)
* [Usage](usage.md)
* [Python Scripting](scripting.md)
* [Node Types](machine.md)
* [CTRLNET](ctrlnet.md)
* [EMANE](emane.md)
* [NS3](ns3.md)
* [Performance](performance.md)
* [Developers Guide](devguide.md)

## Credits

The CORE project was derived from the open source IMUNES project from the University of Zagreb in 2004. In 2006, changes for CORE were released back to that project, some items of which were adopted. Marko Zec <zec@fer.hr> is the primary developer from the University of Zagreb responsible for the IMUNES (GUI) and VirtNet (kernel) projects. Ana Kukec and Miljenko Mikuc are known contributors.

Jeff Ahrenholz has been the primary Boeing developer of CORE, and has written this manual. Tom Goff designed the Python framework and has made significant contributions. Claudiu Danilov, Rod Santiago, Kevin Larson, Gary Pei, Phil Spagnolo, and Ian Chakeres have contributed code to CORE. Dan Mackley helped develop the CORE API, originally to interface with a simulator. Jae Kim and Tom Henderson have supervised the project and provided direction.

Copyright (c) 2005-2018, the Boeing Company.
