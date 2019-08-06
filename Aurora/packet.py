class Packet(object):

    def __init__(self):
        self.seq_num = 0
        self.send_time = 0  # send time
        self.recv_time = 0  # receive time
        self.payload = (1400 - 85) * '*'

        self.frame_id = 0
        self.frame_start_packet_seq = 0
        self.frame_end_packet_seq = 0

        self.codec_bitrate = 0
