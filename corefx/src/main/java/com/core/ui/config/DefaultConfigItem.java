package com.core.ui.config;

import com.core.client.rest.ConfigOption;
import com.jfoenix.controls.JFXTextField;
import javafx.scene.Node;

public class DefaultConfigItem extends BaseConfigItem {
    private JFXTextField textField;

    public DefaultConfigItem(ConfigOption option) {
        super(option);
        textField = new JFXTextField(option.getValue());
        textField.setMaxWidth(Double.MAX_VALUE);
        textField.textProperty().addListener(((observable, oldValue, newValue) -> {
            getOption().setValue(newValue);
        }));
    }

    @Override
    public Node getNode() {
        return textField;
    }
}
