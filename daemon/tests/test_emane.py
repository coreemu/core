"""
Unit tests for testing with a CORE switch.
"""

from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNode
from core.emane.rfpipe import EmaneRfPipeModel
from core.services import quagga
from core.services import utility


class TestGui:
    def test_80211(self, core):
        """
        Test emane 80211 model.

        :param conftest.Core core: core fixture to test with
        """

        # load services
        quagga.load_services()
        utility.load_services()

        # set and load emane models
        core.session.master = True
        core.session.location.setrefgeo(47.57917, -122.13232, 2.00000)
        core.session.location.refscale = 150.0
        core.session.emane.loadmodels()

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        emane_model = EmaneIeee80211abgModel
        values = emane_model.getdefaultvalues()
        core.session.emane.setconfig(emane_node.objid, emane_model.name, values)

        # create nodes
        core.create_node("n1", objid=1)
        core.create_node("n2", objid=2)
        node_one = core.get_node("n1")
        node_two = core.get_node("n2")

        # set node positions
        node_one.setposition(x=150, y=150)
        node_two.setposition(x=300, y=150)

        # add services
        services = "zebra|OSPFv3MDR|IPForward"
        core.session.services.addservicestonode(node_one, "", services)
        core.session.services.addservicestonode(node_two, "", services)

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

        # load services
        quagga.load_services()
        utility.load_services()

        # set and load emane models
        core.session.master = True
        core.session.location.setrefgeo(47.57917, -122.13232, 2.00000)
        core.session.location.refscale = 150.0
        core.session.emane.loadmodels()

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        emane_model = EmaneRfPipeModel
        values = emane_model.getdefaultvalues()
        core.session.emane.setconfig(emane_node.objid, emane_model.name, values)

        # create nodes
        core.create_node("n1", objid=1)
        core.create_node("n2", objid=2)
        node_one = core.get_node("n1")
        node_two = core.get_node("n2")

        # set node positions
        node_one.setposition(x=150, y=150)
        node_two.setposition(x=300, y=150)

        # add services
        services = "zebra|OSPFv3MDR|IPForward"
        core.session.services.addservicestonode(node_one, "", services)
        core.session.services.addservicestonode(node_two, "", services)

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

        # load services
        quagga.load_services()
        utility.load_services()

        # set and load emane models
        core.session.master = True
        core.session.location.setrefgeo(47.57917, -122.13232, 2.00000)
        core.session.location.refscale = 150.0
        core.session.emane.loadmodels()

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        emane_model = EmaneCommEffectModel
        values = emane_model.getdefaultvalues()
        core.session.emane.setconfig(emane_node.objid, emane_model.name, values)

        # create nodes
        core.create_node("n1", objid=1)
        core.create_node("n2", objid=2)
        node_one = core.get_node("n1")
        node_two = core.get_node("n2")

        # set node positions
        node_one.setposition(x=150, y=150)
        node_two.setposition(x=300, y=150)

        # add services
        services = "zebra|OSPFv3MDR|IPForward"
        core.session.services.addservicestonode(node_one, "", services)
        core.session.services.addservicestonode(node_two, "", services)

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

        # load services
        quagga.load_services()
        utility.load_services()

        # set and load emane models
        core.session.master = True
        core.session.location.setrefgeo(47.57917, -122.13232, 2.00000)
        core.session.location.refscale = 150.0
        core.session.emane.loadmodels()

        # create emane node for networking the core nodes
        emane_node = core.session.add_object(name="emane", cls=EmaneNode)
        emane_node.setposition(x=80, y=50)

        # set the emane model
        emane_model = EmaneBypassModel
        values = emane_model.getdefaultvalues()
        core.session.emane.setconfig(emane_node.objid, emane_model.name, values)

        # create nodes
        core.create_node("n1", objid=1)
        core.create_node("n2", objid=2)
        node_one = core.get_node("n1")
        node_two = core.get_node("n2")

        # set node positions
        node_one.setposition(x=150, y=150)
        node_two.setposition(x=300, y=150)

        # add services
        services = "zebra|OSPFv3MDR|IPForward"
        core.session.services.addservicestonode(node_one, "", services)
        core.session.services.addservicestonode(node_two, "", services)

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
