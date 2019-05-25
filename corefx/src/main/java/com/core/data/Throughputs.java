package com.core.data;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class Throughputs {
    private List<InterfaceThroughput> interfaces = new ArrayList<>();
    private List<BridgeThroughput> bridges = new ArrayList<>();
}
