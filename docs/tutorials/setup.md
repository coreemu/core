# Tutorial Setup

## Setup for CORE

We assume the prior installation of CORE, using a virtual environment. You can
then adjust your PATH and add an alias to help more conveniently run CORE
commands.

This can be setup in your **.bashrc**

```shell
export PATH=$PATH:/opt/core/venv/bin
alias sudop='sudo env PATH=$PATH'
```

## Setup for Chat App

There is a simple TCP chat app provided as example software to use and run within
the tutorials provided.

### Installation

The following will install chatapp and its scripts into **/usr/local**, which you
may need to add to PATH within node to be able to use command directly.

``` shell
sudo python3 -m pip install .
```

!!! note

    Some Linux distros will not have **/usr/local** in their PATH and you
    will need to compensate.

``` shell
export PATH=$PATH:/usr/local
```

### Running the Server

The server will print and log connected clients and their messages.

``` shell
usage: chatapp-server [-h] [-a ADDRESS] [-p PORT]

chat app server

optional arguments:
  -h, --help            show this help message and exit
  -a ADDRESS, --address ADDRESS
                        address to listen on (default: )
  -p PORT, --port PORT  port to listen on (default: 9001)
```

### Running the Client

The client will print and log messages from other clients and their join/leave status.

``` shell
usage: chatapp-client [-h] -a ADDRESS [-p PORT]

chat app client

optional arguments:
  -h, --help            show this help message and exit
  -a ADDRESS, --address ADDRESS
                        address to listen on (default: None)
  -p PORT, --port PORT  port to listen on (default: 9001)
```

### Installing the Chat App Service

1. You will first need to edit **/etc/core/core.conf** to update the config
   service path to pick up your service
    ``` shell
    custom_config_services_dir = <path for service>
    ```
2. Then you will need to copy/move **chatapp/chatapp_service.py** to the directory
   configured above
3. Then you will need to restart the **core-daemon** to pick up this new service
4. Now the service will be an available option under the group **ChatApp** with
   the name **ChatApp Server**
