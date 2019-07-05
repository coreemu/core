package com.core.data;

import inet.ipaddr.IPAddress;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
public class CoreInterface {
    private Integer id;
    private String name;
    private String mac;
    private IPAddress ip4;
    private IPAddress ip6;
}
