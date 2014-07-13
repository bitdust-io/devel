#!/usr/bin/python
#dhnstarter.py
#
# <<<COPYRIGHT>>>-2011
#
#
#
#

"""
.. module:: dhnstarter

This is a Windows starter process.
It is used to check and update binaries at start up. 
"""

import os
import sys
import hashlib
import platform
import time
import subprocess
import tempfile
import win32process

from distutils.dir_util import copy_tree
from twisted.python.win32 import cmdLineQuote

import EasyDialogs

#------------------------------------------------------------------------------

def sharedPath(filename, subdir='logs'):
    appdata = os.path.expanduser('~')
    sharedDir = os.path.join(appdata, '.bitpie', subdir)
    if filename is None:
        return os.path.abspath(sharedDir)
    return os.path.abspath(os.path.join(sharedDir, filename))

#------------------------------------------------------------------------------ 

StarterFilename = os.path.basename(sys.argv[0].lower()) #'dhnstarter.exe'

UpdateRepo = ''
UpdateLocationURL = ''
DefaultRepo = 'devel'
DefaultUpdateLocationURL = 'http://bitpie.net/repo/devel/'

UpdateFolder = 'windows/'
FilesDigestsFilename = 'info.txt'
CurrentVersionDigestsFilename = 'version.txt'
WGetFilename = 'wget.exe'
MainExecutableFilename = 'dhnmain.exe'
StarterFilename = 'dhnstarter.exe'

LogFilePath = sharedPath('dhnstarter.log', 'logs')
RepoFileName = sharedPath('repo', 'metadata')
FilesDigestsLocalPath = sharedPath('info', 'metadata')
CurrentVersionDigestsLocalPath = sharedPath('version', 'metadata')
WGetLogFilename = sharedPath('wget.log', 'logs')

#ONLY LOWER CASE
ExcludesFiles = [
    'w9xpopen.exe',
    'MSVCR71.dll'.lower(),
    'python25.dll',
    WGetFilename,
    StarterFilename,
    CurrentVersionDigestsFilename,
    FilesDigestsFilename,
    ]

#------------------------------------------------------------------------------

def logcheck():
    global LogFilePath
    try:
        if os.path.getsize(LogFilePath) >= 100 * 1024:
            os.remove(LogFilePath)
    except:
        pass

def logwrite(txt, mode='a'):
    global LogFilePath
    fout = open(LogFilePath, mode)
    fout.write(txt)
    fout.close()

def read_file(filename, mode='rb'):
    try:
        file = open(filename, mode)
        data = file.read()
        file.close()
        if mode == 'r':
            data = data.replace('\r\n','\n')
        return data
    except:
        return ''

def make_hash(data):
    return hashlib.md5(data).hexdigest()

def file_hash(filename):
    return make_hash(read_file(filename))

def run_wget(url, filename):
    cmd = '%s --no-check-certificate -o%s -O%s -T60 %s' % (WGetFilename, cmdLineQuote(WGetLogFilename), cmdLineQuote(filename), url)
    logwrite('%s\n' % cmd)
    return subprocess.call(cmd, shell=True)

def find_process_win32(applist):
    pidsL = []
    try:
        import win32com.client
        objWMI = win32com.client.GetObject("winmgmts:\\\\.\\root\\CIMV2")
        colProcs = objWMI.ExecQuery("SELECT * FROM Win32_Process")
        for Item in colProcs:
            pid = int(Item.ProcessId)
            if pid == os.getpid():
                continue
            search_str = Item.Caption.lower()
            if Item.CommandLine:
                search_str += Item.CommandLine.lower()
            for app in applist:
                if search_str.find(app) != -1:
                    pidsL.append(pid)
    except:
        logwrite('error in find_process_win32\n')
    return pidsL

def kill_process_win32(pid):
    try:
        from win32api import TerminateProcess, OpenProcess, CloseHandle
        PROCESS_TERMINATE = 1
        handle = OpenProcess(PROCESS_TERMINATE, False, pid)
        TerminateProcess(handle, -1)
        CloseHandle(handle)
    except:
        logwrite('error in kill_process_win32\n')

