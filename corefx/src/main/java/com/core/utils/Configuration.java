package com.core.utils;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
public class Configuration {
    private String coreAddress;
    private int corePort;
    private String xmlPath;
    private String mobilityPath;
    private String iconPath;
    private String shellCommand;
    private List<NodeTypeConfig> nodeTypeConfigs = new ArrayList<>();
    private String nodeLabelColor;
    private String nodeLabelBackgroundColor;
    private Double throughputLimit;
    private Integer throughputWidth;
}
