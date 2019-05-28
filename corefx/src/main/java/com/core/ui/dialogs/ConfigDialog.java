package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.ConfigGroup;
import com.core.data.ConfigOption;
import com.core.ui.config.ConfigItemUtils;
import com.core.ui.config.IConfigItem;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXScrollPane;
import com.jfoenix.controls.JFXTabPane;
import javafx.fxml.FXML;
import javafx.geometry.Insets;
import javafx.scene.Node;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.Tab;
import javafx.scene.layout.ColumnConstraints;
import javafx.scene.layout.GridPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

public class ConfigDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private List<IConfigItem> configItems = new ArrayList<>();
    private JFXButton saveButton;
    @FXML private JFXTabPane tabPane;

    public ConfigDialog(Controller controller) {
        super(controller, "/fxml/config_dialog.fxml");
        saveButton = createButton("Save");
        addCancelButton();
    }

    public List<ConfigOption> getOptions() {
        return configItems.stream().map(IConfigItem::getOption).collect(Collectors.toList());
    }

    private void setDisabled(boolean isDisabled) {
        saveButton.setDisable(isDisabled);
    }

    public void showDialog(String title, List<ConfigGroup> configGroups, Runnable runnable) {
        setTitle(title);
        boolean sessionRunning = getCoreClient().isRunning();
        setDisabled(sessionRunning);

        configItems.clear();
        tabPane.getTabs().clear();
        for (ConfigGroup group : configGroups) {
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
            tabPane.getTabs().add(tab);

            for (ConfigOption option : group.getOptions()) {
                IConfigItem configItem = ConfigItemUtils.get(getStage(), option);
                Node node = configItem.getNode();
                node.setDisable(sessionRunning);
                gridPane.addRow(index, configItem.getLabel(), node);
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
