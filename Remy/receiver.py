#!/usr/bin/env python

import os
import sys
import socket
import select
import argparse
import time
import threading

import jsonpickle
from ack import Ack

sys.path.append('..')
sys.path.append('.')

from indigo.helpers.helpers import ALL_FLAGS


class Receiver(object):
    dir = './'
    subdir = ''
    is_multi = False

    def __init__(self, port=0):
        # UDP socket and poller
        self.peer_addr = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', port))
        sys.stderr.write('[Receiver] RemyCC Listening on port %s\n' %
                         self.sock.getsockname()[1])

        self.poller = select.poll()
        self.poller.register(self.sock, ALL_FLAGS)

        if Receiver.is_multi:
            self.log_path = os.path.join(Receiver.dir, 'log', Receiver.subdir, 'RemyCC_recv_multi.log')
            self.f = open(self.log_path, mode='w')
        else:
            self.log_path = os.path.join(Receiver.dir, 'log', Receiver.subdir, 'RemyCC_recv_single.log')
            self.f = open(self.log_path, mode='w')

        self.received = 0

    def cleanup(self):
        self.sock.close()

    def handshake(self):
        """Handshake with peer receiver. Must be called before run()."""

        while True:
            msg, addr = self.sock.recvfrom(1600)

            '''
            handshake successfully
            end the while and set the peer_addr
            '''
            if msg == str.encode('Hello from receiver') and self.peer_addr is None:
                self.peer_addr = addr
                self.sock.sendto(str.encode('Hello from sender'), self.peer_addr)
                sys.stderr.write('[Receiver] Handshake success! RemyCC'
                                 'Sender\'s address is %s:%s\n' % addr)
                break

    def get_throughput(self):
        while True:
            sys.stderr.write("RemyCC receiver: " + str(self.received * 1500 * 8.0 / 1000000) + " mbps\n")
            sys.stderr.flush()
            self.received = 0
            time.sleep(1)  # second

    def run(self):
        self.sock.setblocking(True)

        thread = threading.Thread(target=self.get_throughput, args=())
        thread.setDaemon(True)

        while True:
            serialized_data, addr = self.sock.recvfrom(1600)

            try:
                packet = jsonpickle.decode(serialized_data)
            except BaseException as e:
                print e
                continue
            if not thread.is_alive():
                thread.start()

            if addr == self.peer_addr:

                
                packet.recv_time = time.time() * 1000

                self.received += 1

                info = "seq:" + str(packet.seq_num) + " frame_id:" + str(packet.frame_id) + " send_ms:" + str(
                    int(packet.send_time)) + " frame_start:" + str(
                    packet.frame_start_packet_seq) + " frame_end:" + str(
                    packet.frame_end_packet_seq) + " recv_time:" + str(
                    int(packet.recv_time)) + " delay:" + str(
                    packet.recv_time - packet.send_time) + " codec_bitrate:" + str(
                    packet.codec_bitrate) + "\n"

                self.f.write(info)
                self.f.flush()

                try:
                    ack = Ack()
                    ack.packet_send_time = packet.send_time
                    ack.packet_receive_time = packet.recv_time
                    ack.ack_send_time = time.time() * 1000
                    ack.seq_num = packet.seq_num

                    serialized_ack = jsonpickle.encode(ack)

                    self.sock.sendto(serialized_ack, self.peer_addr)
                except BaseException as e:
                    sys.stderr.write("[Receiver] RemyCC exception\n")
                    sys.stderr.flush()
                    print e.args


def main(subdir=None, is_multi=False):
    port = 9876

    Receiver.subdir = subdir
    Receiver.is_multi = is_multi
    receiver = Receiver(port)

    try:
        receiver.handshake()
        receiver.run()
    except BaseException as e:
        sys.stderr.write("[Receiver] Remy Exception\n")
        sys.stderr.flush()
        print e.args
    finally:
        receiver.sock.close()
        receiver.f.flush()
        receiver.f.close()


if __name__ == '__main__':
    main()
