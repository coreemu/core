package com.core.ui.config;

import com.core.data.ConfigOption;
import com.core.data.ConfigDataType;
import javafx.stage.Stage;

public final class ConfigItemUtils {
    private ConfigItemUtils() {

    }

    public static IConfigItem get(Stage stage, ConfigOption option) {
        IConfigItem configItem;
        ConfigDataType dataType = ConfigDataType.get(option.getType());
        if (dataType == ConfigDataType.BOOL) {
            configItem = new BooleanConfigItem(stage, option);
        } else {
            if (!option.getSelect().isEmpty()) {
                configItem = new SelectConfigItem(stage, option);
            } else if (option.getLabel().endsWith(" file")) {
                configItem = new FileConfigItem(stage, option);
            } else {
                configItem = new DefaultConfigItem(stage, option);
            }
        }

        return configItem;
    }
}
