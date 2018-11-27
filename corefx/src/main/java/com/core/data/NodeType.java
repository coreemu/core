package com.core.data;

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
    @EqualsAndHashCode.Include
    private final int id;
    private final int value;
    private final Set<String> services = new TreeSet<>();
    private String display;
    private String model;
    private String icon;

    //    PHYSICAL = 1
//    RJ45 = 7
//    TUNNEL = 8
//    KTUNNEL = 9
//    EMANE = 10
//    TAP_BRIDGE = 11
//    PEER_TO_PEER = 12
//    CONTROL_NET = 13
//    EMANE_NET = 14;

    static {
        add(new NodeType(SWITCH, "lanswitch", "Switch", "/icons/switch-100.png"));
        add(new NodeType(HUB, "hub", "Hub", "/icons/hub-100.png"));
        add(new NodeType(WLAN, "wlan", "WLAN", "/icons/wlan-100.png"));
        add(new NodeType(EMANE, "wlan", "EMANE", "/icons/emane-100.png"));
    }


    public NodeType(int value, String model, String display, String icon) {
        this.id = idGenerator.incrementAndGet();
        this.value = value;
        this.model = model;
        this.display = display;
        this.icon = icon;
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
                    boolean sameModel;
                    if (model != null) {
                        sameModel = model.equals(nodeType.getModel());
                    } else {
                        sameModel = nodeType.getModel() == null;
                    }
                    return sameType && sameModel;
                })
                .findFirst().orElse(null);
    }
}
