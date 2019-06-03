package com.core.data;

import java.util.HashMap;
import java.util.Map;

public enum LinkTypes {
    WIRELESS(0),
    WIRED(1);

    private static final Map<Integer, LinkTypes> LOOKUP = new HashMap<>();

    static {
        for (LinkTypes state : LinkTypes.values()) {
            LOOKUP.put(state.getValue(), state);
        }
    }

    private final int value;

    LinkTypes(int value) {
        this.value = value;
    }

    public int getValue() {
        return this.value;
    }

    public static LinkTypes get(int value) {
        return LOOKUP.get(value);
    }
}
