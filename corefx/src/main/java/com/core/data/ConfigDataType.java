package com.core.data;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

public enum ConfigDataType {
    UINT8(1),
    UINT16(2),
    UINT32(3),
    UINT64(4),
    INT8(5),
    INT16(6),
    INT32(7),
    INT64(8),
    FLOAT(9),
    STRING(10),
    BOOL(11);

    private static final Map<Integer, ConfigDataType> LOOKUP = new HashMap<>();

    static {
        Arrays.stream(ConfigDataType.values()).forEach(x -> LOOKUP.put(x.getValue(), x));
    }

    private final int value;

    ConfigDataType(int value) {
        this.value = value;
    }

    public int getValue() {
        return value;
    }


    public static ConfigDataType get(int value) {
        return LOOKUP.get(value);
    }
}
