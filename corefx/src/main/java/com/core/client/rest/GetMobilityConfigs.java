package com.core.client.rest;

import lombok.Data;

import java.util.HashMap;
import java.util.Map;

@Data
public class GetMobilityConfigs {
    private Map<Integer, Map<String, ConfigGroup>> configurations = new HashMap<>();
}
