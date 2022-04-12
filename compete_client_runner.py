import os
import time


def run():
    f = open('./trace/mm-link-scripts-compete.txt', mode='r')
    traces = []
    for line in f:
        traces.append(line.split('\n')[0])
    f.close()
    subdirs = []
    for tt in traces:
        trace_name = tt.split(' ')[1].split('/')[2].split('.')[0]
        subdir = trace_name.split('_')[0] + "_" + trace_name.split('_')[3] + "_" + trace_name.split('_')[
            5] + '_file_compete'
        subdirs.append(subdir)
    # print traces
    print subdirs

    # rl_algorithm = ['rl']
    # algorithms = ['gcc', 'remyCC', 'indigo', 'pcc_rl', 'bbr', 'pcc_vivace', 'il', 'rl']

    algorI = ['bbr']
    algorII = ['pcc_vivace']

    kill_mm_link = 'pkill -9 mm-link'
    kill_mm_loss = 'pkill -9 mm-loss'
    kill_mm_delay = 'pkill -9 mm-delay'

    kill_mm = [kill_mm_link, kill_mm_loss, kill_mm_delay]

    for kk in range(len(traces)):
        mm_cmd = traces[kk]
        mm_cmd += ' ./multi_clients.py '

        for ii in range(len(algorI)):
            for jj in range(len(algorII)):
                cc_vs_cmd = mm_cmd + subdirs[kk] + "_" + algorI[ii] + "_VS_" + algorII[jj]

                # if algorithms[ii] == 'bbr' and algorithms[jj] == 'pcc_vivace':
                #     pass
                # else:
                begin = time.time()
                server_cmd = cc_vs_cmd + " " + algorI[ii] + " " + algorII[jj]
                print server_cmd
                time.sleep(2)
                os.system(server_cmd)
                while True:
                    if time.time() - begin > 150:
                        break
                print (algorI[ii], algorII[jj], 'done')
                for mm in kill_mm:
                    os.system(mm)
        time.sleep(1)


if __name__ == '__main__':
    run()
