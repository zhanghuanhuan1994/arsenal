import os
import time


def run():
    f = open('./trace/mm-link-scripts-with-drop-tail-150.txt', mode='r')
    traces = []
    for line in f:
        traces.append(line.split('\n')[0])
    f.close()
    subdirs = []
    for tt in traces:
        trace_name = tt.split(' ')[1].split('/')[2].split('.')[0]
        subdir = trace_name.split('_')[0] + "_" + trace_name.split('_')[3] + "_" + trace_name.split('_')[5]
        subdirs.append(subdir)

    print(subdirs)
    algorithms = ['gcc', 'remyCC', 'indigo', 'pcc_rl', 'bbr', 'pcc_vivace', 'il', 'rl']

    kill_mm_link = 'pkill -9 mm-link'
    kill_mm_loss = 'pkill -9 mm-loss'
    kill_mm_delay = 'pkill -9 mm-delay'

    kill_mm = [kill_mm_link, kill_mm_loss, kill_mm_delay]

    for ii in range(len(traces)):
        mm_cmd = traces[ii]
        mm_cmd += ' ./single_client.py '
        mm_cmd += subdirs[ii]
        print mm_cmd
        for al in algorithms:
            begin = time.time()
            time.sleep(0.5)
            cmd = mm_cmd + " " + al
            print cmd

            os.system(cmd)

            while True:
                if time.time() - begin > 90:
                    break

            for mm in kill_mm:
                os.system(mm)
            print(al, "done")
        time.sleep(1)


if __name__ == '__main__':
    run()
