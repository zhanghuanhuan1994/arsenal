# -*- coding: UTF-8 -*-
import numpy as np
import warnings
import tensorflow as tf
from rl.Congestion_controller.Model import a3c
import matplotlib.pyplot as plt
from rl.Congestion_controller.congestionController import CongestionController

warnings.filterwarnings("ignore")

S_INFO = 2  # 丢包 时延 时延间隔
S_LEN = 4  # take how many frames in the past
Input_LEN = 60  # 用来控制 RL 多少个包开始训练
S_NUMBER = 8  # 用来检索之前的值
A_DIM = 25  # RL 初始化的维度
ACTOR_LR_RATE = 0.0001  # RL 初始化
CRITIC_LR_RATE = 0.001  # RL 初始化

ACTION_BIT_RATE = np.arange(0.1, 5.1, 0.2)
ACTION_BIT_RATE = [round(c, 2) for c in ACTION_BIT_RATE]

DEFAULT_QUALITY = 1  # default video quality without agent，没有 agent 时的视频质量？？
RANDOM_SEED = 42  # 随机数种子
RAND_RANGE = 1000  # 随机数范围
# NN_MODEL = r'./Congestion_controller/model_RL_with_frame/nn_model_epoch_11.ckpt'

NN_MODEL = r'./Congestion_controller/model_RL_no_frame/nn_model_epoch_10.ckpt'