def stop_all(search_list):
    total_count = 0
    while True:
        count = 0
        appList = find_process_win32(search_list)
        for pid in appList:
            count +=1
            kill_process_win32(pid)
        if len(appList) == 0:
            break
        total_count += 1
        if total_count > 10:
            return 'error killing process '+str(appList)
        time.sleep(1)
    return 0

def launch(show):
    logwrite('launch %s show=%s\n' % (MainExecutableFilename, show))
    try:
        if show:
            subprocess.Popen([MainExecutableFilename, 'show'])
        else:
            subprocess.Popen([MainExecutableFilename,])
    except:
        return 'error starting dhnmain.exe'
    return 0

def uninstall():
    def make_bat_file():
        wait_appname = StarterFilename
        local_dir = os.path.abspath(os.path.dirname(os.path.abspath(sys.executable)))
        dirs2delete = [ sharedPath(None, '.'), os.path.join(tempfile.gettempdir(), 'dhn') ]
        logwrite('make_bat_file\n')
        batfileno, batfilename = tempfile.mkstemp('.bat', 'BitPie.NET-uninstall-')
        logwrite('batfilename:%s\n' % batfilename)
        logwrite('local_dir:%s\n' % local_dir)
        logwrite('dirs2delete:%s\n' % '\n'.join(dirs2delete))
        batsrc = ''
        batsrc += 'cd "%s"\n' % local_dir
        batsrc += 'del search.log /Q\n'
        batsrc += ':again\n'
        batsrc += 'sleep 1\n'
        batsrc += 'tasklist /FI "IMAGENAME eq %s" /FO CSV > search.log\n' % wait_appname
        batsrc += 'FOR /F %%A IN (search.log) DO IF %%-zA EQU 0 GOTO again\n'
        batsrc += 'cd "%s"\n' % os.path.dirname(os.path.abspath(batfilename))
        for dirpath in dirs2delete:
            batsrc += 'rmdir /S /Q "%s"\n' % os.path.abspath(dirpath)
            one_copy = 'if exist "%s\\NUL" rmdir /S /Q "%s"\n' % (os.path.abspath(dirpath), os.path.abspath(dirpath))
            batsrc += (one_copy * 20) 
        batsrc += 'rem del /F /S /Q "%s"\n' % os.path.abspath(batfilename)
        os.write(batfileno, batsrc)
        os.close(batfileno)
        logwrite('bat source:\n')
        logwrite(batsrc)
        return os.path.abspath(batfilename)
    
    def remove_registry_uninstall():
        try:
            import _winreg
        except:
            return False
        unistallpath = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall" 
        regpath = unistallpath + "\\BitPie.NET"
    
        # open
        try:
            reg = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, regpath, 0, _winreg.KEY_ALL_ACCESS)
        except:
            try:
                reg = _winreg.CreateKey(_winreg.HKEY_LOCAL_MACHINE, regpath)
            except:
                return False
    
        # check
        i = 0
        while True:
            try:
                name, value, typ = _winreg.EnumValue(reg, i)
            except:
                break
            i += 1
            try:
                _winreg.DeleteKey(reg, name)
            except:
                try:
                    _winreg.DeleteValue(reg, name)
                except:
                    pass
    
        # delete
        _winreg.CloseKey(reg)
        try:
            reg = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, unistallpath, 0, _winreg.KEY_ALL_ACCESS)
        except:
            return False
        try:
            _winreg.DeleteKey(reg, 'BitPie.NET')
        except:
            _winreg.CloseKey(reg)
            return False
        _winreg.CloseKey(reg)
        return True
    
    logwrite('uninstall()\n')
    ret = stop_all([
            'dhnstarter.exe',
            'dhnmain.exe',
            'dhnview.exe'
            'dhntester.exe',
            'dhnbackup.exe'])
    if ret != 0:
        return ret  
    logwrite('start uninstalling\n')
    remove_registry_uninstall()
    batfilename = make_bat_file()
    #misc.UpdateRegistryUninstall(True)
    cmd = os.path.abspath(batfilename).replace('\\', '/')
    logwrite('cmd:%s\n' % cmd)
    p = subprocess.Popen(cmd, shell=True, creationflags=win32process.CREATE_NO_WINDOW,)
    return ret
       

