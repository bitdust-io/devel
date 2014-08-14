#!/usr/bin/python
#bptester.py
#
# <<<COPYRIGHT>>>-2011
#
#
#
#

"""
.. module:: bptester

This is a BitPie.NET child process, do monitoring of customer's files.

In case some of customers do not play fair - need to stop this.:
   
    * check if he use more space than we gave him, remove too old files
    * test/remove files after list of customers was changed
    * check all packets to be valid
"""

import os
import sys
import time

#------------------------------------------------------------------------------ 

def logfilepath():
    """
    A file path to the file where ``bptester`` will write logs. 
    Need to make sure the ``bptester`` log is in a directory the user has permissions for,
    Such as the customer data directory.  Possibly move to temp directory?
    """
    logspath = os.path.join(os.path.expanduser('~'), '.bitpie', 'logs')
    if not os.path.isdir(logspath):
        return 'tester.log'
    return os.path.join(logspath, 'tester.log')

def printlog(txt):
    """
    Write a line to the log file.
    """
    LogFile = open(logfilepath(), 'a')
    LogFile.write(txt+'\n')
    LogFile.close()
    
#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))

try:
    from logs import lg
    from lib import bpio
    from lib.nameurl import FilenameUrl
    from lib.settings import init as settings_init
    from lib.settings import CustomersSpaceFile, CustomersUsedSpaceFile, getCustomersFilesDir, LocalTesterLogFilename
    from lib.settings import BackupIndexFileName
    from lib.contacts import init as contacts_init
    from lib.commands import init as commands_init
    from crypto.signed import Unserialize
except:
    import traceback
    printlog(traceback.format_exc())
    sys.exit(2)

# sys.stdout = myoutput
# sys.stderr = myoutput

#-------------------------------------------------------------------------------

def SpaceTime():
    """
    Test all packets for each customer.
    Check if he use more space than we gave him and if packets is too old.
    """
    printlog('SpaceTime ' + str(time.strftime("%a, %d %b %Y %H:%M:%S +0000")))
    space = bpio._read_dict(CustomersSpaceFile())
    if space is None:
        printlog('SpaceTime ERROR can not read file ' + CustomersSpaceFile())
        return
    customers_dir = getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        printlog('SpaceTime ERROR customers folder not exist')
        return
    remove_list = {}
    used_space = {}
    for customer_filename in os.listdir(customers_dir):
        onecustdir = os.path.join(customers_dir, customer_filename)
        if not os.path.isdir(onecustdir):
            remove_list[onecustdir] = 'is not a folder'
            continue
        idurl = FilenameUrl(customer_filename)
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
            if not os.access(path, os.R_OK | os.W_OK):
                return False
            if not os.path.isfile(path):
                return True
            if name in [BackupIndexFileName(),]:
                return False
            stats = os.stat(path)
            timedict[path] = stats.st_ctime
            sizedict[path] = stats.st_size
        bpio.traverse_dir_recursive(cb, onecustdir)
        currentV = 0
        for path in sorted(timedict.keys(), key=lambda x:timedict[x], reverse=True):
            filesize = sizedict.get(path, 0)
            currentV += filesize
            if currentV < maxspaceV:
                continue
            try:
                os.remove(path)
                printlog('SpaceTime ' + path + ' file removed (cur:%s, max: %s)' % (str(currentV), str(maxspaceV)) )
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
        if not os.access(path, os.W_OK):
            os.chmod(path, 0600)
        try:
            os.remove(path)
            printlog('SpaceTime ' + path + ' file removed (%s)' % (remove_list[path]))
        except:
            printlog('SpaceTime ERROR removing ' + path)
    del remove_list
    bpio._write_dict(CustomersUsedSpaceFile(), used_space)

#------------------------------------------------------------------------------

def UpdateCustomers():
    """
    Test packets after list of customers was changed.
    """
    space = bpio._read_dict(CustomersSpaceFile())
    if space is None:
        printlog('UpdateCustomers ERROR space file can not be read' )
        return
    customers_dir = getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        printlog('UpdateCustomers ERROR customers folder not exist')
        return
    remove_list = {}
    for customer_filename in os.listdir(customers_dir):
        onecustdir = os.path.join(customers_dir, customer_filename)
        if not os.path.isdir(onecustdir):
            remove_list[onecustdir] = 'is not a folder'
            continue
        idurl = FilenameUrl(customer_filename)
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
        if not os.access(path, os.W_OK):
            os.chmod(path, 0600)
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
    contacts_init()
    commands_init()
    customers_dir = getCustomersFilesDir()
    if not os.path.exists(customers_dir):
        return
    for customer_filename in os.listdir(customers_dir):
        onecustdir = os.path.join(customers_dir, customer_filename)
        if not os.path.isdir(onecustdir):
            continue
        def cb(path, subpath, name):
            if not os.access(path, os.R_OK | os.W_OK):
                return False
            if not os.path.isfile(path):
                return True
            if name in [BackupIndexFileName(),]:
                return False
            packetsrc = bpio.ReadBinaryFile(path)
            if not packetsrc:
                try:
                    os.remove(path) # if is is no good it is of no use to anyone
                    printlog('Validate ' + path + ' removed (empty file)')
                except:
                    printlog('Validate ERROR removing ' + path)
                    return False
            p = Unserialize(packetsrc)
            if p is None:
                try:
                    os.remove(path) # if is is no good it is of no use to anyone
                    printlog('Validate ' + path + ' removed (unserialize error)')
                except:
                    printlog('Validate ERROR removing ' + path)
                    return False
            result = p.Valid()
            packetsrc = ''
            del p
            if not result:
                try:
                    os.remove(path) # if is is no good it is of no use to anyone
                    printlog('Validate ' + path + ' removed (invalid packet)')
                except:
                    printlog('Validate ERROR removing ' + path)
                    return False
            # time.sleep(0.1)
            return False
        bpio.traverse_dir_recursive(cb, onecustdir)

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
    settings_init()
    lg.set_debug_level(0)
    commands = {
        'update_customers' : UpdateCustomers,
        'validate' : Validate,
        'space_time' : SpaceTime,
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






