package com.core.ui.config;

import com.core.client.rest.ConfigOption;
import com.jfoenix.controls.JFXComboBox;
import javafx.scene.Node;

public class SelectConfigItem extends BaseConfigItem {
    private JFXComboBox<String> comboBox = new JFXComboBox<>();

    public SelectConfigItem(ConfigOption option) {
        super(option);
        comboBox.setMaxWidth(Double.MAX_VALUE);
        comboBox.getItems().addAll(option.getSelect());
        comboBox.getSelectionModel().select(option.getValue());
        comboBox.getSelectionModel().selectedItemProperty().addListener(((observable, oldValue, newValue) -> {
            if (newValue == null) {
                return;
            }

            getOption().setValue(newValue);
        }));
    }

    @Override
    public Node getNode() {
        return comboBox;
    }
}
