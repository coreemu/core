package com.core.graph;

import com.core.Controller;
import com.core.data.CoreNode;
import javafx.event.ActionEvent;
import javafx.event.EventHandler;
import javafx.scene.control.MenuItem;

abstract class AbstractNodeContextMenu extends GraphContextMenu {
    final CoreNode coreNode;

    AbstractNodeContextMenu(Controller controller, CoreNode coreNode) {
        super(controller);
        this.coreNode = coreNode;
    }

    void addMenuItem(String text, EventHandler<ActionEvent> handler) {
        MenuItem menuItem = new MenuItem(text);
        menuItem.setOnAction(handler);
        getItems().add(menuItem);
    }
}
