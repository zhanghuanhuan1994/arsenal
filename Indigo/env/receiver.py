import sys
import json
import socket
import select
# import datagram_pb2
import os
import sys
import threading

sys.path.append("../../")
import data_pb2
from indigo.helpers.helpers import READ_FLAGS, ERR_FLAGS, READ_ERR_FLAGS, ALL_FLAGS, curr_ts_ms
import time


class Receiver(object):
    dir = './'
    subdir = ''

    is_multi = False

    def __init__(self, port):
        self.peer_addr = None

        # UDP socket and poller
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.sock.bind(('0.0.0.0', port))
        sys.stderr.write('[Receiver] Indigo Listening on port %s\n' %
                         self.sock.getsockname()[1])

        self.poller = select.poll()
        self.poller.register(self.sock, ALL_FLAGS)

        # multi flow
        if Receiver.is_multi:
            self.log_path = os.path.join(Receiver.dir, 'log', Receiver.subdir, 'indigo_recv_multi.log')
        # single flow
        else:
            self.log_path = os.path.join(Receiver.dir, 'log', Receiver.subdir, 'indigo_recv_single.log')

        self.f = open(self.log_path, mode='w')
        self.one_second_data = 0

    def cleanup(self):
        self.sock.close()

    def construct_ack_from_data(self, serialized_data):
        """Construct a serialized ACK that acks a serialized datagram."""

        # data = datagram_pb2.Data()
        data = data_pb2.Data()
        data.ParseFromString(serialized_data)

        recv_time = time.time()
        delay = 1000 * (recv_time - data.send_time)

        info = "seq:" + str(data.seq_num) + " frame_id:" + str(data.frame_id) + " send_ts:" + str(
            int(1000 * data.send_time)) + " frame_start:" + str(data.frame_start_packet_seq) + " frame_end:" + str(
            data.frame_end_packet_seq) + " recv_time:" + str(int(1000 * recv_time)) + " delay:" + str(
            delay) + " codec_bitrate:" + str(
            data.codec_bitrate) + "\n"

        self.f.write(info)
        self.f.flush()

        sys.stderr.write(info)

        ack = data_pb2.Ack()
        ack.seq_num = data.seq_num
        ack.send_ts = data.send_ts
        ack.sent_bytes = data.sent_bytes
        ack.delivered_time = data.delivered_time
        ack.delivered = data.delivered
        ack.ack_bytes = len(serialized_data)

        return ack.SerializeToString()

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
                sys.stderr.write('[Receiver] Handshake success! Indigo'
                                 'Sender\'s address is %s:%s\n' % addr)
                break

        self.sock.setblocking(False)  # non-blocking UDP socket

    def get_throughput(self):
        while (True):
            throughput_info = "indigo: " + str(self.one_second_data * 8.0 / 1000000.0) + " mbps\n"
            self.one_second_data = 0  # set 0
            sys.stderr.write(throughput_info)
            sys.stderr.flush()
            time.sleep(1)

    def run(self):
        self.sock.setblocking(True)  # blocking UDP socket
        # self.sock.settimeout(10)  # set the timeout seconds

        thread = threading.Thread(target=self.get_throughput)
        thread.setDaemon(True)
        # thread.start()

        while True:
            try:
                serialized_data, addr = self.sock.recvfrom(1600)
                if not thread.is_alive():
                    thread.start()
                # compute throughput
                self.one_second_data += len(serialized_data)
                if addr == self.peer_addr:
                    ack = self.construct_ack_from_data(serialized_data)
                    if ack is not None:
                        self.sock.sendto(ack, self.peer_addr)
            except socket.timeout:
                self.cleanup()
                self.f.flush()
                self.f.close()
                return
            except BaseException:
                self.cleanup()
                self.f.flush()
                self.f.close()
                return
