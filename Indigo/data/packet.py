# -*- coding: utf-8 -*-


class Packet(object):
    max_payload_size = 12000

    def __init__(self, frame_id, payload_size, udp_seq):

        self.seq = udp_seq
        self.frame_id = frame_id

        self.frame_start_packet_seq = 0  # start packet seq
        self.frame_end_packet_seq = 0    # end packet seq

        self.arrival_time_ms = 0
        self.send_time_ms = 0
        self.payload_size = payload_size
        self.bandwidth = 0

        self.payload = None

    def set_bandwidth(self, bandwidth):
        self.bandwidth = bandwidth

    def set_frame_packet_start_end(self, start_seq, end_seq):
        self.frame_start_packet_seq = start_seq
        self.frame_end_packet_seq = end_seq

    def add_delay(self, delta):
        self.arrival_time_ms += delta

    def to_string(self):
        return 'seq:' + str(self.seq) \
               + ',frame_id:' + str(self.frame_id) \
               + ',dealy:' + str(self.arrival_time_ms - self.arrival_time_ms) \
               + ',payload_size:' + str(self.payload_size)

    @classmethod
    def set_max_packet_size(cls, max_payload_size):
        Packet.max_payload_size = max_payload_size

