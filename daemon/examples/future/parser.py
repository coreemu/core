import argparse

DEFAULT_NODES = 2
DEFAULT_TIME = 10
DEFAULT_STEP = 1


def parse_options(name):
    parser = argparse.ArgumentParser(description="Run %s example" % name)
    parser.add_argument("-n", "--nodes", type=int, default=DEFAULT_NODES,
                        help="number of nodes to create in this example")
    parser.add_argument("-t", "--time", type=int, default=DEFAULT_TIME,
                        help="example iperf run time in seconds")

    options = parser.parse_args()

    # usagestr = "usage: %prog [-h] [options] [args]"
    # parser = optparse.OptionParser(usage=usagestr)
    #
    # parser.add_option("-n", "--nodes", dest="nodes", type=int, default=DEFAULT_NODES,
    #                   help="number of nodes to create in this example")
    #
    # parser.add_option("-t", "--time", dest="time", type=int, default=DEFAULT_TIME,
    #                   help="example iperf run time in seconds")

    # def usage(msg=None, err=0):
    #     print
    #     if msg:
    #         print "%s\n" % msg
    #     parser.print_help()
    #     sys.exit(err)

    # parse command line options
    # options, args = parser.parse_args()

    if options.nodes < 2:
        parser.error("invalid min number of nodes: %s" % options.nodes)
    if options.time < 1:
        parser.error("invalid test time: %s" % options.time)

    return options
