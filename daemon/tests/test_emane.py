"""
Unit tests for testing with a CORE switch.
"""
from conftest import EMANE_SERVICES

from core.data import ConfigData
from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNode
from core.emane.rfpipe import EmaneRfPipeModel


class TestGui:
    def test_80211(self, core):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core.set_emane_model(emane_node, EmaneIeee80211abgModel)

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

    def test_rfpipe(self, core):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core.set_emane_model(emane_node, EmaneRfPipeModel)

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

    def test_commeffect(self, core):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core.set_emane_model(emane_node, EmaneCommEffectModel)

        # configure emane to enable default connectivity
        config_data = ConfigData(
            node=emane_node.objid,
            object="emane_commeffect",
            type=2,
            data_types=(11,),
            data_values="defaultconnectivitymode=1"
        )
        EmaneCommEffectModel.configure_emane(core.session, config_data)

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

    def test_bypass(self, core):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        core.set_emane_model(emane_node, EmaneBypassModel)

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
