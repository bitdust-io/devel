#!/usr/bin/env python
# bptester.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (bptester.py) is part of BitDust Software.
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
.. module:: bptester.

This is a BitDust child process, do monitoring of customer's files.

In case some of customers do not play fair - need to stop this.:

    * check if he use more space than we gave him, remove too old files
    * test/remove files after list of customers was changed
    * check all packets to be valid
"""

from __future__ import absolute_import
import os
import sys
import time
from io import open

#------------------------------------------------------------------------------

AppData = ''

#------------------------------------------------------------------------------


def sharedPath(filename, subdir='logs'):
    global AppData
    if AppData == '':
        curdir = os.getcwd()  # os.path.dirname(os.path.abspath(sys.executable))
        if os.path.isfile(os.path.join(curdir, 'appdata')):
            try:
                appdata = os.path.abspath(open(os.path.join(curdir, 'appdata'), 'rb').read().strip())
            except:
                appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
            if not os.path.isdir(appdata):
                appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
        else:
            appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
        AppData = appdata
    return os.path.join(AppData, subdir, filename)


def logfilepath():
    """
    A file path to the file where ``bptester`` will write logs.

    Need to make sure the ``bptester`` log is in a directory the user
    has permissions for, Such as the customer data directory.  Possibly
    move to temp directory?
    """
#    logspath = os.path.join(os.path.expanduser('~'), '.bitdust', 'logs')
#    if not os.path.isdir(logspath):
#        return 'tester.log'
#    return os.path.join(logspath, 'tester.log')
    return sharedPath('bptester.log')


def printlog(txt):
    """
    Write a line to the log file.
    """
    lf = open(logfilepath(), 'a')
    lf.write(txt + '\n')
    lf.close()

#------------------------------------------------------------------------------

# if __name__ == "__main__":
#     dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
#     sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
#     sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))


try:
    from logs import lg
    from system import bpio
    from lib import nameurl
    from lib import misc
    from lib import jsn
    from storage import accounting
    from userid import global_id
    from main import settings
    from contacts import contactsdb
    from p2p import commands
    from crypt import signed
except:
    import traceback
    printlog(traceback.format_exc())
    sys.exit(2)

#-------------------------------------------------------------------------------


def SpaceTime():
    """
    Test all packets for each customer.

    Check if he use more space than we gave him and if packets is too
    old.
    """
    printlog('SpaceTime ' + str(time.strftime("%a, %d %b %Y %H:%M:%S +0000")))
    space = accounting.read_customers_quotas()
    if space is None:
        printlog('SpaceTime ERROR customers quotas file can not be read or it is empty, skip')
        return
    customers_dir = settings.getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        printlog('SpaceTime ERROR customers folder not exist')
        return
    remove_list = {}
    used_space = accounting.read_customers_usage()
    for customer_filename in os.listdir(customers_dir):
        onecustdir = os.path.join(customers_dir, customer_filename)
        if not os.path.isdir(onecustdir):
            remove_list[onecustdir] = 'is not a folder'
            continue
        # idurl = nameurl.FilenameUrl(customer_filename)
        idurl = global_id.GlobalUserToIDURL(customer_filename)
        if idurl is None:
            remove_list[onecustdir] = 'wrong folder name'
            continue
        curspace = space.get(idurl, None)
        if curspace is None:
            remove_list[onecustdir] = 'not found in space file'
            continue
        try:
            maxspaceV = int(curspace)
        except:
            remove_list[onecustdir] = 'wrong space value'
            continue
        timedict = {}
        sizedict = {}

        def cb(path, subpath, name):
            if not os.path.isfile(path):
                return True
            stats = os.stat(path)
            timedict[path] = stats.st_ctime
            sizedict[path] = stats.st_size

        for key_alias in os.listdir(onecustdir):
            if not misc.ValidKeyAlias(key_alias):
                remove_list[onecustdir] = 'invalid key alias'
                continue
            okekeydir = os.path.join(onecustdir, key_alias)
            bpio.traverse_dir_recursive(cb, okekeydir)
            currentV = 0
            for path in sorted(list(timedict.keys()), key=lambda x: timedict[x], reverse=True):
                filesize = sizedict.get(path, 0)
                currentV += filesize
                if currentV < maxspaceV:
                    continue
                try:
                    os.remove(path)
                    printlog('SpaceTime ' + path + ' file removed (cur:%s, max: %s)' % (str(currentV), str(maxspaceV)))
                except:
                    printlog('SpaceTime ERROR removing ' + path)
                # time.sleep(0.01)

        used_space[idurl] = str(currentV)
        timedict.clear()
        sizedict.clear()

    for path in remove_list.keys():
        if not os.path.exists(path):
            continue
        if os.path.isdir(path):
            try:
                bpio._dir_remove(path)
                printlog('SpaceTime ' + path + ' dir removed (%s)' % (remove_list[path]))
            except:
                printlog('SpaceTime ERROR removing ' + path)
            continue
        try:
            if not os.access(path, os.W_OK):
                os.chmod(path, 0o600)
        except:
            pass
        try:
            os.remove(path)
            printlog('SpaceTime ' + path + ' file removed (%s)' % (remove_list[path]))
        except:
            printlog('SpaceTime ERROR removing ' + path)
    del remove_list
    accounting.update_customers_usage(used_space)

#------------------------------------------------------------------------------


def UpdateCustomers():
    """
    Test packets after list of customers was changed.
    """
    space = accounting.read_customers_quotas()
    if space is None:
        printlog('UpdateCustomers ERROR space file can not be read')
        return
    customers_dir = settings.getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        printlog('UpdateCustomers ERROR customers folder not exist')
        return
    remove_list = {}
    for customer_filename in os.listdir(customers_dir):
        onecustdir = os.path.join(customers_dir, customer_filename)
        if not os.path.isdir(onecustdir):
            remove_list[onecustdir] = 'is not a folder'
            continue
        # idurl = nameurl.FilenameUrl(customer_filename)
        idurl = global_id.GlobalUserToIDURL(customer_filename)
        if idurl is None:
            remove_list[onecustdir] = 'wrong folder name'
            continue
        curspace = space.get(idurl, None)
        if curspace is None:
            remove_list[onecustdir] = 'is not a customer'
            continue
    for path in remove_list.keys():
        if not os.path.exists(path):
            continue
        if os.path.isdir(path):
            try:
                bpio._dir_remove(path)
                printlog('UpdateCustomers ' + path + ' folder removed (%s)' % (remove_list[path]))
            except:
                printlog('UpdateCustomers ERROR removing ' + path)
            continue
        try:
            if not os.access(path, os.W_OK):
                os.chmod(path, 0o600)
        except:
            pass
        try:
            os.remove(path)
            printlog('UpdateCustomers ' + path + ' file removed (%s)' % (remove_list[path]))
        except:
            printlog('UpdateCustomers ERROR removing ' + path)
    printlog('UpdateCustomers ' + str(time.strftime("%a, %d %b %Y %H:%M:%S +0000")))

#------------------------------------------------------------------------------


def Validate():
    """
    Check all packets to be valid.
    """
    printlog('Validate ' + str(time.strftime("%a, %d %b %Y %H:%M:%S +0000")))
    contactsdb.init()
    commands.init()
    customers_dir = settings.getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        return
    for customer_filename in os.listdir(customers_dir):
        onecustdir = os.path.join(customers_dir, customer_filename)
        if not os.path.isdir(onecustdir):
            continue
        for key_alias_filename in os.listdir(onecustdir):
            onekeydir = os.path.join(onecustdir, key_alias_filename)
            if not os.path.isdir(onekeydir):
                continue

            def cb(path, subpath, name):
                #             if not os.access(path, os.R_OK | os.W_OK):
                #                 return False
                if not os.path.isfile(path):
                    return True
    #             if name in [settings.BackupIndexFileName(),]:
    #                 return False
                packetsrc = bpio.ReadBinaryFile(path)
                if not packetsrc:
                    try:
                        os.remove(path)  # if is is no good it is of no use to anyone
                        printlog('Validate ' + path + ' removed (empty file)')
                    except:
                        printlog('Validate ERROR removing ' + path)
                        return False
                p = signed.Unserialize(packetsrc)
                if p is None:
                    try:
                        os.remove(path)  # if is is no good it is of no use to anyone
                        printlog('Validate ' + path + ' removed (unserialize error)')
                    except:
                        printlog('Validate ERROR removing ' + path)
                        return False
                result = p.Valid()
                packetsrc = ''
                del p
                if not result:
                    try:
                        os.remove(path)  # if is is no good it is of no use to anyone
                        printlog('Validate ' + path + ' removed (invalid packet)')
                    except:
                        printlog('Validate ERROR removing ' + path)
                        return False
                time.sleep(0.1)
                return False
            bpio.traverse_dir_recursive(cb, onekeydir)

#------------------------------------------------------------------------------


def main():
    """
    Entry point.
    """
    if len(sys.argv) < 2:
        return
    bpio.init()
    lg.disable_logs()
    lg.disable_output()
    settings.init()
    lg.set_debug_level(0)
    commands = {
        'update_customers': UpdateCustomers,
        'validate': Validate,
        'space_time': SpaceTime,
    }
    cmd = commands.get(sys.argv[1], None)
    if not cmd:
        printlog('ERROR wrong command: ' + str(sys.argv))
        return
    cmd()
#    bpio.stdout_stop_redirecting()
#    bpio.CloseLogFile()

#------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
