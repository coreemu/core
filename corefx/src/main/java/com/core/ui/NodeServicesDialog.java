package com.core.ui;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.rest.GetServices;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXComboBox;
import com.jfoenix.controls.JFXScrollPane;
import javafx.fxml.FXML;
import javafx.scene.control.ScrollPane;
import javafx.scene.layout.GridPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

public class NodeServicesDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private CoreNode node;

    @FXML
    private JFXComboBox<String> comboBox;

    @FXML
    private GridPane gridPane;

    @FXML
    private ScrollPane scrollPane;

    private Map<String, List<ServiceItem>> serviceItemGroups = new HashMap<>();

    // TODO: get this from core itself
    private Map<String, Set<String>> defaultServices = new HashMap<>();

    private int index = 0;

    public NodeServicesDialog(Controller controller) {
        super(controller, "/fxml/node_services_dialog.fxml");

        JFXButton saveButton = createButton("Save");
        saveButton.setOnAction(event -> {
            for (List<ServiceItem> items : serviceItemGroups.values()) {
                for (ServiceItem item : items) {
                    if (item.getCheckBox().isSelected()) {
                        logger.info("setting service for node({}): {}", node.getName(), item.getService());
                        node.getServices().add(item.getService());
                    }
                }
            }
            close();
        });
        addCancelButton();

        defaultServices.put("mdr", new HashSet<>(Arrays.asList("zebra", "OSPFv3MDR", "IPForward")));
        defaultServices.put("PC", new HashSet<>(Arrays.asList("DefaultRoute")));
        defaultServices.put("prouter", new HashSet<>(Arrays.asList("zebra", "OSPFv2", "OSPFv3", "IPForward")));
        defaultServices.put("router", new HashSet<>(Arrays.asList("zebra", "OSPFv2", "OSPFv3", "IPForward")));
        defaultServices.put("host", new HashSet<>(Arrays.asList("DefaultRoute", "SSH")));

        comboBox.valueProperty().addListener((ov, previous, current) -> {
            if (current == null) {
                return;
            }

            updateItems(current);
        });
    }

    public void setServices(GetServices getServices) {
        comboBox.getItems().clear();
        serviceItemGroups.clear();

        getServices.getGroups().keySet().stream()
                .sorted()
                .forEach(group -> {
                    comboBox.getItems().add(group);

                    getServices.getGroups().get(group).stream()
                            .sorted()
                            .forEach(service -> {
                                ServiceItem serviceItem = new ServiceItem(service);
                                List<ServiceItem> items = serviceItemGroups.computeIfAbsent(
                                        group, k -> new ArrayList<>());
                                items.add(serviceItem);
                            });
                });
        JFXScrollPane.smoothScrolling(scrollPane);

        comboBox.getSelectionModel().selectFirst();
    }

    private void updateItems(String group) {
        logger.debug("updating services for group: {}", group);
        clear();
        List<ServiceItem> items = serviceItemGroups.get(group);
        for (ServiceItem item : items) {
            gridPane.addRow(index++, item.getCheckBox(), item.getButton());
        }
    }

    private void clear() {
        if (!gridPane.getChildren().isEmpty()) {
            gridPane.getChildren().remove(0, gridPane.getChildren().size());
        }
        index = 0;
    }

    public void showDialog(CoreNode node) {
        this.node = node;
        comboBox.getSelectionModel().selectFirst();
        setTitle(String.format("%s - Services", node.getName()));

        Set<String> nodeServices = node.getServices();
        if (nodeServices.isEmpty()) {
            nodeServices = defaultServices.get(node.getModel());
        }

        for (List<ServiceItem> items : serviceItemGroups.values()) {
            for (ServiceItem item : items) {
                boolean selected = nodeServices.contains(item.getService());
                item.getCheckBox().setSelected(selected);
                item.setEditHandler(event -> getController().getServiceDialog().showDialog(node, item.getService()));
            }
        }

        show();
    }
}
