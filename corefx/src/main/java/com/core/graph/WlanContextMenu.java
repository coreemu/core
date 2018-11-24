package com.core.graph;

import com.core.Controller;
import com.core.data.CoreNode;

class WlanContextMenu extends AbstractNodeContextMenu {
    WlanContextMenu(Controller controller, CoreNode coreNode) {
        super(controller, coreNode);
        setup();
    }

    private void setup() {
        addMenuItem("WLAN Settings",
                event -> controller.getNodeWlanDialog().showDialog(coreNode));
        if (!controller.getCoreClient().isRunning()) {
            addMenuItem("Mobility",
                    event -> controller.getMobilityDialog().showDialog(coreNode));
            addMenuItem("Link MDRs",
                    event -> controller.getNetworkGraph().linkMdrs(coreNode));
            addMenuItem("Delete Node", event -> controller.deleteNode(coreNode));
        }
    }
}
