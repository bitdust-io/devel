#!/usr/bin/python
#dhninit.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: dhninit

The top level methods to manage startup process of the whole BitPie.NET cdoe.  
"""

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in dhninit.py')
from twisted.internet.defer import Deferred,  DeferredList
from twisted.internet import task

import lib.io as io

#------------------------------------------------------------------------------ 

# need to change directory in case we were not in the p2p directory when soft started up,
# need it to find dhntester.py and potentially others
#try:
#    os.chdir(os.path.abspath(os.path.dirname(__file__)))
#except:
#    pass

UImode = ''

#------------------------------------------------------------------------------

#def run(UI='', options=None, args=None, overDict=None):
#    init(UI, options, args, overDict)


def init_local(UI=''):
    """
    Run ``init()`` method in most important modules.
    """
    
    global UImode
    UImode = UI
    io.log(2, "dhninit.init_local")

    import lib.settings as settings
    import lib.misc as misc
    misc.init()
    misc.UpdateSettings()

    settings_patch()

    import lib.commands as commands
    commands.init()

    if sys.argv.count('--twisted'):
        class MyTwistedOutputLog:
            softspace = 0
            def read(self): pass
            def write(self, s):
                io.log(0, s.strip())
            def flush(self): pass
            def close(self): pass
        from twisted.python import log as twisted_log
        twisted_log.startLogging(MyTwistedOutputLog(), setStdout=0)
#    import twisted.python.failure as twisted_failure
#    twisted_failure.startDebugMode()
#    twisted_log.defaultObserver.stop()

    from twisted.internet import defer
    defer.setDebugging(True)

    if settings.enableWebStream():
        misc.StartWebStream()

    # if settings.enableWebTraffic():
    #     misc.StartWebTraffic()
        
    if settings.enableMemoryProfile():
        try:
            from guppy import hpy
            hp = hpy()
            hp.setrelheap()
            io.log(2, 'hp.heap():\n'+str(hp.heap()))
            io.log(2, 'hp.heap().byrcs:\n'+str(hp.heap().byrcs))
            io.log(2, 'hp.heap().byvia:\n'+str(hp.heap().byvia))
            import guppy.heapy.RM
        except:
            io.log(2, "dhninit.init_local guppy package is not installed")            

    import lib.tmpfile as tmpfile
    tmpfile.init(settings.getTempDir())

    import lib.net_misc as net_misc
    net_misc.init()
    settings.update_proxy_settings()

    import run_upnpc
    run_upnpc.init()

    import lib.eccmap as eccmap
    eccmap.init()

    import lib.crypto as crypto
    import userid.identity as identity

    import webcontrol
    import lib.automats as automats
    webcontrol.GetGlobalState = automats.get_global_state
    automats.SetGlobalStateNotifyFunc(webcontrol.OnGlobalStateChanged)
    
    import lib.automat as automat
    automat.SetStateChangedCallback(webcontrol.OnSingleStateChanged)

    import dhnupdate
    dhnupdate.SetNewVersionNotifyFunc(webcontrol.OnGlobalVersionReceived)

    start_logs_rotate()

def init_contacts(callback=None, errback=None):
    """
    Initialize ``contacts`` and ``identitycache``. 
    """
    io.log(2, "dhninit.init_contacts")
    
    import lib.misc as misc
    misc.loadLocalIdentity()
    if misc._LocalIdentity is None:
        if errback is not None:
            errback(1)
        return

    import lib.contacts as contacts
    contacts.init()

    import userid.identitycache as identitycache
    identitycache.init(callback, errback)


def init_connection():
    """
    Initialize other modules related to network communications.
    """
    
    global UImode
    io.log(2, "dhninit.init_connection")

    import webcontrol

    from dht import dht_service
    from lib import settings
    dht_service.init(int(settings.getDHTPort()), settings.DHTDBFile())

    from transport import gate
    gate.init()
    
    from lib import bandwidth
    from transport import callback
    callback.add_inbox_callback(bandwidth.INfile)
    callback.add_finish_file_sending_callback(bandwidth.OUTfile)
    
    import contact_status
    contact_status.init()

    # import central_service
    # central_service.OnListSuppliersFunc = webcontrol.OnListSuppliers
    # central_service.OnListCustomersFunc = webcontrol.OnListCustomers
    # central_service.OnMarketListFunc = webcontrol.OnMarketList

    import p2p_service
    p2p_service.init()

    import money
    money.SetInboxReceiptCallback(webcontrol.OnInboxReceipt)

    import message
    message.init()
    message.OnIncommingMessageFunc = webcontrol.OnIncommingMessage

    import identitypropagate
    identitypropagate.init()

    try:
        from dhnicon import USE_TRAY_ICON
    except:
        USE_TRAY_ICON = False
        io.exception()

    if USE_TRAY_ICON:
        import dhnicon
        dhnicon.SetControlFunc(webcontrol.OnTrayIconCommand)
        
    #init the mechanism for sending and requesting files for repairing backups
    import io_throttle
    io_throttle.init()

    import backup_fs
    backup_fs.init()

    import backup_control
    backup_control.init()

    import backup_matrix
    backup_matrix.init()
    backup_matrix.SetBackupStatusNotifyCallback(webcontrol.OnBackupStats)
    backup_matrix.SetLocalFilesNotifyCallback(webcontrol.OnReadLocalFiles)
    
    import restore_monitor
    restore_monitor.init()
    restore_monitor.OnRestorePacketFunc = webcontrol.OnRestoreProcess
    restore_monitor.OnRestoreBlockFunc = webcontrol.OnRestoreSingleBlock
    restore_monitor.OnRestoreDoneFunc = webcontrol.OnRestoreDone


def init_modules():
    """
    Finish initialization part, run delayed methods.
    """
    
    io.log(2,"dhninit.init_modules")

    import webcontrol

    import local_tester
    # import backupshedule
    #import ratings
    # import fire_hire
    #import backup_monitor
    import dhnupdate

    #reactor.callLater(3, backup_monitor.start)

    reactor.callLater(5, local_tester.init)

    # reactor.callLater(10, backupshedule.init)

    #reactor.callLater(20, ratings.init)

    #reactor.callLater(25, firehire.init)

    reactor.callLater(15, dhnupdate.init)

    webcontrol.OnInitFinalDone()


def shutdown(x=None):
    """
    This is a top level method which control the process of finishing the program.
    Calls method ``shutdown()`` in other modules.
    """
    
    global initdone
    io.log(2, "dhninit.shutdown " + str(x))
    dl = []

    import io_throttle
    io_throttle.shutdown()

    import backup_rebuilder 
    backup_rebuilder.SetStoppedFlag()
    
    import data_sender
    data_sender.SetShutdownFlag()
    data_sender.A('restart')

    import lib.bitcoin as bitcoin
    bitcoin.shutdown()

    import lib.stun
    dl.append(lib.stun.stopUDPListener())
    
    import lib.eccmap as eccmap
    eccmap.shutdown()

    import backup_matrix
    backup_matrix.shutdown()

    import ratings
    ratings.shutdown()

    import contact_status
    contact_status.shutdown()

    import run_upnpc
    run_upnpc.shutdown()

    import local_tester
    local_tester.shutdown()

    import webcontrol
    dl.append(webcontrol.shutdown())

    import identitypropagate
    identitypropagate.shutdown()

    from lib import bandwidth
    from transport import callback
    callback.remove_inbox_callback(bandwidth.INfile)
    callback.remove_finish_file_sending_callback(bandwidth.OUTfile)
    
    from transport import gate
    gate.shutdown()
    
    from dht import dht_service
    dht_service.shutdown()

    import lib.weblog as weblog
    weblog.shutdown()

    initdone = False

    return DeferredList(dl)


def shutdown_restart(param=''):
    """
    Calls ``shutdown()`` method and stop the main reactor, then restart the program. 
    """
    
    io.log(2, "dhninit.shutdown_restart ")

    def do_restart(param):
        import lib.misc as misc
        misc.DoRestart(param)

    def shutdown_finished(x, param):
        io.log(2, "dhninit.shutdown_restart.shutdown_finished want to stop the reactor")
        reactor.addSystemEventTrigger('after','shutdown', do_restart, param)
        reactor.stop()

    d = shutdown('restart')
    d.addBoth(shutdown_finished, param)


def shutdown_exit(x=None):
    """
    Calls ``shutdown()`` method and stop the main reactor, this will finish the program. 
    """
    
    io.log(2, "dhninit.shutdown_exit ")

    def shutdown_reactor_stop(x=None):
        io.log(2, "dhninit.shutdown_exit want to stop the reactor")
        reactor.stop()
        # sys.exit()

    d = shutdown(x)
    d.addBoth(shutdown_reactor_stop)


def settings_patch():
    """
    Here you can change users settings depending on user name.
    Small hacks to switch on/off some options, 
    but we want to do that only during testing period.
    """
    io.log(6, 'dhninit.settings_patch ')
    import lib.settings as settings
    

def start_logs_rotate():
    """
    Checks and remove old or too big log files.
    """
    io.log(4, 'dhninit.start_logs_rotate')
    def erase_logs():
        io.log(4, 'dhninit.erase_logs ')
        import lib.settings as settings
        logs_dir = settings.LogsDir()
        total_sz = 0
        remove_list = []
        for filename in os.listdir(logs_dir):
            filepath = os.path.join(logs_dir, filename)
            if filepath == io.LogFileName:
                # skip current log file
                continue
            if not filename.endswith('.log'):
                # this is not a log file - we did not create it - do nothing
                continue
            if filename.startswith('dhnmain-'):
                # remove "old version" files, now we have files started with "dhn-"
                remove_list.append((filepath, 'old version')) 
                continue
            # count the total size of the all log files
            try:
                file_size = os.path.getsize(filepath)
            except:
                file_size = 0
            total_sz += file_size 
            # if the file is bigger than 10mb and we are not in testing mode - erase it
            if file_size > 1024*1024*10 and io.DebugLevel < 8:
                if os.access(filepath, os.W_OK):
                    remove_list.append((filepath, 'big file'))
                    continue
            # if this is a file for every execution (started with "dhn-") ... 
            if filename.startswith('dhn-'):
                # we check if file is writable - so we can remove it
                if not os.access(filepath, os.W_OK):
                    continue
                # get its datetime
                try:
                    dtm = time.mktime(time.strptime(filename[4:-4],'%y%m%d%H%M%S'))
                except:
                    io.exception()
                    continue          
                # we want to check if it is more than 30 days old ...
                if time.time() - dtm > 60*60*24*30:
                    remove_list.append((filepath, 'old file')) 
                    continue
                # also we want to check if all those files are too big - 50 MB is enough
                # for testers we do not check this
                if total_sz > 1024*1024*50 and io.DebugLevel < 8:
                    remove_list.append((filepath, 'total size'))
                    continue
        for filepath, reason in remove_list:
            try:
                os.remove(filepath)
                io.log(6, 'dhninit.erase_logs %s was deleted because of "%s"' % (filepath, reason))
            except:
                io.log(1, 'dhninit.erase_logs ERROR can not remove %s, reason is [%s]' % (filepath, reason))
                io.exception()
        del remove_list
             
    task.LoopingCall(erase_logs).start(60*60*24)



def check_install():
    """
    Return True if Private Key and local identity files exists and both is valid.
    """
    io.log(2, 'dhninit.check_install ')
    import lib.settings as settings
    import userid.identity as identity
    import lib.crypto as crypto

    keyfilename = settings.KeyFileName()
    keyfilenamelocation = settings.KeyFileNameLocation()
    if os.path.exists(keyfilenamelocation):
        keyfilename = io.ReadTextFile(keyfilenamelocation)
        if not os.path.exists(keyfilename):
            keyfilename = settings.KeyFileName()
    idfilename = settings.LocalIdentityFilename()
    
    if not os.path.exists(keyfilename) or not os.path.exists(idfilename):
        io.log(2, 'dhninit.check_install local key or local id not exists')
        return False

    current_key = io.ReadBinaryFile(keyfilename)
    current_id = io.ReadBinaryFile(idfilename)

    if current_id == '':
        io.log(2, 'dhninit.check_install local identity is empty ')
        return False

    if current_key == '':
        io.log(2, 'dhninit.check_install private key is empty ')
        return False

    try:
        crypto.InitMyKey()
    except:
        io.log(2, 'dhninit.check_install fail loading private key ')
        return False

    try:
        ident = identity.identity(xmlsrc=current_id)
    except:
        io.log(2, 'dhninit.check_install fail init local identity ')
        return False

    try:
        res = ident.Valid()
    except:
        io.log(2, 'dhninit.check_install wrong data in local identity   ')
        return False

    if not res:
        io.log(2, 'dhninit.check_install local identity is not valid ')
        return False

    io.log(2, 'dhninit.check_install done')
    return True


