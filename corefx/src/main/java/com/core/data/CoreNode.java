package com.core.data;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

@Data
@NoArgsConstructor
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
public class CoreNode {
    private static final Logger logger = LogManager.getLogger();
    @EqualsAndHashCode.Include
    private Integer id;
    private String name;
    private Integer type;
    private String model;
    private Position position = new Position();
    private Set<String> services = new HashSet<>();
    private String emane;
    private String url;
    @JsonIgnore
    private String icon;
    @JsonIgnore
    private Map<Integer, CoreInterface> interfaces = new HashMap<>();
    @JsonIgnore
    private boolean loaded = true;

    public CoreNode(Integer id) {
        this.id = id;
        this.name = String.format("Node%s", this.id);
        this.loaded = false;
    }

    public CoreInterface getInterface(Integer id) {
        return interfaces.get(id);
    }

    @JsonIgnore
    public String getNodeTypeKey() {
        if (model == null) {
            return type.toString();
        } else {
            return String.format("%s-%s", type, model);
        }
    }

    public void addInterface(CoreInterface coreInterface) {
        logger.info("adding interface node({}) {}", id, coreInterface);
        interfaces.put(coreInterface.getId(), coreInterface);
    }

    @JsonIgnore
    public int getNextInterfaceId() {
        if (interfaces.isEmpty()) {
            return 0;
        } else {
            return Collections.max(interfaces.keySet()) + 1;
        }
    }
}
