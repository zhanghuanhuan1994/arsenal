# Arsenal: Understanding Learning-based Wireless Video Transport via In-depth Evaluation
## Overview

![images](./images/overview.png)


This work is the first to make an extensive comparative study of all mainstream AI-driven congestion control algorithms, under a custom-designed uniform evaluation platform. The system architecture consists of following modules:


+ **Video telephony module** is an adaptive real-time video communication system, which transmits video content according to the instantaneous network available bandwidth estimated by the underlying CC algorithms. Arsenal faithfully emulates real-world video telephony by implementing the video codec, frame formulation and packet parsing components.
+ **Bulk file transfer.** For a comprehensive evaluation, Arsenal designs a bulk file transfer module to examine the performance of transmitting non-video content. Different from video telephony, file transfer supports full-throttle and continuous traffic.
+ **Link simulator.** Arsenal collects and uses large-scale video-telephony traces with ≥ 1 million sessions and the 1-second fine-grained records, from a mainstream live-video APP in China. Arsenal then designs a trace mapping procedure that allows the link emulation software mahimahi to faithfully simulate the practical network dynamics.
+ **CC algorithms collection:** Arsenal incorporates a series of representative AI-driven transport algorithms, as shown in Table. 1: 2 traditional machine learning (i.e., ML, not based on deep neural network) based algorithms (Remy, PCC-Vivace) and 4 deep learning (DL) based algorithms (Pensieve’V, Aurora, Concerto and Indigo). Besides, we also use two widely used non-AI protocols, BBR and WebRTC. 
+ **Video and file analysis.** Arsenal develops an analysis module at receiver side to record and calculate the performance metrics for evaluating different CC algorithms.

![images](./images/algorithms.png)

## Environment
- Ubuntu 14.04 and later
- python 2.7
- tensorflow, tflearn, numpy, jsonpickle, and so on
- bbr and pcc_vivace kernel support
- protobuf support

## Preparations
We use the **mahimahi** as the emulator, so we need to install the environment mahimahi. For details, refer to the official website [mahimahi](http://mahimahi.mit.edu/).

Each time we run the project, we need ensure two things.
1. The bbr and pcc_vivace kernel modules have been installed into the kernel. For details, refer to the website [pcc-kernel](https://github.com/PCCproject/PCC-Kernel). The bbr module does the same thing like pcc_vivace.
2. Run `sudo sysctl -w net.ipv4.ip_forward=1` to ensure the `ip_forward = 1`

## Run
1. Open a terminal, run following command to generate mahimahi environment.
```
mm-link 2mbps.trace 2mbps.trace mm-delay 10
```
The command means the delay of the link is 10 milliseconds and the bandwidth follows the given file `2mbps.trace`. Of course, we need prepare the `.trace` file in advance.

2. Run one side inside the first command window and open a new terminal to run the another side. 

For single flow,
```
./single_client.py
./single_server.py
```
For compete flows,
```
./compete_client_runner.py
./compete_server_runner.py
```
3. Then we will get the log file that records the communication process and we can use the scripts to analyze the log.
