package com.core.ui;

import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXCheckBox;
import javafx.event.ActionEvent;
import javafx.event.EventHandler;
import lombok.Data;

@Data
public class ServiceItem {
    private String service;
    private JFXButton button = new JFXButton("Edit");
    private JFXCheckBox checkBox;

    public ServiceItem(String service) {
        this.service = service;
        checkBox = new JFXCheckBox(service);
        button.getStyleClass().add("core-button");
        button.setMaxWidth(Double.MAX_VALUE);
    }

    public void setEditHandler(EventHandler<ActionEvent> handler) {
        button.setOnAction(handler);
    }
}
