# -*- coding: utf-8 -*-
from example.network_simulator.packet import Packet

try:
    import cPickle as pickle
except ImportError:
    import pickle


class Frame(object):
    def __init__(self, frame_id, frame_size):
        self.frameId = frame_id
        self.frame_size = frame_size
        self.packet_list = []
        self.loss = 0

    def separate_frame_to_packet(self, start_seq):
        packet_num = self.frame_size // Packet.max_payload_size
        packet_list = []
        seq = start_seq
        for i_packet in range(0, packet_num):
            packet = Packet(self.frameId, Packet.max_payload_size, seq)
            packet_list.append(packet)
            # print('seq:', seq)
            seq += 1

        if self.frame_size % Packet.max_payload_size != 0:
            packet = Packet(self.frameId, self.frame_size % Packet.max_payload_size, seq)
            # print('seq:', seq)
            packet_list.append(packet)

        end_seq = packet_list[-1].seq
        for packet in packet_list:
            packet.set_frame_packet_start_end(start_seq, end_seq)

        return packet_list

    def compute_loss(self):
        """
        use self.packet_list to compute out packet loss
        :return: self.loss
        """
        packet = self.packet_list[0]
        start_seq = packet.frame_start_packet_seq
        end_seq = packet.frame_end_packet_seq
        self.loss = 100 * (1 - float(len(self.packet_list)) / (end_seq - start_seq + 1))
        return self.loss


if __name__ == '__main__':
    pass
