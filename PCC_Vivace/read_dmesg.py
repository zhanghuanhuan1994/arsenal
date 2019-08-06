import commands


def get_bbr_pacing_rate():
    output = commands.getoutput('tail -n 20 /var/log/messages')
    latest_pacing_rate = 0
    for line in output.splitlines():
        arr = line.split()
        # print arr
        if arr[-1] == 'rate':
            latest_pacing_rate = arr[-4].strip(':')
    return int(latest_pacing_rate)


def get_pcc_pacing_rate():
    output = commands.getoutput('tail -n 20 /var/log/messages')
    latest_pacing_rate = 0
    for line in output.splitlines():
        arr = line.split()
        # print arr
        if arr[-1] == 'pcc_vivace':
            latest_pacing_rate = arr[-2]
    # print latest_pacing_rate
    return int(latest_pacing_rate)

if __name__ == '__main__':
    print get_bbr_pacing_rate()