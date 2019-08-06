# -*- coding: UTF-8 -*-
from il.Congestion_controller.daggerMasterController import DaggerMasterController, \
    S_LEN, INPUT_LEN

import tensorflow as tf
import os
import sys
import numpy as np
import il.Congestion_controller.Model.NN_3_state as NN

import il.network_simulator.project_root as project_root

CLASS_NUM = 50  # 26->50
# 替代 data_len
ROW_DATA_LEN = INPUT_LEN * (S_LEN * 2 + 1)
# 向前看的时间段 替代 length
# 用旧模型的时候，使用 10
# 用新模型的时候，使用 1
FORWARD_TIME_LEN = 1


def accCNN(logits):
    index = tf.cast(tf.argmax(logits, 1), tf.int32)
    # print(index)
    return index[0]


def init_nn():
    logits, x, _ = NN.Network_Conv(S_LEN, INPUT_LEN, FORWARD_TIME_LEN, CLASS_NUM)
    index = accCNN(logits)
    saver = tf.train.Saver()
    return logits, index, saver, x


def run_nn(sess, saver):
    init = tf.global_variables_initializer()
    sess.run(init)

    model_path = os.path.join(project_root.DIR, 'Congestion_controller', 'model_IL_with_frame', 'checkpoint')
    model_name = os.path.join(project_root.DIR, 'Congestion_controller', 'model_IL_with_frame', 'model.ckpt-49')

    if os.path.exists(model_path):
        saver.restore(sess, model_name)
    else:
        raise IOError("""Network simulator can't find MODEL""")
    return sess


class DaggerCongestionController(DaggerMasterController):
    bitrate_lst = [n for n in range(0, 51)]  # 26->51
    bitrate_lst[0] = 0.1
    bitrate_lst = list(map(lambda i: round(i * 0.1, 2), bitrate_lst))

    # 初始化神经网络
    logits, index, saver, x = init_nn()
    sess = tf.Session()
    sess.__enter__()
    sess = run_nn(sess, saver)

    count = 0
    print "### dagger with frame"

    def __init__(self):
        DaggerCongestionController.count += 1  # 引用计数法

        super(DaggerCongestionController, self).__init__()
        self.target_bitrate = 1e6
        # 神经网络输入，长度为 FORWARD_TIME_LEN * ROW_DATA_LEN 的队列，每次来值
        self.save_data = np.zeros((FORWARD_TIME_LEN, ROW_DATA_LEN))  # fill data+real data

        self.save_data_one = np.zeros((1, ROW_DATA_LEN))
        print("sess inited")

    def estimate(self, feedback):
        """
        重写父类方法，使用神经网络预测
        :param feedback:
        :return:
        """
        if not feedback:
            self.target_bitrate = self.start_bitrate_bps
            return self.start_bitrate_bps
        self.predict(feedback)
        self.time.append(feedback.arrival_time_ms[-1] / 1000.0)
        self.rate.append(self.target_bitrate)
        self.loss.extend(feedback.loss)
        self.delay.extend([feedback.arrival_time_ms[i] - feedback.send_time_ms[i]
                           for i in range(len(feedback.arrival_time_ms))])
        self.bandwidth.append(feedback.average_bandwidth)
        # print(self.target_bitrate)
        # print("this is estimate function", self.target_bitrate)
        return self.target_bitrate

    def predict(self, feedbackPacket):
        loss = feedbackPacket.loss[:S_LEN]  # 1
        # print('loss:' + str(loss))

        now_time = (feedbackPacket.arrival_time_ms[-1] - 4) // 1000

        # 如果发送时间是 0 ，那么初始化这些列表
        if self.send_time_last_state == 0:
            self.start_time = now_time

        delay_interval = self.compute_delay_interval(feedbackPacket)
        # print('delay_interval:' + str(delay_interval))
        throughput = self.compute_throught(feedbackPacket)

        # print("now time and start time",now_time, self.start_time)

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
            self.save_data_one[0, 0:INPUT_LEN * S_LEN] = self.save_loss_windows.reshape(-1)
            self.save_data_one[0, INPUT_LEN * S_LEN: INPUT_LEN * S_LEN * 2] = self.save_delay_interval_windows.reshape(
                -1)
            self.save_data_one[0,
            INPUT_LEN * S_LEN * 2:INPUT_LEN * (S_LEN * 2 + 1)] = self.save_throughput_windows.reshape(-1)
            self.save_data[0:-1, :] = self.save_data[1:FORWARD_TIME_LEN, :]
            self.save_data[-1, :] = self.save_data_one[0, :]

            x_train = self.save_data  # test
            # for row in x_train:
            #     print(row)
            # print("######")
            # print(DaggerCongestionController.index)
            # print(type(DaggerCongestionController.index))
            predicte = DaggerCongestionController.index.eval(session=DaggerCongestionController.sess, feed_dict={
                DaggerCongestionController.x: x_train[np.newaxis, :, :]})
            # print("this is predic", predicte)
            self.target_bitrate = DaggerCongestionController.bitrate_lst[predicte] * 1e6

            self.start_time = now_time
            self.loss_windows = []
            self.throughput_windows = []
            self.delay_interval_windows = []

            self.count = self.count + 1

        self.loss_windows.append(loss)  # 1  append
        self.delay_interval_windows.append(delay_interval)  # 2 append
        self.throughput_windows.append(throughput)  # 3 append
        # print self.target_bitrate
        return self.target_bitrate

    def __del__(self):
        """
        重写对象销毁方法
        :return:
        """
        DaggerCongestionController.count -= 1
        print("开始销毁 dagger 对象")
        if DaggerCongestionController.count == 0:
            DaggerCongestionController.sess.__exit__(None, None, None)

    def plot_target_send_rate(self, ip):
        super(DaggerCongestionController, self).plot_target_send_rate(ip)
