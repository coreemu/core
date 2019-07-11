package com.core.data;

import javafx.scene.control.Label;
import javafx.scene.image.ImageView;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

@Data
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
public class NodeType {
    private static final Logger logger = LogManager.getLogger();
    private static final AtomicInteger idGenerator = new AtomicInteger(0);
    private static final Map<Integer, NodeType> ID_LOOKUP = new HashMap<>();
    public static final int DEFAULT = 0;
    public static final int SWITCH = 4;
    public static final int HUB = 5;
    public static final int WLAN = 6;
    public static final int EMANE = 10;
    public static final int DOCKER = 15;
    public static final int LXC = 16;
    @EqualsAndHashCode.Include
    private final int id;
    private final int value;
    private final Set<String> services = new TreeSet<>();
    private String display;
    private String model;
    private String icon;

    static {
        add(new NodeType(SWITCH, "lanswitch", "Switch", "/icons/switch-100.png"));
        add(new NodeType(HUB, "hub", "Hub", "/icons/hub-100.png"));
        add(new NodeType(WLAN, "wlan", "WLAN", "/icons/wlan-100.png"));
        add(new NodeType(EMANE, "wlan", "EMANE", "/icons/emane-100.png"));
        add(new NodeType(NodeType.DOCKER, null, "DockerNode", "/icons/dockernode-100.png"));
        add(new NodeType(NodeType.LXC, null, "LxcNode", "/icons/lxcnode-100.png"));
    }


    public NodeType(int value, String model, String display, String icon) {
        this.id = idGenerator.incrementAndGet();
        this.value = value;
        this.model = model;
        this.display = display;
        this.icon = icon;
    }

    public Label createLabel(int size) {
        ImageView labelIcon = new ImageView(icon);
        labelIcon.setFitWidth(size);
        labelIcon.setFitHeight(size);
        Label label = new Label(display, labelIcon);
        label.setUserData(id);
        return label;
    }

    public static boolean isDefault(NodeType nodeType) {
        return nodeType.value == DEFAULT || nodeType.value == DOCKER || nodeType.value == LXC;
    }

    public static void add(NodeType nodeType) {
        ID_LOOKUP.put(nodeType.getId(), nodeType);
    }

    public static void remove(NodeType nodeType) {
        ID_LOOKUP.remove(nodeType.getId());
    }

    public static NodeType get(Integer id) {
        return ID_LOOKUP.get(id);
    }

    public static Collection<NodeType> getAll() {
        return ID_LOOKUP.values();
    }

    public static NodeType find(Integer type, String model) {
        return ID_LOOKUP.values().stream()
                .filter(nodeType -> {
                    boolean sameType = nodeType.getValue() == type;
                    boolean sameModel = true;
                    if (model != null && !model.isEmpty()) {
                        sameModel = model.equals(nodeType.getModel());
                    }
                    return sameType && sameModel;
                })
                .findFirst().orElse(null);
    }
}
