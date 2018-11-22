package com.core.utils;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
public class NodeTypeConfig {
    private String model;
    private String display;
    private String icon;
    private List<String> services = new ArrayList<>();
}
