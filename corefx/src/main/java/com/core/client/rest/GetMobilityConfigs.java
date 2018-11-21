package com.core.client.rest;

import com.core.data.MobilityConfig;
import lombok.Data;

import java.util.HashMap;
import java.util.Map;

@Data
public class GetMobilityConfigs {
    private Map<Integer, MobilityConfig> configurations = new HashMap<>();
}
