"""
Unit tests for testing with a CORE switch.
"""

from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNode
from core.emane.rfpipe import EmaneRfPipeModel

_EMANE_SERVICES = "zebra|OSPFv3MDR|IPForward"


class TestGui:
    def test_80211(self, core_emane):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # create emane node for networking the core nodes
        emane_node = core_emane.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core_emane.set_emane_model(emane_node, EmaneIeee80211abgModel)

        # create nodes
        core_emane.create_node("n1", objid=1, position=(150, 150), services=_EMANE_SERVICES, model="mdr")
        core_emane.create_node("n2", objid=2, position=(300, 150), services=_EMANE_SERVICES, model="mdr")

        # add interfaces to nodes
        core_emane.add_interface(emane_node, "n1")
        core_emane.add_interface(emane_node, "n2")

        # instantiate session
        core_emane.session.instantiate()

        # assert node directories created
        core_emane.assert_nodes()

        # ping n2 from n1 and assert success
        status = core_emane.ping("n1", "n2")
        assert not status

    def test_rfpipe(self, core_emane):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # create emane node for networking the core nodes
        emane_node = core_emane.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core_emane.set_emane_model(emane_node, EmaneRfPipeModel)

        # create nodes
        core_emane.create_node("n1", objid=1, position=(150, 150), services=_EMANE_SERVICES, model="mdr")
        core_emane.create_node("n2", objid=2, position=(300, 150), services=_EMANE_SERVICES, model="mdr")

        # add interfaces to nodes
        core_emane.add_interface(emane_node, "n1")
        core_emane.add_interface(emane_node, "n2")

        # instantiate session
        core_emane.session.instantiate()

        # assert node directories created
        core_emane.assert_nodes()

        # ping n2 from n1 and assert success
        status = core_emane.ping("n1", "n2")
        assert not status

    def test_commeffect(self, core_emane):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # create emane node for networking the core nodes
        emane_node = core_emane.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core_emane.set_emane_model(emane_node, EmaneCommEffectModel)

        # create nodes
        core_emane.create_node("n1", objid=1, position=(150, 150), services=_EMANE_SERVICES, model="mdr")
        core_emane.create_node("n2", objid=2, position=(300, 150), services=_EMANE_SERVICES, model="mdr")

        # add interfaces to nodes
        core_emane.add_interface(emane_node, "n1")
        core_emane.add_interface(emane_node, "n2")

        # instantiate session
        core_emane.session.instantiate()

        # assert node directories created
        core_emane.assert_nodes()

        # ping n2 from n1 and assert success
        status = core_emane.ping("n1", "n2")
        assert not status

    def test_bypass(self, core_emane):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # create emane node for networking the core nodes
        emane_node = core_emane.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core_emane.set_emane_model(emane_node, EmaneBypassModel)

        # create nodes
        core_emane.create_node("n1", objid=1, position=(150, 150), services=_EMANE_SERVICES, model="mdr")
        core_emane.create_node("n2", objid=2, position=(300, 150), services=_EMANE_SERVICES, model="mdr")

        # add interfaces to nodes
        core_emane.add_interface(emane_node, "n1")
        core_emane.add_interface(emane_node, "n2")

        # instantiate session
        core_emane.session.instantiate()

        # assert node directories created
        core_emane.assert_nodes()

        # ping n2 from n1 and assert success
        status = core_emane.ping("n1", "n2")
        assert not status
