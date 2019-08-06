import inspect
import os
import numpy as np
import random
import sys
import loaded_agent
import loaded_client

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
grandparentdir = os.path.dirname(parentdir)
sys.path.insert(0, parentdir)
sys.path.insert(0, grandparentdir)
# from common import sender_obs
# from common.simple_arg_parse import arg_or_default


MIN_RATE = 0.5
MAX_RATE = 300.0
DELTA_SCALE = 0.05

RESET_RATE_MIN = 5.0
RESET_RATE_MAX = 100.0


def cal(num):
    print(num[0])
    print(num[1])


def update_array(arr, temp):
    for i in range(9):
        arr[i] = arr[i + 1]
    arr[9] = temp
    return arr


def cal_latency_increase(rtt):
    half = int(len(rtt) / 2)
    return np.mean(rtt[half:]) - np.mean(rtt[:half])


if __name__ == "__main__":
    print("main")

    agent = loaded_agent.LoadedModelAgent("./model_A")
    history = []
    history_length = 10
    for i in range(2):

        latency_inflation = [-0.0020467637406302763, 6.197045148749663e-05, 0.003443366368505903, -0.005570727876581319,
                             -0.005922674628630597,
                             0.007535832071585812, 0.002841173847234403, -0.00603276793107062, 0.0017493162988263334,
                             -6.534271457983947e-05]
        latency_ratio = [1.0012232099309957, 1.0008362821146977, 1.0053358050441012, 1.0014844206291296,
                         1.0008171670290928,
                         1.0023694237441163, 1.0018225871179531, 1.0028103784660207, 1.0044347517095558,
                         1.0022336190687209]
        send_ratio = [1.076923076923077, 1.0714285714285714, 1.0769230769230769, 1.0714285714285714, 1.0,
                      1.153846153846154,
                      1.0769230769230769, 1.0714285714285714, 1.076923076923077, 1.0714285714285714]
        if i == 1:
            latency_inflation = [6.197045148749663e-05, 0.003443366368505903, -0.005570727876581319,
                                 -0.005922674628630597,
                                 0.007535832071585812, 0.002841173847234403, -0.00603276793107062,
                                 0.0017493162988263334, -6.534271457983947e-05, 6.197045148749663e-05]
            latency_ratio = [1.0008362821146977, 1.0053358050441012, 1.0014844206291296,
                             1.0008171670290928,
                             1.0023694237441163, 1.0018225871179531, 1.0028103784660207, 1.0044347517095558,
                             1.0022336190687209, 1.0022336190687209]
            send_ratio = [1.0714285714285714, 1.0769230769230769, 1.0714285714285714, 1.0,
                          1.153846153846154,
                          1.0769230769230769, 1.0714285714285714, 1.076923076923077, 1.07142857142857141,
                          1.07142857142857141]
        # latency_inflation = [2,3,4,5.6,6.7,9.3,86,100,142,183]
        # latency_ratio = [2,3,9,52,11,39,81,15,30,72]
        # send_ratio = [1,2,3,14,25,36,47,58,69,110]

        history = []
        for i in range(10):
            array = [latency_inflation[i], latency_ratio[i], send_ratio[i]]
            history.append(array)

        history = np.array(history).flatten()
        print history
        # print(history.reshape(1,-1))
        rate_delta = agent.act(history)
        print(rate_delta)
        print("main end")
