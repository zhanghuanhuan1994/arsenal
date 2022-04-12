#!/usr/bin/env python
import sys
import time
import os
import signal
import argparse

sys.path.append('.')

from multiprocessing import Process


def il_server(subdir):
    from il.receiver import main as il_server_main
    il_server_main(subdir)


def indigo_server(subdir):
    from indigo.env.run_receiver import main as indigo_server_main
    indigo_server_main(subdir)


def rl_server(subdir):
    from rl.receiver import main as rl_server_main
    rl_server_main(subdir)


def gcc_server(subdir):
    from gcc.receiver import main as gcc_server_main
    gcc_server_main(subdir)


def remy_server(subdir):
    from remy.receiver import main as remy_server_main
    remy_server_main(subdir)


def pcc_rl_server(subdir):
    from Aurora.receiver import main as pcc_rl_server_main
    pcc_rl_server_main(subdir)


def bbr_server(subdir):
    from bbr.receiver import main as bbr_server_main
    bbr_server_main(subdir)


def pcc_vivace_server(subdir):
    from pcc_vivace.receiver import main as pcc_vivace_server_main
    pcc_vivace_server_main(subdir)


def main():
    # parser = argparse.ArgumentParser()
    # parser.add_argument('subdir', default='default')
    # parser.add_argument('algorithm', default='il')
    # args = parser.parse_args()

    # subdir = time.strftime("%m%d%H", time.localtime())
    start_time = time.time()
    # subdir = raw_input("Please input the trace name:")

    subdir = sys.argv[1]
    algorithm_name = sys.argv[2]

    dir = './log/' + subdir
    if not os.path.exists(dir):
        os.mkdir(dir)

    running_time = 60 + 20

    process_sets = []
    il_process = Process(target=il_server, name='IL Server', args=(subdir,))
    indigo_process = Process(target=indigo_server, name='Indigo Server', args=(subdir,))
    rl_process = Process(target=rl_server, name='RL Server', args=(subdir,))
    gcc_process = Process(target=gcc_server, name='GCC Server', args=(subdir,))
    remy_process = Process(target=remy_server, name='RemyCC Server', args=(subdir,))
    pcc_rl_process = Process(target=pcc_rl_server, name='PCC-RL Server', args=(subdir,))
    bbr_process = Process(target=bbr_server, name='bbr Server', args=(subdir,))
    pcc_vivace_process = Process(target=pcc_vivace_server, name='pcc_vivace Server', args=(subdir,))

    # process_sets.append(il_process)
    # process_sets.append(indigo_process)
    # process_sets.append(rl_process)
    # process_sets.append(gcc_process)
    # process_sets.append(remy_process)
    # process_sets.append(pcc_rl_process)
    # process_sets.append(bbr_process)
    # process_sets.append(pcc_vivace_process)

    # print args.algorithm

    if algorithm_name == 'il':
        process_sets.append(il_process)

    if algorithm_name == 'indigo':
        process_sets.append(indigo_process)

    if algorithm_name == 'rl':
        process_sets.append(rl_process)

    if algorithm_name == 'gcc':
        process_sets.append(gcc_process)

    if algorithm_name == 'remyCC':
        process_sets.append(remy_process)

    if algorithm_name == 'pcc_rl':
        process_sets.append(pcc_rl_process)

    if algorithm_name == 'bbr':
        process_sets.append(bbr_process)

    if algorithm_name == 'pcc_vivace':
        process_sets.append(pcc_vivace_process)

    # start the process
    for p in process_sets:
        begin = time.time()
        p.start()

        while True:
            if time.time() - begin > running_time:
                break

        # time.sleep(running_time)

        # string = raw_input("Run the next algorithm(Y/N)?")
        try:
            os.kill(p.pid, signal.SIGTERM)
        except Exception:
            pass
        print(p, 'done')

        # if string == 'Y' or string == 'y':
        #     continue
        # else:
        #     break

    end_time = time.time()
    print("It takes " + str(end_time - start_time) + " seconds")


if __name__ == '__main__':
    main()
