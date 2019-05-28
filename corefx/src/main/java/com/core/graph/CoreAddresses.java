package com.core.graph;

import com.core.data.CoreInterface;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Collection;

public class CoreAddresses {
    private static final Logger logger = LogManager.getLogger();
    public static final int IP4_MASK = 24;
    public static final int IP4_INDEX = (IP4_MASK / 8) - 1;

    private String ip4Base;

    public CoreAddresses(String ip4Base) {
        this.ip4Base = ip4Base;
    }

    public int getSubnet(Collection<CoreInterface> nodeOneInterfaces, Collection<CoreInterface> nodeTwoInterfaces) {
        int subOne = getMaxSubnet(nodeOneInterfaces);
        int subTwo = getMaxSubnet(nodeTwoInterfaces);
        logger.info("next subnet: {} - {}", subOne, subTwo);
        return Math.max(subOne, subTwo) + 1;
    }

    private int getMaxSubnet(Collection<CoreInterface> coreInterfaces) {
        int sub = 0;
        for (CoreInterface coreInterface : coreInterfaces) {
            String[] values = coreInterface.getIp4().split("\\.");
            int currentSub = Integer.parseInt(values[IP4_INDEX]);
            logger.info("checking {} value {}", coreInterface.getIp4(), currentSub);
            sub = Math.max(currentSub, sub);
        }
        return sub;
    }

    public String getIp4Address(int sub, int id) {
        return String.format("%s.%s.%s", ip4Base, sub, id);
    }
}
