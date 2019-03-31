import logging
import os

from core.grpc import client
from core.grpc import core_pb2


def log_event(event):
    logging.info("event: %s", event)


def main():
    xml_file_name = "/tmp/core.xml"
    core = client.CoreGrpcClient()

    with core.context_connect():
        if os.path.exists(xml_file_name):
            response = core.open_xml(xml_file_name)
            print("open xml: {}".format(response))

        print("services: {}".format(core.get_services()))

        # create session
        session = core.create_session()
        core.exception_events(session.id, log_event)
        core.node_events(session.id, log_event)
        core.session_events(session.id, log_event)
        core.link_events(session.id, log_event)
        core.file_events(session.id, log_event)
        core.config_events(session.id, log_event)
        print("created session: {}".format(session))
        print("default services: {}".format(core.get_service_defaults(session.id)))
        print("emane models: {}".format(core.get_emane_models(session.id)))
        print("add hook: {}".format(core.add_hook(session.id, core_pb2.STATE_RUNTIME, "test", "echo hello")))
        print("hooks: {}".format(core.get_hooks(session.id)))

        response = core.get_sessions()
        print("core client received: {}".format(response))

        print("set emane config: {}".format(core.set_emane_config(session.id, {"otamanagerttl": "2"})))
        print("emane config: {}".format(core.get_emane_config(session.id)))

        # set session location
        response = core.set_session_location(
            session.id, x=0, y=0,
            lat=47.57917, lon=-122.13232, alt=3.0,
            scale=150000.0
        )
        print("set location response: {}".format(response))

        # get options
        print("get options: {}".format(core.get_session_options(session.id)))

        # get location
        print("get location: {}".format(core.get_session_location(session.id)))

        # change session state
        print("set session state: {}".format(core.set_session_state(session.id, core_pb2.STATE_CONFIGURATION)))

        # create switch node
        switch = core_pb2.Node(type=core_pb2.NODE_SWITCH)
        response = core.add_node(session.id, switch)
        print("created switch: {}".format(response))
        switch_id = response.id

        # ip generator for example
        interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/16")

        # create node nodes and link them to switch
        for _ in xrange(2):
            node = core_pb2.Node()
            response = core.add_node(session.id, node)
            print("created node: {}".format(response))
            node_id = response.id
            position = core_pb2.Position(x=5, y=5)
            print("edit node: {}".format(core.edit_node(session.id, node_id, position)))
            print("get node: {}".format(core.get_node(session.id, node_id)))
            print("emane model config: {}".format(
                core.get_emane_model_config(session.id, node_id, "emane_tdma")))

            print("node service: {}".format(core.get_node_service(session.id, node_id, "zebra")))

            # create link
            interface_one = interface_helper.create_interface(node_id, 0)
            print("created link: {}".format(core.add_link(session.id, node_id, switch_id, interface_one)))
            link_options = core_pb2.LinkOptions(per=50)
            print("edit link: {}".format(core.edit_link(
                session.id, node_id, switch_id, link_options, interface_one=0)))

            print("get node links: {}".format(core.get_node_links(session.id, node_id)))

        # change session state
        print("set session state: {}".format(core.set_session_state(session.id, core_pb2.STATE_INSTANTIATION)))

        # get session
        print("get session: {}".format(core.get_session(session.id)))

        # save xml
        core.save_xml(session.id, xml_file_name)

        # delete session
        print("delete session: {}".format(core.delete_session(session.id)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
