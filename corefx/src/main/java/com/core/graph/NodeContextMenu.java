package com.core.graph;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.ui.Toast;
import javafx.scene.control.Menu;
import javafx.scene.control.MenuItem;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.Collections;
import java.util.Set;

class NodeContextMenu extends AbstractNodeContextMenu {
    private static final Logger logger = LogManager.getLogger();

    NodeContextMenu(Controller controller, CoreNode coreNode) {
        super(controller, coreNode);
        setup();
    }

    private MenuItem createStartItem(String service) {
        MenuItem menuItem = new MenuItem("Start");
        menuItem.setOnAction(event -> {
            try {
                boolean result = controller.getCoreClient().startService(coreNode, service);
                if (result) {
                    Toast.success("Started " + service);
                } else {
                    Toast.error("Failure to start " + service);
                }
            } catch (IOException ex) {
                Toast.error("Error starting " + service, ex);
            }
        });
        return menuItem;
    }

    private MenuItem createStopItem(String service) {
        MenuItem menuItem = new MenuItem("Stop");
        menuItem.setOnAction(event -> {
            try {
                boolean result = controller.getCoreClient().stopService(coreNode, service);
                if (result) {
                    Toast.success("Stopped " + service);
                } else {
                    Toast.error("Failure to stop " + service);
                }
            } catch (IOException ex) {
                Toast.error("Error stopping " + service, ex);
            }
        });
        return menuItem;
    }

    private MenuItem createRestartItem(String service) {
        MenuItem menuItem = new MenuItem("Restart");
        menuItem.setOnAction(event -> {
            try {
                boolean result = controller.getCoreClient().restartService(coreNode, service);
                if (result) {
                    Toast.success("Restarted " + service);
                } else {
                    Toast.error("Failure to restart " + service);
                }
            } catch (IOException ex) {
                Toast.error("Error restarting " + service, ex);
            }
        });
        return menuItem;
    }

    private MenuItem createValidateItem(String service) {
        MenuItem menuItem = new MenuItem("Validate");
        menuItem.setOnAction(event -> {
            try {
                boolean result = controller.getCoreClient().validateService(coreNode, service);
                if (result) {
                    Toast.success("Validated " + service);
                } else {
                    Toast.error("Validation failed for " + service);
                }
            } catch (IOException ex) {
                Toast.error("Error validating " + service, ex);
            }
        });
        return menuItem;
    }

    private void setup() {
        if (controller.getCoreClient().isRunning()) {
            Set<String> services = coreNode.getServices();
            if (services.isEmpty()) {
                services = controller.getDefaultServices().getOrDefault(coreNode.getModel(), Collections.emptySet());
            }

            if (!services.isEmpty()) {
                Menu menu = new Menu("Manage Services");
                for (String service : services) {
                    Menu serviceMenu = new Menu(service);
                    MenuItem startItem = createStartItem(service);
                    MenuItem stopItem = createStopItem(service);
                    MenuItem restartItem = createRestartItem(service);
                    MenuItem validateItem = createValidateItem(service);
                    serviceMenu.getItems().addAll(startItem, stopItem, restartItem, validateItem);
                    menu.getItems().add(serviceMenu);
                }
                getItems().add(menu);
            }
        } else {
            addMenuItem("Services", event -> controller.getNodeServicesDialog().showDialog(coreNode));
            addMenuItem("Delete Node", event -> controller.deleteNode(coreNode));
        }
    }
}
