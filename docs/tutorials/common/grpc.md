## gRPC Python Scripts

You can also run the same steps above, using the provided gRPC script versions of scenarios.
Below are the steps to run and join one of these scenario, then you can continue with
the remaining steps of a given section.

1. Make sure the CORE daemon is running a terminal, if not already
    ``` shell
    sudop core-daemon
    ```
2. From another terminal run the tutorial python script, which will create a session to join
    ``` shell
    /opt/core/venv/bin/python scenario.py
    ```
3. In another terminal run the CORE GUI
    ``` shell
    core-gui
    ```
4. You will be presented with sessions to join, select the one created by the script
   <p align="center">
     <img src="/core/static/tutorial-common/running-join.png" width="75%">
   </p>