def main():
    logwrite('main()\n')
    
    global ExcludesFiles
    global UpdateLocationURL
    global UpdateRepo
    global RepoFileName
    global DefaultUpdateLocationURL
    global DefaultRepo
    global FilesDigestsFilename
    global FilesDigestsLocalPath
    global CurrentVersionDigestsLocalPath
    global StarterFilename
    
    #if we need to stop - we kill all running instances and exit
    if sys.argv.count('stop'):
        #we want to check if another instance is running
        return stop_all([
            'dhnstarter.exe',
            'dhnmain.exe',
            'dhnmain.py',
            'dhnview.exe',
            'dhnview.py',
            'bitpie.py',
            ])

    search_list = ['dhnstarter.exe',]
    # if we do not need to stop,
    # but still other instance is running
    # we do not want to work together. EXIT.
    if len(find_process_win32(search_list)) > 0:
        logwrite('another dhnstarter.exe found working')
        return 0

    show = False
    if sys.argv.count('show') or sys.argv.count('install'):
        show = True

    if not show:
        #if dhnmain.exe or dhnview.exe is running - stop it.
        search_list.extend([
            'dhnmain.exe',
            'dhnmain.py',
            'dhnview.exe',
            'dhnview.py',
            'bitpie.py',
            ])
        res = stop_all(search_list)
        if res != 0:
            return res

    #read file "info"
    if os.path.isfile(FilesDigestsLocalPath):
        src = read_file(FilesDigestsLocalPath, 'r')
        if src == '':
            logwrite('file %s is empty\n' % FilesDigestsLocalPath)
    else:
        logwrite('file not found: %s\n' % FilesDigestsLocalPath)
        src = read_file(os.path.join(os.path.dirname(
            os.path.abspath(sys.executable)), FilesDigestsFilename), 'r')
        if src != '':
            logwrite('take %s from the current executable folder\n' % FilesDigestsFilename)
        else:
            logwrite('file %s in the current executable folder is empty or not exist\n' % FilesDigestsFilename)
            
    logwrite('info length: ' + str(len(src)) + '\n')

    if os.path.isfile(CurrentVersionDigestsLocalPath):
        cur_version = read_file(CurrentVersionDigestsLocalPath, 'r').strip()
        if cur_version == '':
            logwrite('file %s is empty\n' % CurrentVersionDigestsLocalPath)
    else:
        logwrite('file not found: %s\n' % CurrentVersionDigestsLocalPath)
        cur_version = read_file(os.path.join(os.path.dirname(
            os.path.abspath(sys.executable)), CurrentVersionDigestsFilename), 'r').strip()
        if cur_version != '':
            logwrite('take %s from the current executable folder\n' % CurrentVersionDigestsFilename)
        else:
            logwrite('file %s in the current executable folder is empty or not exist\n' % CurrentVersionDigestsFilename)

    logwrite('current version is: %s\n' % cur_version)

    #if local info is not exist, or it is empty - we want to download it from the server
    if src.strip() == '':
        url = UpdateLocationURL + FilesDigestsFilename
        logwrite('want to download %s\n' % url)

        if run_wget(url, FilesDigestsLocalPath):
            logwrite('wget error url=%s\n' % url)
            return 1

        if not os.path.isfile(FilesDigestsLocalPath):
            logwrite('file not found %s\n' % FilesDigestsLocalPath)
            return 1

        src = read_file(FilesDigestsLocalPath, 'r')
        if src == '':
            logwrite('error when reading from file %s\n' % FilesDigestsLocalPath)
            return 1

    # make new version digest from info file
    new_version = make_hash(src)
    logwrite('the new version is: %s\n' % new_version)

    # and compare with current version
    if new_version == cur_version and cur_version != '':
        # digests are equal so our binaries have latest version - ready to start
        logwrite('version was not changed\n')

        # also try to remove info.txt and version.txt in the current folder
        # they can be here because included in the installation release
        # so they needed only during first start of the dhnstarter.exe
        # if we did not start with param "install" - we do not need them at all
        if sys.argv.count('install') == 0:
            try:
                if os.path.exists('info.txt'):
                    os.remove('info.txt')
                if os.path.exists('version.txt'):
                    os.remove('version.txt')
            except:
                logwrite('can not remove info.txt or version.txt from current folder\n')
        return launch(show)

    # so versions is not the same - save the new version 
    logwrite('save the new version to %s\n' % CurrentVersionDigestsLocalPath)
    try:
        fout = open(CurrentVersionDigestsLocalPath, 'w')
        fout.write(new_version)
        fout.close()
    except:
        logwrite('error writing to %s\n' % CurrentVersionDigestsLocalPath)

    #reading files hash values from info file
    current_info = {}
    for line in src.strip().split('\n'):
        words = line.split(' ')
        if len(words) < 2:
            continue
        fname = words[1].strip()
        #we do not want to check or download this files:
        if os.path.basename(fname.lower()) in ExcludesFiles:
            continue
        current_info[fname] = words[0].strip()

    logwrite('current info files ' + str(len(current_info)) +'\n')

    #read hash values for all files in the current folder
    local_info = {}
    logwrite('current path:  %s\n' % os.path.abspath('.'))
    # executable_filename = os.path.abspath(sys.argv[0])
    # fullpath = os.path.dirname(executable_filename)
    # fullpath = os.path.abspath('.')
    fullpath = sharedPath('', 'bin')
    logwrite('new path:      %s\n' % fullpath)
    for root, dirs, files in os.walk(fullpath):
        for fname in files:
            abspath = os.path.abspath(os.path.join(root, fname))
            relpath = abspath[len(fullpath)+1:]
            local_info[relpath] = file_hash(abspath)

    logwrite('local files %s\n' % str(len(local_info)) )

    #compare hash values
    download_list = []
    for fpath in current_info.keys():
        #if some file are missing - we want to download it
        if not local_info.has_key(fpath):
            logwrite('%s - missied\n' % fpath)
            download_list.append(fpath)
            continue
        #if some file hash is different - we want to download it and overwrite existing
        if local_info[fpath] != current_info[fpath]:
            logwrite('%s - hash is not the same\n' % fpath)
            download_list.append(fpath)
            continue

    logwrite('files to download: %s\n' % str(len(download_list)))

    download_list.sort()

    if len(download_list) > 0:
        try:
            dlg = None
            dlgshow = False

            if show:
                dlgshow = True

            if dlgshow:
                dlg = EasyDialogs.ProgressBar(
                    'Updating BitPie.NET',
                    len(download_list),
                    '')

            #we want to download needed files
            for path in download_list:
                url = UpdateLocationURL + UpdateFolder + path
                url = url.replace('\\', '/')
                filename = os.path.join('.', path)
                dirname = os.path.dirname(filename)
