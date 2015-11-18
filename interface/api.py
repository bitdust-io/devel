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

Here is a bunch of methods to interact with BitDust software.
"""

#------------------------------------------------------------------------------ 

_Debug = True

#------------------------------------------------------------------------------ 

from twisted.internet.defer import Deferred

from services import driver

#------------------------------------------------------------------------------ 

def stop():
    from logs import lg
    lg.out(2, 'api.stop sending event "stop" to the shutdowner() machine')
    from main import shutdowner
    shutdowner.A('stop', 'exit')
    return { 'result': 'stopped', }
    

def restart(show=False):
    from logs import lg
    from system import bpio
    from main import shutdowner
    appList = bpio.find_process(['bpgui.',])
    if len(appList) > 0:
        lg.out(2, 'api.restart found bpgui process, added param "show", sending event "stop" to the shutdowner() machine')
        shutdowner.A('stop', 'restartnshow')
        return { 'result': 'restarted with GUI', }
    if show: 
        lg.out(2, 'api.restart forced for GUI, added param "show", sending event "stop" to the shutdowner() machine')
        shutdowner.A('stop', 'restartnshow')
        return { 'result': 'restarted with GUI', }
    lg.out(2, 'api.restart did not found bpgui process nor forced for GUI, just do the restart, sending event "stop" to the shutdowner() machine')
    shutdowner.A('stop', 'restart')
    return { 'result': 'restarted', }


def show():
    from logs import lg
    lg.out(4, 'api.show')
    from main import settings
    if settings.NewWebGUI():
        from web import control
        control.show()
    else:
        from web import webcontrol
        webcontrol.show()
    return { 'result': '"show" event sent to UI', }

#------------------------------------------------------------------------------ 

def config_get(key, default=None):
    from logs import lg
    lg.out(4, 'api.config_get [%s]' % key)
    from main import config
    if not config.conf().exist(key):
        return { 'result': {'error': 'option "%s" not exist' % key} }
    return { 'result': {
        'key': key, 
        'value': config.conf().getData(key, default), 
        'type': config.conf().getTypeLabel(key),
        # 'code': config.conf().getType(key),
        # 'label': config.conf().getLabel(key),
        # 'info': config.conf().getInfo(key)
        } }
        
def config_set(key, value, typ=None):
    from logs import lg
    lg.out(4, 'api.config_set [%s]' % key)
    from main import config
    v = {}
    if config.conf().exist(key):
        v['old_value'] = config.conf().getData(key)
    if type in [ config.TYPE_STRING, 
                 config.TYPE_TEXT,
                 config.TYPE_UNDEFINED, ] or typ is None: 
        config.conf().setData(key, value)
    elif typ in [config.TYPE_BOOLEAN, ]:
        config.conf().setBool(key, value)
    elif typ in [config.TYPE_INTEGER, 
                 config.TYPE_POSITIVE_INTEGER, 
                 config.TYPE_NON_ZERO_POSITIVE_INTEGER, ]:
        config.conf().setInt(key, value)
    elif typ in [config.TYPE_FOLDER_PATH,
                 config.TYPE_FILE_PATH, 
                 config.TYPE_COMBO_BOX,
                 config.TYPE_PASSWORD,]:
        config.conf().setString(key, value)
    else:
        config.conf().setData(key, str(value))
    v.update({  'key': key, 
                'value': config.conf().getData(key), 
                'type': config.conf().getTypeLabel(key)
                # 'code': config.conf().getType(key),
                # 'label': config.conf().getLabel(key),
                # 'info': config.conf().getInfo(key), 
                })
    return { 'result': v }

def config_list(sort=False):
    from logs import lg
    lg.out(4, 'api.config_list')
    from main import config
    r = config.conf().cache()
    r = map(lambda key: {
        'key': key,
        'value': r[key],
        'type': config.conf().getTypeLabel(key)}, sorted(r.keys()))
    if sort:
        r = sorted(r, key=lambda i: i['key'])
    return { 'result': r } 

#------------------------------------------------------------------------------ 

def filemanager(json_request):
    from storage import filemanager_api
    return filemanager_api.process(json_request) 

#------------------------------------------------------------------------------ 

def backups_update():
    from storage import backup_monitor
    backup_monitor.A('restart') 
    from logs import lg
    lg.out(4, 'api.backups_update')
    return { 'result': 'the main loop has been restarted', }


def backups_list():
    from storage import backup_fs
    from lib import diskspace
    result = []
    for pathID, localPath, item in backup_fs.IterateIDs():
        result.append({
            'id': pathID,
            'path': localPath,
            'type': backup_fs.TYPES.get(item.type, '').lower(),
            'size': item.size,
            'versions': map(
                lambda v: {
                   'version': v,
                   'blocks': max(0, item.versions[v][0]),
                   'size': diskspace.MakeStringFromBytes(max(0, item.versions[v][1])),},
                item.versions.keys())})
        # if len(result) > 20:
        #     break
    from logs import lg
    lg.out(4, 'api.backups_list %s' % result)
    return { 'result': result, }


def backups_id_list():
    from storage import backup_fs
    from contacts import contactsdb
    from lib import diskspace
    result = []
    for itemName, backupID, versionInfo, localPath in backup_fs.ListAllBackupIDsFull(True, True):
        if versionInfo[1] >= 0 and contactsdb.num_suppliers() > 0:
            szver = diskspace.MakeStringFromBytes(versionInfo[1]) + ' / ' + diskspace.MakeStringFromBytes(versionInfo[1]/contactsdb.num_suppliers()) 
        else:
            szver = '?'
        szver = diskspace.MakeStringFromBytes(versionInfo[1]) if versionInfo[1] >= 0 else '?'
        result.append({
            'backupid': backupID,
            'size': szver,
            'path': localPath, })
        # if len(result) > 20:
        #     break
    return { 'result': result, }


def backup_start_id(pathID):
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    from web import control
    local_path = backup_fs.ToPath(pathID)
    if local_path is not None:
        if bpio.pathExist(local_path):
            backup_control.StartSingle(pathID, local_path)
            backup_fs.Calculate()
            backup_control.Save()
            control.request_update()
            return { 'result': 'backup started : %s' % pathID,
                     'local_path': local_path, }
    else:
        return { 'result': 'item %s not found' % pathID, }

    
def backup_start_path(path):
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    from web import control
    localPath = bpio.portablePath(unicode(path))
    if not bpio.pathExist(localPath):
        return {'result': 'local path %s not found' % path, }
    result = ''
    pathID = backup_fs.ToID(localPath)
    if pathID is None:
        if bpio.pathIsDir(localPath):
            pathID, iter, iterID = backup_fs.AddDir(localPath, True)
            result += 'new folder was added: %s, ' % localPath
        else:
            pathID, iter, iterID = backup_fs.AddFile(localPath, True)
            result += 'new file was added: %s, ' % localPath
    backup_control.StartSingle(pathID, localPath)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update()
    result += 'backup started: %s' % pathID
    return { 'result': result, }

        
def backup_dir_add(dirpath):
    from storage import backup_fs
    from storage import backup_control
    from system import dirsize
    from web import control
    newPathID, iter, iterID = backup_fs.AddDir(dirpath, True)
    dirsize.ask(dirpath, backup_control.FoundFolderSize, (newPathID, None))
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update()
    return { 'result': 'new folder was added: %s %s' % (newPathID, dirpath), }


def backup_file_add(filepath):    
    from storage import backup_fs
    from storage import backup_control
    from web import control
    newPathID, iter, iterID = backup_fs.AddFile(filepath, True)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update()
    return { 'result': 'new file was added: %s %s' % (newPathID, filepath), }


def backup_tree_add(dirpath):
    from storage import backup_fs
    from storage import backup_control
    from web import control
    newPathID, iter, iterID, num = backup_fs.AddLocalPath(dirpath, True)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update()
    if not newPathID:
        return { 'result': 'nothing was added to catalog', }
    return { 'result': '%d items were added to catalog, parent path ID is: %s  %s' % (
        num, newPathID, dirpath), }


def backup_delete_local(backupID):
    from storage import backup_fs
    from storage import backup_matrix
    from main import settings
    from logs import lg
    lg.out(4, 'api.backup_delete_local %s' % backupID)
    num, sz = backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
    backup_matrix.EraseBackupLocalInfo(backupID)
    backup_fs.Scan()
    backup_fs.Calculate()
    return { 'result': "%d files were removed with total size of %s" % (num,sz) }


def backup_delete_id(pathID):
    from storage import backup_fs
    from storage import backup_control
    from storage import backup_monitor
    from main import settings
    from web import control
    from logs import lg
    lg.out(4, 'api.backup_delete_id %s' % pathID)
    result = backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    if not result:
        return { 'result': 'item %s is not found in catalog' % pathID }
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update()
    backup_monitor.A('restart')
    return { 'result': 'item %s were deleted' % pathID }


def backup_delete_path(localPath):
    from storage import backup_fs
    from storage import backup_control
    from storage import backup_monitor
    from main import settings
    from web import control
    from lib import packetid
    from system import bpio
    from logs import lg
    localPath = bpio.portablePath(unicode(localPath))
    lg.out(4, 'api.backup_delete_path %s' % localPath)
    pathID = backup_fs.ToID(localPath)
    if not pathID:
        return { 'result': 'path %s is not found in catalog' % localPath }
    if not packetid.Valid(pathID):
        return { 'result': 'invalid pathID found %s' % pathID }
    backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    return { 'result': 'item %s were deleted' % pathID }
        

#------------------------------------------------------------------------------ 

def list_messages():
    if not driver.is_started('service_private_messages'):
        return { 'result': 'service_private_messages() is not started', }
    from chat import message
    mlist = {} #TODO: just need some good idea to keep messages synchronized!!!
    return { 'result': mlist }
    
    
def send_message(recipient, message_body):
    if not driver.is_started('service_private_messages'):
        return { 'result': 'service_private_messages() is not started', }
    from chat import message
    recipient = str(recipient)
    if not recipient.startswith('http://'):
        from contacts import contactsdb
        recipient = contactsdb.find_correspondent_by_nickname(recipient) or recipient
    packet = message.SendMessage(recipient, message_body)
    if packet:
        try:
            packet = str(packet.outpacket)
        except:
            packet = str(packet)
    return {'result': { 
            'packet': packet },
            'recipient': recipient }
    
#------------------------------------------------------------------------------ 

def list_correspondents():
    from contacts import contactsdb
    return { 'result': map(lambda v: {
        'idurl': v[0],
        'nickname': v[1],},
        contactsdb.correspondents()), } 
    
    
def add_correspondent(idurl, nickname=''):
    from contacts import contactsdb
    contactsdb.add_correspondent(idurl, nickname)
    contactsdb.save_correspondents()
    return { 'result': 'new correspondent was added',
             'nickname': nickname,
             'idurl': idurl, }
    

def remove_correspondent(idurl):
    from contacts import contactsdb
    result = contactsdb.remove_correspondent(idurl)
    contactsdb.save_correspondents()
    if result:
        result = 'correspondent %s were removed'
    else:
        result = 'correspondent %s was not found'
    return { 'result': result, }


def find_peer_by_nickname(nickname):
    from twisted.internet.defer import Deferred
    from chat import nickname_observer
    nickname_observer.stop_all()
    d = Deferred()
    def _result(result, nik, pos, idurl):
        return d.callback({'result':
            { 'result': result,
              'nickname': nik,
              'position': pos,
              'idurl': idurl,}})        
    nickname_observer.find_one(nickname, 
        results_callback=_result)
    # nickname_observer.observe_many(nickname, 
        # results_callback=lambda result, nik, idurl: d.callback((result, nik, idurl)))
    return d

#------------------------------------------------------------------------------ 

def ping(idurl):
    if not driver.is_started('service_identity_propagate'):
        return { 'result': 'service_identity_propagate() is not started', }
    from p2p import propagate
    d = Deferred()
    propagate.PingContact(idurl, ack_handler=lambda newpacket, info: d.callback(
        { 'result': str(newpacket), }))
    return d
    
#------------------------------------------------------------------------------ 



