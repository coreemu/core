package com.core.client.rest;

import com.core.data.ConfigOption;
import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class SetEmaneConfig {
    private Integer node;
    private List<ConfigOption> values = new ArrayList<>();
}
