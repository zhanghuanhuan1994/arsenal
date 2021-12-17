#!/usr/bin/env python

import sys
import argparse
import project_root
import numpy as np
import tensorflow as tf
from os import path

sys.path.append('../../')

from indigo.env.sender import Sender
from models import DaggerLSTM
from indigo.helpers.helpers import normalize, one_hot, softmax

from helpers import (DONE, RUN, STOP)


class Learner(object):
    def __init__(self, state_dim, action_cnt, restore_vars):
        self.aug_state_dim = state_dim + action_cnt
        self.action_cnt = action_cnt
        self.prev_action = action_cnt - 1

        with tf.variable_scope('global'):
            self.model = DaggerLSTM(
                state_dim=self.aug_state_dim, action_cnt=action_cnt)

        self.lstm_state = self.model.zero_init_state(1)

        self.sess = tf.Session()

        # restore saved variables
        saver = tf.train.Saver(self.model.trainable_vars)
        saver.restore(self.sess, restore_vars)

        # init the remaining vars, especially those created by optimizer
        uninit_vars = set(tf.global_variables())
        uninit_vars -= set(self.model.trainable_vars)
        self.sess.run(tf.variables_initializer(uninit_vars))

    def sample_action(self, state):
        norm_state = normalize(state)

        one_hot_action = one_hot(self.prev_action, self.action_cnt)
        aug_state = norm_state + one_hot_action

        # Get probability of each action from the local network.
        pi = self.model
        feed_dict = {
            pi.input: [[aug_state]],
            pi.state_in: self.lstm_state,
        }
        ops_to_run = [pi.action_probs, pi.state_out]
        action_probs, self.lstm_state = self.sess.run(ops_to_run, feed_dict)

        # Choose an action to take
        action = np.argmax(action_probs[0][0])
        self.prev_action = action

        # action = np.argmax(np.random.multinomial(1, action_probs[0] - 1e-5))
        # temperature = 1.0
        # temp_probs = softmax(action_probs[0] / temperature)
        # action = np.argmax(np.random.multinomial(1, temp_probs - 1e-5))
        return action


def main(pipe=None, subdir=None, with_frame=True, is_multi=False, ):
    ip = '100.64.0.1'
    port = 8877

    Sender.with_frame = True
    Sender.subdir = subdir
    Sender.with_frame = with_frame
    Sender.is_multi = is_multi

    sender = Sender(ip, port)

    model_path = path.join(project_root.DIR, 'dagger', 'model', 'model')

    learner = Learner(
        state_dim=Sender.state_dim,
        action_cnt=Sender.action_cnt,
        restore_vars=model_path)

    sender.set_sample_action(learner.sample_action)

    try:
        sys.stderr.write("[sender] indigo begin handshake\n")
        sys.stderr.flush()

        sender.handshake()

        sys.stderr.write("[sender] indigo handshake done\n")
        sys.stderr.flush()

        # send handshake done and run
        pipe.send(DONE)
        while True:
            if pipe.recv() == RUN:
                break

        sender.run_1()  # modify here
        sys.stderr.write("[sender] indigo running\n")
        sys.stderr.flush()

        # stop the process
        while True:
            if pipe.recv() == STOP:
                sender.f.flush()
                sender.f.close()
                sender.cleanup()
                break


    except BaseException as e:
        sys.stderr.write("[sender]indigo exception\n")
        sys.stderr.flush()
        print e.args


if __name__ == '__main__':
    main()
