#!/usr/bin/env python

import os
import socket
import select
import sys
import time
import argparse
import threading
import random

import numpy as np

import jsonpickle

from packet import Packet
from ack import Ack

import loaded_agent

sys.path.append('../')

from indigo.helpers.helpers import (READ_FLAGS, ERR_FLAGS, READ_ERR_FLAGS, WRITE_FLAGS, ALL_FLAGS)
from helpers import (DONE, RUN, STOP)
from helpers import curr_ts_ms

from example.network_simulator.videoCodec import VideoCodec

MAX_RATE = 12  # 12mbps -> 1000 packets per second
MIN_RATE = 0.48  # 0.48mpbs -> 40 packets per second
START_RATE = 2.0  # mbps

DELTA_SCALE = 0.025

HISTORY_LENGTH = 10

PACKET_SIZE = 1500  # bytes

TIMEOUT = 1000  # poller


class Sender(object):
    dir = './'
    subdir = ''

    is_multi = False
    with_frame = True

    def __init__(self, ip, port):
        self.peer_addr = (ip, port)

        # UDP socket and poller
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.poller = select.poll()
        self.poller.register(self.sock, ALL_FLAGS)

        self.seq_num = 1

        # the rtt during a MI
        self.rtt_samples = []

        # the parameters of neural network input
        self.latency_inflation = [0.0] * HISTORY_LENGTH
        self.latency_ratio = [1.0] * HISTORY_LENGTH
        self.send_ratio = [1.0] * HISTORY_LENGTH

        self.run_during = 800  # the initial running during (ms), it may need long
        self.last_MI_start_time = None  # last monitor interval start time
        self.MI_end_time = None  # monitor interval end time

        self.sent = 0  # the nun of packets sent during the MI
        self.acked = 0  # the num of acks received during the MI

        self.avg_latency = None  # the avg_latency in a MI
        self.min_latency = None  # the min avg_latency of all past avg_latency

        self.rate = START_RATE

        self.agent = loaded_agent.LoadedModelAgent("./Congestion_controller/model_A")

        # record the log
        if Sender.is_multi:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'Aurora_send_multi.log')
            self.f = open(self.log_path, mode='w')
        else:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'Aurora_send_single.log')
            self.f = open(self.log_path, mode='w')

        self.codec = VideoCodec()
        # without frame
        if not Sender.with_frame:
            self.codec.is_fix_frame_size = True
        self.codec.choose_bps(START_RATE * 1000000)

        self.buffer = []
        self.read_frame_interval = 33
        self.last_read_frame_time = 0

        self.inuse_bitrate = 0
        self.last_set_bitrate_time = 0
        self.set_bitrate_interval = 1000  # ms

        self.packets_interval = 1500 * 8.0 / (START_RATE * 1000000)  # the interval between two packets
        self.true_rate = START_RATE

        self.next_packet_timestamp = time.time()

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
        return True  # without window control

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
        self.set_bitrate(self.rate * 1000000.0)  # the codec needs bps (mbps->bps)
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
            if not self.buffer or len(self.buffer) == 0:
                self.codec.add_frame()
                new_frame_packet_list = self.codec.read_frame_data()
                self.buffer += new_frame_packet_list

    def on_packet_acked(self, rtt):
        self.acked += 1
        self.rtt_samples.append(rtt)

    def get_latency_increase(self):
        half = int(len(self.rtt_samples) / 2)
        if half >= 1:
            return np.mean(self.rtt_samples[half:]) - np.mean(self.rtt_samples[:half])
        else:
            return 0.0

    def get_latency_inflation(self):
        latency_increase = self.get_latency_increase()
        if self.run_during > 0.0:
            return latency_increase / self.run_during
        else:
            return 0.0

    def get_send_rate(self):
        if self.run_during > 0.0:
            return 8.0 * self.sent * 1500 / self.run_during
        else:
            return 0.0

    def get_recv_rate(self):
        if self.run_during > 0.0:
            return 8.0 * (self.acked - 1) * 1500 / self.run_during
        return 0.0

    def get_send_ratio(self):
        '''
        :return: send_ratio float
        '''
        send_rate = self.get_send_rate()
        recv_throughput = self.get_recv_rate()
        if recv_throughput > 0.0 and send_rate < 1000.0 * recv_throughput:
            return send_rate / recv_throughput
        return 1.0

    def get_avg_latency(self):
        if len(self.rtt_samples) > 0:
            self.avg_latency = np.mean(self.rtt_samples)
        else:
            self.avg_latency = 0.0

    def get_min_latency(self):
        # the first state
        if self.min_latency is None:
            if self.avg_latency > 0.0:
                self.min_latency = self.avg_latency
            else:
                self.min_latency = 0.0
        # the state except the first time
        else:
            # the avg_latency is not 0.0 and less than min_latency
            if self.avg_latency > 0.0 and self.avg_latency < self.min_latency:
                self.min_latency = self.avg_latency
            else:
                pass
        # print "avg " + str(self.avg_latency)
        # print "min " + str(self.min_latency)

    def get_latency_ratio(self):
        '''
        :return: latency_ration float
        '''
        self.get_avg_latency()
        self.get_min_latency()
        # print "avg_latency" + str(self.avg_latency)
        # print "min_latency" + str(self.min_latency)
        if self.min_latency > 0.0:
            return self.avg_latency / self.min_latency
        return 1.0

    def get_pacer_rate(self):
        packets_in_buffer = len(self.buffer)
        pacer_rate = packets_in_buffer * 1500 * 8 / 2.0 / 1000000  # empty the buffer in 2 seconds, return mbps
        return pacer_rate

    def set_rate(self, new_rate):
        self.rate = new_rate
        if self.rate > MAX_RATE:
            self.rate = MAX_RATE
        if self.rate < MIN_RATE:
            self.rate = MIN_RATE

    def apply_rate_delta(self, delta):
        delta *= DELTA_SCALE
        if delta >= 0.0:
            self.set_rate(self.rate * (1.0 + delta))
        else:
            self.set_rate(self.rate / (1.0 - delta))

    def send(self):
        packet = Packet()
        packet.send_time = time.time() * 1000  # to ms
        packet.seq_num = self.seq_num

        # add video frame
        packet_video = self.buffer.pop(0)
        packet.frame_id = packet_video.frame_id
        packet.frame_start_packet_seq = packet_video.frame_start_packet_seq
        packet.frame_end_packet_seq = packet_video.frame_end_packet_seq
        packet.codec_bitrate = packet_video.codec_bitrate

        # serialize
        data = jsonpickle.encode(packet)
        # print len(data)
        self.sock.sendto(data, self.peer_addr)

        info = "seq:" + str(packet.seq_num) + " frame_id:" + str(packet.frame_id) + " send_ms:" + str(
            packet.send_time) + " frame_start:" + str(packet.frame_start_packet_seq) + " frame_end:" + str(
            packet.frame_end_packet_seq) + "\n"

        # sys.stderr.write(info)

        # when send a packet
        self.seq_num += 1
        self.sent += 1

    def recv(self):
        serialized_ack, addr = self.sock.recvfrom(1600)
        if addr != self.peer_addr:
            return
        ack = jsonpickle.decode(serialized_ack)
        ack.ack_receive_time = time.time() * 1000.0  # to ms

        # rtt formulate : ack_receive - packet_send (ms)
        rtt = ack.ack_receive_time - ack.packet_send_time
        self.on_packet_acked(rtt=rtt)

    def send_thread(self):
        # keep sending
        while True:
            self.read_frame_info()
            if self.buffer and len(self.buffer) != 0:
                if Sender.with_frame:
                    # update the sending rate
                    pacer_rate = self.get_pacer_rate()
                    # print self.rate
                    # print self.true_rate
                    self.true_rate = max(self.rate, pacer_rate)
                    self.packets_interval = PACKET_SIZE * 8.0 / (self.true_rate * 1000000)  # second
                    current_timestamp = time.time()
                    if current_timestamp > self.next_packet_timestamp + self.packets_interval:
                        self.send()
                        self.next_packet_timestamp = current_timestamp
                else:
                    self.packets_interval = PACKET_SIZE * 8.0 / (self.rate * 1000000)  # second
                    current_timestamp = time.time()
                    if current_timestamp > self.next_packet_timestamp + self.packets_interval:
                        self.send()
                        self.next_packet_timestamp = current_timestamp

    def recv_thread(self):
        # keep receiving
        while True:
            self.recv()

    def get_throughput(self):
        while True:
            sys.stderr.write("Aurora sender: " + str(self.rate) + " mbps\n")  # the rate of algorithms
            sys.stderr.flush()
            time.sleep(1)  # second

    def run(self):
        TIMEOUT = 1000  # ms
        self.poller.modify(self.sock, ALL_FLAGS)
        self.sock.setblocking(True)

        # execute send and receive thread
        thread_send = threading.Thread(target=self.send_thread, args=())
        thread_recv = threading.Thread(target=self.recv_thread, args=())
        # print the throughput each second
        thread_get_throughput = threading.Thread(target=self.get_throughput, args=())

        thread_send.setDaemon(True)
        thread_recv.setDaemon(True)
        thread_get_throughput.setDaemon(True)

        thread_send.start()
        thread_recv.start()
        thread_get_throughput.start()

        while True:
            # the monitor interval start and end time
            if self.last_MI_start_time is None:
                self.last_MI_start_time = time.time() * 1000  # to ms
            self.MI_end_time = self.last_MI_start_time + self.run_during

            # during the MI
            while time.time() * 1000 < self.MI_end_time:
                events = self.poller.poll(TIMEOUT)
                for fd, flag in events:
                    assert self.sock.fileno() == fd

                    if flag & ERR_FLAGS:
                        sys.exit('Error occurred to the channel')
            # end while (during MI)

            # print(self.rtt_samples)
            # print self.sent
            # print self.acked

            latency_inflation = self.get_latency_inflation()
            latency_ratio = self.get_latency_ratio()
            send_ratio = self.get_send_ratio()

            # reset the rtt_samples and so on.
            self.reset()

            self.latency_inflation.pop(0)
            self.latency_ratio.pop(0)
            self.send_ratio.pop(0)

            self.latency_inflation.append(latency_inflation)
            self.latency_ratio.append(latency_ratio)
            self.send_ratio.append(send_ratio)

            # print "latency inflation, latency ratio, send ratio"
            # print self.latency_inflation
            # print self.latency_ratio
            # print self.send_ratio

            # the input of the neural network
            history = []
            for i in range(HISTORY_LENGTH):
                array = [self.latency_inflation[i], self.latency_ratio[i], self.send_ratio[i]]
                history.append(array)
            history = np.array(history).flatten()

            # call the neural network, get the delta
            delta = self.agent.act(history)
            # if delta < 0.0:
            # print "delta" + str(delta)

            # update rate
            self.apply_rate_delta(delta=delta)

            send_rate = "time: " + str(curr_ts_ms()) + " send_rate: " + str(self.rate) + " mbps\n"
            self.f.write(send_rate)
            self.f.flush()

            # update the rate that codec choose
            self.set_bitrate(self.rate * 1000000)  # mbps->bps

            # print str(self.rate) + " mbps"

            # update next run_during
            if self.avg_latency > 0.0:
                self.run_during = 0.5 * self.avg_latency
            # print "run_during " + str(self.run_during)

            # current MI_end_time is next MI_start_time
            self.last_MI_start_time = self.MI_end_time

    def reset(self):
        self.rtt_samples = []
        self.sent = 0
        self.acked = 0


def main(pipe=None, subdir=None, with_frame=True, is_multi=False):
    LOCAL_IP = '127.0.0.1'
    MAHIMAHI_IP = '100.64.0.1'

    ip = MAHIMAHI_IP
    port = 9777

    Sender.subdir = subdir
    Sender.with_frame = with_frame
    Sender.is_multi = is_multi
    sender = Sender(ip, port)

    try:
        sys.stderr.write("[sender] Aurora begin handshake\n")
        sys.stderr.flush()
        sender.handshake()
        sys.stderr.write("[sender] Aurora handshake done\n")
        sys.stderr.flush()

        # run
        pipe.send(DONE)
        while True:
            if pipe.recv() == RUN:
                break

        sender.run()

        sys.stderr.write("[sender] Aurora running\n")
        sys.stderr.flush()

        # stop
        while True:
            if pipe.recv() == STOP:
                sender.cleanup()
                if is_multi:
                    sender.f.flush()
                    sender.f.close()

    except BaseException as e:
        sys.stderr.write("[sender] Aurora Exception\n")
        sys.stderr.flush()
        print e.args
    finally:
        sender.cleanup()
        if not sender.f.closed:
            sender.f.close()


if __name__ == '__main__':
    main()
