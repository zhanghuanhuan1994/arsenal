# -*- coding: UTF-8 -*-
from example.network_simulator.packet import Packet
from example.network_simulator.frame import Frame
import example.network_simulator.project_root as project_root
import os

import cPickle as pickle


class VideoCodec(object):
    def __init__(self):
        self.f_id = []
        self.f_type = []
        self.f_size = []
        self.i_frame = -1
        self.is_fix_frame_size = False
        self.fix_frame_size = Packet.max_payload_size * 10  # when fixed, frame size is 200000 byte
        self.bitrate = 0.7
        self.frame_num = 0
        self.frame_list = []
        self.max_bitrate = 2.0
        self.min_bitrate = 0.1

        self.frame_buffer = []
        self.frame_buffer_size = 30

        self.frame_queue = []
        self.frame_queue_size = 30

        self.udp_seq = 1

    def set_default_frame_size(self, frame_size):
        self.fix_frame_size = frame_size

    def set_fix_frame_size(self, is_fix_frame_size):
        self.is_fix_frame_size = is_fix_frame_size

    def choose_bps(self, bitrate):

        bitrate /= 50.0  # the bit rate enlarge 5 times

        bitrate //= 1e5
        bitrate /= 10.0
        if self.i_frame == -1:
            file_path = os.path.join(project_root.DIR, 'videoFrame', 'frame_size.pk')
            f_f_size = open(file_path, "rb")

            self.f_size = pickle.load(f_f_size)  # f_size is a dict

            # for key, value in self.f_size.items():
            #     print(key, value)
            # print self.bitrate
            self.frame_num = len(self.f_size[self.bitrate])  # the length of frame in current bit rate
            f_f_size.close()
            self.i_frame += 1
        bitrate = min(bitrate, self.max_bitrate)
        bitrate = max(bitrate, self.min_bitrate)
        self.bitrate = bitrate
        # print("the bit rate is " + str(bitrate))
        # print self.frame_num
        # print self.f_size

        self.frame_list = self.f_size[bitrate]  # a list that contains frames with different size
        # print(bitrate)
        # print(self.frame_list)

    def read_frame_data(self):
        """
        frame_buffer is not empty, pop all frame in buffer and return packet_list
        is empty, return None
        :return:
        """
        result_packets = []
        while len(self.frame_buffer) > 0:
            frame = self.frame_buffer.pop(0)
            # print('frame_size:', frame.frame_size)
            tmp_packets = frame.separate_frame_to_packet(self.udp_seq)
            for packet in tmp_packets:
                packet.codec_bitrate = frame.codec_bitrate
            self.udp_seq += len(tmp_packets)
            result_packets += tmp_packets
        # print len(result_packets)
        return result_packets

    def reset(self):
        self.i_frame = -1
        self.frame_buffer = []
        self.bitrate = 0.7

    def add_frame(self):
        """
        every read_frame_interval, add one frame
        :return:
        """
        if self.is_fix_frame_size:
            frame_size = self.fix_frame_size
        else:
            # get the frame size from the frame list (byte*8 -> bit)
            frame_size = self.frame_list[self.i_frame % self.frame_num] * 8
            # print(frame_size)

        # print frame_size
        frame_size *= 50  # enlarge 5 times
        # print frame_size
        # frame: id size
        frame = Frame(self.i_frame, frame_size)

        self.frame_queue.append(frame_size)  # the queue contains the size of frame
        if len(self.frame_queue) >= self.frame_queue_size:
            self.frame_queue.pop(0)

        frame.codec_bitrate = self.get_real_codec_bitrate()

        self.frame_buffer.append(frame)  # add one frame to frame_buffer
        # print frame.frame_size
        # print(len(self.frame_buffer))
        self.i_frame += 1

    def get_real_codec_bitrate(self):
        # print (sum(self.frame_queue))
        return sum(self.frame_queue)  # the sum of current queue, the queue contains the size of frame


if __name__ == '__main__':
    codec = VideoCodec()
    codec.choose_bps(15000000)
    codec.add_frame()

    frame_list = codec.read_frame_data()
