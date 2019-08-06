import socket
import jsonpickle
import time
import sys
import os
from example.network_simulator.packet import Packet
import threading


class Receiver(object):
    dir = './'
    subdir = ''
    is_multi = False

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', 12000))
        # self.sock.bind(('127.0.0.1', 10100))
        self.sock.listen(3)

        sys.stderr.write("[receiver] pcc_vivace is listening!\n")
        sys.stderr.flush()

        self.conn, self.addr = self.sock.accept()
        # self.peer_addr = ('100.64.0.2', 11100)

        self.recvd = 0

        # the log file
        if Receiver.is_multi:
            self.log_path = os.path.join(Receiver.dir, 'log', Receiver.subdir, 'pcc_vivace_recv_multi.log')
            self.f = open(self.log_path, mode='w')
        else:
            self.log_path = os.path.join(Receiver.dir, 'log', Receiver.subdir, 'pcc_vivace_recv_single.log')
            self.f = open(self.log_path, mode='w')

    def get_throughput(self):
        while True:
            sys.stderr.write("receiver: " + str(self.recvd * 1500 * 8.0 / 1000000) + " mbps\n")
            self.recvd = 0
            sys.stderr.flush()
            time.sleep(1)

    def recv(self):
        self.sock.setblocking(True)
        total_data = ""

        thread = threading.Thread(target=self.get_throughput, args=())
        thread.setDaemon(True)
        thread.start()

        while True:
            data = self.conn.recv(1500)
            total_data += data

            if len(total_data) >= 1500:
                tmp_data = total_data[:1500]
                total_data = total_data[1500:]
                packet = jsonpickle.decode(tmp_data)
                self.recvd += 1
                packet.arrival_time_ms = int(time.time() * 1000)

                info = "seq:" + str(packet.seq) + " frame_id:" + str(packet.frame_id) + " send_ms:" + str(
                    int(packet.send_time_ms)) + " frame_start:" + str(
                    packet.frame_start_packet_seq) + " frame_end:" + str(
                    packet.frame_end_packet_seq) + " recv_time:" + str(
                    int(packet.arrival_time_ms)) + " delay:" + str(
                    packet.arrival_time_ms - packet.send_time_ms) + " codec_bitrate:" + str(
                    packet.codec_bitrate) + "\n"
                self.f.write(info)
                self.f.flush()
                # sys.stderr.write(info)
                # sys.stderr.flush()

    def run(self):
        self.recv()


def main(subdir=None, is_multi=False):
    Receiver.subdir = subdir
    Receiver.is_multi = is_multi
    receiver = Receiver()
    try:
        receiver.run()
    except Exception as e:
        print e.args


if __name__ == '__main__':
    pass
