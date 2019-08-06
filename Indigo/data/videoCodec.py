# -*- coding: UTF-8 -*-
from data.frame import Frame
import project_root
import os

try:
    import cPickle as pickle
except ImportError:
    import pickle


class VideoCodec(object):
    def __init__(self):
        self.f_id = []
        self.f_type = []
        self.f_size = []
        self.i_frame = -1
        self.is_fix_frame_size = False
        self.fix_frame_size = 200000  # when fixed, frame size is 200000 byte
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
        bitrate //= 1e5
        bitrate /= 10.0
        if self.i_frame == -1:
            file_path = os.path.join(project_root.DIR, 'data', 'videoFrame', 'frame_size.pk')
            f_f_size = open(file_path, "rb")

            self.f_size = pickle.load(f_f_size)  # f_size is a dict

            # for key, value in self.f_size.items():
            #     print(key, value)

            self.frame_num = len(self.f_size[self.bitrate])  # the length of frame in current bit rate
            f_f_size.close()
            self.i_frame += 1
        bitrate = min(bitrate, self.max_bitrate)
        bitrate = max(bitrate, self.min_bitrate)
        self.bitrate = bitrate
        self.frame_list = self.f_size[bitrate]  # a list that contains frames with different size
        # print(bitrate)

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
        return sum(self.frame_queue)  # the sum of current queue, the queue contains the size of frame


if __name__ == '__main__':
    codec = VideoCodec()
    codec.choose_bps(1000000)
    codec.add_frame()
    codec.read_frame_data()