class RlCongestionController(CongestionController):
    count = 0
    if count == 0:
        sess = tf.Session()
        sess.__enter__()
        actor = a3c.ActorNetwork(sess,
                                 state_dim=[S_INFO, S_NUMBER, S_LEN], action_dim=A_DIM,
                                 learning_rate=ACTOR_LR_RATE)

        critic = a3c.CriticNetwork(sess,
                                   state_dim=[S_INFO, S_NUMBER, S_LEN],
                                   learning_rate=CRITIC_LR_RATE)

        np.random.seed(RANDOM_SEED)

        summary_ops, summary_vars = a3c.build_summaries()

        sess.run(tf.global_variables_initializer())
        saver = tf.train.Saver(max_to_keep=0)  # save neural net parameters

        # restore neural net parameters
        nn_model = NN_MODEL
        if nn_model is not None:  # nn_model is the path to file
            # print(NN_MODEL)
            saver.restore(sess, nn_model)
            print("Model restored.")

    def __init__(self):
        RlCongestionController.count += 1

        self.bit_rate = DEFAULT_QUALITY

        self.s_batch = [np.zeros((S_INFO, S_NUMBER, S_LEN))]
        self.entropy_record = []

        self.send_time_last_state = 0
        self.arrival_time_last_state = 0
        self.frame_time_windows = []

        self.delay_interval_windows = []
        self.loss_windows = []
        self.arrival_time_windows = []
        self.start_arrival_time = 0
        self.frame_inner_loss_count = []
        self.frame_inner_delay_interval_count = []
        self.payload_size_windows = []

        self.target_bitrate = 0.3
        self.start_bitrate_bps = 0.3
        self.estimate_bitrate = 0.3
        self.frame_inner_loss = []
        self.arrival_time = []
        self.frame_delay_interval = []
        self.delay_interval_windows = []
        self.start_arrival_time = 0
        self.target_send_rate = 0
        self.start_arrival_time = 0
        self.frame_counts_in_packet = 0
        self.last_estimate_bitrate = 0

        self.time = []
        self.rate = []
        self.loss = []
        self.delay = []
        self.bandwidth = []
        pass

    def estimate(self, feedback):
        if not feedback:
            self.target_bitrate = self.start_bitrate_bps
        else:
            self.target_bitrate = self.predict(feedback)
        self.time.append(feedback.arrival_time_ms[-1] / 1000.0)
        self.rate.append(self.target_bitrate)
        self.loss.extend(feedback.loss)
        self.delay.extend([feedback.arrival_time_ms[i] - feedback.send_time_ms[i]
                           for i in range(len(feedback.arrival_time_ms))])
        self.bandwidth.append(feedback.average_bandwidth)
        return self.target_bitrate

    def predict(self, feedbackPacket):
        loss = feedbackPacket.loss  # 临时
        send_time = feedbackPacket.send_time_ms  # 临时
        arrival_time = feedbackPacket.arrival_time_ms  # 临时
        payload_size = feedbackPacket.payload_size  # 临时
        frame_inner_loss = feedbackPacket.frame_inner_loss  # 临时
        frame_delay_interval = feedbackPacket.frame_delay_interval  # 临时

        delay_send = []
        delay_arrival = []
        delay_interval = []

        # >>>>>>>>>> start compute delay_interval, loss, payload_size
        delay_interval.append(
            (send_time[0] - self.send_time_last_state) - (arrival_time[0] - self.arrival_time_last_state))
        for i in range(1, S_LEN):
            delay_send.append(send_time[i] - send_time[i - 1])
            delay_arrival.append(arrival_time[i] - arrival_time[i - 1])
            delay_interval.append(delay_arrival[i - 1] - delay_send[i - 1])
        self.send_time_last_state = send_time[-1]
        self.arrival_time_last_state = arrival_time[-1]

        # if len(self.delay_interval_windows) >= Input_LEN:  # 用来控制从第Input_LEN个，启动RL开始训练

            # >>>>>>>>>> 从第 1 秒开始运行

        self.start_arrival_time = arrival_time[-1]

        # 检索之前的状态
        if len(self.s_batch) == 0:
            state = [np.zeros((S_INFO, S_NUMBER, S_LEN))]
        else:
            state = np.array(self.s_batch[-1], copy=True)

        state = np.roll(state, -1, axis=1)
        state[0, -1] = loss
        state[1, -1] = delay_interval

        action_prob = RlCongestionController.actor.predict(
            np.reshape(state, (1, S_INFO, S_NUMBER, S_LEN)))  # 输入给神经网络
        action_cumsum = np.cumsum(action_prob)
        self.bit_rate = (action_cumsum > np.random.randint(1, RAND_RANGE) / float(RAND_RANGE)).argmax()

        self.entropy_record.append(a3c.compute_entropy(action_prob[0]))
        if self.bit_rate > 24:
            self.bit_rate = 24
        if self.bit_rate < 0:
            self.bit_rate = 0
        self.estimate_bitrate = ACTION_BIT_RATE[self.bit_rate]  # 神经网络的输出:  ‘estimate_bitrate’

        self.frame_counts_in_packet = 0
        self.frame_inner_delay_interval_count = []
        self.frame_inner_loss_count = []
        self.payload_size_windows = []

        self.target_send_rate = self.estimate_bitrate * 1e6
        # self.last_estimate_bitrate = self.estimate_bitrate
        self.target_bitrate = self.target_send_rate
        return self.target_bitrate

    def __del__(self):
        """
        重写对象销毁方法
        :return:
        """
        RlCongestionController.count -= 1
        print("开始销毁 RL 对象")
        if RlCongestionController.count == 0:
            RlCongestionController.sess.__exit__(None, None, None)

    def plot_target_send_rate(self, ip):
        """
        用来绘制图像
        :return:
        """
        # print(self.time[-1])
        plt.figure()
        plt.suptitle(ip + ', avg_loss:' + str(round(np.mean(self.loss), 2)) + '%'
                     + ', delay:' + str(round(np.mean(self.delay), 2)) + 'ms'
                     )

        plt.subplot(511)
        # plt.plot(self.time, self.bandwidth)
        plt.plot(self.bandwidth)
        plt.ylabel('Bitrate (bps)')
        # plt.plot(self.time, self.rate[:-1])
        plt.plot(self.rate[:-1])
        plt.legend(['bandwidth', 'target send rate'])

        plt.subplot(512)
        plt.ylabel('Delay (ms)')
        plt.ylim((0, 200))
        plt.plot(self.delay)

        plt.subplot(513)
        plt.ylabel('Loss (%)')
        plt.plot(self.loss)

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
        plt.show()


if __name__ == '__main__':
    print('main')
    sess = tf.Session()
    sess.__enter__()
    actor = a3c.ActorNetwork(sess,
                             state_dim=[S_INFO, S_NUMBER, S_LEN], action_dim=A_DIM,
                             learning_rate=ACTOR_LR_RATE)

    critic = a3c.CriticNetwork(sess,
                               state_dim=[S_INFO, S_NUMBER, S_LEN],
                               learning_rate=CRITIC_LR_RATE)

    summary_ops, summary_vars = a3c.build_summaries()

    sess.run(tf.global_variables_initializer())
    saver = tf.train.Saver(max_to_keep=0)  # save neural net parameters

    # 重新保存模型数值
    nn_model = NN_MODEL
    if nn_model is not None:  # nn_model is the path to file
        saver.restore(sess, nn_model)
        print("Model restored.")
