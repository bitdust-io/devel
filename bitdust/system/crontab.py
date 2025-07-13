#!/usr/bin/python
# crontab.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (crontab.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#
"""
..

module:: crontab

"""

import os
import subprocess


def read_cronttab():
    proc = subprocess.Popen('crontab -l', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=-1)
    crontab_stdout, crontab_stderr = proc.communicate()
    if proc.returncode:
        if crontab_stderr and crontab_stderr.decode().count('no crontab for'):
            return ''
        raise Exception('was not able to read crontab file')
    crontab_stdout = crontab_stdout.decode()
    crontab_stderr = crontab_stderr.decode()
    if crontab_stderr:
        raise Exception('was not able to read crontab file')
    return crontab_stdout


def verify_record_exist(crontab_content):
    for ln in crontab_content.splitlines():
        if ln.count('bitdust daemon') and ln.count('@reboot') and not ln.strip().startswith('#'):
            return True
    return False


def check_install_crontab_record(base_dir):
    crontab_content = read_cronttab()

    if verify_record_exist(crontab_content):
        return 'crontab record for BitDust already exist'

    crontab_content += f'\n@reboot {base_dir}/bitdust daemon\n'
    tmp_file_path = os.path.join(base_dir, 'crontab_updated')
    open(tmp_file_path, 'wt').write(crontab_content)

    proc = os.popen(f'crontab {tmp_file_path}')
    proc.read()
    proc.close()

    try:
        os.remove(tmp_file_path)
    except:
        pass

    return 'added new crontab record, BitDust node will automatically start at system boot'
