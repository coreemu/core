package com.core.ui.config;

import com.core.data.ConfigOption;
import javafx.scene.Node;
import javafx.scene.control.Label;

public interface IConfigItem {
    Label getLabel();

    Node getNode();

    ConfigOption getOption();
}
