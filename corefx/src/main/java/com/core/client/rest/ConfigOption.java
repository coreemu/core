package com.core.client.rest;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class ConfigOption {
    private String label;
    private String name;
    private String value;
    private Integer type;
    private List<String> select = new ArrayList<>();
}
