import sys
import time

from core.api.grpc import client
from core.api.grpc.wrappers import Position


# start_row can be used to share a search
def find_next_position(arr, start_row):
    # find next position with value of 0 for 'not visited'
    min_rows, min_cols = (25, 25)
    rows, cols = (470, 900)
    if start_row < min_rows:
        start_row = min_rows
    for y in range(start_row, rows):
        for x in range(min_cols, cols):
            if (y % 2) == 0:
                print(f"search_x={x}")
                print(f"search_y={y}")
                val = arr[x][y]
                if (val == 0) or (val == 100):
                    return x, y
            else:
                search_x = cols - (x - min_cols + 1)
                print(f"search_x={search_x}")
                print(f"search_y={y}")
                val = arr[search_x][y]
                if val == 0:
                    return search_x, y


def move(current_x, current_y, to_x, to_y):
    # move 1 pixel
    speed = 1
    if to_x > current_x:
        move_x = current_x + speed
    elif to_x < current_x:
        move_x = current_x - speed
    else:
        move_x = current_x
    if to_y > current_y:
        move_y = current_y + speed
    elif to_y < current_y:
        move_y = current_y - speed
    else:
        move_y = current_y
    return move_x, move_y


def main():
    n = len(sys.argv)
    if n < 3:
        print("Usage: core-python demo.py <node num> <total search nodes>")
        exit()

    # number of search nodes
    num_search_nodes = int(sys.argv[2])

    # create grpc client and connect
    core = client.CoreGrpcClient("172.16.0.254:50051")
    core.connect()

    # get session
    sessions = core.get_sessions()
    rows_per_zone = (499 - 25) / num_search_nodes
    node_number = int(sys.argv[1])
    y_start = (node_number - 1) * int(rows_per_zone)
    current_x = 25
    current_y = y_start

    # max x and y
    rows, cols = (470, 900)
    arr = [[0 for i in range(rows)] for j in range(cols)]
    print(arr, "before")

    # place target
    # update one element as target
    arr[200][165] = 100
    print(arr, "after")

    position = None
    while True:
        val = arr[current_x][current_y]
        # if position has target, stop
        if val == 100:
            print(f"found target, position={position}")
        else:
            # update one element for this starting position
            arr[current_x][current_y] = 1
            # move
            to_x, to_y = find_next_position(arr, y_start)
            print(f"next x={to_x}, next y={to_y}")
            x, y = move(current_x, current_y, to_x, to_y)
            # command the move
            position = Position(x, y)
            print(f"move to position {position}")
            core.move_node(sessions[0].id, node_number, position=position)
            current_x = x
            current_y = y
        time.sleep(0.25)


if __name__ == "__main__":
    main()
