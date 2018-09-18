package com.core.client.graph;

import lombok.Data;

@Data
public class CoreGraph {
    private String title;
    private CoreGraphAxis xAxis;
    private CoreGraphAxis yAxis;
    private GraphType graphType;
}
