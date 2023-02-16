#!/usr/bin/env python
# bptester.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False

#------------------------------------------------------------------------------

import os
import sys
import time
from io import open

#------------------------------------------------------------------------------

AppData = ''
CurrentNetwork = ''

#------------------------------------------------------------------------------


def sharedPath(filename, subdir='logs'):
    global AppData
    global CurrentNetwork
    if not AppData:
        curdir = os.getcwd()  # os.path.dirname(os.path.abspath(sys.executable))
        if os.path.isfile(os.path.join(curdir, 'appdata')):
            try:
                appdata = os.path.abspath(open(os.path.join(curdir, 'appdata'), 'r').read().strip())
            except:
                appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
            if not os.path.isdir(appdata):
                appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
        else:
            if sys.executable == 'android_python' or ('ANDROID_ARGUMENT' in os.environ or 'ANDROID_ROOT' in os.environ):
                from android.storage import app_storage_path  # @UnresolvedImport
                appdata = os.path.join(app_storage_path(), '.bitdust')
            else:
                appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
        AppData = appdata
    if not CurrentNetwork:
        try:
            cur_network = open(os.path.join(AppData, 'current_network'), 'r').read().strip()
        except:
            cur_network = 'default'
        if not os.path.isdir(os.path.join(AppData, cur_network)):
            cur_network = 'default'
        CurrentNetwork = cur_network
    return os.path.join(AppData, CurrentNetwork, subdir, filename)


def logfilepath():
    """
    A file path to the file where ``bptester`` will write logs.

    Need to make sure the ``bptester`` log is in a directory the user
    has permissions for, Such as the customer data directory.  Possibly
    move to temp directory?
    """
    return sharedPath('bptester.log')


def printlog(txt):
    """
    Write a line to the log file.
    """
    try:
        if sys.version_info[0] == 3:
            if not isinstance(txt, str):
                txt = txt.decode()
        else:
            if not isinstance(txt, unicode):  # @UndefinedVariable
                txt = txt.decode()
        lf = open(logfilepath(), 'a')
        lf.write(txt + '\n')
        lf.close()
    except:
        pass


#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.system import bpio

from bitdust.lib import misc

from bitdust.crypt import signed

from bitdust.storage import accounting

from bitdust.main import settings

from bitdust.userid import global_id
from bitdust.userid import id_url

#-------------------------------------------------------------------------------


def SpaceTime():
    """
    Test all packets for each customer.

    Check if he use more space than we gave him and if packets is too
    old.
    """
    if _Debug:
        printlog('SpaceTime %r' % time.strftime('%a, %d %b %Y %H:%M:%S +0000'))
    space, _ = accounting.read_customers_quotas()
    if space is None:
        if _Debug:
            printlog('SpaceTime ERROR customers quotas file can not be read or it is empty, skip')
        return False
    customers_dir = settings.getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        if _Debug:
            printlog('SpaceTime ERROR customers folder not exist: %r' % customers_dir)
        return False
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
        curspace = space.get(idurl.to_bin(), None)
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
            return False

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
                    if _Debug:
                        printlog('SpaceTime %r file removed (cur:%s, max: %s)' % (path, str(currentV), str(maxspaceV)))
                except:
                    if _Debug:
                        printlog('SpaceTime ERROR removing %r' % path)
                # time.sleep(0.01)

        used_space[idurl.to_bin()] = str(currentV)
        timedict.clear()
        sizedict.clear()

    for customer_idurl_bin in list(used_space.keys()):
        if not id_url.field(customer_idurl_bin).is_latest():
            latest_customer_idurl_bin = id_url.field(customer_idurl_bin).to_bin()
            if latest_customer_idurl_bin != customer_idurl_bin:
                used_space[latest_customer_idurl_bin] = used_space.pop(customer_idurl_bin)
                if _Debug:
                    printlog('found customer idurl rotated in customer usage dictionary : %r -> %r' % (
                        latest_customer_idurl_bin,
                        customer_idurl_bin,
                    ))

    for path in remove_list.keys():
        if not os.path.exists(path):
            continue
        if os.path.isdir(path):
            try:
                bpio._dir_remove(path)
                if _Debug:
                    printlog('SpaceTime %r dir removed (%s)' % (path, remove_list[path]))
            except:
                if _Debug:
                    printlog('SpaceTime ERROR removing %r' % path)
            continue
        try:
            if not os.access(path, os.W_OK):
                os.chmod(path, 0o600)
        except:
            pass
        try:
            os.remove(path)
            if _Debug:
                printlog('SpaceTime %r file removed (%s)' % (path, remove_list[path]))
        except:
            if _Debug:
                printlog('SpaceTime ERROR removing %r' % path)
    del remove_list

    accounting.update_customers_usage(used_space)

    return True


