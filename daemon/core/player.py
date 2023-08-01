import ast
import csv
import enum
import logging
import sched
from pathlib import Path
from threading import Thread
from typing import IO, Callable, Optional

import grpc

from core.api.grpc.client import CoreGrpcClient, MoveNodesStreamer
from core.api.grpc.wrappers import LinkOptions

logger = logging.getLogger(__name__)


@enum.unique
class PlayerEvents(enum.Enum):
    """
    Provides event types for processing file events.
    """

    XY = enum.auto()
    GEO = enum.auto()
    CMD = enum.auto()
    WLINK = enum.auto()
    WILINK = enum.auto()
    WICONFIG = enum.auto()

    @classmethod
    def get(cls, value: str) -> Optional["PlayerEvents"]:
        """
        Retrieves a valid event type from read input.

        :param value: value to get event type for
        :return: valid event type, None otherwise
        """
        event = None
        try:
            event = cls[value]
        except KeyError:
            pass
        return event


class CorePlayerWriter:
    """
    Provides conveniences for programatically creating a core file for playback.
    """

    def __init__(self, file_path: str):
        """
        Create a CorePlayerWriter instance.

        :param file_path: path to create core file
        """
        self._time: float = 0.0
        self._file_path: str = file_path
        self._file: Optional[IO] = None
        self._csv_file: Optional[csv.writer] = None

    def open(self) -> None:
        """
        Opens the provided file path for writing and csv creation.

        :return: nothing
        """
        logger.info("core player write file(%s)", self._file_path)
        self._file = open(self._file_path, "w", newline="")
        self._csv_file = csv.writer(self._file, quoting=csv.QUOTE_MINIMAL)

    def close(self) -> None:
        """
        Closes the file being written to.

        :return: nothing
        """
        if self._file:
            self._file.close()

    def update(self, delay: float) -> None:
        """
        Update and move the current play time forward by delay amount.

        :param delay: amount to move time forward by
        :return: nothing
        """
        self._time += delay

    def write_xy(self, node_id: int, x: float, y: float) -> None:
        """
        Write a node xy movement event.

        :param node_id: id of node to move
        :param x: x position
        :param y: y position
        :return: nothing
        """
        self._csv_file.writerow([self._time, PlayerEvents.XY.name, node_id, x, y])

    def write_geo(self, node_id: int, lon: float, lat: float, alt: float) -> None:
        """
        Write a node geo movement event.

        :param node_id: id of node to move
        :param lon: longitude position
        :param lat: latitude position
        :param alt: altitude position
        :return: nothing
        """
        self._csv_file.writerow(
            [self._time, PlayerEvents.GEO.name, node_id, lon, lat, alt]
        )

    def write_cmd(self, node_id: int, wait: bool, shell: bool, cmd: str) -> None:
        """
        Write a node command event.

        :param node_id: id of node to run command on
        :param wait: should command wait for successful execution
        :param shell: should command run under shell context
        :param cmd: command to run
        :return: nothing
        """
        self._csv_file.writerow(
            [self._time, PlayerEvents.CMD.name, node_id, wait, shell, f"'{cmd}'"]
        )

    def write_wlan_link(
        self, wireless_id: int, node1_id: int, node2_id: int, linked: bool
    ) -> None:
        """
        Write a wlan link event.

        :param wireless_id: id of wlan network for link
        :param node1_id: first node connected to wlan
        :param node2_id: second node connected to wlan
        :param linked: True if nodes are linked, False otherwise
        :return: nothing
        """
        self._csv_file.writerow(
            [
                self._time,
                PlayerEvents.WLINK.name,
                wireless_id,
                node1_id,
                node2_id,
                linked,
            ]
        )

    def write_wireless_link(
        self, wireless_id: int, node1_id: int, node2_id: int, linked: bool
    ) -> None:
        """
        Write a wireless link event.

        :param wireless_id: id of wireless network for link
        :param node1_id: first node connected to wireless
        :param node2_id: second node connected to wireless
        :param linked: True if nodes are linked, False otherwise
        :return: nothing
        """
        self._csv_file.writerow(
            [
                self._time,
                PlayerEvents.WILINK.name,
                wireless_id,
                node1_id,
                node2_id,
                linked,
            ]
        )

    def write_wireless_config(
        self,
        wireless_id: int,
        node1_id: int,
        node2_id: int,
        loss1: float,
        delay1: int,
        loss2: float = None,
        delay2: float = None,
    ) -> None:
        """
        Write a wireless link config event.

        :param wireless_id: id of wireless network for link
        :param node1_id: first node connected to wireless
        :param node2_id: second node connected to wireless
        :param loss1: loss for the first interface
        :param delay1: delay for the first interface
        :param loss2: loss for the second interface, defaults to first interface loss
        :param delay2: delay for second interface, defaults to first interface delay
        :return: nothing
        """
        loss2 = loss2 if loss2 is not None else loss1
        delay2 = delay2 if delay2 is not None else delay1
        self._csv_file.writerow(
            [
                self._time,
                PlayerEvents.WICONFIG.name,
                wireless_id,
                node1_id,
                node2_id,
                loss1,
                delay1,
                loss2,
                delay2,
            ]
        )


