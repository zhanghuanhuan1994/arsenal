#!/usr/bin/env python

import os
import socket
import select
import sys
import time
import argparse
import threading

import jsonpickle

from packet import Packet
from ack import Ack
from rule import Rule

sys.path.append('../')

from indigo.helpers.helpers import (READ_FLAGS, ERR_FLAGS, READ_ERR_FLAGS, WRITE_FLAGS, ALL_FLAGS)
from helpers import (DONE, RUN, STOP)
from helpers import curr_ts_ms

from example.network_simulator.videoCodec import VideoCodec

START_RATE = 700000  # 0.7mbps


class Sender(object):
    alpha = 1.0 / 8.0
    slow_alpha = 1.0 / 256.0

    with_frame = True
    is_multi = False

    dir = './'
    subdir = ''

    def __init__(self, ip, port):
        self.peer_addr = (ip, port)

        # UDP socket and poller
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.poller = select.poll()
        self.poller.register(self.sock, ALL_FLAGS)

        self.window_size = 10
        self.seq_num = 1
        self.next_ack = 1

        # current received packet
        self.packet_send_time = 0
        self.packet_receive_time = 0
        # last packet
        self.last_packet_send_time = 0
        self.last_packet_receive_time = 0

        self.rtt = 0
        self.min_rtt = 0

        self.flag_first_packet = 1  # default 1

        self.s_ewma = 0
        self.r_ewma = 0
        self.slow_r_ewma = 0
        self.rtt_ratio = 1.0

        self.win_multiple = 1
        self.win_increment = 1
        self.intersend = 3

        self.last_sent_time = 0

        # get the rule list
        self.rule = Rule()
        self.rule_list = self.rule.generate(outfile="./remy/log.txt")

        self.cc = 0

        self.sent = 0

        # add frame info
        self.codec = VideoCodec()
        # fix the frame size
        if not Sender.with_frame:
            self.codec.is_fix_frame_size = True
        self.rate = START_RATE  # default
        self.set_bitrate(bitrate=self.rate)

        self.buffer = []
        self.read_frame_interval = 33  # ms
        self.last_read_frame_time = 0

        self.inuse_bitrate = 0
        self.last_set_bitrate_time = 0
        self.set_bitrate_interval = 1000  # ms

        if Sender.is_multi:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'RemyCC_send_multi.log')
            self.f = open(self.log_path, mode='w')
        else:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'RemyCC_send_single.log')
            self.f = open(self.log_path, mode='w')

        self.next_packet_timestamps = time.time()

    def set_bitrate(self, bitrate):
        self.rate = bitrate
        if (
                (True)
                or (self.last_set_bitrate_time == 0)
                or ((1000 * (time.time() - self.last_set_bitrate_time) > self.set_bitrate_interval)
                    and (abs(self.inuse_bitrate - bitrate) / float(self.inuse_bitrate) > 0.1))
        ):
            self.last_set_bitrate_time = time.time()
            self.inuse_bitrate = bitrate
            self.codec.choose_bps(bitrate)

    def get_pacer_rate(self):
        packets_in_buffer = len(self.buffer)
        pacer_rate = packets_in_buffer * 1500 * 8 / 2  # bps
        return pacer_rate

    def get_rate_from_window(self):
        # print self.rtt
        new_rate = self.window_size * 1500 * 8.0 / (self.rtt / 1000)  # bps
        return new_rate

    def read_frame_info(self):
        self.set_bitrate(self.rate)
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

            self.set_bitrate(self.rate)
        else:
            # the buffer is empty
            if not self.buffer or len(self.buffer) == 0:
                self.codec.add_frame()
                new_frame_packet_list = self.codec.read_frame_data()
                self.buffer += new_frame_packet_list

    def cleanup(self):
        self.sock.close()

    def handshake(self):
        """Handshake with peer sender. Must be called before run()."""

        self.sock.setblocking(False)  # non-blocking UDP socket

        TIMEOUT = 1000  # ms

        retry_times = 0
        self.poller.modify(self.sock, READ_ERR_FLAGS)

        while True:
            self.sock.sendto(str.encode('Hello from receiver'), self.peer_addr)
            events = self.poller.poll(TIMEOUT)

            if not events:  # timed out
                retry_times += 1
                if retry_times > 30:
                    sys.stderr.write(
                        '[Sender] Handshake failed after 10 retries\n')
                    return
                else:
                    sys.stderr.write(
                        '[Sender] Handshake timed out and retrying...\n')
                    continue

            for fd, flag in events:
                assert self.sock.fileno() == fd

                if flag & ERR_FLAGS:
                    sys.exit('Channel closed or error occurred')

                if flag & READ_FLAGS:
                    msg, addr = self.sock.recvfrom(1600)

                    if addr == self.peer_addr:
                        return

    def window_is_open(self):
        return self.seq_num < self.next_ack + self.window_size

    def send(self):
        # the interval between two packets
        if 1000 * time.time() - self.last_sent_time > self.intersend:
            video_packet = self.buffer.pop(0)

            packet = Packet()
            packet.send_time = time.time() * 1000
            packet.seq_num = self.seq_num

            # the video frame info
            packet.frame_id = video_packet.frame_id
            packet.frame_start_packet_seq = video_packet.frame_start_packet_seq
            packet.frame_end_packet_seq = video_packet.frame_end_packet_seq
            packet.codec_bitrate = video_packet.codec_bitrate

            # serialize
            data = jsonpickle.encode(packet)
            # print len(data)
            self.sock.sendto(data, self.peer_addr)

            info = "seq:" + str(packet.seq_num) + " frame_id:" + str(packet.frame_id) + " send_ms:" + str(
                packet.send_time) + " frame_start:" + str(packet.frame_start_packet_seq) + " frame_end:" + str(
                packet.frame_end_packet_seq) + "\n"

            # sys.stderr.write(info)

            # save the last packet send time
            self.last_sent_time = packet.send_time
            self.seq_num += 1

            self.sent += 1

    def recv(self):
        serialized_ack, addr = self.sock.recvfrom(1600)

        if addr != self.peer_addr:
            return
        try:
            ack = jsonpickle.decode(serialized_ack)
        except BaseException as e:
            return
        ack.ack_receive_time = time.time() * 1000.0  # to ms
        # get the next ack
        self.next_ack = max(self.next_ack, ack.seq_num + 1)

        # rtt formulate : ack_receive - packet_send
        self.rtt = ack.ack_receive_time - ack.packet_send_time

        # first packet
        if self.flag_first_packet == 1:
            self.flag_first_packet = 0  # reset 0
            self.last_packet_send_time = ack.packet_send_time
            self.last_packet_receive_time = ack.packet_receive_time
            self.min_rtt = self.rtt
        # not first packet
        else:
            self.packet_send_time = ack.packet_send_time
            self.packet_receive_time = ack.packet_receive_time

            self.s_ewma = (1 - Sender.alpha) * self.s_ewma + Sender.alpha * (
                    self.packet_send_time - self.last_packet_send_time)
            self.r_ewma = (1 - Sender.alpha) * self.r_ewma + Sender.alpha * (
                    self.packet_receive_time - self.last_packet_receive_time)
            self.slow_r_ewma = (1 - Sender.slow_alpha) * self.slow_r_ewma + Sender.slow_alpha * (
                    self.packet_receive_time - self.last_packet_receive_time)

            # upgrade the last packet
            self.last_packet_send_time = self.packet_send_time
            self.last_packet_receive_time = self.packet_receive_time
            self.min_rtt = min(self.min_rtt, self.rtt)

            self.rtt_ratio = self.rtt * 1.0 / self.min_rtt

            # print self.s_ewma, self.r_ewma, self.rtt_ratio, self.slow_r_ewma

            self.win_increment, self.win_multiple, self.intersend = self.rule.control(self.s_ewma,
                                                                                      self.r_ewma,
                                                                                      self.rtt_ratio,
                                                                                      self.slow_r_ewma,

                                                                                      self.rule_list)
            # update the window_size
            self.window_size = self.rule.act(self.window_size, self.win_increment, self.win_multiple)

        # print self.window_size
        # update the rate that codec choose
        new_rate = self.get_rate_from_window()

        sender_rate = "time: " + str(curr_ts_ms()) + " send_rate: " + str(new_rate / 1000000.0) + " mbps\n"
        self.f.write(sender_rate)
        self.f.flush()

        # sys.stderr.write(sender_rate)
        # sys.stderr.flush()
        # print new_rate
        self.set_bitrate(new_rate)

    def run(self):
        TIMEOUT = 1000  # ms
        self.poller.modify(self.sock, ALL_FLAGS)
        curr_flags = ALL_FLAGS

        # print throughput
        thread_get_throughput = threading.Thread(target=self.get_throughput, args=())
        thread_get_throughput.setDaemon(True)
        thread_get_throughput.start()

        while True:
            if self.window_is_open():
                if curr_flags != ALL_FLAGS:
                    self.poller.modify(self.sock, ALL_FLAGS)
                    curr_flags = ALL_FLAGS
            else:
                if curr_flags != READ_ERR_FLAGS:
                    self.poller.modify(self.sock, READ_ERR_FLAGS)
                    curr_flags = READ_ERR_FLAGS

            events = self.poller.poll(TIMEOUT)

            for fd, flag in events:
                assert self.sock.fileno() == fd

                if flag & ERR_FLAGS:
                    sys.exit('Error occurred to the channel')

                if flag & READ_FLAGS:
                    self.recv()

                if flag & WRITE_FLAGS:
                    self.read_frame_info()
                    # the buffer is not empty
                    if self.buffer and len(self.buffer) != 0:
                        if Sender.with_frame:
                            pacer_rate = self.get_pacer_rate()  # bps
                            if self.rate < pacer_rate:
                                # use timestamp
                                current_timestamps = time.time()
                                if current_timestamps > self.next_packet_timestamps + 1500 * 8.0 / pacer_rate:
                                    self.send()
                                    self.next_packet_timestamps = current_timestamps
                            else:
                                if self.window_is_open():
                                    self.send()
                        else:
                            # print "no frame"
                            if self.window_is_open():
                                self.send()

    def get_throughput(self):
        while True:
            sys.stderr.write("RemyCC sender: " + str(self.sent * 1500 * 8.0 / 1000000) + " mbps\n")
            sys.stderr.flush()
            self.sent = 0
            time.sleep(1)  # second


def main(pipe=None, subdir=None, with_frame=True, is_multi=False):
    ip = '100.64.0.1'
    port = 9876

    Sender.subdir = subdir
    Sender.with_frame = with_frame
    Sender.is_multi = is_multi
    sender = Sender(ip, port)

    try:
        sys.stderr.write("[sender] RemyCC begin handshake\n")
        sys.stderr.flush()
        sender.handshake()
        sys.stderr.write("[sender] RemyCC handshake done\n")
        sys.stderr.flush()

        # run
        pipe.send(DONE)
        while True:
            if pipe.recv() == RUN:
                break

        sender.run()

        sys.stderr.write("[sender] RemyCC running\n")
        sys.stderr.flush()

        # stop
        while True:
            if pipe.recv() == STOP:
                sender.cleanup()

    except BaseException as e:
        sys.stderr.write("[sender] RemyCC Exception\n")
        sys.stderr.flush()
        print e.args
    finally:
        sender.sock.close()


if __name__ == '__main__':
    main()
