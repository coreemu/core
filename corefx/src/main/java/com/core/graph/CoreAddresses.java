package com.core.graph;

import com.core.data.CoreInterface;
import inet.ipaddr.IPAddress;
import inet.ipaddr.IPAddressString;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Comparator;
import java.util.Queue;
import java.util.Set;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.atomic.AtomicBoolean;

public class CoreAddresses {
    private static final Logger logger = LogManager.getLogger();
    private IPAddress currentSubnet = new IPAddressString("10.0.0.0/24").getAddress().toPrefixBlock();
    private AtomicBoolean firstSubnet = new AtomicBoolean(true);
    private Queue<IPAddress> deleted = new LinkedBlockingQueue<>();

    public void reuseSubnet(IPAddress subnet) {
        deleted.add(subnet);
    }

    public IPAddress nextSubnet() {
        logger.info("getting next subnet: {}", currentSubnet);
        if (!firstSubnet.getAndSet(false)) {
            IPAddress deletedSubnet = deleted.poll();
            if (deletedSubnet != null) {
                currentSubnet = deletedSubnet;
            } else {
                currentSubnet = currentSubnet.incrementBoundary(1).toPrefixBlock();
            }
        }
        logger.info("getting updated boundary: {}", currentSubnet);
        return currentSubnet;
    }

    public IPAddress findSubnet(Set<CoreInterface> interfaces) {
        IPAddress subnet;
        logger.info("finding subnet from interfaces: {}", interfaces);
        if (interfaces.isEmpty()) {
            subnet = nextSubnet();
        } else {
            IPAddress maxAddress = getMaxAddress(interfaces);
            subnet = maxAddress.toPrefixBlock();
        }
        return subnet;
    }

    private IPAddress getMaxAddress(Set<CoreInterface> interfaces) {
        return interfaces.stream()
                .map(CoreInterface::getIp4)
                .max(Comparator.comparingInt(x -> x.toIPv4().intValue()))
                .orElseGet(() -> currentSubnet);
    }

    public void reset() {
        deleted.clear();
        firstSubnet.set(true);
        currentSubnet = new IPAddressString("10.0.0.0/24").getAddress().toPrefixBlock();
    }

    public static void main(String... args) {
        IPAddress addresses = new IPAddressString("10.0.0.0/16").getAddress();
        System.out.println(String.format("address: %s", addresses.increment(257)));
    }
}
