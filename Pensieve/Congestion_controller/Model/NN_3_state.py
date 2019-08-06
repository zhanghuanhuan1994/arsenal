import numpy as np
import tflearn
import tensorflow as tf
import os

def Network_Conv(S_LEN, Input_LEN, length, class_num):

	data_len=Input_LEN*(S_LEN*2+1)
	x = tf.placeholder(tf.float32, shape=[None, length,data_len], name='x')
	y_ = tf.placeholder(tf.int32, shape=[None, ], name='y_')
	x_reshape = tflearn.reshape(x, [-1, length,data_len,1])

	print(x_reshape.shape)
	split_1 = tflearn.conv_2d(x_reshape[:,:,0:Input_LEN*S_LEN,:], 64, 3, activation='LeakyReLU',restore = False)
	split_2 = tflearn.conv_2d(x_reshape[:,:,Input_LEN*S_LEN:Input_LEN*S_LEN*2,:], 64, 3, activation='LeakyReLU')
	split_3 = tflearn.conv_2d(x_reshape[:,:,Input_LEN*S_LEN*2:data_len,:], 64, 3, activation='LeakyReLU')
	print(split_1.shape)
	print(split_2.shape)
	print(split_3.shape)

	# dense_concat = tf.concat([split_1[:,:,:,np.newaxis],split_2[:,:,:,np.newaxis],split_3[:,:,:,np.newaxis]],axis = 2)
	dense_concat = tflearn.merge([split_1, split_2,split_3], 'concat',axis=2)
	# print dense_concat.shape

	cov=tflearn.conv_2d(dense_concat, 128, 3, activation='relu')
	#print type(cov)
	cov = tflearn.flatten(cov)
	#print cov.shape
	logits = tf.layers.dense(inputs=cov,
							 units=256,  
							 activation=tf.nn.relu,
							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
	logits = tf.layers.dense(inputs=logits,
							 units=class_num,  
							 activation=None,
							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
	return logits, x, y_

def Network_LSTM(S_LEN, Input_LEN, length, class_num):

	data_len=Input_LEN*(S_LEN*2+1)
	x = tf.placeholder(tf.float32, shape=[None, length,data_len], name='x')
	y_ = tf.placeholder(tf.int32, shape=[None, ], name='y_')
	# x_reshape = tflearn.reshape(x, [-1, length,data_len])

	# print x_reshape.shape    
	split_1 = tflearn.lstm(x[:,:,0:Input_LEN*S_LEN], 64, activation='tanh', inner_activation='LeakyReLU',return_seq=False,  name='LSTM_1')
	split_2 = tflearn.lstm(x[:,:,Input_LEN*S_LEN:Input_LEN*S_LEN*2], 64, activation='tanh', inner_activation='LeakyReLU',return_seq=False,  name='LSTM_1')
	split_3 = tflearn.lstm(x[:,:,Input_LEN*S_LEN*2:data_len], 64, activation='tanh', inner_activation='LeakyReLU',return_seq=False,  name='LSTM_1')

	# split_1 = tflearn.conv_2d(x_reshape[:,:,0:Input_LEN*S_LEN,:], 64, 3, activation='LeakyReLU',restore = False)
	# split_2 = tflearn.conv_2d(x_reshape[:,:,Input_LEN*S_LEN:Input_LEN*S_LEN*2,:], 64, 3, activation='LeakyReLU')
	# split_3 = tflearn.conv_2d(x_reshape[:,:,Input_LEN*S_LEN*2:data_len,:], 64, 3, activation='LeakyReLU')
	# print split_1.shape
	# print split_2.shape
	# print split_3.shape

	# dense_concat = tf.concat([split_1[:,:,:,np.newaxis],split_2[:,:,:,np.newaxis],split_3[:,:,:,np.newaxis]],axis = 2)
	dense_concat = tflearn.merge([split_1, split_2,split_3], 'concat',axis=1)
	# print dense_concat.shape

	# cov=tflearn.conv_2d(dense_concat, 128, 3, activation='relu')
	# #print type(cov)
	# cov = tflearn.flatten(cov)
	#print cov.shape
	logits = tf.layers.dense(inputs=dense_concat,
							 units=256,  
							 activation=tf.nn.relu,
							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
	logits = tf.layers.dense(inputs=logits,
							 units=class_num,  
							 activation=None,
							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
	return logits, x, y_

# def NN(S_LEN, Input_LEN, class_num):   #mz

# 	data_len=Input_LEN*(S_LEN*2+1)
# 	x = tf.placeholder(tf.float32, shape=[None, data_len], name='x')
# 	y_ = tf.placeholder(tf.int32, shape=[None, ], name='y_')
# 	dense1_1 = tf.layers.dense(inputs=x[:,0:Input_LEN*S_LEN],
# 							 units=128,
# 							 activation=tf.nn.relu,
# 							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
# 							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
# 	dense1_2 = tf.layers.dense(inputs=x[:,Input_LEN*S_LEN:Input_LEN*S_LEN*2],
# 							 units=128,
# 							 activation=tf.nn.relu,
# 							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
# 							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
# 	dense1_3 = tf.layers.dense(inputs=x[:,Input_LEN*S_LEN*2:data_len,length],
# 							 units=128,
# 							 activation=tf.nn.relu,
# 							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
# 							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
# 	dense_concat = tf.concat([dense1_1[:,:,np.newaxis],dense1_2[:,:,np.newaxis],dense1_3[:,:,np.newaxis]],axis = 2)
# 	cov=tflearn.conv_2d(dense_concat[:,:,:,np.newaxis], 64, 3,padding = 'valid', activation='relu')
# 	#print type(cov)
# 	cov = tflearn.flatten(cov)
# 	#print cov.shape
# 	logits = tf.layers.dense(inputs=cov,
# 							 units=256,  
# 							 activation=tf.nn.relu,
# 							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
# 							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
# 	logits = tf.layers.dense(inputs=logits,
# 							 units=class_num,  
# 							 activation=None,
# 							 kernel_initializer=tf.truncated_normal_initializer(stddev=0.01),
# 							 kernel_regularizer=tf.contrib.layers.l2_regularizer(0.003))
# 	return logits, x, y_
