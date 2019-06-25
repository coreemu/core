# CORE Services

* Table of Contents
{:toc}

## Custom Services

CORE supports custom developed services by way of dynamically loading user created python files.
Custom services should be placed within the path defined by **custom_services_dir** in the CORE
configuration file. This path cannot end in **/services**.

Follow these steps to add your own services:

1. Modify the [Example Service File](/daemon/examples/myservices/sample.py)
   to do what you want. It could generate config/script files, mount per-node
   directories, start processes/scripts, etc. sample.py is a Python file that
   defines one or more classes to be imported. You can create multiple Python
   files that will be imported. Add any new filenames to the __init__.py file.

2. Put these files in a directory such as /home/username/.core/myservices
   Note that the last component of this directory name **myservices** should not
   be named something like **services** which conflicts with an existing Python
   name (the syntax 'from myservices import *' is used).

3. Add a **custom_services_dir = /home/username/.core/myservices** entry to the
   /etc/core/core.conf file.

4. Restart the CORE daemon (core-daemon). Any import errors (Python syntax)
   should be displayed in the /var/log/core-daemon.log log file (or on screen).

5. Start using your custom service on your nodes. You can create a new node
   type that uses your service, or change the default services for an existing
   node type, or change individual nodes.
