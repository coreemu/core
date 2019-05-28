package com.core.graph;

import com.core.Controller;
import javafx.event.ActionEvent;
import javafx.event.EventHandler;
import javafx.scene.control.ContextMenu;
import javafx.scene.control.MenuItem;

abstract class GraphContextMenu extends ContextMenu {
    final Controller controller;

    GraphContextMenu(Controller controller) {
        super();
        this.controller = controller;
    }

    void addMenuItem(String text, EventHandler<ActionEvent> handler) {
        MenuItem menuItem = new MenuItem(text);
        menuItem.setOnAction(handler);
        getItems().add(menuItem);
    }
}
