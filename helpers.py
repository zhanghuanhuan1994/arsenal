import os
import sys
import time
import select
from os import path

DIR = path.abspath(path.join(path.dirname(path.abspath(__file__)), os.pardir))
sys.path.append(DIR)

# signal
DONE = "done"
RUN = "run"
STOP = "stop"


READ_FLAGS = select.POLLIN | select.POLLPRI
WRITE_FLAGS = select.POLLOUT
ERR_FLAGS = select.POLLERR | select.POLLHUP | select.POLLNVAL
READ_ERR_FLAGS = READ_FLAGS | ERR_FLAGS
ALL_FLAGS = READ_FLAGS | WRITE_FLAGS | ERR_FLAGS


def curr_ts_ms():
    if not hasattr(curr_ts_ms, 'epoch'):
        curr_ts_ms.epoch = time.time()

    return int((time.time() - curr_ts_ms.epoch) * 1000)
