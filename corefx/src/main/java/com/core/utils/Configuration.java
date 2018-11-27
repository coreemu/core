package com.core.utils;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
public class Configuration {
    private String coreRest;
    private String xmlPath;
    private String mobilityPath;
    private String iconPath;
    private String shellCommand;
    private List<NodeTypeConfig> nodeTypeConfigs = new ArrayList<>();
}
