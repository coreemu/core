# EMANE Antenna Profiles

## Overview

Introduction to using the EMANE antenna profile in CORE, based on the example
EMANE Demo linked below.

[EMANE Demo 6](https://github.com/adjacentlink/emane-tutorial/wiki/Demonstration-6)
for more specifics.

## Demo Setup

We will need to create some files in advance of starting this session.

Create directory to place antenna profile files.

```shell
mkdir /tmp/emane
```

Create `/tmp/emane/antennaprofile.xml` with the following contents.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE profiles SYSTEM "file:///usr/share/emane/dtd/antennaprofile.dtd">
<profiles>
    <profile id="1"
             antennapatternuri="/tmp/emane/antenna30dsector.xml"
             blockagepatternuri="/tmp/emane/blockageaft.xml">
        <placement north="0" east="0" up="0"/>
    </profile>
    <profile id="2"
             antennapatternuri="/tmp/emane/antenna30dsector.xml">
        <placement north="0" east="0" up="0"/>
    </profile>
</profiles>
```

Create `/tmp/emane/antenna30dsector.xml` with the following contents.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE antennaprofile SYSTEM "file:///usr/share/emane/dtd/antennaprofile.dtd">

<!-- 30degree sector antenna pattern with main beam at +6dB and gain decreasing by 3dB every 5 degrees in elevation or bearing.-->
<antennaprofile>
    <antennapattern>
        <elevation min='-90' max='-16'>
            <bearing min='0' max='359'>
                <gain value='-200'/>
            </bearing>
        </elevation>
        <elevation min='-15' max='-11'>
            <bearing min='0' max='5'>
                <gain value='0'/>
            </bearing>
            <bearing min='6' max='10'>
                <gain value='-3'/>
            </bearing>
            <bearing min='11' max='15'>
                <gain value='-6'/>
            </bearing>
            <bearing min='16' max='344'>
                <gain value='-200'/>
            </bearing>
            <bearing min='345' max='349'>
                <gain value='-6'/>
            </bearing>
            <bearing min='350' max='354'>
                <gain value='-3'/>
            </bearing>
            <bearing min='355' max='359'>
                <gain value='0'/>
            </bearing>
        </elevation>
        <elevation min='-10' max='-6'>
            <bearing min='0' max='5'>
                <gain value='3'/>
            </bearing>
            <bearing min='6' max='10'>
                <gain value='0'/>
            </bearing>
            <bearing min='11' max='15'>
                <gain value='-3'/>
            </bearing>
            <bearing min='16' max='344'>
                <gain value='-200'/>
            </bearing>
            <bearing min='345' max='349'>
                <gain value='-3'/>
            </bearing>
            <bearing min='350' max='354'>
                <gain value='0'/>
            </bearing>
            <bearing min='355' max='359'>
                <gain value='3'/>
            </bearing>
        </elevation>
        <elevation min='-5' max='-1'>
            <bearing min='0' max='5'>
                <gain value='6'/>
            </bearing>
            <bearing min='6' max='10'>
                <gain value='3'/>
            </bearing>
            <bearing min='11' max='15'>
                <gain value='0'/>
            </bearing>
            <bearing min='16' max='344'>
                <gain value='-200'/>
            </bearing>
            <bearing min='345' max='349'>
                <gain value='0'/>
            </bearing>
            <bearing min='350' max='354'>
                <gain value='3'/>
            </bearing>
            <bearing min='355' max='359'>
                <gain value='6'/>
            </bearing>
        </elevation>
        <elevation min='0' max='5'>
            <bearing min='0' max='5'>
                <gain value='6'/>
            </bearing>
            <bearing min='6' max='10'>
                <gain value='3'/>
            </bearing>
            <bearing min='11' max='15'>
                <gain value='0'/>
            </bearing>
            <bearing min='16' max='344'>
                <gain value='-200'/>
            </bearing>
            <bearing min='345' max='349'>
                <gain value='0'/>
            </bearing>
            <bearing min='350' max='354'>
                <gain value='3'/>
            </bearing>
            <bearing min='355' max='359'>
                <gain value='6'/>
            </bearing>
        </elevation>
        <elevation min='6' max='10'>
            <bearing min='0' max='5'>
                <gain value='3'/>
            </bearing>
            <bearing min='6' max='10'>
                <gain value='0'/>
            </bearing>
            <bearing min='11' max='15'>
                <gain value='-3'/>
            </bearing>
            <bearing min='16' max='344'>
                <gain value='-200'/>
            </bearing>
            <bearing min='345' max='349'>
                <gain value='-3'/>
            </bearing>
            <bearing min='350' max='354'>
                <gain value='0'/>
            </bearing>
            <bearing min='355' max='359'>
                <gain value='3'/>
            </bearing>
        </elevation>
        <elevation min='11' max='15'>
            <bearing min='0' max='5'>
                <gain value='0'/>
            </bearing>
            <bearing min='6' max='10'>
                <gain value='-3'/>
            </bearing>
            <bearing min='11' max='15'>
                <gain value='-6'/>
            </bearing>
            <bearing min='16' max='344'>
                <gain value='-200'/>
            </bearing>
            <bearing min='345' max='349'>
                <gain value='-6'/>
            </bearing>
            <bearing min='350' max='354'>
                <gain value='-3'/>
            </bearing>
            <bearing min='355' max='359'>
                <gain value='0'/>
            </bearing>
        </elevation>
        <elevation min='16' max='90'>
            <bearing min='0' max='359'>
                <gain value='-200'/>
            </bearing>
        </elevation>
    </antennapattern>
</antennaprofile>
```

Create `/tmp/emane/blockageaft.xml` with the following contents.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE antennaprofile SYSTEM "file:///usr/share/emane/dtd/antennaprofile.dtd">

<!-- blockage pattern: 1) entire aft in bearing (90 to 270) blocked 2) elevation below -10 blocked, 3) elevation from -10 to -1 is at -10dB to -1 dB 3) elevation from 0 to 90 no blockage-->
<antennaprofile>
    <blockagepattern>
        <elevation min='-90' max='-11'>
            <bearing min='0' max='359'>
                <gain value='-200'/>
            </bearing>
        </elevation>
        <elevation min='-10' max='-10'>
            <bearing min='0' max='89'>
                <gain value='-10'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-10'/>
            </bearing>
        </elevation>
        <elevation min='-9' max='-9'>
            <bearing min='0' max='89'>
                <gain value='-9'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-9'/>
            </bearing>
        </elevation>
        <elevation min='-8' max='-8'>
            <bearing min='0' max='89'>
                <gain value='-8'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-8'/>
            </bearing>
        </elevation>
        <elevation min='-7' max='-7'>
            <bearing min='0' max='89'>
                <gain value='-7'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-7'/>
            </bearing>
        </elevation>
        <elevation min='-6' max='-6'>
            <bearing min='0' max='89'>
                <gain value='-6'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-6'/>
            </bearing>
        </elevation>
        <elevation min='-5' max='-5'>
            <bearing min='0' max='89'>
                <gain value='-5'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-5'/>
            </bearing>
        </elevation>
        <elevation min='-4' max='-4'>
            <bearing min='0' max='89'>
                <gain value='-4'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-4'/>
            </bearing>
        </elevation>
        <elevation min='-3' max='-3'>
            <bearing min='0' max='89'>
                <gain value='-3'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-3'/>
            </bearing>
        </elevation>
        <elevation min='-2' max='-2'>
            <bearing min='0' max='89'>
                <gain value='-2'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-2'/>
            </bearing>
        </elevation>
        <elevation min='-1' max='-1'>
            <bearing min='0' max='89'>
                <gain value='-1'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='-1'/>
            </bearing>
        </elevation>
        <elevation min='0' max='90'>
            <bearing min='0' max='89'>
                <gain value='0'/>
            </bearing>
            <bearing min='90' max='270'>
                <gain value='-200'/>
            </bearing>
            <bearing min='271' max='359'>
                <gain value='0'/>
            </bearing>
        </elevation>
    </blockagepattern>
