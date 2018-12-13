package com.core.data;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class InterfaceThroughput {
    private int node;
    @JsonProperty("interface")
    private int nodeInterface;
    private double throughput;
}
