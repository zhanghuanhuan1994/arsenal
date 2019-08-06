import time
import os


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

    for ii in range(len(subdirs)):
        cmd = './single_server.py ' + subdirs[ii]
        for al in algorithms:
            begin = time.time()
            server_cmd = cmd + " " + al

            # print server_cmd
            os.system(server_cmd)
            while True:
                if time.time() - begin > 90:
                    break
            print(al, 'done')
        time.sleep(1)


if __name__ == '__main__':
    run()
