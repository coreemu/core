package com.core.ui.config;

import com.core.client.rest.ConfigOption;
import com.core.data.ConfigDataType;
import javafx.stage.Stage;

public final class ConfigItemUtils {
    private ConfigItemUtils() {

    }

    public static IConfigItem get(Stage stage, ConfigOption option) {
        IConfigItem configItem = null;
        ConfigDataType dataType = ConfigDataType.get(option.getType());
        switch (dataType) {
            case BOOL:
                configItem = new BooleanConfigItem(option);
                break;
            default:
                if (!option.getSelect().isEmpty()) {
                    configItem = new SelectConfigItem(option);
                } else {
                    configItem = new DefaultConfigItem(option);
                }
                break;
        }

        return configItem;
    }
}
