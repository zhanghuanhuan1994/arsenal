import re


class Rule(object):

    # read the file, return the rules
    def generate(self, outfile=None):
        if not outfile:
            return 0
        file = open(outfile, mode='r')
        try:
            lines = file.readlines()

            for line in lines:
                if 'Rules' in line:
                    rule = "".join(line)
                    new_rule = rule[6:]
                    rule_list = new_rule.split("[")
                    return rule_list
        except Exception as e:
            print e.args

    def control(self, sewma, rewma, rttr, slowrewma, rule_list):
        win_increment = 0
        win_multiple = 0
        intersend = 0
        judge = 1
        for i in range(1, len(rule_list)):
            # print rule_list[i]
            rule_number = re.findall(r"\d+\.?\d*", rule_list[i])
            rule_number = map(float, rule_number)
            if sewma >= rule_number[0] and sewma <= rule_number[4]:
                if rewma >= rule_number[1] and rewma <= rule_number[5]:
                    if rttr >= rule_number[2] and rttr <= rule_number[6]:
                        if slowrewma >= rule_number[3] and slowrewma <= rule_number[7]:
                            win_increment = rule_number[10]
                            win_multiple = rule_number[11]
                            intersend = rule_number[12]
                            judge = 0
        # the default value
        if judge == 1:
            print "Oringal rules matched!"
            win_increment = 1
            win_multiple = 1
            intersend = 3

        return win_increment, win_multiple, intersend

    def act(self, old_win, win_increment, win_multiple):
        return int(win_increment + win_multiple * old_win)


if __name__ == '__main__':
    rule = Rule()
    rule_list = rule.generate(outfile="log.txt")
    print rule.control(1.61067401921, 1.61265672737, 1.01158994031, 1.3725358095, rule_list)
