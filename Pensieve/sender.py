#!/usr/bin/env python

import sys
import argparse
import socket
import threading
import time
import select

import jsonpickle

sys.path.append('..')
sys.path.append('.')

from rl.network_simulator.packet import Packet
from rl.network_simulator.videoCodec import VideoCodec
from rl.Congestion_controller.congestionControllerFactory import CongestionControllerFactory
import os

from helpers import (DONE, RUN, STOP, curr_ts_ms, ALL_FLAGS, READ_ERR_FLAGS, ERR_FLAGS, READ_FLAGS, WRITE_FLAGS)


class Sender(object):
    dir = './'
    subdir = ''

    with_frame = True
    is_multi = False

    def __init__(self, ip, port, bitrate, source_ip, destination_ip, controller_name, pipe=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # create a UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.peer_addr = (ip, port)

        self.source_ip = source_ip
        self.destination_ip = destination_ip

        self.poller = select.poll()
        self.poller.register(self.sock, ALL_FLAGS)

        self.bitrate = bitrate
        self.interval = 4  # the interval between two packets (ms)
        self.buffer = []  # the buffer that store the packets to send
        self.send_time_line = 0

        self.read_frame_interval = 33  # read video frame every 33 milliseconds
        self.last_read_frame_time = 0

        self.inuse_bitrate = 0  # the bitrate that set the codec
        self.last_set_bitrate_time = 0
        self.set_bitrate_interval = 1000  # the min interval between last setting and current setting bitrate(ms)

        self.congestion_controller = CongestionControllerFactory.get_congestion_controller(controller_name)
        self.congestion_name = controller_name

        self.codec = VideoCodec()  # initialize the codec
        # without frame
        if not Sender.with_frame:
            self.codec.is_fix_frame_size = True
        self.codec.choose_bps(1000000)
        # self.set_bitrate(bitrate)

        self.sent_bytes_per_second = 0
        self.next_packet_timestamp = time.time()

        if Sender.is_multi:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'RL_send_multi.log')
            self.f = open(self.log_path, mode='w')
        else:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'RL_send_single.log')
            self.f = open(self.log_path, mode='w')
        self.pipe = pipe

    def set_bitrate(self, bitrate):
        self.bitrate = bitrate
        if (
                (True)
                or (self.last_set_bitrate_time == 0)
                or ((1000 * (time.time() - self.last_set_bitrate_time) > self.set_bitrate_interval)
                    and (abs(self.inuse_bitrate - bitrate) / float(self.inuse_bitrate) > 0.1))
        ):
            self.last_set_bitrate_time = time.time()
            self.inuse_bitrate = bitrate
            self.codec.choose_bps(bitrate)
        self.set_real_send_bitrate(bitrate)

    #
    def set_real_send_bitrate(self, bitrate):
        '''
        self.bitrate = max(b_2s, self.bitrate)
        :param bitrate:
        :return:
        '''
        pacer_send_bitrate = self.compute_pacer_send_bitrate()
        self.bitrate = max(pacer_send_bitrate, bitrate)
        self.interval = 1000 / (float(self.bitrate) / Packet.max_payload_size)

    def compute_pacer_send_bitrate(self):
        '''
        pacer_send_bitrate
        b_2s,bitrate used to clear packet_buffer within 2 second
        :return:
        '''
        sum_packet_payload = 0
        for packet in self.buffer:
            sum_packet_payload += packet.payload_size
        pacer_send_bitrate = sum_packet_payload / 2.0  # 2 seconds
        return pacer_send_bitrate

    def send_data(self):
        packet = self.buffer.pop(0)  # get the front packet of the queue
        packet.send_time_ms = time.time()
        data = jsonpickle.encode(packet)

        data_fill_size = Packet.max_payload_size // 8 - len(data)
        packet.payload = (data_fill_size + 2) * '*'

        data = jsonpickle.encode(packet)

        info = "seq:" + str(packet.seq) + " frame_id:" + str(packet.frame_id) + \
               " send_ms:" + str(packet.send_time_ms) + " frame_start:" + str(
            packet.frame_start_packet_seq) + " frame_end:" + str(packet.frame_end_packet_seq) + " codec_bitrate:" + str(
            packet.codec_bitrate) + "\n"
        # sys.stderr.write(info)
        # sys.stderr.flush()

        self.sock.sendto(data, self.peer_addr)
        self.sent_bytes_per_second += len(data)

    def send(self):

        # print self.bitrate
        self.set_bitrate(self.bitrate)
        # without frame
        if not Sender.with_frame:
            if not self.buffer or len(self.buffer) == 0:
                self.codec.add_frame()
                new_frame_packet_list = self.codec.read_frame_data()
                self.buffer += new_frame_packet_list
            self.send_data()
        # with frame
        else:
            try:
                if self.last_read_frame_time == 0:
                    self.last_read_frame_time = time.time()
                    self.codec.add_frame()
                elif 1000 * (time.time() - self.last_read_frame_time) > self.read_frame_interval:
                    n = 1000 * (time.time() - self.last_read_frame_time) // self.read_frame_interval
                    # print("##" + str(n))
                    # print("read frame ",n)
                    for i in range(int(n)):
                        self.codec.add_frame()
                    self.last_read_frame_time = time.time()

                # add packets to buffer
                new_frame_packet_list = self.codec.read_frame_data()
                self.buffer += new_frame_packet_list
                self.set_bitrate(self.bitrate)
                if len(self.buffer) != 0:
                    self.send_data()

            except BaseException as e:
                sys.stderr.write("[sender] RL exception\n")
                sys.stderr.flush()
                print e.args

    def recv(self):
        '''
        receive a feedback and modify the bitrate
        :return:
        '''
        data, addr = self.sock.recvfrom(1600)
        try:
            feedback = jsonpickle.decode(data)
            bitrate = self.congestion_controller.estimate(feedback)
            send_rate = "time: " + str(curr_ts_ms()) + " send_rate: " + str(bitrate / 1000000.0) + " mbps\n"
            self.f.write(send_rate)
            self.f.flush()
            self.set_bitrate(bitrate)
        except BaseException as e:
            pass

    def handshake(self):
        """Handshake with peer sender. Must be called before run()."""

        self.sock.setblocking(False)  # non-blocking UDP socket

        TIMEOUT = 1000  # ms

        retry_times = 0
        self.poller.modify(self.sock, READ_ERR_FLAGS)

        while True:
            self.sock.sendto(str.encode('Hello from sender'), self.peer_addr)
            events = self.poller.poll(TIMEOUT)

            if not events:  # timed out
                retry_times += 1
                if retry_times > 30:
                    sys.stderr.write(
                        '[sender] Handshake failed after 10 retries\n')
                    return
                else:
                    sys.stderr.write(
                        '[sender] Handshake timed out and retrying...\n')
                    continue

            for fd, flag in events:
                assert self.sock.fileno() == fd

                if flag & ERR_FLAGS:
                    sys.exit('Channel closed or error occurred')

                if flag & READ_FLAGS:
                    msg, addr = self.sock.recvfrom(1600)

                    if addr == self.peer_addr:
                        if msg == str.encode('Hello from receiver'):
                            return

    def get_throughput(self):
        while True:
            bitrate = self.sent_bytes_per_second * 8
            self.sent_bytes_per_second = 0
            throughput_info = "RL sender: " + str(bitrate / 1000000.0) + " mbps\n"
            sys.stderr.write(throughput_info)
            sys.stderr.flush()
            time.sleep(1)

    def run(self):
        TIMEOUT = 1000  # ms
        self.poller.modify(self.sock, ALL_FLAGS)

        thread = threading.Thread(target=self.get_throughput)
        thread.setDaemon(True)
        thread.start()

        while True:

            self.poller.modify(self.sock, ALL_FLAGS)
            events = self.poller.poll(TIMEOUT)

            if not events:  # timed out
                self.send()

            for fd, flag in events:
                assert self.sock.fileno() == fd

                if flag & ERR_FLAGS:
                    sys.exit('Error occurred to the channel')

                if flag & READ_FLAGS:
                    self.recv()

                if flag & WRITE_FLAGS:
                    current_timestamps = time.time()
                    if current_timestamps >= self.next_packet_timestamp + self.interval / 1000.0:
                        self.send()
                        self.next_packet_timestamp = current_timestamps


