package com.core.ui.config;

import com.core.client.rest.ConfigOption;
import javafx.scene.control.Label;
import javafx.stage.Stage;
import lombok.Data;

@Data
public abstract class BaseConfigItem implements IConfigItem {
    private final Stage stage;
    private final Label label;
    private final ConfigOption option;

    public BaseConfigItem(Stage stage, ConfigOption option) {
        this.stage = stage;
        this.option = option;
        this.label = new Label(option.getLabel());
    }
}
