# EMANE GPSD Integration

## Overview

Introduction to integrating gpsd in CORE with EMANE.

[EMANE Demo 0](https://github.com/adjacentlink/emane-tutorial/wiki/Demonstration-0)
may provide more helpful details.

!!! warning

    Requires installation of [gpsd](https://gpsd.gitlab.io/gpsd/index.html)

## Run Demo

1. Select `Open...` within the GUI
2. Load `emane-demo-gpsd.xml`
3. Click ![Start Button](../static/gui/start.png)
4. After startup completes, double click n1 to bring up the nodes terminal

## Example Demo

This section will cover how to run a gpsd location agent within EMANE, that will
write out locations to a pseudo terminal file. That file can be read in by the
gpsd server and make EMANE location events available to gpsd clients.

### EMANE GPSD Event Daemon

First create an `eventdaemon.xml` file on n1 with the following contents.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eventdaemon SYSTEM "file:///usr/share/emane/dtd/eventdaemon.dtd">
<eventdaemon nemid="1">
    <param name="eventservicegroup" value="224.1.2.8:45703"/>
    <param name="eventservicedevice" value="ctrl0"/>
    <agent definition="gpsdlocationagent.xml"/>
</eventdaemon>
```

Then create the `gpsdlocationagent.xml` file on n1 with the following contents.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eventagent SYSTEM "file:///usr/share/emane/dtd/eventagent.dtd">
<eventagent library="gpsdlocationagent">
    <param name="pseudoterminalfile" value="gps.pty"/>
</eventagent>
```

Start the EMANE event agent. This will facilitate feeding location events
out to a pseudo terminal file defined above.

```shell
emaneeventd eventdaemon.xml -r -d -l 3 -f emaneeventd.log
```

Start gpsd, reading in the pseudo terminal file.

```shell
gpsd -G -n -b $(cat gps.pty)
```

### EMANE EEL Event Daemon

EEL Events will be played out from the actual host machine over the designated
control network interface. Create the following files in the same directory
somewhere on your host.

!!! note

    Make sure the below eventservicedevice matches the control network
    device being used on the host for EMANE

Create `eventservice.xml` on the host machine with the following contents.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eventservice SYSTEM "file:///usr/share/emane/dtd/eventservice.dtd">
<eventservice>
    <param name="eventservicegroup" value="224.1.2.8:45703"/>
    <param name="eventservicedevice" value="b.9001.1"/>
    <generator definition="eelgenerator.xml"/>
</eventservice>
```

Create `eelgenerator.xml` on the host machine with the following contents.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eventgenerator SYSTEM "file:///usr/share/emane/dtd/eventgenerator.dtd">
<eventgenerator library="eelgenerator">
    <param name="inputfile" value="scenario.eel"/>
    <paramlist name="loader">
        <item value="commeffect:eelloadercommeffect:delta"/>
        <item value="location,velocity,orientation:eelloaderlocation:delta"/>
        <item value="pathloss:eelloaderpathloss:delta"/>
        <item value="antennaprofile:eelloaderantennaprofile:delta"/>
    </paramlist>
</eventgenerator>
```

Create `scenario.eel` file with the following contents.

```shell
0.0  nem:1 location gps 40.031075,-74.523518,3.000000
0.0  nem:2 location gps 40.031165,-74.523412,3.000000
```

Start the EEL event service, which will send the events defined in the file above
over the control network to all EMANE nodes. These location events will be received
and provided to gpsd. This allows gpsd client to connect to and get gps locations.

```shell
emaneeventservice eventservice.xml -l 3
```

