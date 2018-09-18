package com.core.client.graph;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class CoreGraphData {
    private String name;
    private Double x;
    private Double y;
    private Double weight;
}
