package com.core.data;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
public class CoreInterface {
    private Integer id;
    private String name;
    private String mac;
    private String ip4;
    @JsonProperty("ip4mask")
    private Integer ip4Mask;
    private String ip6;
    @JsonProperty("ip6mask")
    private String ip6Mask;
}
