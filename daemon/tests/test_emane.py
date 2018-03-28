"""
Unit tests for testing CORE EMANE networks.
"""

import pytest

from conftest import EMANE_SERVICES

from core.data import ConfigData
from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNode
from core.emane.rfpipe import EmaneRfPipeModel
from core.emane.tdma import EmaneTdmaModel


_EMANE_MODELS = [
    EmaneIeee80211abgModel,
    EmaneRfPipeModel,
    EmaneBypassModel,
    EmaneCommEffectModel,
    EmaneTdmaModel,
]


class TestEmane:
    @pytest.mark.parametrize("model", _EMANE_MODELS)
    def test_models(self, core, model):
        """
        Test emane models within a basic network.

        :param conftest.Core core: core fixture to test with
        :param model: emane model to test
        :param func setup: setup function  to configure emane node
        """

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core.set_emane_model(emane_node, model)

        # create nodes
        core.create_node("n1", objid=1, position=(150, 150), services=EMANE_SERVICES, model="mdr")
        core.create_node("n2", objid=2, position=(300, 150), services=EMANE_SERVICES, model="mdr")

        # add interfaces to nodes
        core.add_interface(emane_node, "n1")
        core.add_interface(emane_node, "n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # ping n2 from n1 and assert success
        status = core.ping("n1", "n2")
        assert not status
