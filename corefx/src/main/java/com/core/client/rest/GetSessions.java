package com.core.client.rest;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
public class GetSessions {
    private List<GetSessionsData> sessions = new ArrayList<>();
}
