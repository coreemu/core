package com.core.ui.config;

import com.core.client.rest.ConfigOption;
import com.jfoenix.controls.JFXToggleButton;
import javafx.scene.Node;

public class BooleanConfigItem extends BaseConfigItem {
    private JFXToggleButton button = new JFXToggleButton();

    public BooleanConfigItem(ConfigOption option) {
        super(option);
        button.setMaxWidth(Double.MAX_VALUE);
        if ("1".equals(option.getValue())) {
            button.setSelected(true);
        }
        button.selectedProperty().addListener(((observable, oldValue, newValue) -> {
            String value;
            if (newValue) {
                value = "1";
            } else {
                value = "0";
            }
            getOption().setValue(value);
        }));
    }

    @Override
    public Node getNode() {
        return button;
    }
}
