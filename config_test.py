#!/usr/bin/env python
# Written by Qusai Abu-Obaida

"""The script validates the PVT lines in config files for consistency and accordance with the specifications"""

import argparse
import logging
import os
import sys
import re
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
POK = False
temp_folder = os.getcwd()
sys.path.append(temp_folder)
# Parsing the command line arguments
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=__doc__)
parser.add_argument('-m', '--max_slew', help='file specifying voltage cluster groups for max_slew pvt', required=True)
parser.add_argument('-l', '--load_alignment', default='same', help='file specifying load alignment groups for each pvt')
parser.add_argument('-f', '--config_file', default='.chute-config', help='path to chute-config file')
args = parser.parse_args()


class PVT(object):
    def __init__(self, full_name):
        self.fullname = full_name
        name_parts = full_name.split('_')
        self.input_v = None
        if len(name_parts) == 1:
            self.type = 'ret' if POK else 'base'
            self.name = name_parts[0]
        else:
            self.type = name_parts[0]
            self.name = name_parts[1]
            if len(name_parts) == 3:
                self.input_v = float(name_parts[2][1:].strip('v').replace('p', '.'))
            elif name_parts[0] in ('ulvl', 'dlvl'):
                name_groups = pvt_name.search(self.name).groups()
                self.input_v = float(name_groups[1].strip('v').replace('p', '.'))
        name_groups = pvt_name.search(self.name).groups()
        self.voltage = float(name_groups[1].strip('v').replace('p', '.'))
        self.process = name_groups[0]
        self.temperature = int(name_groups[2].strip('c').replace('n', '-'))

    def test(self, line):
        errors = []
        if line['maxSlewPVT'] not in max_slew_list or not any(
                        i == self.name for i in max_slew_list[line['maxSlewPVT']]):
            errors.append('Max slew PVT error')

        if args.load_alignment != 'same' and (line['load_alignment'] not in load_alignment_list or not any(
                    self.name in i for i in load_alignment_list[line['maxSlewPVT']])):
            errors.append('load align error')
        if self.process != line['process']:
            errors.append('process error')
        if self.temperature != line['temp']:
            errors.append('temp error')
        if self.voltage != line['vdd']:
            errors.append('vdd error')
        if (self.input_v and 'vddi' not in line) or (not self.input_v and 'vddi' in line):
            errors.append('vddi exists in one and not the other')
        if self.input_v and (self.input_v != line['vddi']):
            errors.append('mismatch in value of vddi')
        if self.type != line['pvtType']:
            errors.append('type error')
        if (line['func_name'] == 'PVT' and self.type in ('ulvl', 'dlvl')) or (
                        line['func_name'] == 'PVT_LSH' and self.type in ('pg', 'ret', 'base')):
            errors.append('function type is wrong for this type')
        if self.fullname != line['loadAlignGroup']:
            errors.append('Load align group error')
        return errors


def read_list(list_file):
    out = {}
    latest = 'error'
    with open(list_file) as f:
        for line in f:
            line = line.strip()
            if len(line) == 0:
                continue
            if ':' in line:
                latest = line.strip(':')
                out[latest] = []
            else:
                out[latest].append(line)
    if 'error' in out:
        sys.exit('Error in %s' % list_file)
    return out


# writes a temporary python file that creates a list of all the PVTs and their attributes
def temp_config(config):
    global POK
    try:
        cfg = open(config, 'r')
    except IOError:
        sys.exit("Can't open config-file")
    temp_cfg = open(os.path.join(temp_folder, "temp_cfg.py"), 'w+')
    pvts = []
    for line in cfg:
        if '#!' in line:
            temp_cfg.write('#!/usr/bin/env python\n')
            temp_cfg.write('import inspect\n')
        elif 'def' in line:
            if 'PVT_LSH' in line:
                POK = True
            temp_cfg.write(line)
            temp_cfg.write('    out = locals()\n')
            temp_cfg.write('    out["func_name"] = inspect.stack()[0][3]\n')
            temp_cfg.write('    return out\n')
        elif all(word in line for word in ('PVT', '(', ')')):
            pvts.append(line)
    temp_cfg.write('attrs = []\n')
    for pvt in pvts:
        temp_cfg.write('current = %s\n' % pvt.strip())
        temp_cfg.write('attrs.append(current)\n')


temp_config(args.config_file)
from temp_cfg import attrs

pvt_name = re.compile(r'([a-z]+)(\d+p\d+v)(n?\d+c)')
max_slew_list = read_list(args.max_slew)
if args.load_alignment != 'same':
    load_alignment_list = read_list(args.load_alignment)

for i in attrs:
    current_class = PVT(i['name'])
    if current_class.test(i):
        print(current_class.test(i), i['name'])
os.remove(os.path.join(temp_folder, "temp_cfg.py"))
