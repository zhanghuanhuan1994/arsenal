#!/usr/bin/env python

import os
import sys
import socket
import time
import argparse
import threading

sys.path.append('.')
sys.path.append('..')

import cPickle
import jsonpickle

from il.network_simulator.feedbackPacket import FeedbackPacket
from il.network_simulator.frame import Frame


class Receiver(object):
    dir = './'
    subdir = ''

    is_multi = False

    def __init__(self, port=0, buffer_size=10):
        # receiver as the listener
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # create a UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', port))
        sys.stderr.write('[Receiver] GCC Listening on port %s\n' %
                         self.sock.getsockname()[1])

        self.buffer_size = buffer_size
        self.buffer_list = []

        self.feedbackPacket_size = 4
        self.feedbackPacket = FeedbackPacket()

        self.frame_buffer = []
        self.frame_buffer_size = 30
        self.frame = Frame(0, 0)

        self.bandwidth_pre_time = 0

        self.peer_addr = None

        self.count = 0

        if Receiver.is_multi:
            self.log_path = os.path.join(Receiver.dir, 'log', Receiver.subdir, 'GCC_recv_multi.log')
            self.f = open(self.log_path, mode='w')
        else:
            self.log_path = os.path.join(Receiver.dir, 'log', Receiver.subdir, 'GCC_recv_single.log')
            self.f = open(self.log_path, mode='w')

        self.one_second_data = 0

    def combine_frame(self, packet):
        """
        use new packet to combine frame
        :param packet:
        :return:
        """
        if self.frame.frameId != packet.frame_id:
            # add frame delay interval
            self.feedbackPacket.frame_delay_interval.append(self.compute_frame_delay_interval())
            self.feedbackPacket.frame_delay.append(self.compute_frame_delay())
            # here test if new frame comes
            self.frame_buffer.append(self.frame)
            # print('frame_id:', self.frame.frameId, ',inner_frame_loss:', self.frame.compute_loss())
            self.feedbackPacket.frame_inner_loss.append(self.frame.compute_loss())

            if len(self.frame_buffer) > self.frame_buffer_size:
                self.frame_buffer.pop(0)
            self.frame = None
            self.frame = Frame(packet.frame_id, packet.payload_size)
            self.frame.packet_list.append(packet)
        else:
            self.frame.frame_size += packet.payload_size
            self.frame.packet_list.append(packet)
            self.feedbackPacket.frame_inner_loss.append(-1)
            self.feedbackPacket.frame_delay_interval.append(0)
            self.feedbackPacket.frame_delay.append(0)

        if len(self.frame_buffer) > 1:
            max_f_id = -1
            min_f_id = sys.maxsize
            for frame in self.frame_buffer:
                max_f_id = max(max_f_id, frame.frameId)
                min_f_id = min(min_f_id, frame.frameId)

    def compute_frame_delay_interval(self):
        """
        compute out frame delay interval by frame_buffer  and current_frame
        :return:
        """
        last_frame_arrival_time = 0
        last_frame_send_time = 0
        if len(self.frame_buffer) != 0:
            last_frame = self.frame_buffer[-1]
            last_packet = last_frame.packet_list[-1]
            first_packet = last_frame.packet_list[0]
            last_frame_send_time = first_packet.send_time_ms
            last_frame_arrival_time = last_packet.arrival_time_ms
        current_frame = self.frame
        first_packet = current_frame.packet_list[0]
        last_packet = current_frame.packet_list[-1]
        current_frame_send_time = first_packet.send_time_ms
        current_frame_arrival_time = last_packet.arrival_time_ms

        # print current_frame_arrival_time, last_frame_arrival_time
        # print current_frame_send_time, last_frame_send_time

        frame_delay_interval = (current_frame_arrival_time - last_frame_arrival_time) - \
                               (current_frame_send_time - last_frame_send_time)

        return frame_delay_interval

    def compute_frame_delay(self):
        """
        compute out frame delay interval by frame_buffer  and current_frame
        :return:
        """
        current_frame = self.frame
        first_packet = current_frame.packet_list[0]
        last_packet = current_frame.packet_list[-1]
        current_frame_send_time = first_packet.send_time_ms
        current_frame_arrival_time = last_packet.arrival_time_ms
        frame_delay = (current_frame_arrival_time - current_frame_send_time)
        # print('frame_delay:', frame_delay)
        return frame_delay

    def compute_feedback_average_bandwidth(self):
        feedback = self.feedbackPacket
        list_bandwidth = feedback.bandwidth
        start_bw = list_bandwidth[0]
        list_arrival_time = feedback.arrival_time_ms
        feedback_period = list_arrival_time[-1] - self.bandwidth_pre_time

        average_bandwidth = 0
        for i in range(1, len(list_bandwidth)):
            if start_bw != list_bandwidth[i]:
                period = list_arrival_time[i - 1] - self.bandwidth_pre_time
                average_bandwidth = average_bandwidth + period * start_bw
                self.bandwidth_pre_time = list_arrival_time[i - 1]
                start_bw = list_bandwidth[i]

        period = list_arrival_time[-1] - self.bandwidth_pre_time
        average_bandwidth = average_bandwidth + period * start_bw
        average_bandwidth = average_bandwidth / float(feedback_period)
        self.feedbackPacket.average_bandwidth = average_bandwidth
        self.bandwidth_pre_time = list_arrival_time[-1]

        pass

    def add_packet_to_feedback(self, packet, loss):
        """
        add packet to feedbackpacket, when feedbackpacket is full, send it to RL, then renew feedbackpacket
        :param packet:
        :param loss:
        :return:
        """
        self.feedbackPacket.loss.append(loss * 100)
        self.feedbackPacket.send_time_ms.append(packet.send_time_ms)
        self.feedbackPacket.arrival_time_ms.append(packet.arrival_time_ms)
        self.feedbackPacket.payload_size.append(packet.payload_size)
        # self.feedbackPacket.bitrate_list.append(packet.bitrate)

        self.feedbackPacket.frame_id.append(packet.frame_id)
        self.feedbackPacket.frame_packet_start_seq.append(packet.frame_start_packet_seq)
        self.feedbackPacket.frame_packet_end_seq.append(packet.frame_end_packet_seq)

        self.feedbackPacket.bandwidth.append(packet.bandwidth)
        self.feedbackPacket.codec_bitrate.append(packet.codec_bitrate)
        if len(self.feedbackPacket.loss) >= self.feedbackPacket_size:
            self.compute_feedback_average_bandwidth()
            self.passback_feedback()
            self.feedbackPacket = FeedbackPacket([], [], [], [], [], [])

    def passback_feedback(self):
        '''
        send back the feedback after serializing
        :return:
        '''
        # self.sender.receive_feedback(self.feedbackPacket)

        # data = cPickle.dumps(self.feedbackPacket)

        data = jsonpickle.encode(self.feedbackPacket)
        # print(len(data))
        self.sock.sendto(data, self.peer_addr)
        # self.count += 1
        # if self.count % 100 == 0:
        #     print("send feedback", self.count, self.feedbackPacket.arrival_time_ms)

    def compute_loss(self):
        """
        problem: when seq increases to sys.maxsize??
        :return:
        """
        min_seq = sys.maxsize
        max_seq = 0
        for packet in self.buffer_list:
            min_seq = min(min_seq, packet.seq)
            max_seq = max(max_seq, packet.seq)
        loss = 1 - len(self.buffer_list) / float(max_seq - min_seq + 1)
        return loss

    def set_buffer_size(self, buffer_size):
        self.buffer_size = buffer_size

    def receive(self, packet):
        self.buffer_list.append(packet)
        # here buffer size is 10
        if len(self.buffer_list) > self.buffer_size:
            self.buffer_list.pop(0)
        loss = self.compute_loss()
        packet.arrival_time_ms = time.time()
        # print(packet.arrival_time_ms - packet.send_time_ms)
        info = "seq:" + str(packet.seq) + " frame_id:" + str(packet.frame_id) + \
               " send_ms:" + str(int(1000 * packet.send_time_ms)) + " frame_start:" + str(
            packet.frame_start_packet_seq) + \
               " frame_end:" + str(packet.frame_end_packet_seq) + " recv_time:" + str(
            int(1000 * packet.arrival_time_ms)) + \
               " delay:" + str(1000.0 * (packet.arrival_time_ms - packet.send_time_ms)) + " codec_bitrate:" + str(
            packet.codec_bitrate) + "\n"

        self.f.write(info)
        self.f.flush()

        sys.stderr.write(info)
        # sys.stderr.flush()
        packet.arrival_time_ms *= 1000.0
        packet.send_time_ms *= 1000.0

        self.combine_frame(packet)
        self.add_packet_to_feedback(packet, loss)

    def handshake(self):
        """Handshake with peer receiver. Must be called before run()."""

        while True:
            msg, addr = self.sock.recvfrom(1600)

            '''
            handshake successfully
            end the while and set the peer_addr
            '''
            if msg == str.encode('Hello from sender') and self.peer_addr is None:
                self.peer_addr = addr
                self.sock.sendto(str.encode('Hello from receiver'), self.peer_addr)
                sys.stderr.write('[Receiver] Handshake success! GCC'
                                 'Sender\'s address is %s:%s\n' % addr)
                break

        self.sock.setblocking(False)  # non-blocking UDP socket

    def get_throughput(self):
        while True:
            throughput_info = "GCC: " + str(self.one_second_data * 1500 * 8.0 / 1000000.0) + " mbps\n"
            self.one_second_data = 0
            sys.stderr.write(throughput_info)
            sys.stderr.flush()
            time.sleep(1)

    def run(self):
        '''
        run the receiver
        :return:
        '''
        self.sock.setblocking(True)

        # self.sock.settimeout(10)

        thread = threading.Thread(target=self.get_throughput)
        thread.setDaemon(True)
        # thread.start()

        while True:
            try:
                data, addr = self.sock.recvfrom(1600)
                if not thread.is_alive():
                    thread.start()
                self.one_second_data += 1
                # print data
                try:
                    packet = jsonpickle.decode(data)
                    self.receive(packet=packet)
                except BaseException as e:
                    pass
                # packet = cPickle.loads(data)

            except socket.timeout:

                self.sock.close()
                return
            except BaseException as e:
                print("GCC BaseException")
                print(e.args)
                self.sock.close()
                break


def main(subdir=None, is_multi=False):
    port = 6677

    # receiver buffer size of packet
    loss_window = 10

    Receiver.subdir = subdir
    Receiver.is_multi = is_multi
    receiver = Receiver(port, buffer_size=loss_window)

    try:
        receiver.handshake()
        receiver.run()
    except KeyboardInterrupt as e:
        print("GCC_receiver exception")
        print(e.args)
    finally:
        print("[receiver] GCC finally")


if __name__ == '__main__':
    time.sleep(2)
    main()
