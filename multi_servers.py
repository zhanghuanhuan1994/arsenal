#!/usr/bin/env python
import sys
import time
import os
import signal

sys.path.append('.')

from multiprocessing import Process


def il_server(subdir, is_multi):
    from il.receiver import main as il_server_main
    il_server_main(subdir, is_multi)


def indigo_server(subdir, is_multi):
    from indigo.env.run_receiver import main as indigo_server_main
    indigo_server_main(subdir, is_multi)


def rl_server(subdir, is_multi):
    from rl.receiver import main as rl_server_main
    rl_server_main(subdir, is_multi)


def gcc_server(subdir, is_multi):
    from gcc.receiver import main as gcc_server_main
    gcc_server_main(subdir, is_multi)


def remy_server(subdir, is_multi):
    from remy.receiver import main as remy_server_main
    remy_server_main(subdir, is_multi)


def pcc_rl_server(subdir, is_multi):
    from Aurora.receiver import main as pcc_rl_server_main
    pcc_rl_server_main(subdir, is_multi)


def bbr_server(subdir, is_multi):
    from bbr.receiver import main as bbr_server_main
    bbr_server_main(subdir, is_multi)


def pcc_vivace_server(subdir, is_multi):
    from pcc_vivace.receiver import main as pcc_vivace_server_main
    pcc_vivace_server_main(subdir, is_multi)


def main():
    running_time = 100 + 30
    subdir = sys.argv[1]
    algorithm1 = sys.argv[2]
    algorithm2 = sys.argv[3]

    dir = './log/' + subdir
    if not os.path.exists(dir):
        os.mkdir(dir)

    is_multi = True

    process_sets = []
    il_process = Process(target=il_server, name='IL Server', args=(subdir, is_multi))
    indigo_process = Process(target=indigo_server, name='Indigo Server', args=(subdir, is_multi))
    rl_process = Process(target=rl_server, name='RL Server', args=(subdir, is_multi))
    gcc_process = Process(target=gcc_server, name='GCC Server', args=(subdir, is_multi))
    remy_process = Process(target=remy_server, name='RemyCC Server', args=(subdir, is_multi))
    pcc_rl_process = Process(target=pcc_rl_server, name='PCC-RL Server', args=(subdir, is_multi))
    bbr_process = Process(target=bbr_server, name='bbr Server', args=(subdir, is_multi))
    pcc_vivace_process = Process(target=pcc_vivace_server, name='pcc_vivace Server', args=(subdir, is_multi))

    # process_sets.append(il_process)
    # process_sets.append(indigo_process)
    # process_sets.append(rl_process)
    # process_sets.append(gcc_process)
    # process_sets.append(remy_process)
    # process_sets.append(pcc_rl_process)
    # process_sets.append(bbr_process)
    # process_sets.append(pcc_vivace_process)

    # algorithm 1
    if algorithm1 == 'il':
        process_sets.append(il_process)

    if algorithm1 == 'indigo':
        process_sets.append(indigo_process)

    if algorithm1 == 'rl':
        process_sets.append(rl_process)

    if algorithm1 == 'gcc':
        process_sets.append(gcc_process)

    if algorithm1 == 'remyCC':
        process_sets.append(remy_process)

    if algorithm1 == 'pcc_rl':
        process_sets.append(pcc_rl_process)

    if algorithm1 == 'bbr':
        process_sets.append(bbr_process)

    if algorithm1 == 'pcc_vivace':
        process_sets.append(pcc_vivace_process)

    # algorithm 2
    if algorithm2 == 'il':
        process_sets.append(il_process)

    if algorithm2 == 'indigo':
        process_sets.append(indigo_process)

    if algorithm2 == 'rl':
        process_sets.append(rl_process)

    if algorithm2 == 'gcc':
        process_sets.append(gcc_process)

    if algorithm2 == 'remyCC':
        process_sets.append(remy_process)

    if algorithm2 == 'pcc_rl':
        process_sets.append(pcc_rl_process)

    if algorithm2 == 'bbr':
        process_sets.append(bbr_process)

    if algorithm2 == 'pcc_vivace':
        process_sets.append(pcc_vivace_process)

    for p in process_sets:
        p.start()

    time.sleep(running_time)

    for p in process_sets:
        try:
            os.kill(p.pid, signal.SIGTERM)
        except Exception:
            pass


if __name__ == '__main__':
    main()