##                if os.path.exists(filename):
##                    try:
##                        os.remove(filename)
##                    except:
##                        pass
                if not os.path.isdir(dirname):
                    try:
                        os.makedirs(dirname)
                    except:
                        pass

                if dlg:
                    dlg.label( '%s' % (path) )

                filenameWget = filename+'.wget'
                if os.path.isfile(filenameWget):
                    try:
                        os.remove(filenameWget)
                    except:
                        logwrite('wget warning can not remove filename=%s\n' % filenameWget)

                if run_wget(url, filenameWget):
                    logwrite('wget error url=%s filename=%s\n' % (url, filenameWget))

                else:
                    h = file_hash(filenameWget)
                    if h == current_info[path]:
                        try:
                            if os.path.isfile(filename):
                                os.remove(filename)
                                logwrite('REMOVED: %s\n' % path)
                        except:
                            logwrite('can not remove %s\n' % (filename))
                        try:
                            os.rename(filenameWget, filename)
                            logwrite('UPDATED: %s\n' % path)
                        except:
                            logwrite('can not rename %s->%s\n' % (filenameWget, filename))
                    else:
                        logwrite('incorrect file %s :  hash values is not equal\n' % path)

                if dlg:
                    dlg.inc()

            if dlg:
                del dlg
                dlg = None

        except KeyboardInterrupt:
            return 'canceled'

    #finally - start dhnmain.exe and exit
    return launch(show)


