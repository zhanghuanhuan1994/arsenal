#coding=utf-8

import numpy as np
import tensorflow as tf
import tflearn


GAMMA = 0.99
ENTROPY_WEIGHT = 0.5
ENTROPY_EPS = 1e-6
# S_INFO = 2  # bit_rate, buffer_size, next_chunk_size, bandwidth_measurement(throughput and time), chunk_til_video_end
# S_LEN = 10  # take how many frames in the past


class ActorNetwork(object):
    """
    Input to the network is the state, output is the distribution
    of all actions.
    """
    def __init__(self, sess, state_dim, action_dim, learning_rate):
        self.sess = sess
        self.s_dim = state_dim
        self.a_dim = action_dim
        self.lr_rate = learning_rate

        # Create the actor network
        self.inputs, self.out = self.create_actor_network()

        # Get all network parameters
        self.network_params = \
            tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope='actor')

        # Set all network parameters
        self.input_network_params = []
        for param in self.network_params:
            self.input_network_params.append(
                tf.placeholder(tf.float32, shape=param.get_shape()))
        self.set_network_params_op = []
        for idx, param in enumerate(self.input_network_params):
            self.set_network_params_op.append(self.network_params[idx].assign(param))

        # Selected action, 0-1 vector
        self.acts = tf.placeholder(tf.float32, [None, self.a_dim])

        # This gradient will be provided by the critic network
        self.act_grad_weights = tf.placeholder(tf.float32, [None, 1])

        # Compute the objective (log action_vector and entropy)
        self.obj = tf.reduce_sum(tf.multiply(
                       tf.log(tf.reduce_sum(tf.multiply(self.out, self.acts),
                                            reduction_indices=1, keep_dims=True)),
                       -self.act_grad_weights)) \
                   + ENTROPY_WEIGHT * tf.reduce_sum(tf.multiply(self.out,
                                                           tf.log(self.out + ENTROPY_EPS)))

        # Combine the gradients here
        self.actor_gradients = tf.gradients(self.obj, self.network_params)
        # # Optimization Op
        # with tf.variable_scope(tf.get_variable_scope(), reuse= tf.AUTO_REUSE):
        #     self.optimize = tf.train.RMSPropOptimizer(self.lr_rate).\
        #         apply_gradients(zip(self.actor_gradients, self.network_params))
        # # Optimization Op
        with tf.variable_scope(tf.get_variable_scope()):
            self.optimize = tf.train.RMSPropOptimizer(self.lr_rate).\
                apply_gradients(zip(self.actor_gradients, self.network_params))

    def create_actor_network(self,reuse = True):
        with tf.variable_scope('actor'):
            inputs = tflearn.input_data(shape=[None, self.s_dim[0], self.s_dim[1],self.s_dim[2]])     # input layer
            print 'self.s_dim[0]',self.s_dim[0]
            # split_0 = tflearn.fully_connected(inputs[:, 0:1, -1], 128, activation='relu', reuse=tf.AUTO_REUSE, scope = 'critic_fc1')
            print 'inputs[:, 0:1, :].shape:', inputs[:, 0:1, :].shape
            print 'inputs[:, 1:2, :].shape:', inputs[:, 1:2, :].shape
            x_reshape1 = tflearn.reshape(inputs[:, 0:1, :], [-1, self.s_dim[1],self.s_dim[2],1])
            x_reshape2 = tflearn.reshape(inputs[:, 1:2, :], [-1, self.s_dim[1],self.s_dim[2],1])
            # split_0 = tflearn.fully_connected(inputs[:, 0:1, :], 128, activation='relu', reuse=tf.AUTO_REUSE, scope = 'fc1')
            split_1 = tflearn.conv_2d(x_reshape1, 128, 4, activation='relu', scope = 'conv1_1')
            split_2 = tflearn.conv_2d(x_reshape2, 128, 4, activation='relu', scope = 'conv1_2')

            # split_2 = tflearn.fully_connected(inputs[:, 1:2, -1], 128, activation='relu', reuse=tf.AUTO_REUSE, scope = 'fc2')

            split_1_flat = tflearn.flatten(split_1)
            split_2_flat = tflearn.flatten(split_2)

            merge_net = tflearn.merge([split_1_flat, split_2_flat], 'concat')

            dense_net_0 = tflearn.fully_connected(merge_net, 128, activation='relu', scope = 'fc3')
            out = tflearn.fully_connected(dense_net_0, self.a_dim, activation='softmax', scope = 'fc4')     # output layer

            return inputs, out

    def train(self, inputs, acts, act_grad_weights):

        self.sess.run(self.optimize, feed_dict={
            self.inputs: inputs,
            self.acts: acts,
            self.act_grad_weights: act_grad_weights
        })

    def predict(self, inputs):
        return self.sess.run(self.out, feed_dict={
            self.inputs: inputs
        })

    def get_gradients(self, inputs, acts, act_grad_weights):
        return self.sess.run(self.actor_gradients, feed_dict={
            self.inputs: inputs,
            self.acts: acts,
            self.act_grad_weights: act_grad_weights
        })

    def apply_gradients(self, actor_gradients):
        return self.sess.run(self.optimize, feed_dict={
            i: d for i, d in zip(self.actor_gradients, actor_gradients)
        })

    def get_network_params(self):
        return self.sess.run(self.network_params)

    def set_network_params(self, input_network_params):
        self.sess.run(self.set_network_params_op, feed_dict={
            i: d for i, d in zip(self.input_network_params, input_network_params)
        })


