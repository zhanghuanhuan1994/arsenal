# -*- coding: UTF-8 -*-
from il.Congestion_controller.congestionController import CongestionController
# import matplotlib.pyplot as plt
import numpy as np
import datetime
# from main_multi import stop_time
stop_time = 10000000

S_LEN = 4
INPUT_LEN = 15
ROW_DATA_LEN = INPUT_LEN * (S_LEN * 2 + 1)

FLOOR_BITRATE_M = 0.01
CEIL_BITRATE_M = 2.5


def rectificate_bitrate(bitrate):
        """
        矫正速率
        :param bitrate:
        :return:
        """
        bitrate = bitrate // 1e5 * 0.1
        bitrate = min(CEIL_BITRATE_M, bitrate)
        bitrate = max(FLOOR_BITRATE_M, bitrate)
        return bitrate


class DaggerMasterController(CongestionController):
    """
    收集数据
    """

    def __init__(self):
        self.start_bitrate_bps = 1e6
        self.rate, self.lbrates, self.dbrates, self.delay, self.loss, self.delay_diff, self.bandwidth = \
            [], [], [], [], [], [], []
        self.ts_delta, self.t_delta, self.trendline, self.mt, self.threashold = [], [], [], [], []
        self.time = []
        self.inuse = []
        self.rate.append(self.start_bitrate_bps)

        # mz
        # 获取当前时间
        self.start_time = datetime.datetime.now()

        # 初始化
        # 保存路径
        self.save_path = './data_ver/D.npy'

        # 初始配置
        self.start_bitrate = 0.7  # 初始速率
        # self.codec_bitrate = 0  # 初始编码速率
        self.send_time_last_state = 0  # 上一次发送时间的状态
        self.arrival_time_last_state = 0  # 达到发送时间的状态
        self.start_arrival_time = 0  # 开始到达的时间

        self.count = 0  # 计数
        # 三输入的数组维度为  1 X (INPUT_LEN * (S_LEN * 2 + 1) + 1)
        raw = INPUT_LEN * (S_LEN * 2 + 1) + 1
        self.save_data_one = np.zeros((1, raw))  # len+1  初始化 save_data_one 数组维度为

        # 数组维度为 (stop_time // 1000) X (INPUT_LEN * (S_LEN))
        self.save_data = np.zeros((stop_time // 1000, raw))  # len+1

        # 丢包窗口 (INPUT_LEN X SLEN)
        self.save_loss_windows = np.zeros((INPUT_LEN, S_LEN))
        # 吞吐量窗口   INPUT_LEN X 1
        self.save_throughput_windows = np.zeros((INPUT_LEN, 1))
        # 延迟窗口      INPUT_LEN X S_LEN
        self.save_delay_interval_windows = np.zeros((INPUT_LEN, S_LEN))

        self.start_time = 0
        self.bitrate_lable = self.start_bitrate
        self.loss_windows = []
        self.throughput_windows = []
        self.delay_interval_windows = []

    def estimate(self, feedback):
        if not feedback:
            return self.start_bitrate_bps
        target_bitrate = feedback.bandwidth[-1]

        self.time.append(feedback.arrival_time_ms[-1] / 1000.0)
        self.rate.append(target_bitrate)
        self.loss.extend(feedback.loss)
        self.delay.extend([feedback.arrival_time_ms[i] - feedback.send_time_ms[i]
                           for i in range(len(feedback.arrival_time_ms))])
        self.bandwidth.append(feedback.average_bandwidth)
        self.save_master_data(feedback)
        return target_bitrate

    def compute_throught(self, feedbackPacket):
        """
        计算吞吐量
        :param feedbackPacket:
        :return:
        """
        arrival_time = feedbackPacket.arrival_time_ms
        payload_size = feedbackPacket.payload_size
        # 计算吞吐量
        intervals = arrival_time[-1] - self.start_arrival_time
        throughput = np.sum(payload_size) / intervals / 1000.0
        self.start_arrival_time = arrival_time[-1]
        return throughput

    def compute_delay_interval(self, feedbackPacket):
        """
        计算时延
        :param feedbackPacket:
        :return:
        """
        send_time = feedbackPacket.send_time_ms
        arrival_time = feedbackPacket.arrival_time_ms

        # 需要计算时延，这些是输出
        delay_send = []
        delay_arrival = []
        delay_interval = []

        # 初始时间间隔
        # delay_interval.append(
        #     (send_time[0] - self.send_time_last_state) - (arrival_time[0] - self.arrival_time_last_state))
        delay_interval.append((arrival_time[0] - self.arrival_time_last_state) -(send_time[0] -
                                                                                 self.send_time_last_state))

        # 计算时间间隔
        for i in range(1, S_LEN):
            delay_send.append(send_time[i] - send_time[i - 1])
            delay_arrival.append(arrival_time[i] - arrival_time[i - 1])
            delay_interval.append(delay_arrival[i - 1] - delay_send[i - 1])  # 2

        self.send_time_last_state = send_time[-1]
        self.arrival_time_last_state = arrival_time[-1]
        # print(self.send_time_last_state)
        # print(self.arrival_time_last_state)
        return delay_interval

    def save_master_data(self, feedbackPacket):
        """
        保存数据
        :param feedbackPacket:
        :return:
        """
        self.bitrate_lable = feedbackPacket.average_bandwidth // 1e6  # M

        loss = feedbackPacket.loss[:S_LEN]  # 1
        now_time = (feedbackPacket.arrival_time_ms[-1] - 4) // 1000

        # 如果发送时间是 0 ，那么初始化这些列表
        if self.send_time_last_state == 0:
            self.start_time = now_time

        delay_interval = self.compute_delay_interval(feedbackPacket)
        throughput = self.compute_throught(feedbackPacket)

        # 保存
        if now_time != self.start_time:
            np_loss_windows = np.array(self.loss_windows)
            np_throughput_windows = np.array(self.throughput_windows)
            np_throughput_windows = np_throughput_windows[:, np.newaxis]
            np_delay_interval_windows = np.array(self.delay_interval_windows)

            #  如果累计的值达到 INPUT_LEN，开始
            #  shape[0] 存放了数组的一维大小
            if np_delay_interval_windows.shape[0] >= INPUT_LEN:
                self.save_delay_interval_windows = np_delay_interval_windows[-INPUT_LEN:, :]
                self.save_throughput_windows = np_throughput_windows[-INPUT_LEN:, :]
                self.save_loss_windows = np_loss_windows[-INPUT_LEN:, :]
            else:
                # row_stack() 列数不变，合并
                self.save_loss_windows = np.row_stack(
                    (self.save_loss_windows[-(INPUT_LEN - np_delay_interval_windows.shape[0]):, :], np_loss_windows))
                self.save_throughput_windows = np.row_stack((self.save_throughput_windows[
                                                             -(INPUT_LEN - np_delay_interval_windows.shape[0]):, :],
                                                             np_throughput_windows))
                self.save_delay_interval_windows = np.row_stack((self.save_delay_interval_windows[
                                                                 -(INPUT_LEN - np_delay_interval_windows.shape[0]):, :],
                                                                 np_delay_interval_windows))

            # print(self.bitrate_lable)
            # 保存一行
            self.save_one_row()

            self.start_time = now_time
            self.loss_windows = []
            self.throughput_windows = []
            self.delay_interval_windows = []

            self.count = self.count + 1

            # 每过一段时间缓存或者是快到达临界值的时候
            if now_time % 3600 == 0 or stop_time // 1000 - now_time < 5:
                print(stop_time // 1000 - now_time)
                print(self.save_data[0:self.count, :].shape)
                np.save(self.save_path, self.save_data[0:self.count, :])

        self.loss_windows.append(loss)  # 1  append
        self.delay_interval_windows.append(delay_interval)  # 2 append
        self.throughput_windows.append(throughput)  # 3 append

    def save_one_row(self):
        """
        保存一行数据，[loss, delay, throughput, bitrate_label]
        :return:
        """
        # reshape(-1) 将二维数组展开成一维数组
        self.save_data_one[0, 0:INPUT_LEN * S_LEN] = self.save_loss_windows.reshape(-1)
        self.save_data_one[0, INPUT_LEN * S_LEN:INPUT_LEN * S_LEN * 2] = self.save_delay_interval_windows.reshape(
            -1)
        self.save_data_one[0,
        INPUT_LEN * S_LEN * 2:INPUT_LEN * (S_LEN * 2 + 1)] = self.save_throughput_windows.reshape(-1)
        self.save_data_one[0, -1] = self.bitrate_lable
        self.save_data[self.count, :] = self.save_data_one

    def plot_target_send_rate(self, ip):
        """
        用来绘制图像
        :return:
        """
        pass
        # print(self.time[-1])
        # plt.figure()
        # plt.suptitle(ip + ', avg_loss:' + str(round(np.mean(self.loss), 2)) + '%'
        #              + ', delay:' + str(round(np.mean(self.delay), 2)) + 'ms'
        #              )
        #
        # plt.subplot(511)
        # # plt.plot(self.time, self.bandwidth)
        # plt.plot(self.bandwidth)
        # plt.ylabel('Bitrate (bps)')
        # # plt.plot(self.time, self.rate[:-1])
        # plt.plot(self.rate[:-1])
        # plt.legend(['bandwidth', 'target send rate'])
        #
        # plt.subplot(512)
        # plt.ylabel('Delay (ms)')
        # plt.ylim((0, 200))
        # plt.plot(self.delay)
        #
        # plt.subplot(513)
        # plt.ylabel('Loss (%)')
        # plt.plot(self.loss)
        #
        # plt.subplot(514)
        # plt.ylabel('Deltas(ms)')
        # plt.plot(self.ts_delta)
        # plt.plot(self.t_delta)
        # plt.legend(['send deltas', 'arrival deltas'])
        #
        # plt.subplot(515)
        # plt.ylabel('m(t)')
        # plt.ylim((-10, 10))
        # plt.plot(self.mt)
        # plt.plot(self.threashold)
        # plt.legend(['m(t)', 'threashold'])
        # plt.show()
