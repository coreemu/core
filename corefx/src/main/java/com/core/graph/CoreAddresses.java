package com.core.graph;

import com.core.data.CoreInterface;
import inet.ipaddr.IPAddress;
import inet.ipaddr.IPAddressString;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Comparator;
import java.util.Set;

public class CoreAddresses {
    private static final Logger logger = LogManager.getLogger();
    private IPAddress defaultSubnet = new IPAddressString("10.0.0.0/24").getAddress();

    private IPAddress getMaxAddress(Set<CoreInterface> interfaces) {
        return interfaces.stream()
                .map(CoreInterface::getIp4)
                .max(Comparator.comparingInt(x -> x.toIPv4().intValue()))
                .orElseGet(() -> defaultSubnet);
    }

    public IPAddress getSubnet(Set<CoreInterface> nodeOneInterfaces, Set<CoreInterface> nodeTwoInterfaces,
                               boolean nodeOneIsNetwork, boolean nodeTwoIsNetwork) {
        IPAddress nodeOneMax = getMaxAddress(nodeOneInterfaces);
        IPAddress nodeTwoMax = getMaxAddress(nodeTwoInterfaces);

        logger.info("node one max: {}, node two max: {}", nodeOneMax, nodeTwoMax);
        logger.info("max one compared to two: {} - {}",
                nodeOneMax.toIPv4().intValue(), nodeTwoMax.toIPv4().intValue());
        boolean shouldBump;
        boolean isDefault;
        IPAddress subnet;

        if (nodeOneMax.toIPv4().intValue() > nodeTwoMax.toIPv4().intValue()) {
            subnet = nodeOneMax;
            isDefault = nodeOneMax == defaultSubnet;
            shouldBump = !nodeOneIsNetwork && !isDefault;
        } else {
            subnet = nodeTwoMax;
            isDefault = nodeTwoMax == defaultSubnet;
            shouldBump = !nodeTwoIsNetwork && !isDefault;
        }

        logger.info("found max address: {} - {}", isDefault, subnet);
        if (!isDefault) {
            subnet = subnet.toPrefixBlock();
        }

        if (shouldBump) {
            logger.info("incrementing subnet for host to host");
            subnet = subnet.incrementBoundary(1);
        }

        logger.info("found subnet: {}", subnet);
        return subnet;
    }

    public static void main(String... args) {
        IPAddress addresses = new IPAddressString("10.0.100.1/24").getAddress();
        IPAddress addresses3 = new IPAddressString("10.0.0.2/24").getAddress();
        IPAddress addresses1 = new IPAddressString("10.0.1.0/24").getAddress();
        IPAddress addresses2 = new IPAddressString("10.0.2.0/24").getAddress();
        System.out.println(String.format("compare to greater: %s", addresses.compareTo(addresses3)));
        System.out.println(String.format("compare to greater: %s", addresses3.compareTo(addresses1)));
        System.out.println(String.format("compare to greater: %s", addresses.toInetAddress()));

        IPAddress address = addresses.increment(1);
        IPAddress address1 = addresses1.increment(1);
        IPAddress address2 = addresses2.increment(1);
        System.out.println(String.format("divisions: %s", address.toPrefixBlock()));
        System.out.println(String.format("divisions: %s", address1.toPrefixBlock()));
        System.out.println(String.format("divisions: %s", address2.toPrefixBlock()));
        System.out.println(String.format("compares: %s", address1.compareTo(address2)));
        System.out.println(String.format("compares: %s", address1.compareTo(address)));
        System.out.println(String.format("compares: %s", address2.getSection(2, 3)));
        System.out.println(String.format("compares: %s", address2.getSegment(2)));
        System.out.println(String.format("address: %s", address2));

        IPAddress prefixBlock = address1.toPrefixBlock();
        System.out.println(String.format("prefix block: %s", prefixBlock));
        IPAddress update = new IPAddressString("0.0.1.0").getAddress();
        IPAddress nextAddress = prefixBlock.incrementBoundary(1);
//        nextAddress.setPrefixLength(prefixBlock.getPrefixLength(), true);
        System.out.println(String.format("prefix block update: %s", nextAddress));
    }
}
