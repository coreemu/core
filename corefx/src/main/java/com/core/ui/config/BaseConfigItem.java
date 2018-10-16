package com.core.ui.config;

import com.core.client.rest.ConfigOption;
import javafx.scene.control.Label;
import lombok.Data;

@Data
public abstract class BaseConfigItem implements IConfigItem {
    private final Label label;
    private final ConfigOption option;

    public BaseConfigItem(ConfigOption option) {
        this.option = option;
        this.label = new Label(option.getLabel());
    }
}
