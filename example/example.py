import time

from example.network_simulator.packet import Packet
from example.network_simulator.videoCodec import VideoCodec


class Example_sender(object):
    with_frame = False

    def __init__(self, bitrate=0.0):
        self.codec = VideoCodec()
        # set frame size fixed
        if not Example_sender.with_frame:
            self.codec.is_fix_frame_size = True

        # update the rate the codec choose
        self.set_bitrate(bitrate)
        self.rate = 0.0

        self.buffer = []
        self.read_frame_interval = 33  # ms
        self.last_read_frame_time = 0

        self.inuse_bitrate = 0
        self.last_set_bitrate_time = 0
        self.set_bitrate_interval = 1000  # ms

        self.cwnd = 10

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

    def send_data(self):
        packet = Packet()
        pass

    def read_frame_info(self):
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

        while True:
            # with video frame
            if Example_sender.with_frame:
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

                if self.buffer and len(self.buffer) != 0:
                    self.send_data()
            # without frame
            else:
                # the buffer is empty
                if not self.buffer or len(self.buffer) == 0:
                    self.codec.add_frame()
                    new_frame_packet_list = self.codec.read_frame_data()
                    self.buffer += new_frame_packet_list
                self.set_bitrate(self.rate)
                self.send_data()

    def recv(self, ack):
        rtt = time.time() * 1000 - ack.packet_send_time  # ms
        rtt /= 1000.0  # second
        new_bitrate = self.cwnd * 1500 * 8.0 / rtt  # bps
        self.set_bitrate(new_bitrate)
