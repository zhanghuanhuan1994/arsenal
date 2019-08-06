import os
import time
import sys
import socket
import select
from os import path
import numpy as np
# import datagram_pb2
import data_pb2

import project_root

from indigo.helpers.helpers import (
    curr_ts_ms, apply_op,
    READ_FLAGS, ERR_FLAGS, READ_ERR_FLAGS, WRITE_FLAGS, ALL_FLAGS)

from helpers import curr_ts_ms as help_curr_ts_ms
from indigo.data.videoCodec import VideoCodec
import threading


def format_actions(action_list):
    """ Returns the action list, initially a list with elements "[op][val]"
    like /2.0, -3.0, +1.0, formatted as a dictionary.

    The dictionary keys are the unique indices (to retrieve the action) and
    the values are lists ['op', val], such as ['+', '2.0'].
    """
    return {idx: [action[0], float(action[1:])]
            for idx, action in enumerate(action_list)}


class Sender(object):
    # RL exposed class/static variables
    max_steps = 1000
    state_dim = 4
    action_mapping = format_actions(["/2.0", "-10.0", "+0.0", "+10.0", "*2.0"])
    action_cnt = len(action_mapping)

    start_bitrate = 2000000

    dir = './'
    subdir = ''

    with_frame = True
    is_multi = False

    def __init__(self, ip, port=0, train=False, debug=False):
        self.train = train
        self.debug = debug

        # UDP socket and poller
        self.peer_addr = (ip, port)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.poller = select.poll()
        self.poller.register(self.sock, ALL_FLAGS)

        self.dummy_payload = 'x' * (1440)  # the payload that emulated

        if self.debug:
            self.sampling_file = open(path.join(project_root.DIR, 'env', 'sampling_time'), 'w', 0)

        # congestion control related
        self.seq_num = 1
        self.next_ack = 1
        self.cwnd = 10.0
        self.step_len_ms = 10  # adjust the congestion window every 10 ms

        # state variables for RLCC
        self.delivered_time = 0
        self.delivered = 0
        self.sent_bytes = 0

        self.min_rtt = float('inf')
        self.delay_ewma = None
        self.send_rate_ewma = None
        self.delivery_rate_ewma = None

        self.step_start_ms = None
        self.running = True

        self.buffer = []  # add video frame
        self.codec = VideoCodec()  # video Codec
        if not Sender.with_frame:
            self.codec.is_fix_frame_size = True

        self.read_frame_interval = 33
        self.last_read_frame_time = 0
        self.rate = Sender.start_bitrate

        self.inuse_bitrate = 0
        self.set_bitrate_interval = 1000
        self.sent_bytes_per_second = 0

        self.codec.choose_bps(self.rate)

        self.curr_rtt = 0  # the rtt when acked

        # multi flow
        if Sender.is_multi:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'indigo_send_multi.log')
            self.f = open(self.log_path, mode='w')
        # single flow
        else:
            self.log_path = os.path.join(Sender.dir, 'log', Sender.subdir, 'indigo_send_single.log')
            self.f = open(self.log_path, mode='w')

        self.begin_send_time = 0
        self.sent_queue = []

        self.one_second_data = 0  # used to compute throughput
        self.next_packet_timestamp = time.time()

        if self.train:
            self.step_cnt = 0

            self.ts_first = None
            self.rtt_buf = []

    # close the socket
    def cleanup(self):
        if self.debug and self.sampling_file:
            self.sampling_file.close()
        self.sock.close()

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

    def set_sample_action(self, sample_action):
        """Set the policy. Must be called before run()."""

        self.sample_action = sample_action

    def update_state(self, ack):
        """ Update the state variables listed in __init__() """
        self.next_ack = max(self.next_ack, ack.seq_num + 1)
        curr_time_ms = curr_ts_ms()

        # Update RTT
        rtt = float(curr_time_ms - ack.send_ts)
        self.min_rtt = min(self.min_rtt, rtt)

        self.curr_rtt = rtt / 1000.0  # ms to second

        if self.train:
            if self.ts_first is None:
                self.ts_first = curr_time_ms
            self.rtt_buf.append(rtt)

        delay = rtt - self.min_rtt
        if self.delay_ewma is None:
            self.delay_ewma = delay
        else:
            self.delay_ewma = 0.875 * self.delay_ewma + 0.125 * delay

        # Update BBR's delivery rate
        self.delivered += ack.ack_bytes
        self.delivered_time = curr_time_ms
        delivery_rate = (0.008 * (self.delivered - ack.delivered) /
                         max(1, self.delivered_time - ack.delivered_time))

        if self.delivery_rate_ewma is None:
            self.delivery_rate_ewma = delivery_rate
        else:
            self.delivery_rate_ewma = (
                    0.875 * self.delivery_rate_ewma + 0.125 * delivery_rate)

        # Update Vegas sending rate
        send_rate = 0.008 * (self.sent_bytes - ack.sent_bytes) / max(1, rtt)

        if self.send_rate_ewma is None:
            self.send_rate_ewma = send_rate
        else:
            self.send_rate_ewma = (
                    0.875 * self.send_rate_ewma + 0.125 * send_rate)

    def take_action(self, action_idx):
        old_cwnd = self.cwnd
        op, val = self.action_mapping[action_idx]

        self.cwnd = apply_op(op, self.cwnd, val)
        self.cwnd = max(2.0, self.cwnd)

    def window_is_open(self):
        return self.seq_num - self.next_ack < self.cwnd

    def get_rate_from_window(self):
        new_rate = self.cwnd * 1500 * 8.0 / self.curr_rtt  # bps
        return new_rate

    def get_pacer_rate(self):
        packets_in_buffer = len(self.buffer)
        pacer_rate = packets_in_buffer * 1500 * 8.0 / 2.0  # bps
        return pacer_rate

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

    def send(self):
        # data = datagram_pb2.Data()
        data = data_pb2.Data()
        data.seq_num = self.seq_num
        data.send_ts = curr_ts_ms()
        data.sent_bytes = self.sent_bytes
        data.delivered_time = self.delivered_time
        data.delivered = self.delivered
        data.payload = self.dummy_payload

        packet = self.buffer.pop(0)
        data.frame_id = packet.frame_id  # fixed32 occupy 6 bytes, totally add 18 bytes
        data.frame_start_packet_seq = packet.frame_start_packet_seq
        data.frame_end_packet_seq = packet.frame_end_packet_seq
        data.codec_bitrate = packet.codec_bitrate

        data.send_time = time.time()  # second
        serialized_data = data.SerializeToString()

        info = "seq_num:" + str(data.seq_num) + " send_ts:" + str(data.send_time) + " frame_id:" + str(
            data.frame_id) + " frame_start:" + str(data.frame_start_packet_seq) + " frame_end:" + str(
            data.frame_end_packet_seq) + "\n"

        # self.f.write(info)

        self.sock.sendto(serialized_data, self.peer_addr)
        self.seq_num += 1
        self.sent_bytes += len(serialized_data)

        self.one_second_data += len(serialized_data)

    def recv(self):

        serialized_ack, addr = self.sock.recvfrom(1600)

        if addr != self.peer_addr:
            return

        ack = data_pb2.Ack()
        ack.ParseFromString(serialized_ack)

        self.update_state(ack)

        if self.step_start_ms is None:
            self.step_start_ms = curr_ts_ms()

        # At each step end, feed the state:
        if curr_ts_ms() - self.step_start_ms > self.step_len_ms:  # step's end
            state = [self.delay_ewma,
                     self.delivery_rate_ewma,
                     self.send_rate_ewma,
                     self.cwnd]

            # time how long it takes to get an action from the NN
            if self.debug:
                start_sample = time.time()

            action = self.sample_action(state)

            if self.debug:
                self.sampling_file.write('%.2f ms\n' % ((time.time() - start_sample) * 1000))

            self.take_action(action)

            self.delay_ewma = None
            self.delivery_rate_ewma = None
            self.send_rate_ewma = None

            self.step_start_ms = curr_ts_ms()

            if self.train:
                self.step_cnt += 1
                if self.step_cnt >= Sender.max_steps:
                    self.step_cnt = 0
                    self.running = False

                    self.compute_performance()

        # update the rate that codec choose
        new_rate = self.get_rate_from_window()

        send_rate = "time: " + str(help_curr_ts_ms()) + " send_rate: " + str(new_rate / 1000000.0) + " mbps\n"
        self.f.write(send_rate)
        self.f.flush()

        # print new_rate
        self.set_bitrate(new_rate)

    def run(self):
        TIMEOUT = 1000  # ms

        self.poller.modify(self.sock, ALL_FLAGS)
        curr_flags = ALL_FLAGS

        while self.running:
            self.read_frame_info()

            if self.window_is_open():
                if curr_flags != ALL_FLAGS:
                    self.poller.modify(self.sock, ALL_FLAGS)
                    curr_flags = ALL_FLAGS
            else:
                if curr_flags != READ_ERR_FLAGS:
                    self.poller.modify(self.sock, READ_ERR_FLAGS)
                    curr_flags = READ_ERR_FLAGS

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
                    if self.buffer and len(self.buffer) != 0:
                        if Sender.with_frame:
                            pacer_rate = self.get_pacer_rate()  # bps
                            # use pacing rate
                            if self.rate < pacer_rate:
                                current_timestamp = time.time()
                                if current_timestamp > self.next_packet_timestamp + (1500 * 8.0 / pacer_rate):
                                    self.send()
                                    self.next_packet_timestamp = current_timestamp
                                    # time.sleep(1500 * 8.0 / pacer_rate)  # second
                            # use the windows
                            else:
                                if self.window_is_open():
                                    self.send()
                        # without frame
                        else:
                            if self.window_is_open():
                                self.send()

    def get_throughput(self):
        while (True):
            throughput_info = "indigo: " + str(self.one_second_data * 8.0 / 1000000.0) + " mbps\n"
            self.one_second_data = 0  # set 0
            sys.stderr.write(throughput_info)
            sys.stderr.flush()
            time.sleep(1)

    # start the threads
    def run_1(self):
        thread1 = threading.Thread(target=self.get_throughput)
        thread2 = threading.Thread(target=self.run)
        thread1.start()
        thread2.start()

    def compute_performance(self):
        duration = curr_ts_ms() - self.ts_first
        tput = 0.008 * self.delivered / duration
        perc_delay = np.percentile(self.rtt_buf, 95)

        with open(path.join(project_root.DIR, 'env', 'perf'), 'a', 0) as perf:
            perf.write('%.2f %d\n' % (tput, perc_delay))
