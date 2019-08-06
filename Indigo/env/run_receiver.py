#!/usr/bin/env python

import argparse
from receiver import Receiver
import time
import sys

sys.path.append('/home/jamy/cc/')


def main(subdir=None, is_multi=False):
    port = 8877

    Receiver.subdir = subdir
    Receiver.is_multi = is_multi
    receiver = Receiver(port)

    try:
        receiver.handshake()
        receiver.run()
    except KeyboardInterrupt:
        sys.stderr.write("[receiver] indigo exception")
        sys.stderr.flush()
    finally:
        receiver.cleanup()
        print("[receiver] indigo finally")


if __name__ == '__main__':
    main()
