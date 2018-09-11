package com.core.rest;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class SetEmaneConfig {
    private Integer node;
    private List<ConfigOption> values = new ArrayList<>();
}
