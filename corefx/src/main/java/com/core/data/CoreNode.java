package com.core.data;

import com.core.graph.RadioIcon;
import com.core.utils.IconUtils;
import edu.uci.ics.jung.visualization.LayeredIcon;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.HashSet;
import java.util.Set;

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
    private NodeType nodeType;
    private String icon;
    private String image;
    private boolean loaded = true;
    private LayeredIcon graphIcon;
    private RadioIcon radioIcon = new RadioIcon();

    public CoreNode(Integer id) {
        this.id = id;
        this.name = String.format("Node%s", this.id);
        this.loaded = false;
    }

    public void setNodeType(NodeType nodeType) {
        type = nodeType.getValue();
        model = nodeType.getModel();
        icon = nodeType.getIcon();
        if (icon.startsWith("file:")) {
            graphIcon = IconUtils.getExternalLayeredIcon(icon);
        } else {
            graphIcon = IconUtils.getLayeredIcon(icon);
        }
        graphIcon.add(radioIcon);
        this.nodeType = nodeType;
    }
}