def run():
    global UpdateLocationURL
    global UpdateRepo
    global RepoFileName
    global DefaultUpdateLocationURL
    global DefaultRepo
    global FilesDigestsFilename
    global FilesDigestsLocalPath
    global CurrentVersionDigestsLocalPath
    global StarterFilename
    
    if hasattr(sys, 'frozen'):
        executable_filename = os.path.abspath(sys.executable)
    else:
        executable_filename = os.path.abspath(sys.argv[0])
    sharedStarterFilename = sharedPath(StarterFilename, 'bin')
    binDirExist = os.path.isdir(sharedPath(None, 'bin'))

    if not os.path.isdir(sharedPath('', 'bin')):
        os.makedirs(sharedPath('', 'bin'))

    if not os.path.isdir(sharedPath('', 'logs')):
        os.makedirs(sharedPath('', 'logs'))

    if not os.path.isdir(sharedPath('', 'metadata')):
        os.makedirs(sharedPath('', 'metadata'))

    logcheck()
    if sys.argv.count('uninstall'):
        return uninstall()

    try:
        UpdateRepo, UpdateLocationURL = read_file(RepoFileName, 'r').split('\n')
    except:
        logwrite('can\'t read repo file from %s\n' % RepoFileName)
        UpdateRepo = ''
        UpdateLocationURL = ''
    if UpdateRepo.strip() == '' or UpdateLocationURL.strip() == '':
        logwrite('empty repo file, use default repo\n')
        UpdateRepo = DefaultRepo
        UpdateLocationURL = DefaultUpdateLocationURL

    logwrite('[%s]--------------------------------------\n' % time.asctime())
    logwrite('sys.argv:%s \n' % (str(sys.argv)))
    logwrite('update repo: %s\n' % UpdateRepo)
    logwrite('update location: %s\n' % UpdateLocationURL)
    logwrite('is bin folder exist? : %s\n' % str(binDirExist))
    logwrite('executable filename is [%s]\n' % executable_filename)
    logwrite('shared location is     [%s]\n' % sharedStarterFilename)

    if (not binDirExist) or executable_filename != sharedStarterFilename:
        #if dhn is running - stop it.
        res = stop_all([    'dhnstarter.',
                            'dhnmain.',
                            'dhnview.',
                            'bitpie.',
                            ])
        if res != 0:
            logwrite('can not stop dhn: %s\n' % res)
            sys.exit(res)

        logwrite('copy files to %s\n' % sharedPath('', 'bin'))
        try:
            copy_tree( os.path.dirname(executable_filename),
                       sharedPath('', 'bin'))
        except:
            logwrite('can not copy tree %s to %s\n' % (
                os.path.dirname(executable_filename),
                sharedPath('', 'bin')))

        logwrite('cd to bin\n')
        os.chdir(sharedPath('', 'bin'))

        try:
            os.remove(FilesDigestsLocalPath)
        except:
            logwrite('can not remove %s\n' % FilesDigestsLocalPath)

        exepath = sharedStarterFilename
        cmdargs = [StarterFilename,]
        if sys.argv.count('show') or sys.argv.count('install'):
            cmdargs.append('show')
        logwrite('launch %s cmdargs=%s' % (exepath, str(cmdargs)))
        os.spawnv(os.P_DETACH, exepath, cmdargs)
        sys.exit(0)

    else:
        os.chdir(sharedPath('', 'bin'))

    retcode = main()

    if retcode == 1:
        launch(sys.argv.count('show') or sys.argv.count('install'))

    elif retcode != 0:
        logwrite('retcode='+retcode+'\n')


if __name__ == "__main__":
    run()




