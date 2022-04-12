#!/usr/bin/env python

import os
import sys
import time
import signal
import argparse

from multiprocessing import Pipe, Process
from helpers import (DONE, RUN, STOP)

import commands


def il(pipe, subdir, with_frame):
    from il.sender import main as il_sender_main
    il_sender_main(pipe, subdir, with_frame)


def indigo(pipe, subdir, with_frame):
    from indigo.dagger.run_sender import main as indigo_sender_main
    indigo_sender_main(pipe, subdir, with_frame)


def rl(pipe, subdir, with_frame):
    from rl.sender import main as rl_sender_main
    rl_sender_main(pipe, subdir, with_frame)


def gcc(pipe, subdir, with_frame):
    from gcc.sender import main as gcc_sender_main
    gcc_sender_main(pipe, subdir, with_frame)


def remyCC(pipe, subdir, with_frame):
    from remy.sender import main as remyCC_sender_main
    remyCC_sender_main(pipe, subdir, with_frame)


def pcc_rl(pipe, subdir, with_frame):
    from Aurora.sender import main as pcc_rl_sender_main
    pcc_rl_sender_main(pipe, subdir, with_frame)


def bbr(pipe, subdir, with_frame):
    from bbr.sender import main as bbr_sender_main
    bbr_sender_main(pipe, subdir, with_frame)


def pcc_vivace(pipe, subdir, with_frame):
    from pcc_vivace.sender import main as pcc_vivace_sender_main
    pcc_vivace_sender_main(pipe, subdir, with_frame)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('subdir', default='default')
    parser.add_argument('algorithm', default='il')
    args = parser.parse_args()
    running_time = 60  # second
    # subdir = time.strftime("%m%d%H", time.localtime())

    # the trace name to save log
    subdir = args.subdir

    dir = './log/' + subdir
    if not os.path.exists(dir):
        os.mkdir(dir)

    with_frame = True
    is_multi = False

    parent_il, il_pipe = Pipe(True)
    parent_indigo, indigo_pipe = Pipe(True)
    parent_rl, rl_pipe = Pipe(True)
    parent_gcc, gcc_pipe = Pipe(True)
    parent_remyCC, remyCC_pipe = Pipe(True)
    parent_pcc_rl, pcc_rl_pipe = Pipe(True)
    parent_bbr, bbr_pipe = Pipe(True)
    parent_pcc_vivace, pcc_vivace_pipe = Pipe(True)

    # the parent process pipe
    parent_pipes = []
    # parent_pipes.append(parent_il)
    # parent_pipes.append(parent_indigo)
    # parent_pipes.append(parent_rl)
    # parent_pipes.append(parent_gcc)
    # parent_pipes.append(parent_remyCC)
    # parent_pipes.append(parent_pcc_rl)
    # parent_pipes.append(parent_bbr)
    # parent_pipes.append(parent_pcc_vivace)

    process_sets = []
    p1 = Process(target=il, name='il_sender', args=(il_pipe, subdir, with_frame))
    p3 = Process(target=indigo, name='indigo_sender', args=(indigo_pipe, subdir, with_frame))
    p5 = Process(target=rl, name='rl_sender', args=(rl_pipe, subdir, with_frame))
    p7 = Process(target=gcc, name='gcc_sender', args=(gcc_pipe, subdir, with_frame))
    p9 = Process(target=remyCC, name='remyCC_sender', args=(remyCC_pipe, subdir, with_frame))
    p11 = Process(target=pcc_rl, name='pcc_rl_sender', args=(pcc_rl_pipe, subdir, with_frame))
    p13 = Process(target=bbr, name='bbr_sender', args=(bbr_pipe, subdir, with_frame))
    p15 = Process(target=pcc_vivace, name='pcc_vivace_sender', args=(pcc_vivace_pipe, subdir, with_frame))

    # process_sets.append(p1)
    # process_sets.append(p3)
    # process_sets.append(p5)
    # process_sets.append(p7)
    # process_sets.append(p9)
    # process_sets.append(p11)
    # process_sets.append(p13)
    # process_sets.append(p15)

    if args.algorithm == 'il':
        parent_pipes.append(parent_il)
        process_sets.append(p1)

    if args.algorithm == 'indigo':
        parent_pipes.append(parent_indigo)
        process_sets.append(p3)

    if args.algorithm == 'rl':
        parent_pipes.append(parent_rl)
        process_sets.append(p5)

    if args.algorithm == 'gcc':
        parent_pipes.append(parent_gcc)
        process_sets.append(p7)

    if args.algorithm == 'remyCC':
        parent_pipes.append(parent_remyCC)
        process_sets.append(p9)

    if args.algorithm == 'pcc_rl':
        parent_pipes.append(parent_pcc_rl)
        process_sets.append(p11)

    if args.algorithm == 'bbr':
        parent_pipes.append(parent_bbr)
        process_sets.append(p13)

    if args.algorithm == 'pcc_vivace':
        parent_pipes.append(parent_pcc_vivace)
        process_sets.append(p15)

    # start the process
    for i in range(len(process_sets)):
        start_time = time.time()

        process_sets[i].start()
        print "start"
        flag = ""
        while True:
            flag = parent_pipes[i].recv()
            if flag == DONE:
                parent_pipes[i].send(RUN)
                break

        # start to run
        print("Process Beginning!")
        time.sleep(running_time)
        print("Process Ended!")

        # send stop signal
        parent_pipes[i].send(STOP)
        # kill the process
        try:
            os.kill(process_sets[i].pid, signal.SIGTERM)
        except BaseException as e:
            print e.args

        # while True:
        #     if time.time() - begin > running_time + 60:
        #         break
        # print(i, 'done')

        # string = raw_input("Run the next algorithm(Y/N)?")
        # if string == 'Y' or string == 'y':
        #     continue
        # else:
        #     break

        end_time = time.time()
        print("It takes " + str(end_time - start_time) + " seconds")


if __name__ == '__main__':
    main()
