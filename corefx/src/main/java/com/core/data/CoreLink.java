package com.core.data;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;
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

    @JsonIgnore
    private boolean loaded = true;

    private Integer type = 1;

    @JsonProperty("node_one")
    private Integer nodeOne;

    @JsonProperty("node_two")
    private Integer nodeTwo;

    @JsonProperty("interface_one")
    private CoreInterface interfaceOne;

    @JsonProperty("interface_two")
    private CoreInterface interfaceTwo;

    private CoreLinkOptions options = new CoreLinkOptions();

    public CoreLink(Integer id) {
        this.id = id;
        this.weight = (float) id;
        this.loaded = false;
    }
}
