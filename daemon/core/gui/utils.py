from typing import Optional


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


def delay_jitter_text(delay: int, jitter: int) -> Optional[str]:
    line = None
    if delay > 0 and jitter > 0:
        line = f"{delay} us (\u00B1{jitter} us)"
    elif jitter > 0:
        line = f"0 us (\u00B1{jitter} us)"
    return line
