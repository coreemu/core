"""
Unit tests for testing CORE EMANE networks.
"""

import pytest

from conftest import ping
from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.rfpipe import EmaneRfPipeModel
from core.emane.tdma import EmaneTdmaModel
from core.future.futuredata import NodeOptions

_EMANE_MODELS = [
    EmaneIeee80211abgModel,
    EmaneRfPipeModel,
    EmaneBypassModel,
    EmaneCommEffectModel,
    EmaneTdmaModel,
]


class TestEmane:
    @pytest.mark.parametrize("model", _EMANE_MODELS)
    def test_models(self, session, model, ip_prefixes):
        """
        Test emane models within a basic network.

        :param core.future.coreemu.FutureSession session: session for test
        :param model: emane model to test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create emane node for networking the core nodes
        emane_network = session.create_emane_network(
            model,
            geo_reference=(47.57917, -122.13232, 2.00000)
        )
        emane_network.setposition(x=80, y=50)

        # create nodes
        node_options = NodeOptions()
        node_options.set_position(150, 150)
        node_one = session.create_wireless_node(node_options=node_options)
        node_options.set_position(300, 150)
        node_two = session.create_wireless_node(node_options=node_options)

        for i, node in enumerate([node_one, node_two]):
            node.setposition(x=150 * (i + 1), y=150)
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.objid, emane_network.objid, interface_one=interface)

        # instantiate session
        session.instantiate()

        # ping n2 from n1 and assert success
        status = ping(node_one, node_two, ip_prefixes, count=5)
        assert not status
