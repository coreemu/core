package com.core.client.rest;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class SetEmaneModelConfig {
    private Integer node;
    private String name;
    private List<ConfigOption> values = new ArrayList<>();
}