class CriticNetwork(object):
    """
    Input to the network is the state and action, output is V(s).
    On policy: the action must be obtained from the output of the Actor network.
    """
    def __init__(self, sess, state_dim, learning_rate):
        self.sess = sess
        self.s_dim = state_dim
        self.lr_rate = learning_rate

        # Create the critic network
        self.inputs, self.out = self.create_critic_network()

        # Get all network parameters
        self.network_params = \
            tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope='critic')

        # Set all network parameters
        self.input_network_params = []
        for param in self.network_params:
            self.input_network_params.append(
                tf.placeholder(tf.float32, shape=param.get_shape()))
        self.set_network_params_op = []
        for idx, param in enumerate(self.input_network_params):
            self.set_network_params_op.append(self.network_params[idx].assign(param))

        # Network target V(s)
        self.td_target = tf.placeholder(tf.float32, [None, 1])

        # Temporal Difference, will also be weights for actor_gradients
        self.td = tf.subtract(self.td_target, self.out)              # 减

        # Mean square error   # MSE
        self.loss = tflearn.mean_square(self.td_target, self.out)     # tflearn.objectives.mean_square (y_pred, y_true)

        # Compute critic gradient
        self.critic_gradients = tf.gradients(self.loss, self.network_params)

        # Optimization Op
        with tf.variable_scope(tf.get_variable_scope()):
            self.optimize = tf.train.RMSPropOptimizer(self.lr_rate).\
                apply_gradients(zip(self.critic_gradients, self.network_params))

    def create_critic_network(self):
        with tf.variable_scope('critic'):
            inputs = tflearn.input_data(shape=[None, self.s_dim[0], self.s_dim[1],self.s_dim[2]])
            print 'self.s_dim[0]',self.s_dim[0]
            # split_0 = tflearn.fully_connected(inputs[:, 0:1, -1], 128, activation='relu', reuse=tf.AUTO_REUSE, scope = 'critic_fc1')
            print 'inputs[:, 0:1, :].shape:', inputs[:, 0:1, :].shape
            print 'inputs[:, 1:2, :].shape:', inputs[:, 1:2, :].shape
            x_reshape1 = tflearn.reshape(inputs[:, 0:1, :], [-1, self.s_dim[1],self.s_dim[2],1])
            x_reshape2 = tflearn.reshape(inputs[:, 1:2, :], [-1, self.s_dim[1],self.s_dim[2],1])
            print 'x_reshape1.shape:', x_reshape1.shape
            print 'x_reshape2.shape:', x_reshape2.shape
            split_1 = tflearn.conv_2d(x_reshape1, 128, 4, activation='relu', scope = 'critic_conv1_1')
            print 'split_1.shape:', split_1.shape
            # split_2 = tflearn.fully_connected(inputs[:, 1:2, -1], 128, activation='relu', reuse=tf.AUTO_REUSE, scope = 'critic_fc2')
            split_2 = tflearn.conv_2d(x_reshape2, 128, 4, activation='relu', scope = 'critic_conv1_2')
            print 'split_2.shape:', split_2.shape

            split_1_flat_1 = tflearn.flatten(split_1)
            split_1_flat_2 = tflearn.flatten(split_2)

            merge_net = tflearn.merge([split_1_flat_1, split_1_flat_2], 'concat')

            dense_net_0 = tflearn.fully_connected(merge_net, 128, activation='relu', scope = 'critic_fc3')
            out = tflearn.fully_connected(dense_net_0, 1, activation='linear', scope = 'critic_fc4')

            return inputs, out

    def train(self, inputs, td_target):
        return self.sess.run([self.loss, self.optimize], feed_dict={
            self.inputs: inputs,
            self.td_target: td_target
        })

    def predict(self, inputs):
        return self.sess.run(self.out, feed_dict={
            self.inputs: inputs
        })

    def get_td(self, inputs, td_target):
        return self.sess.run(self.td, feed_dict={
            self.inputs: inputs,
            self.td_target: td_target
        })

    def get_gradients(self, inputs, td_target):
        return self.sess.run(self.critic_gradients, feed_dict={
            self.inputs: inputs,
            self.td_target: td_target
        })

    def apply_gradients(self, critic_gradients):
        return self.sess.run(self.optimize, feed_dict={
            i: d for i, d in zip(self.critic_gradients, critic_gradients)
        })

    def get_network_params(self):
        return self.sess.run(self.network_params)

    def set_network_params(self, input_network_params):
        self.sess.run(self.set_network_params_op, feed_dict={
            i: d for i, d in zip(self.input_network_params, input_network_params)
        })

