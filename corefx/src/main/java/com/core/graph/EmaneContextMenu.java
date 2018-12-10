package com.core.graph;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.ui.dialogs.MobilityPlayerDialog;

class EmaneContextMenu extends AbstractNodeContextMenu {
    EmaneContextMenu(Controller controller, CoreNode coreNode) {
        super(controller, coreNode);
        setup();
    }

    private void setup() {
        addMenuItem("EMANE Settings", event -> controller.getNodeEmaneDialog().showDialog(coreNode));
        if (controller.getCoreClient().isRunning()) {
            MobilityPlayerDialog mobilityPlayerDialog = controller.getMobilityPlayerDialogs().get(coreNode.getId());
            if (mobilityPlayerDialog != null && !mobilityPlayerDialog.getStage().isShowing()) {
                addMenuItem("Mobility Script", event -> mobilityPlayerDialog.show());
            }
        } else {
            addMenuItem("Mobility", event -> controller.getMobilityDialog().showDialog(coreNode));
            addMenuItem("Link MDRs", event -> controller.getNetworkGraph().linkMdrs(coreNode));
            addMenuItem("Delete Node", event -> controller.deleteNode(coreNode));
        }
    }
}
