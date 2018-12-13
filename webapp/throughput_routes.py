import re
import threading
import time

from flask import jsonify
from flask.blueprints import Blueprint

import websocket_routes

coreemu = None
_interface_regex = re.compile("\d+")
_throughput_thread = None
_thread_flag = True

api = Blueprint("throughput_api", __name__)


def get_net_stats():
    with open("/proc/net/dev", "r") as net_stats:
        data = net_stats.readlines()[2:]

    stats = {}
    for line in data:
        line = line.strip()
        if not line:
            continue
        line = line.split()
        line[0] = line[0].strip(":")
        stats[line[0]] = {"rx": float(line[1]), "tx": float(line[9])}

    return stats


def throughput_collector(delay=3):
    global _thread_flag
    _thread_flag = True
    last_check = None
    last_stats = None
    while _thread_flag:
        now = time.time()
        stats = get_net_stats()

        # calculate average
        if last_check is not None:
            interval = now - last_check
            bridges = []
            interfaces = []
            for key, current_rxtx in stats.iteritems():
                previous_rxtx = last_stats.get(key)
                if not previous_rxtx:
                    print "skipping %s, no previous value" % key
                    continue
                rx_kbps = (current_rxtx["rx"] - previous_rxtx["rx"]) * 8.0 / interval
                tx_kbps = (current_rxtx["tx"] - previous_rxtx["tx"]) * 8.0 / interval
                throughput = rx_kbps + tx_kbps
                print "%s - %s" % (key, throughput)
                if key.startswith("veth"):
                    key = key.split(".")
                    node_id = int(_interface_regex.search(key[0]).group())
                    interface_id = int(key[1])
                    interfaces.append({"node": node_id, "interface": interface_id, "throughput": throughput})
                elif key.startswith("b."):
                    node_id = key.split(".")[1]
                    bridges.append({"node": node_id, "throughput": throughput})

            throughputs = {"bridges": bridges, "interfaces": interfaces}
            websocket_routes.socketio.emit("throughput", throughputs)
            # for interface in sorted(interfaces, key=lambda x: x["node"]):
            #     print "%s:%s - %s" % (interface["node"], interface["interface"], interface["throughput"])
            # for bridge in sorted(bridges, key=lambda x: x["node"]):
            #     print "%s - %s" % (bridge["node"], bridge["throughput"])

        last_check = now
        last_stats = stats
        time.sleep(delay)


@api.route("/throughput/start", methods=["PUT"])
def start_throughput():
    global _throughput_thread
    if not _throughput_thread:
        _throughput_thread = threading.Thread(target=throughput_collector)
        _throughput_thread.daemon = True
        _throughput_thread.start()
    return jsonify()


@api.route("/throughput/stop", methods=["PUT"])
def stop_throughput():
    global _throughput_thread
    global _thread_flag
    if _throughput_thread:
        _thread_flag = False
        _throughput_thread.join()
        _throughput_thread = None
    return jsonify()