</antennaprofile>
```

## Run Demo

1. Select `Open...` within the GUI
1. Load `emane-demo-antenna.xml`
1. Click ![Start Button](../static/gui/start.png)
1. After startup completes, double click n1 to bring up the nodes terminal

## Example Demo

This demo will cover running an EMANE event service to feed in antenna,
location, and pathloss events to demonstrate how antenna profiles
can be used.

### EMANE Event Dump

On n1 lets dump EMANE events, so when we later run the EMANE event service
you can monitor when and what is sent.

```shell
root@n1:/tmp/pycore.44917/n1.conf# emaneevent-dump -i ctrl0
```

### Send EMANE Events

On the host machine create the following to send EMANE events.

!!! warning

    Make sure to set the `eventservicedevice` to the proper control
    network value

Create `eventservice.xml` with the following contents.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eventservice SYSTEM "file:///usr/share/emane/dtd/eventservice.dtd">
<eventservice>
    <param name="eventservicegroup" value="224.1.2.8:45703"/>
    <param name="eventservicedevice" value="b.9001.da"/>
    <generator definition="eelgenerator.xml"/>
</eventservice>
```

Create `eelgenerator.xml` with the following contents.

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

Create `scenario.eel` with the following contents.

```shell
0.0 nem:1 antennaprofile 1,0.0,0.0
0.0 nem:4 antennaprofile 2,0.0,0.0
#
0.0 nem:1  pathloss nem:2,60  nem:3,60   nem:4,60
0.0 nem:2  pathloss nem:3,60  nem:4,60
0.0 nem:3  pathloss nem:4,60
#
0.0 nem:1  location gps 40.025495,-74.315441,3.0
0.0 nem:2  location gps 40.025495,-74.312501,3.0
0.0 nem:3  location gps 40.023235,-74.315441,3.0
0.0 nem:4  location gps 40.023235,-74.312501,3.0
0.0 nem:4  velocity 180.0,0.0,10.0
#
30.0 nem:1 velocity 20.0,0.0,10.0
30.0 nem:1 orientation 0.0,0.0,10.0
30.0 nem:1 antennaprofile 1,60.0,0.0
30.0 nem:4 velocity 270.0,0.0,10.0
#
60.0 nem:1 antennaprofile 1,105.0,0.0
60.0 nem:4 antennaprofile 2,45.0,0.0
#
90.0 nem:1 velocity 90.0,0.0,10.0
90.0 nem:1 orientation 0.0,0.0,0.0
90.0 nem:1 antennaprofile 1,45.0,0.0
```

Run the EMANE event service, monitor what is output on n1 for events
dumped and see the link changes within the CORE GUI.

```shell
emaneeventservice -l 3 eventservice.xml
```

### Stages

The events sent will trigger 4 different states.

* State 1
    * n2 and n3 see each other
    * n4 and n3 are pointing away
* State 2
    * n2 and n3 see each other
    * n1 and n2 see each other
    * n4 and n3 see each other
* State 3
    * n2 and n3 see each other
    * n4 and n3 are pointing at each other but blocked
* State 4
    * n2 and n3 see each other
    * n4 and n3 see each other
