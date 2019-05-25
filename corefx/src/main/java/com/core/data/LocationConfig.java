package com.core.data;

import lombok.Data;

@Data
public class LocationConfig {
    private Position position = new Position();
    private Location location = new Location();
    private Double scale;
}
