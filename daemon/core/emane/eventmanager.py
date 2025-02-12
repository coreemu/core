import logging
import threading
from typing import Callable, Union

from core.errors import CoreError

logger = logging.getLogger(__name__)

try:
    from emane.events import (
        AntennaProfileEvent,
        CommEffectEvent,
        EventService,
        FadingSelectionEvent,
        LocationEvent,
        PathlossEvent,
    )
    from emane.events.eventserviceexception import EventServiceException
except ImportError:
    try:
        from emanesh.events import (
            AntennaProfileEvent,
            CommEffectEvent,
            EventService,
            FadingSelectionEvent,
            LocationEvent,
            PathlossEvent,
        )
        from emanesh.events.eventserviceexception import EventServiceException
    except ImportError:
        EventService = None
        AntennaProfileEvent = None
        CommEffectEvent = None
        FadingSelectionEvent = None
        LocationEvent = None
        PathlossEvent = None
        EventServiceException = None
        logger.debug("compatible emane python bindings not installed")


class EmaneEventService:
    def __init__(
        self,
        device: str,
        group: str,
        port: int,
        location_handler: Callable[[LocationEvent], None],
    ) -> None:
        self.device: str = device
        self.group: str = group
        self.port: int = port
        self.location_handler: Callable[[LocationEvent], None] = location_handler
        self.running: bool = False
        self.thread: threading.Thread | None = None
        logger.info("starting emane event service %s %s:%s", device, group, port)
        self.events: EventService = EventService(
            eventchannel=(group, port, device), otachannel=None
        )

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self) -> None:
        """
        Run and monitor events.
        """
        logger.info("subscribing to emane location events")
        while self.running:
            _uuid, _seq, events = self.events.nextEvent()
            # this occurs with 0.9.1 event service
            if not self.running:
                break
            for _nem_id, event_id, data in events:
                if event_id == LocationEvent.IDENTIFIER:
                    events = LocationEvent()
                    events.restore(data)
                    self.location_handler(events)
        logger.info("unsubscribing from emane location events")

    def stop(self) -> None:
        """
        Stop service and monitoring events.
        """
        self.events.breakloop()
        self.running = False
        if self.thread:
            self.thread.join()
            self.thread = None


class EmaneEventManager:
    def __init__(self, location_handler: Callable[[LocationEvent], None]):
        self.location_handler: Callable[[LocationEvent], None] = location_handler
        self.services: dict[str, EmaneEventService] = {}
        self.nem_service: dict[int, EmaneEventService] = {}

    def reset(self) -> None:
        self.services.clear()
        self.nem_service.clear()

    def shutdown(self) -> None:
        while self.services:
            _, service = self.services.popitem()
            service.stop()
        self.nem_service.clear()

    def create_service(
        self, nem_id: int, device: str, group: str, port: int, should_start: bool
    ) -> None:
        # initialize emane event services
        service = self.services.get(device)
        if not service:
            try:
                service = EmaneEventService(device, group, port, self.location_handler)
                if should_start:
                    service.start()
                self.services[device] = service
                self.nem_service[nem_id] = service
            except EventServiceException:
                raise CoreError(
                    "failed to start emane event services {name} {group}:{port}"
                )
        else:
            self.nem_service[nem_id] = service

    def get_service(self, nem_id: int) -> EmaneEventService | None:
        service = self.nem_service.get(nem_id)
        if not service:
            logger.error("failure to find event service for nem(%s)", nem_id)
        return service

    def publish_location(
        self,
        nem_id: int,
        lon: float,
        lat: float,
        alt: float,
        azimuth: float = None,
        elevation: float = None,
        magnitude: float = None,
        roll: float = None,
        pitch: float = None,
        yaw: float = None,
    ) -> None:
        args = dict(
            azimuth=azimuth,
            elevation=elevation,
            magnitude=magnitude,
            roll=roll,
            pitch=pitch,
            yaw=yaw,
        )
        args = {k: v for k, v in args.items() if v is not None}
        event = LocationEvent()
        event.append(nem_id, latitude=lat, longitude=lon, altitude=alt, **args)
        self._publish_event(nem_id, event, 0)

    def publish_locations(
        self, positions: list[tuple[int, float, float, float]]
    ) -> None:
        services = {}
        for nem_id, lon, lat, alt in positions:
            service = self.get_service(nem_id)
            if not service:
                continue
            event = services.setdefault(service, LocationEvent())
            event.append(nem_id, latitude=lat, longitude=lon, altitude=alt)
        for service, event in services.items():
            service.events.publish(0, event)

    def publish_comm_effect(
        self,
        nem1_id: int,
        nem2_id: int,
        delay: int,
        jitter: int,
        loss: float,
        dup: int,
        unicast: int,
        broadcast: int,
    ) -> None:
        # TODO: batch these into multiple events per transmission
        # TODO: may want to split out seconds portion of delay and jitter
        event = CommEffectEvent()
        event.append(
            nem1_id,
            latency=delay,
            jitter=jitter,
            loss=loss,
            duplicate=dup,
            unicast=unicast,
            broadcast=broadcast,
        )
        self._publish_event(nem2_id, event)

    def publish_pathloss(
        self,
        nem1_id: int,
        nem2_id: int,
        forward1: float = None,
        reverse1: float = None,
        forward2: float = None,
        reverse2: float = None,
    ) -> None:
        args1 = dict(forward=forward1, reverse=reverse1)
        args1 = {k: v for k, v in args1.items() if v is not None}
        args2 = dict(forward=forward2, reverse=reverse2)
        args2 = {k: v for k, v in args2.items() if v is not None}
        event = PathlossEvent()
        event.append(nem1_id, **args1)
        event.append(nem2_id, **args2)
        self._publish_event(nem1_id, event)
        self._publish_event(nem2_id, event)

    def publish_antenna_profile(
        self, nem_id: int, profile: int, azimuth: float, elevation: float
    ) -> None:
        event = AntennaProfileEvent()
        event.append(nem_id, profile=profile, azimuth=azimuth, elevation=elevation)
        self._publish_event(nem_id, event, 0)

    def publish_fading_selection(self, nem_id: int, model: str) -> None:
        event = FadingSelectionEvent()
        event.append(nem_id, model=model)
        self._publish_event(nem_id, event)

    def _publish_event(
        self,
        nem_id: int,
        event: Union[
            AntennaProfileEvent,
            CommEffectEvent,
            FadingSelectionEvent,
            LocationEvent,
            PathlossEvent,
        ],
        publish_id: int = None,
    ) -> None:
        service = self.get_service(nem_id)
        if not service:
            return
        if publish_id is None:
            publish_id = nem_id
        service.events.publish(publish_id, event)