#------------------------------------------------------------------------------


def UpdateCustomers():
    """
    Test packets after list of customers was changed.
    """
    space, _ = accounting.read_customers_quotas()
    if space is None:
        if _Debug:
            printlog('UpdateCustomers ERROR space file can not be read')
        return False
    customers_dir = settings.getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        if _Debug:
            printlog('UpdateCustomers ERROR customers folder not exist')
        return False

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
        curspace = space.get(idurl.to_bin(), None)
        if curspace is None:
            remove_list[onecustdir] = 'is not a customer'
            continue

    for path in remove_list.keys():
        if not os.path.exists(path):
            continue
        if os.path.isdir(path):
            try:
                bpio._dir_remove(path)
                if _Debug:
                    printlog('UpdateCustomers %r folder removed (%s)' % (
                        path,
                        remove_list[path],
                    ))
            except:
                if _Debug:
                    printlog('UpdateCustomers ERROR removing %r' % path)
            continue
        try:
            if not os.access(path, os.W_OK):
                os.chmod(path, 0o600)
        except:
            pass
        try:
            os.remove(path)
            if _Debug:
                printlog('UpdateCustomers %r file removed (%s)' % (
                    path,
                    remove_list[path],
                ))
        except:
            if _Debug:
                printlog('UpdateCustomers ERROR removing %r' % path)
    if _Debug:
        printlog('UpdateCustomers %r' % time.strftime('%a, %d %b %Y %H:%M:%S +0000'))
    return True


#------------------------------------------------------------------------------


def Validate():
    """
    Check all packets to be valid.
    """
    if _Debug:
        printlog('Validate %r' % time.strftime('%a, %d %b %Y %H:%M:%S +0000'))
    customers_dir = settings.getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        return False

    for customer_filename in os.listdir(customers_dir):
        onecustdir = os.path.join(customers_dir, customer_filename)
        if not os.path.isdir(onecustdir):
            continue
        for key_alias_filename in os.listdir(onecustdir):
            onekeydir = os.path.join(onecustdir, key_alias_filename)
            if not os.path.isdir(onekeydir):
                continue

            def cb(path, subpath, name):
                if not os.path.isfile(path):
                    return True
                packetsrc = bpio.ReadBinaryFile(path)
                if not packetsrc:
                    try:
                        os.remove(path)  # if is is no good it is of no use to anyone
                        if _Debug:
                            printlog('Validate %r removed (empty file)' % path)
                    except:
                        if _Debug:
                            printlog('Validate ERROR removing %r' % path)
                        return False
                p = signed.Unserialize(packetsrc)
                if p is None:
                    try:
                        os.remove(path)  # if is is no good it is of no use to anyone
                        if _Debug:
                            printlog('Validate %r removed (unserialize error)' % path)
                    except:
                        if _Debug:
                            printlog('Validate ERROR removing %r')
                        return False
                result = p.Valid()
                packetsrc = ''
                del p
                if not result:
                    try:
                        os.remove(path)  # if is is no good it is of no use to anyone
                        if _Debug:
                            printlog('Validate %r removed (invalid packet)' % path)
                    except:
                        if _Debug:
                            printlog('Validate ERROR removing %r' % path)
                        return False
                time.sleep(0.1)
                return False

            bpio.traverse_dir_recursive(cb, onekeydir)

    return True


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
    id_url.init()
    commands = {
        'update_customers': UpdateCustomers,
        'validate': Validate,
        'space_time': SpaceTime,
    }
    cmd = commands.get(sys.argv[1], None)
    if not cmd:
        if _Debug:
            printlog('ERROR wrong command: %r' % sys.argv)
        return
    cmd()
    settings.shutdown()
    id_url.shutdown()


#------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