class CorePlayer:
    """
    Provides core player functionality for reading a file with timed events
    and playing them out.
    """

    def __init__(self, file_path: Path):
        """
        Creates a CorePlayer instance.

        :param file_path: file to play path
        """
        self.file_path: Path = file_path
        self.core: CoreGrpcClient = CoreGrpcClient()
        self.session_id: Optional[int] = None
        self.node_streamer: Optional[MoveNodesStreamer] = None
        self.node_streamer_thread: Optional[Thread] = None
        self.scheduler: sched.scheduler = sched.scheduler()
        self.handlers: dict[PlayerEvents, Callable] = {
            PlayerEvents.XY: self.handle_xy,
            PlayerEvents.GEO: self.handle_geo,
            PlayerEvents.CMD: self.handle_cmd,
            PlayerEvents.WLINK: self.handle_wlink,
            PlayerEvents.WILINK: self.handle_wireless_link,
            PlayerEvents.WICONFIG: self.handle_wireless_config,
        }

    def init(self, session_id: Optional[int]) -> bool:
        """
        Initialize core connections, settings to or retrieving session to use.
        Also setup node streamer for xy/geo movements.

        :param session_id: session id to use, None for default session
        :return: True if init was successful, False otherwise
        """
        self.core.connect()
        try:
            if session_id is None:
                sessions = self.core.get_sessions()
                if len(sessions):
                    session_id = sessions[0].id
            if session_id is None:
                logger.error("no core sessions found")
                return False
            self.session_id = session_id
            logger.info("playing to session(%s)", self.session_id)
            self.node_streamer = MoveNodesStreamer(self.session_id)
            self.node_streamer_thread = Thread(
                target=self.core.move_nodes, args=(self.node_streamer,), daemon=True
            )
            self.node_streamer_thread.start()
        except grpc.RpcError as e:
            logger.error("core is not running: %s", e.details())
            return False
        return True

    def start(self) -> None:
        """
        Starts playing file, reading the csv data line by line, then handling
        each line event type. Delay is tracked and calculated, while processing,
        to ensure we wait for the event time to be active.

        :return: nothing
        """
        current_time = 0.0
        with self.file_path.open("r", newline="") as f:
            for row in csv.reader(f):
                # determine delay
                input_time = float(row[0])
                delay = input_time - current_time
                current_time = input_time
                # determine event
                event_value = row[1]
                event = PlayerEvents.get(event_value)
                if not event:
                    logger.error("unknown event type: %s", ",".join(row))
                    continue
                # get args and event functions
                args = tuple(ast.literal_eval(x) for x in row[2:])
                event_func = self.handlers.get(event)
                if not event_func:
                    logger.error("unknown event type handler: %s", ",".join(row))
                    continue
                logger.info(
                    "processing line time(%s) event(%s) args(%s)",
                    input_time,
                    event.name,
                    args,
                )
                # schedule and run event
                self.scheduler.enter(delay, 1, event_func, argument=args)
                self.scheduler.run()
        self.stop()

    def stop(self) -> None:
        """
        Stop and cleanup playback.

        :return: nothing
        """
        logger.info("stopping playback, cleaning up")
        self.node_streamer.stop()
        self.node_streamer_thread.join()
        self.node_streamer_thread = None

    def handle_xy(self, node_id: int, x: float, y: float) -> None:
        """
        Handle node xy movement event.

        :param node_id: id of node to move
        :param x: x position
        :param y: y position
        :return: nothing
        """
        logger.debug("handling xy node(%s) x(%s) y(%s)", node_id, x, y)
        self.node_streamer.send_position(node_id, x, y)

    def handle_geo(self, node_id: int, lon: float, lat: float, alt: float) -> None:
        """
        Handle node geo movement event.

        :param node_id: id of node to move
        :param lon: longitude position
        :param lat: latitude position
        :param alt: altitude position
        :return: nothing
        """
        logger.debug(
            "handling geo node(%s) lon(%s) lat(%s) alt(%s)", node_id, lon, lat, alt
        )
        self.node_streamer.send_geo(node_id, lon, lat, alt)

    def handle_cmd(self, node_id: int, wait: bool, shell: bool, cmd: str) -> None:
        """
        Handle node command event.

        :param node_id: id of node to run command
        :param wait: True to wait for successful command, False otherwise
        :param shell: True to run command in shell context, False otherwise
        :param cmd: command to run
        :return: nothing
        """
        logger.debug(
            "handling cmd node(%s) wait(%s) shell(%s) cmd(%s)",
            node_id,
            wait,
            shell,
            cmd,
        )
        status, output = self.core.node_command(
            self.session_id, node_id, cmd, wait, shell
        )
        logger.info("cmd result(%s): %s", status, output)

    def handle_wlink(
        self, net_id: int, node1_id: int, node2_id: int, linked: bool
    ) -> None:
        """
        Handle wlan link event.

        :param net_id: id of wlan network
        :param node1_id: first node in link
        :param node2_id: second node in link
        :param linked: True if linked, Flase otherwise
        :return: nothing
        """
        logger.debug(
            "handling wlink node1(%s) node2(%s) net(%s) linked(%s)",
            node1_id,
            node2_id,
            net_id,
            linked,
        )
        self.core.wlan_link(self.session_id, net_id, node1_id, node2_id, linked)

    def handle_wireless_link(
        self, wireless_id: int, node1_id: int, node2_id: int, linked: bool
    ) -> None:
        """
        Handle wireless link event.

        :param wireless_id: id of wireless network
        :param node1_id: first node in link
        :param node2_id: second node in link
        :param linked: True if linked, Flase otherwise
        :return: nothing
        """
        logger.debug(
            "handling link wireless(%s) node1(%s) node2(%s) linked(%s)",
            wireless_id,
            node1_id,
            node2_id,
            linked,
        )
        self.core.wireless_linked(
            self.session_id, wireless_id, node1_id, node2_id, linked
        )

    def handle_wireless_config(
        self,
        wireless_id: int,
        node1_id: int,
        node2_id: int,
        loss1: float,
        delay1: int,
        loss2: float,
        delay2: int,
    ) -> None:
        """
        Handle wireless config event.

        :param wireless_id: id of wireless network
        :param node1_id: first node in link
        :param node2_id: second node in link
        :param loss1: first interface loss
        :param delay1: first interface delay
        :param loss2: second interface loss
        :param delay2: second interface delay
        :return: nothing
        """
        logger.debug(
            "handling config wireless(%s) node1(%s) node2(%s) "
            "options1(%s/%s) options2(%s/%s)",
            wireless_id,
            node1_id,
            node2_id,
            loss1,
            delay1,
            loss2,
            delay2,
        )
        options1 = LinkOptions(loss=loss1, delay=delay1)
        options2 = LinkOptions(loss=loss2, delay=delay2)
        self.core.wireless_config(
            self.session_id, wireless_id, node1_id, node2_id, options1, options2
        )
