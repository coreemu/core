"""
parse meta data
"""


def parse(meta_string):
    parsed = {}
    if meta_string[0] == "{" and meta_string[len(meta_string) - 1] == "}":
        meta_string = meta_string[1:-1]
    for key_value in meta_string.split("} {"):
        if key_value[len(key_value) - 1] == "}":
            key, value = key_value[:-1].split(" {")
            if key == "wallpaper-style":
                if value == "upperleft":
                    parsed[key] = 1
                elif value == "centered":
                    parsed[key] = 2
                elif value == "scaled":
                    parsed[key] = 3
                elif value == "tiled":
                    parsed[key] = 4
            else:
                parsed[key] = value
        else:
            key, value = tuple(key_value.split())
            parsed[key] = value
    return parsed
