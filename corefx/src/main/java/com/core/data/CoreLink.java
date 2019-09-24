package com.core.data;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
public class CoreLink {
    @EqualsAndHashCode.Include
    private Integer id;
    private Float weight = 1.0f;
    private boolean loaded = true;
    private double throughput;
    private boolean visible = true;
    private Integer messageType;
    private Integer type = LinkTypes.WIRED.getValue();
    private Integer nodeOne;
    private Integer nodeTwo;
    private CoreInterface interfaceOne;
    private CoreInterface interfaceTwo;
    private CoreLinkOptions options = new CoreLinkOptions();

    public CoreLink(Integer id) {
        this.id = id;
        this.weight = (float) id;
        this.loaded = false;
    }

    public boolean isWireless() {
        return interfaceOne == null && interfaceTwo == null;
    }
}
