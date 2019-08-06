class Ack(object):
    def __init__(self):
        self.seq_num = 0
        # the packet
        self.packet_send_time = 0
        self.packet_receive_time = 0
        # the ack
        self.ack_send_time = 0
        self.ack_receive_time = 0

        # self.payload = 1400 * '*'
