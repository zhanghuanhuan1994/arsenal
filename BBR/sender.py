import socket
import jsonpickle
import json
import time
import sys
import os
import threading

from example.network_simulator.videoCodec import VideoCodec
from helpers import (DONE, RUN, STOP, curr_ts_ms)
from bbr.read_dmesg import get_bbr_pacing_rate, get_pcc_pacing_rate

START_RATE = 2000000  # bps


class Sender(object):
    dir = './'
    subdir = ''
    with_frame = True
    is_multi = False

    def __init__(self):
        TCP_CONGESTION = getattr(socket, 'TCP_CONGESTION', 13)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.IPPROTO_TCP, TCP_CONGESTION, 'bbr')
        # self.sock.setsockopt(socket.SOL_SOCKET, socket.MSG_NOSIGNAL, 1)

        self.peer_addr = ('100.64.0.1', 10100)
        # self.peer_addr = ('127.0.0.1', 10100)
        self.sock.connect(self.peer_addr)

        sys.stderr.write("[sender] bbr is running\n")

        self.rate = START_RATE

        self.codec = VideoCodec()
        if not Sender.with_frame:
            self.codec.is_fix_frame_size = True
        self.codec.choose_bps(START_RATE)

        self.buffer = []
        self.read_frame_interval = 33
        self.last_read_frame_time = 0

        self.inuse_bitrate = 0
        self.last_set_bitrate_time = 0
        self.set_bitrate_interval = 1000  # ms

        self.packets_interval = 1500 * 8.0 / (START_RATE)  # the interval between two packets
        self.next_packet_timestamp = time.time()

        self.sent = 0

        # self.kernel_path = "./kernel_info/bbr_kernel.log"

        # record the log
        if Sender.is_multi:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'BBR_send_multi.log')
            self.f = open(self.log_path, mode='w')
        else:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'BBR_send_single.log')
            self.f = open(self.log_path, mode='w')

    def set_bitrate(self, bitrate):
        if (
                (True)
                or (self.last_set_bitrate_time == 0)
                or ((1000 * (time.time() - self.last_set_bitrate_time) > self.set_bitrate_interval)
                    and (abs(self.inuse_bitrate - bitrate) / float(self.inuse_bitrate) > 0.1))
        ):
            self.last_set_bitrate_time = time.time()
            self.inuse_bitrate = bitrate
            self.codec.choose_bps(bitrate)

    def read_frame_info(self):
        self.set_bitrate(self.rate)  # the codec needs bps
        if Sender.with_frame:
            if self.last_read_frame_time == 0:
                self.last_read_frame_time = time.time()
                self.codec.add_frame()
            elif 1000 * (time.time() - self.last_read_frame_time) > self.read_frame_interval:
                n = 1000 * (time.time() - self.last_read_frame_time) // self.read_frame_interval
                # print("read frame ",n)
                for i in range(int(n)):
                    self.codec.add_frame()
                self.last_read_frame_time = time.time()
            # add packets to buffer
            new_frame_packet_list = self.codec.read_frame_data()
            self.buffer += new_frame_packet_list
        else:
            # the buffer is empty
            if len(self.buffer) == 0:
                self.codec.add_frame()
                new_frame_packet_list = self.codec.read_frame_data()
                self.buffer += new_frame_packet_list

    def read_kernel_info(self):
        bbr_pacing_rate = get_bbr_pacing_rate()
        if bbr_pacing_rate != 0:
            self.rate = bbr_pacing_rate * 8
        # print(str(self.rate / 1000000.0) + " mbps(bbr)")
        send_rate = "time: " + str(curr_ts_ms()) + " send_rate: " + str(self.rate / 1000000.0) + " mbps\n"
        self.f.write(send_rate)
        self.f.flush()

    def get_sending_rate(self):
        while True:
            sys.stderr.write("sender: " + str(self.sent * 1500 * 8 / 1000000.0) + " mbps\n")
            sys.stderr.flush()
            self.sent = 0
            time.sleep(1)

    def send(self):
        while True:
            self.read_kernel_info()
            self.read_frame_info()
            if len(self.buffer) != 0:
                current_timestamp = time.time()
                self.packets_interval = 1500 * 8.0 / self.rate  # second
                if current_timestamp > self.next_packet_timestamp + self.packets_interval:
                    packet = self.buffer.pop(0)
                    packet.send_time_ms = int(1000 * time.time())
                    # packet.payload = (1000) * '#'
                    data = jsonpickle.encode(packet)
                    # data = json.dumps(packet.to_dict())
                    offset = 1500 - len(data)
                    data += " " * offset
                    self.sock.send(data)
                    self.next_packet_timestamp = current_timestamp
                    self.sent += 1

    def run(self):
        thread = threading.Thread(target=self.get_sending_rate, args=())
        thread.setDaemon(True)
        thread.start()
        self.send()

    def cleanup(self):
        self.sock.close()


def main(pipe=None, subdir=None, with_frame=True, is_multi=False):
    Sender.subdir = subdir
    Sender.with_frame = with_frame
    Sender.is_multi = is_multi
    sender = Sender()

    try:
        pipe.send(DONE)
        # print "done"
        while True:
            if pipe.recv() == RUN:
                break
        try:
            # print "running"
            sender.run()
        except IOError as e:
            pass

        while True:
            if pipe.recv() == STOP:
                sender.sock.close()
    except Exception as e:
        print e.args


if __name__ == '__main__':
    pass
