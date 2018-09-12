package com.core.client.rest;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class GetConfig {
    private List<ConfigGroup> groups = new ArrayList<>();
}
