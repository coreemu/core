package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.ui.ServiceItem;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXListView;
import com.jfoenix.controls.JFXScrollPane;
import javafx.collections.FXCollections;
import javafx.fxml.FXML;
import javafx.scene.control.ScrollPane;
import javafx.scene.layout.GridPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

public class NodeServicesDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private final Map<String, List<ServiceItem>> serviceItemGroups = new HashMap<>();
    private final Map<String, ServiceItem> serviceItemMap = new HashMap<>();
    // TODO: get this from core itself
    private final Map<String, Set<String>> defaultServices = new HashMap<>();
    private CoreNode node;
    private int index = 0;
    @FXML private GridPane gridPane;
    @FXML private ScrollPane scrollPane;
    @FXML private JFXListView<String> groupListView;
    @FXML private JFXListView<String> activeListView;
    @FXML private JFXButton removeButton;
    @FXML private JFXButton editButton;

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

        groupListView.getSelectionModel().selectedItemProperty().addListener((ov, previous, current) -> {
            if (current == null) {
                return;
            }

            updateItems(current);
        });

        activeListView.getSelectionModel().selectedItemProperty().addListener((ov, previous, current) -> {
            boolean isDisabled = current == null;
            removeButton.setDisable(isDisabled);
            editButton.setDisable(isDisabled);
        });

        removeButton.setOnAction(event -> {
            String service = activeListView.getSelectionModel().getSelectedItem();
            activeListView.getItems().remove(service);
            ServiceItem serviceItem = serviceItemMap.get(service);
            serviceItem.getCheckBox().setSelected(false);
        });

        editButton.setOnAction(event -> {
            String service = activeListView.getSelectionModel().getSelectedItem();
            getController().getServiceDialog().showDialog(node, service);
        });
    }

    public void setServices(Map<String, List<String>> serviceGroups) {
        serviceItemGroups.clear();

        serviceGroups.keySet().stream()
                .sorted()
                .forEach(group -> {
                    groupListView.getItems().add(group);
                    serviceGroups.get(group).stream()
                            .sorted()
                            .forEach(service -> {
                                ServiceItem serviceItem = new ServiceItem(service);
                                List<ServiceItem> items = serviceItemGroups.computeIfAbsent(
                                        group, k -> new ArrayList<>());
                                items.add(serviceItem);

                                if (serviceItem.getCheckBox().isSelected()) {
                                    activeListView.getItems().add(serviceItem.getService());
                                }

                                serviceItem.getCheckBox().setOnAction(event -> {
                                    if (serviceItem.getCheckBox().isSelected()) {
                                        activeListView.getItems().add(service);
                                        FXCollections.sort(activeListView.getItems());
                                    } else {
                                        activeListView.getItems().remove(service);
                                    }
                                });

                                serviceItemMap.put(service, serviceItem);
                            });
                });
        groupListView.getSelectionModel().selectFirst();
        JFXScrollPane.smoothScrolling(scrollPane);
    }

    private void updateItems(String group) {
        logger.debug("updating services for group: {}", group);
        clearAvailableServices();
        List<ServiceItem> items = serviceItemGroups.get(group);
        for (ServiceItem item : items) {
            gridPane.addRow(index++, item.getCheckBox());
        }
    }

    private void clearAvailableServices() {
        gridPane.getChildren().clear();
        index = 0;
    }

    public void showDialog(CoreNode node) {
        this.node = node;
        setTitle(String.format("%s - Services", node.getName()));
        groupListView.getSelectionModel().selectFirst();
        activeListView.getItems().clear();

        Set<String> nodeServices = node.getServices();
        if (nodeServices.isEmpty()) {
            nodeServices = defaultServices.get(node.getModel());
        }

        for (List<ServiceItem> items : serviceItemGroups.values()) {
            for (ServiceItem item : items) {
                boolean selected = nodeServices.contains(item.getService());
                item.getCheckBox().setSelected(selected);
                if (item.getCheckBox().isSelected()) {
                    activeListView.getItems().add(item.getService());
                }
            }
        }

        FXCollections.sort(activeListView.getItems());
        show();
    }
}