def compute_gradients(s_batch, a_batch, r_batch, actor, critic):
    """
    batch of s, a, r is from samples in a sequence
    the format is in np.array([batch_size, s/a/r_dim])
    terminal is True when sequence ends as a terminal state
    """
    # print('............>s_batch',s_batch.shape[0])
    # print('............>a_batch',a_batch.shape[0])

    assert s_batch.shape[0] == a_batch.shape[0]
    assert s_batch.shape[0] == r_batch.shape[0]
    ba_size = s_batch.shape[0]

    v_batch = critic.predict(s_batch)      # input state and then output V(x)

    R_batch = np.zeros(r_batch.shape)


    R_batch[-1, 0] = v_batch[-1, 0]  # boot strap from last state

    for t in reversed(xrange(ba_size - 1)):
        R_batch[t, 0] = r_batch[t] + GAMMA * R_batch[t + 1, 0]

    td_batch = R_batch - v_batch

    actor_gradients = actor.get_gradients(s_batch, a_batch, td_batch)
    critic_gradients = critic.get_gradients(s_batch, R_batch)

    return actor_gradients, critic_gradients, td_batch


def discount(x, gamma):
    """
    Given vector x, computes a vector y such that
    y[i] = x[i] + gamma * x[i+1] + gamma^2 x[i+2] + ...
    """
    out = np.zeros(len(x))
    out[-1] = x[-1]
    for i in reversed(xrange(len(x)-1)):
        out[i] = x[i] + gamma*out[i+1]
    assert x.ndim >= 1
    # More efficient version:
    # scipy.signal.lfilter([1],[1,-gamma],x[::-1], axis=0)[::-1]
    return out


def compute_entropy(x):
    """
    Given vector x, computes the entropy
    H(x) = - sum( p * log(p))
    """
    H = 0.0
    for i in xrange(len(x)):
        if 0 < x[i] < 1:
            H -= x[i] * np.log(x[i])
    return H


def build_summaries():
    td_loss = tf.Variable(0.)
    tf.summary.scalar("TD_loss", td_loss)
    eps_total_reward = tf.Variable(0.)
    tf.summary.scalar("Eps_total_reward", eps_total_reward)
    avg_entropy = tf.Variable(0.)
    tf.summary.scalar("Avg_entropy", avg_entropy)

    summary_vars = [td_loss, eps_total_reward, avg_entropy]
    summary_ops = tf.summary.merge_all()

    return summary_ops, summary_vars
