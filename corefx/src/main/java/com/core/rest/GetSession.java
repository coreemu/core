package com.core.rest;

import com.core.data.CoreNode;
import com.core.data.CoreLink;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
public class GetSession {
    private Integer state;
    private List<CoreNode> nodes = new ArrayList<>();
    private List<CoreLink> links = new ArrayList<>();
}
