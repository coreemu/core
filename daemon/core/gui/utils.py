def bandwidth_text(bandwidth: int) -> str:
    size = {0: "bps", 1: "Kbps", 2: "Mbps", 3: "Gbps"}
    unit = 1000
    i = 0
    while bandwidth > unit:
        bandwidth /= unit
        i += 1
        if i == 3:
            break
    return f"{bandwidth} {size[i]}"
