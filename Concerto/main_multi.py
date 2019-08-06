# -*- coding: UTF-8 -*-
import sys

sys.path.append('.')
sys.path.append('..')
print sys.path

from il.network_simulator.router import Router
from il.network_simulator import receiver, sender, packet
from il.network_simulator.router import TimeOutException
import matplotlib.pyplot as plt

LOSS_WINDOW = 10
ROUTER_BUFFER = 20
START_BITRATE_BPS = 8000E3

stop_time = 20 * 1000 * 60


class Link(object):
    def __init__(self, source_ip, destination_ip, congestion_controller_name):
        self.source_ip = source_ip
        self.destination_ip = destination_ip
        self.cc_name = congestion_controller_name


def create_links(link_list):
    """
    返回多条链接 links
    :return:
    """
    sender_map = dict()
    receiver_map = dict()
    for link in link_list:
        tmp_sender = sender.Sender(START_BITRATE_BPS, link.source_ip, link.destination_ip, link.cc_name)
        tmp_receiver = receiver.Receiver(link.destination_ip, buffer_size=LOSS_WINDOW, sender=tmp_sender)
        sender_map[link.source_ip] = tmp_sender
        receiver_map[link.destination_ip] = tmp_receiver
    return sender_map, receiver_map


def avg_10s(time, rate):
    """
    10s 平均一次
    :param time:
    :param rate:
    :return:
    """
    pre_idx = 0
    avg_rate = []
    pre_time = 0
    for idx in range(len(time)):
        if (time[idx] // 1) - pre_time == 4:
            rate_sum = sum(rate[pre_idx:idx])
            if idx != pre_idx:
                avg_rate.append(rate_sum / (idx - pre_idx))
            else:
                if len(avg_rate) > 0:
                    avg_rate.append(rate_sum[-1])
                else:
                    avg_rate.append(0)
            pre_idx = idx
            pre_time = time[idx] // 1
    return avg_rate


if __name__ == '__main__':
    # 添加了竞争流后，n 个流时，router 的带宽最好设置成 n M
    # 保存数据的环境如何，测试的环境也应该相同
    link_list = [
        # Link('192.168.1.1', '192.168.2.1', 'IL'),
        Link('192.168.1.2', '192.168.2.2', 'IL'),
        Link('192.168.1.3', '192.168.2.3', 'IL'),
        # Link('192.168.1.4', '192.168.2.4', 'RL'),
        # Link('192.168.1.5', '192.168.2.5', 'dagger_master'),
        # Link('192.168.1.6', '192.168.2.6', 'RL'),
        Link('192.168.1.7', '192.168.2.7', 'gcc_old'),
        # Link('192.168.1.8', '192.168.2.8', 'gcc_old'),
        # Link('192.168.1.9', '192.168.2.9', 'gcc_old'),
    ]

    sender_map, receiver_map = create_links(link_list)

    packet.Packet.set_max_packet_size(12000)  # bit

    router = Router(START_BITRATE_BPS)
    router.set_sender(sender_map)
    router.set_receiver(receiver_map)

    router.stop_time = stop_time

    try:
        router.start()
    except TimeOutException as e:
        print(e.atleast)
        print('router stop')
        fig = plt.figure()
        plt.suptitle("total bandwidth: 4 Mbps")
        ax = fig.add_subplot(1, 1, 1)
        ax.set_xlabel('time(s)')
        ax.set_ylabel('bitrate(bps)')
        title_name = []
        index = 1
        for s in sender_map.values():
            # p = Process(target=s.plot_result)
            # p.start()
            # s.plot_result()
            # pass
            # plt.plot()
            plt.plot(avg_10s(s.congestion_controller.time,
                             s.congestion_controller.rate[-len(s.congestion_controller.time):]))
            title_name.append("flow:" + str(index) + ":" + s.congestion_name)
            index += 1
        plt.legend(title_name)
        plt.show()
