# EMANE Emulation Event Log (EEL) Generator
* Table of Contents
{:toc}

## Overview
Introduction to using the EMANE event service and eel files to provide events.

[EMANE Demo 1](https://github.com/adjacentlink/emane-tutorial/wiki/Demonstration-1)
for more specifics.

## Run Demo
1. Select `Open...` within the GUI
1. Load `emane-demo-eel.xml`
1. Click ![Start Button](../static/gui/start.gif)
1. After startup completes, double click n1 to bring up the nodes terminal

## Example Demo
This demo will go over defining an EMANE event service and eel file to drive
an emane event service.

### Viewing Events
On n1 we will use the EMANE event dump utility to listen to events.
```shell
root@n1:/tmp/pycore.46777/n1.conf# emaneevent-dump -i ctrl0
```

### Sending Events
On the host machine we will create the following files and start the
EMANE event service targeting the control network.

> **WARNING:** make sure to set the `eventservicedevice` to the proper control
> network value

Create `eventservice.xml` with the following contents.
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eventservice SYSTEM "file:///usr/share/emane/dtd/eventservice.dtd">
<eventservice>
  <param name="eventservicegroup" value="224.1.2.8:45703"/>
  <param name="eventservicedevice" value="b.9001.f"/>
  <generator definition="eelgenerator.xml"/>
</eventservice>
```

Next we will create the `eelgenerator.xml` file. The EEL Generator is actually
a plugin that loads sentence parsing plugins. The sentence parsing plugins know
how to convert certain sentences, in this case commeffect, location, velocity,
orientation, pathloss and antennaprofile sentences, into their corresponding
emane event equivalents.

* commeffect:eelloadercommeffect:delta
* location,velocity,orientation:eelloaderlocation:delta
* pathloss:eelloaderpathloss:delta
* antennaprofile:eelloaderantennaprofile:delta

These configuration items tell the EEL Generator which sentences to map to
which plugin and whether to issue delta or full updates.

Create `eelgenerator.xml` with the following contents.
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eventgenerator SYSTEM "file:///usr/share/emane/dtd/eventgenerator.dtd">
<eventgenerator library="eelgenerator">
    <param name="inputfile" value="scenario.eel" />
    <paramlist name="loader">
      <item value="commeffect:eelloadercommeffect:delta"/>
      <item value="location,velocity,orientation:eelloaderlocation:delta"/>
      <item value="pathloss:eelloaderpathloss:delta"/>
      <item value="antennaprofile:eelloaderantennaprofile:delta"/>
    </paramlist>
</eventgenerator>
```

Finally, create `scenario.eel` with the following contents.
```shell
0.0  nem:1 pathloss nem:2,90.0
0.0  nem:2 pathloss nem:1,90.0
0.0  nem:1 location gps 40.031075,-74.523518,3.000000
0.0  nem:2 location gps 40.031165,-74.523412,3.000000
```

Start the EMANE event service using the files created above.
```shell
emaneeventservice eventservice.xml -l 3
```

### Sent Events
If we go back to look at our original terminal we will see the events logged
out to the terminal.

```shell
root@n1:/tmp/pycore.46777/n1.conf# emaneevent-dump -i ctrl0
[1601858142.917224] nem: 0 event: 100 len: 66 seq: 1 [Location]
 UUID: 0af267be-17d3-4103-9f76-6f697e13bcec
   (1, {'latitude': 40.031075, 'altitude': 3.0, 'longitude': -74.823518})
   (2, {'latitude': 40.031165, 'altitude': 3.0, 'longitude': -74.523412})
[1601858142.917466] nem: 1 event: 101 len: 14 seq: 2 [Pathloss]
 UUID: 0af267be-17d3-4103-9f76-6f697e13bcec
   (2, {'forward': 90.0, 'reverse': 90.0})
[1601858142.917889] nem: 2 event: 101 len: 14 seq: 3 [Pathloss]
 UUID: 0af267be-17d3-4103-9f76-6f697e13bcec
   (1, {'forward': 90.0, 'reverse': 90.0})
```
