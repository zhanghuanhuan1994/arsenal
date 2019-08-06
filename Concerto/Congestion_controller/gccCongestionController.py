# -*- coding: UTF-8 -*-
from il.Congestion_controller.congestionController import CongestionController
from il.GCC_estimator.SendSideCongestionControl import SendSideCongestionController


import matplotlib.pyplot as plt
import numpy as np


class GccCongestionController(CongestionController):
    def __init__(self):
        start_bitrate_bps = 1000e3
        self.estimator = SendSideCongestionController()
        self.estimator.SetStartBitrate(start_bitrate_bps)
        self.bitrate_list = []
        self.rate, self.lbrates, self.dbrates, self.delay, self.loss, self.delay_diff, self.bandwidth = \
            [], [], [], [], [], [], []
        self.ts_delta, self.t_delta, self.trendline, self.mt, self.threashold = [], [], [], [], []
        self.time = []
        self.inuse = []

    def estimate(self, feedback):
        target_send_rate, lbrate, dbrate, ts_d, t_d, trendl, mtt, th = \
            self.estimator.OnRTCPFeedbackPacket(feedback)

        self.time.append(feedback.arrival_time_ms[-1] / 1000)
        self.delay.extend([feedback.arrival_time_ms[i] - feedback.send_time_ms[i]
                           for i in range(len(feedback.arrival_time_ms))])
        self.loss.extend(feedback.loss)
        self.bandwidth.append(feedback.average_bandwidth)
        self.rate.append(target_send_rate)
        self.dbrates.append(dbrate)
        self.lbrates.append(lbrate)
        self.ts_delta.extend(ts_d)
        self.t_delta.extend(t_d)
        self.trendline.extend(trendl)
        self.mt.extend(mtt)
        self.threashold.extend(th)
        return target_send_rate

    def plot_target_send_rate(self, ip):
        """
        用来绘制图像
        :return:
        """
        pass
        print(self.time[-1])
        plt.figure()
        plt.suptitle(ip + ', avg_loss:' + str(round(np.mean(self.loss), 2)) + '%'
                    + ', delay:' + str(round(np.mean(self.delay), 2)) + 'ms'
                     )

        plt.subplot(511)
        # plt.plot(self.time, self.bandwidth)
        plt.plot(self.bandwidth)
        plt.ylabel('Bitrate (bps)')
        # plt.plot(self.time, self.rate)
        plt.plot(self.rate)
        plt.legend(['bandwidth', 'target send rate'])

        plt.subplot(512)
        plt.ylabel('Delay (ms)')
        plt.ylim((0, 200))
        plt.plot(self.delay)

        plt.subplot(513)
        plt.ylabel('Loss (%)')
        plt.plot(self.loss)

        plt.subplot(514)
        plt.ylabel('Deltas(ms)')
        plt.plot(self.ts_delta)
        plt.plot(self.t_delta)
        plt.legend(['send deltas', 'arrival deltas'])

        plt.subplot(515)
        plt.ylabel('m(t)')
        plt.ylim((-10, 10))
        plt.plot(self.mt)
        plt.plot(self.threashold)
        plt.legend(['m(t)', 'threashold'])
        plt.show()
