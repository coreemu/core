# EMANE Procomputed

## Overview

Introduction to using the precomputed propagation model.

[EMANE Demo 1](https://github.com/adjacentlink/emane-tutorial/wiki/Demonstration-1)
for more specifics.

## Run Demo

1. Select `Open...` within the GUI
2. Load `emane-demo-precomputed.xml`
3. Click ![Start Button](../static/gui/start.png)
4. After startup completes, double click n1 to bring up the nodes terminal

## Example Demo

This demo is using the RF Pipe model with the propagation model set to
precomputed.

### Failed Pings

Due to using precomputed and having not sent any pathloss events, the nodes
cannot ping each other yet.

Open a terminal on n1.

```shell
root@n1:/tmp/pycore.46777/n1.conf# ping 10.0.0.2
connect: Network is unreachable
```

### EMANE Shell

You can leverage `emanesh` to investigate why packets are being dropped.

```shell
root@n1:/tmp/pycore.46777/n1.conf# emanesh localhost get table nems phy BroadcastPacketDropTable0 UnicastPacketDropTable0
nem 1   phy BroadcastPacketDropTable0
| NEM | Out-of-Band | Rx Sensitivity | Propagation Model | Gain Location | Gain Horizon | Gain Profile | Not FOI | Spectrum Clamp | Fade Location | Fade Algorithm | Fade Select |
| 2   | 0           | 0              | 169               | 0             | 0            | 0            | 0       | 0              | 0             | 0              | 0           |

nem 1   phy UnicastPacketDropTable0
| NEM | Out-of-Band | Rx Sensitivity | Propagation Model | Gain Location | Gain Horizon | Gain Profile | Not FOI | Spectrum Clamp | Fade Location | Fade Algorithm | Fade Select |
```

In the example above we can see that the reason packets are being dropped is due to
the propogation model and that is because we have not issued any pathloss events.
You can run another command to validate if you have received any pathloss events.

```shell
root@n1:/tmp/pycore.46777/n1.conf# emanesh localhost get table nems phy  PathlossEventInfoTable
nem 1   phy PathlossEventInfoTable
| NEM | Forward Pathloss | Reverse Pathloss |
```

### Pathloss Events

On the host we will send pathloss events from all nems to all other nems.

!!! note

    Make sure properly specify the right control network device

```shell
emaneevent-pathloss 1:2 90 -i <controlnet device>
```

Now if we check for pathloss events on n2 we will see what was just sent above.

```shell
root@n1:/tmp/pycore.46777/n1.conf# emanesh localhost get table nems phy  PathlossEventInfoTable
nem 1   phy PathlossEventInfoTable
| NEM | Forward Pathloss | Reverse Pathloss |
| 2   | 90.0             | 90.0
```

You should also now be able to ping n1 from n2.

```shell
root@n1:/tmp/pycore.46777/n1.conf# ping -c 3 10.0.0.2
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=3.06 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=2.12 ms
64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=1.99 ms

--- 10.0.0.2 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2001ms
rtt min/avg/max/mdev = 1.991/2.393/3.062/0.479 ms
```