def main(pipe=None, subdir=None, with_frame=True, is_multi=False, ):
    ip = '100.64.0.1'
    port = 9977
    start_bitrate = 2000e3

    Packet.set_max_packet_size(12000)  # bit
    Sender.subdir = subdir
    Sender.with_frame = with_frame
    Sender.is_multi = is_multi

    if Sender.with_frame:
        controller_name = 'RL'
    else:
        controller_name = 'RL_noFrame'

    # create the sender object
    sender = Sender(ip, port, bitrate=start_bitrate, source_ip='192.168.1.3',
                    destination_ip='192.168.3.1',
                    controller_name=controller_name, pipe=pipe)
    try:
        sys.stderr.write("[sender] RL begin handshake\n")
        sys.stderr.flush()

        sender.handshake()

        sys.stderr.write("[sender] RL handshake done\n")
        sys.stderr.flush()

        # run
        sender.pipe.send(DONE)
        while True:
            if sender.pipe.recv() == RUN:
                break

        sender.run()
        sys.stderr.write("[sender] RL running\n")
        sys.stderr.flush()

        # stop
        while True:
            if sender.pipe.recv() == STOP:
                sender.f.flush()
                sender.f.close()
                sender.sock.close()
                break

    except BaseException as e:
        sys.stderr.write("[sender] RL exception\n")
        sys.stderr.flush()
        # sender.f.close()
        # sender.sock.close()
        print(e.args)


if __name__ == '__main__':
    main()
