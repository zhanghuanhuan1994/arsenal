#!/usr/bin/env python

import os
import sys
import argparse
import socket
import threading
import time
import select
import random

sys.path.append('.')
sys.path.append('..')

import jsonpickle

from il.network_simulator.packet import Packet
from il.network_simulator.videoCodec import VideoCodec
from il.Congestion_controller.congestionControllerFactory import CongestionControllerFactory

from helpers import (DONE, RUN, STOP, curr_ts_ms, READ_FLAGS, ERR_FLAGS, READ_ERR_FLAGS, WRITE_FLAGS, ALL_FLAGS)


class Sender(object):
    dir = './'
    subdir = ''

    with_frame = True
    is_multi = False

    def __init__(self, ip, port, bitrate, source_ip, destination_ip, controller_name, pipe=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # create a UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.peer_addr = (ip, port)

        self.poller = select.poll()
        self.poller.register(self.sock, ALL_FLAGS)

        self.source_ip = source_ip
        self.destination_ip = destination_ip

        self.bitrate = bitrate
        self.interval = 0  # the interval between two packets (ms)
        self.buffer = []  # the buffer that store the packets to send

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

        self.set_bitrate(bitrate)

        self.sent_bytes_per_second = 0

        self.next_packet_timestamp = time.time()

        if Sender.is_multi:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'GCC_send_multi.log')
            self.f = open(self.log_path, mode='w')
        else:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'GCC_send_single.log')
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

    def set_real_send_bitrate(self, bitrate):
        '''
        self.bitrate = max(b_2s, self.bitrate)
        :param bitrate:
        :return:
        '''
        pacer_send_bitrate = self.compute_pacer_send_bitrate()
        self.bitrate = max(pacer_send_bitrate, bitrate)
        self.interval = 1000 / (float(self.bitrate) / Packet.max_payload_size)
        # self.interval *= random.uniform(0.9, 1)
        # self.interval /= 1.21828
        self.interval = max(self.interval, 1)  # compare with 1ms
        # print self.interval

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

        # print len(data)

        info = "seq:" + str(packet.seq) + " frame_id:" + str(packet.frame_id) + \
               " send_ms:" + str(packet.send_time_ms) + " frame_start:" + str(
            packet.frame_start_packet_seq) + " frame_end:" + str(packet.frame_end_packet_seq) + "\n"
        sys.stderr.write(info)
        sys.stderr.flush()

        self.sock.sendto(data, self.peer_addr)
        self.sent_bytes_per_second += 1

    def send(self):
        self.set_bitrate(self.bitrate)
        # without frame
        if not Sender.with_frame:
            if not self.buffer or len(self.buffer) == 0:
                self.codec.add_frame()
                new_frame_packet_list = self.codec.read_frame_data()
                self.buffer += new_frame_packet_list
            self.set_bitrate(self.bitrate)
            self.send_data()
        # with frame
        else:
            try:
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
                new_frame_packet_list = self.codec.read_frame_data(source_ip='192.168.1.1',
                                                                   destination_ip='192.168.2.1')
                self.buffer += new_frame_packet_list

                # print(len(self.buffer))

                self.set_bitrate(self.bitrate)

                if self.buffer and len(self.buffer) != 0:
                    self.send_data()

            except BaseException as e:
                sys.stderr.write("[sender] GCC exception\n")
                sys.stderr.flush()
                print e.args

    def recv(self):
        '''
        receive a feedback and modify the bitrate
        :return:
        '''

        data, addr = self.sock.recvfrom(1600)
        # print data
        try:
            feedback = jsonpickle.decode(data)

            bitrate = self.congestion_controller.estimate(feedback)
            send_rate = "time: " + str(curr_ts_ms()) + " send_rate: " + str(bitrate / 1000000.0) + " mbps\n"
            self.f.write(send_rate)
            self.f.flush()
            # sys.stderr.write(send_rate)

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

    def run(self):
        TIMEOUT = 1000  # ms
        self.poller.modify(self.sock, ALL_FLAGS)

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


def main(pipe=None, subdir=None, with_frame=False, is_multi=False):
    # LOCAL_IP = '127.0.0.1'
    MAHIMAHI_IP = '100.64.0.1'
    ip = MAHIMAHI_IP
    port = 6677
    start_bitrate = 2000e3

    Packet.set_max_packet_size(12000)  # bit

    Sender.subdir = subdir
    Sender.with_frame = with_frame
    Sender.is_multi = is_multi

    # create the sender object
    sender = Sender(ip, port, bitrate=start_bitrate, source_ip='192.168.1.1', destination_ip='192.168.2.1',
                    controller_name="gcc", pipe=pipe)
    try:
        sys.stderr.write("[sender] GCC begin handshake\n")
        sys.stderr.flush()

        sender.handshake()

        sys.stderr.write("[sender] GCC handshake done\n")
        sys.stderr.flush()

        # # run
        sender.pipe.send(DONE)
        while True:
            if sender.pipe.recv() == RUN:
                break

        sender.run()
        sys.stderr.write("[sender] GCC running\n")
        sys.stderr.flush()

        # stop
        while True:
            if sender.pipe.recv() == STOP:
                # sender.congestion_controller.plot_target_send_rate('192.168.1.1')
                sender.f.flush()
                sender.f.close()
                sender.sock.close()
                break

    except BaseException as e:
        sys.stderr.write("[sender] GCC exception\n")
        sys.stderr.flush()
        # sender.f.close()
        # sender.sock.close()
        print(e.args)


if __name__ == '__main__':
    main()
