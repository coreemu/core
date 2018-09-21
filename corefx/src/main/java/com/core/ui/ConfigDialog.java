package com.core.ui;

import com.core.Controller;
import com.core.client.rest.ConfigGroup;
import com.core.client.rest.ConfigOption;
import com.core.client.rest.GetConfig;
import com.core.data.CoreNode;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXScrollPane;
import com.jfoenix.controls.JFXTabPane;
import javafx.fxml.FXML;
import javafx.geometry.Insets;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.Tab;
import javafx.scene.layout.ColumnConstraints;
import javafx.scene.layout.GridPane;
import javafx.scene.layout.HBox;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

public class ConfigDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private CoreNode coreNode;
    private List<ConfigItem> configItems = new ArrayList<>();
    private JFXButton saveButton;
    @FXML private JFXTabPane tabPane;
    @FXML private HBox buttonBar;

    public ConfigDialog(Controller controller) {
        super(controller, "/fxml/config_dialog.fxml");
        saveButton = createButton("Save");
        addCancelButton();
    }

    public List<ConfigOption> getOptions() {
        return configItems.stream().map(ConfigItem::getOption).collect(Collectors.toList());
    }

    public void showDialog(String title, GetConfig getConfig, Runnable runnable) {
        setTitle(title);

        configItems.clear();
        tabPane.getTabs().clear();
        for (ConfigGroup group : getConfig.getGroups()) {
            String groupName = group.getName();
            Tab tab = new Tab(groupName);
            ScrollPane scrollPane = new ScrollPane();
            scrollPane.setFitToWidth(true);
            tab.setContent(scrollPane);
            GridPane gridPane = new GridPane();
            gridPane.setPadding(new Insets(10));
            scrollPane.setContent(gridPane);
            gridPane.setPrefWidth(Double.MAX_VALUE);
            ColumnConstraints labelConstraints = new ColumnConstraints(10);
            labelConstraints.setPercentWidth(50);
            ColumnConstraints valueConstraints = new ColumnConstraints(10);
            valueConstraints.setPercentWidth(50);
            gridPane.getColumnConstraints().addAll(labelConstraints, valueConstraints);
            gridPane.setHgap(10);
            gridPane.setVgap(10);
            int index = 0;
            logger.info("tabs: {}", tabPane.getTabs());
            tabPane.getTabs().add(tab);

            for (ConfigOption option : group.getOptions()) {
                ConfigItem configItem = new ConfigItem(getStage(), option);
                gridPane.addRow(index, configItem.getLabel(), configItem.getNode());
                configItems.add(configItem);
                index += 1;
            }

            JFXScrollPane.smoothScrolling(scrollPane);
        }

        saveButton.setOnAction(event -> {
            runnable.run();
            close();
        });

        show();
    }
}
