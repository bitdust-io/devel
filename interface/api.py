#!/usr/bin/python
#api.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: api

Here is a bunch of methods to interact with BitPie.NET software.
"""

#------------------------------------------------------------------------------ 

def stop():
    from logs import lg
    lg.out(2, 'api.stop sending event "stop" to the shutdowner() machine')
    from main import shutdowner
    shutdowner.A('stop', 'exit')
    

def restart():
    from logs import lg
    from system import bpio
    from main import shutdowner
    appList = bpio.find_process(['bpgui.',])
    if len(appList) > 0:
        lg.out(2, 'api.restart found bpgui process, added param "show", sending event "stop" to the shutdowner() machine')
        shutdowner.A('stop', 'restartnshow')
        return 'restarted with GUI'
    lg.out(2, 'api.restart did not found bpgui process, just do the restart, sending event "stop" to the shutdowner() machine')
    shutdowner.A('stop', 'restart')
    return 'restarted'


def show():
    from web import webcontrol
    webcontrol.show()
    
#------------------------------------------------------------------------------ 

def backups_list():
    from storage import backup_fs
    result = []
    for pathID, localPath, item in backup_fs.IterateIDs():
        result.append((pathID, localPath, item))
    return result


def backups_id_list():
    from storage import backup_fs
    from userid import contacts
    from lib import diskspace
    result = []
    for backupID, versionInfo, localPath in backup_fs.ListAllBackupIDsFull(True, True):
        if versionInfo[1] >= 0 and contacts.numSuppliers() > 0:
            szver = diskspace.MakeStringFromBytes(versionInfo[1]) + ' / ' + diskspace.MakeStringFromBytes(versionInfo[1]/contacts.numSuppliers()) 
        else:
            szver = '?'
        szver = diskspace.MakeStringFromBytes(versionInfo[1]) if versionInfo[1] >= 0 else '?'
        result.append((backupID, szver, localPath))
    return result


def backup_start_id(pathID):
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    localPath = backup_fs.ToPath(pathID)
    if localPath is not None:
        if bpio.pathExist(localPath):
            backup_control.StartSingle(pathID)
            backup_fs.Calculate()
            backup_control.Save()
            return (localPath, 'backup started : %s' % pathID)
    else:
        return 'item %s not found' % pathID

    
def backup_start_path(path):
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    localPath = unicode(path)
    if not bpio.pathExist(localPath):
        return 'local path %s not found' % path
    result = []
    pathID = backup_fs.ToID(localPath)
    if pathID is None:
        if bpio.pathIsDir(localPath):
            pathID, iter, iterID = backup_fs.AddDir(localPath, True)
            result.append('new folder was added: %s' % localPath)
        else:
            pathID, iter, iterID = backup_fs.AddFile(localPath, True)
            result.append('new file was added: %s' % localPath)
    backup_control.StartSingle(pathID)
    backup_fs.Calculate()
    backup_control.Save()
    result.append('backup started: %s' % pathID)
    return result

        
def backup_dir_add(dirpath):
    from storage import backup_fs
    from storage import backup_control
    from system import dirsize
    newPathID, iter, iterID = backup_fs.AddDir(dirpath, True)
    dirsize.ask(dirpath, backup_control.FoundFolderSize, (newPathID, None))
    backup_fs.Calculate()
    backup_control.Save()
    return 'new folder was added: %s %s' % (newPathID, dirpath)


def backup_file_add(filepath):    
    from storage import backup_fs
    from storage import backup_control
    newPathID, iter, iterID = backup_fs.AddFile(filepath, True)
    backup_fs.Calculate()
    backup_control.Save()
    return 'new file was added: %s %s' % (newPathID, filepath)


def backup_tree_add(dirpath):
    from storage import backup_fs
    from storage import backup_control
    from lib import packetid
    newPathID, iter, iterID, num = backup_fs.AddLocalPath(dirpath, True)
    backup_fs.Calculate()
    backup_control.Save()
    if not newPathID:
        return 'nothing was added to catalog'
    return '%d items were added to catalog, parent path ID is: %s  %s' % (
        num, newPathID, dirpath)

#------------------------------------------------------------------------------ 

def list_messages():
    from chat import message
    mlist = message.ListAllMessages()
    mlist.sort(key=lambda item: item[3])
    return mlist
    
    
def send_message(recipient, subject, body):
    from chat import message
    if not recipient.startswith('http://'):
        from userid import contacts
        for idurl, nickname in contacts.getCorrespondentsDict().items():
            if recipient == nickname:
                recipient = idurl
                break 
    msgbody = message.MakeMessage(recipient, subject, body)
    message.SendMessage(recipient, msgbody)
    message.SaveMessage(msgbody)
    return msgbody
    

def find_peer_by_nickname(nickname):
    from twisted.internet.defer import Deferred
    from userid import nickname_observer
    nickname_observer.stop_all()
    d = Deferred()
    nickname_observer.find_one(nickname, 
        results_callback=lambda result, nik, idurl: d.callback((result, nik, idurl)))
    # nickname_observer.observe_many(nickname, 
        # results_callback=lambda result, nik, idurl: d.callback((result, nik, idurl)))
    return d


def list_correspondents():
    from userid import contacts
    return contacts.getCorrespondentsDict() 
    
    
