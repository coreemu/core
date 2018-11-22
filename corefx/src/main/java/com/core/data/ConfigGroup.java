package com.core.data;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class ConfigGroup {
    private String name;
    private List<ConfigOption> options = new ArrayList<>();
}
