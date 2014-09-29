#!/usr/bin/python
#init_shutdown.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: init_shutdown

The top level methods to manage startup process of the whole BitPie.NET code
and also correct shutdown all things when finishing.  
"""

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in init_shutdown.py')

from twisted.internet.defer import Deferred,  DeferredList
from twisted.internet import task

from logs import lg

from lib import bpio

#------------------------------------------------------------------------------ 

UImode = ''

#------------------------------------------------------------------------------

def init_local(UI=''):
    """
    Run ``init()`` method in most important modules.
    """
    global UImode
    UImode = UI
    lg.out(2, "init_shutdown.init_local")

    from lib import settings
    from lib import misc
    misc.init()
    misc.UpdateSettings()

    settings_patch()

    from lib import commands 
    commands.init()

    if sys.argv.count('--twisted'):
        class MyTwistedOutputLog:
            softspace = 0
            def read(self): pass
            def write(self, s):
                lg.out(0, s.strip())
            def flush(self): pass
            def close(self): pass
        from twisted.python import log as twisted_log
        twisted_log.startLogging(MyTwistedOutputLog(), setStdout=0)
#    import twisted.python.failure as twisted_failure
#    twisted_failure.startDebugMode()
#    twisted_log.defaultObserver.stop()

    from twisted.internet import defer
    defer.setDebugging(True)

    from logs import weblog
    if settings.enableWebStream():
        weblog.init(settings.getWebStreamPort())

    from logs import webtraffic
    if settings.enableWebTraffic():
        webtraffic.init(port=settings.getWebTrafficPort())
        
#    if settings.enableMemoryProfile():
#        try:
#            from guppy import hpy
#            hp = hpy()
#            hp.setrelheap()
#            lg.out(2, 'hp.heap():\n'+str(hp.heap()))
#            lg.out(2, 'hp.heap().byrcs:\n'+str(hp.heap().byrcs))
#            lg.out(2, 'hp.heap().byvia:\n'+str(hp.heap().byvia))
#            import guppy.heapy.RM
#        except:
#            lg.out(2, "init_shutdown.init_local guppy package is not installed")            

    from lib import tmpfile
    tmpfile.init(settings.getTempDir())

    from lib import net_misc
    net_misc.init()
    settings.update_proxy_settings()

    import run_upnpc
    run_upnpc.init()

    from raid import eccmap
    eccmap.init()

    from userid import identity

    import webcontrol
    from lib import automats
    webcontrol.GetGlobalState = automats.get_global_state
    automats.SetGlobalStateNotifyFunc(webcontrol.OnGlobalStateChanged)
    
    from lib import automat
    automat.SetStateChangedCallback(webcontrol.OnSingleStateChanged)

    start_logs_rotate()
    

def init_contacts(callback=None, errback=None):
    """
    Initialize ``contacts`` and ``identitycache``. 
    """
    lg.out(2, "init_shutdown.init_contacts")
    
    from lib import misc
    misc.loadLocalIdentity()
    if misc._LocalIdentity is None:
        if errback is not None:
            errback(1)
        return

    from lib import contacts
#    import local_site
    # contacts.SetSuppliersChangedCallback(lambda old, new: local_site.update_suppliers(new))
    # contacts.SetCustomersChangedCallback(lambda old, new: local_site.update_customers(new))
    contacts.init()

    import userid.identitycache as identitycache
    identitycache.init(callback, errback)
    


def init_connection():
    """
    Initialize other modules related to network communications.
    """
    
    global UImode
    lg.out(2, "init_shutdown.init_connection")

    import webcontrol
    import interface.xmlrpc_server 
    interface.xmlrpc_server.init()

    from dht import dht_service
    from lib import settings
    dht_service.init(int(settings.getDHTPort()), settings.DHTDBFile())

    # from transport import gate
    # gate.init()
    
    from transport import bandwidth
    from transport import callback
    callback.add_inbox_callback(bandwidth.INfile)
    callback.add_finish_file_sending_callback(bandwidth.OUTfile)
    
    import contact_status
    contact_status.init()

    import p2p_service
    p2p_service.init()

    import message
    message.init()
    message.OnIncommingMessageFunc = webcontrol.OnIncommingMessage

    from userid import propagate
    propagate.init()

    try:
        from tray_icon import USE_TRAY_ICON
    except:
        USE_TRAY_ICON = False
        lg.exc()

    if USE_TRAY_ICON:
        import tray_icon
        tray_icon.SetControlFunc(webcontrol.OnTrayIconCommand)
        
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
    
    lg.out(2,"init_shutdown.init_modules")

    import local_tester
    reactor.callLater(0, local_tester.init)
    
    import software_update
    import webcontrol
    software_update.SetNewVersionNotifyFunc(webcontrol.OnGlobalVersionReceived)
    reactor.callLater(0, software_update.init)

    import webcontrol
    reactor.callLater(0, webcontrol.OnInitFinalDone)


def shutdown(x=None):
    """
    This is a top level method which control the process of finishing the program.
    Calls method ``shutdown()`` in other modules.
    """
    
    global initdone
    lg.out(2, "init_shutdown.shutdown " + str(x))
    dl = []

    import io_throttle
    io_throttle.shutdown()

    import backup_rebuilder 
    backup_rebuilder.SetStoppedFlag()
    
    import data_sender
    data_sender.SetShutdownFlag()
    data_sender.A('restart')

    import lib.stun
    dl.append(lib.stun.stopUDPListener())
    
    from raid import eccmap
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

    from userid import propagate
    propagate.shutdown()

    from transport import bandwidth
    from transport import callback
    callback.remove_inbox_callback(bandwidth.INfile)
    callback.remove_finish_file_sending_callback(bandwidth.OUTfile)
    
    from transport import gate
    gate.shutdown()
    
    from dht import dht_service
    dht_service.shutdown()

    from logs import weblog
    weblog.shutdown()
    
    from logs import webtraffic
    webtraffic.shutdown()

    initdone = False

    return DeferredList(dl)


def shutdown_restart(param=''):
    """
    Calls ``shutdown()`` method and stop the main reactor, then restart the program. 
    """
    
    lg.out(2, "init_shutdown.shutdown_restart ")

    def do_restart(param):
        from lib import misc
        misc.DoRestart(param)

    def shutdown_finished(x, param):
        lg.out(2, "init_shutdown.shutdown_restart.shutdown_finished want to stop the reactor")
        reactor.addSystemEventTrigger('after','shutdown', do_restart, param)
        reactor.stop()

    d = shutdown('restart')
    d.addBoth(shutdown_finished, param)


def shutdown_exit(x=None):
    """
    Calls ``shutdown()`` method and stop the main reactor, this will finish the program. 
    """
    
    lg.out(2, "init_shutdown.shutdown_exit ")

    def shutdown_reactor_stop(x=None):
        lg.out(2, "init_shutdown.shutdown_exit want to stop the reactor")
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
    lg.out(6, 'init_shutdown.settings_patch ')
    from lib import settings
    

def start_logs_rotate():
    """
    Checks and remove old or too big log files.
    """
    lg.out(4, 'init_shutdown.start_logs_rotate')
    def erase_logs():
        lg.out(4, 'init_shutdown.erase_logs ')
        from lib import settings
        logs_dir = settings.LogsDir()
        total_sz = 0
        remove_list = []
        for filename in os.listdir(logs_dir):
            filepath = os.path.join(logs_dir, filename)
            if filepath == lg.log_filename():
                # skip current log file
                continue
            if not filename.endswith('.log'):
                # this is not a log file - we did not create it - do nothing
                continue
#            if filename.startswith('dhnmain-'):
#                # remove "old version" files, now we have files started with "bpmain-"
#                remove_list.append((filepath, 'old version')) 
#                continue
            # count the total size of the all log files
            try:
                file_size = os.path.getsize(filepath)
            except:
                file_size = 0
            total_sz += file_size 
            # if the file is bigger than 10mb and we are not in testing mode - erase it
            if file_size > 1024*1024*10 and not lg.is_debug(8):
                if os.access(filepath, os.W_OK):
                    remove_list.append((filepath, 'big file'))
                    continue
            # if this is a file for every execution (started with "bpmain-") ... 
            if filename.startswith('bpmain-'):
                # we check if file is writable - so we can remove it
                if not os.access(filepath, os.W_OK):
                    continue
                # get its datetime
                try:
                    dtm = time.mktime(time.strptime(filename[7:-4],'%y%m%d%H%M%S'))
                except:
                    lg.exc()
                    continue          
                # we want to check if it is more than 30 days old ...
                if time.time() - dtm > 60*60*24*30:
                    remove_list.append((filepath, 'old file')) 
                    continue
                # also we want to check if all those files are too big - 50 MB is enough
                # for testers we do not check this
                if total_sz > 1024*1024*50 and bpio.DebugLevel < 8:
                    remove_list.append((filepath, 'total size'))
                    continue
        for filepath, reason in remove_list:
            try:
                os.remove(filepath)
                lg.out(6, 'init_shutdown.erase_logs %s was deleted because of "%s"' % (filepath, reason))
            except:
                lg.out(1, 'init_shutdown.erase_logs ERROR can not remove %s, reason is [%s]' % (filepath, reason))
                lg.exc()
        del remove_list
             
    task.LoopingCall(erase_logs).start(60*60*24)



def check_install():
    """
    Return True if Private Key and local identity files exists and both is valid.
    """
    lg.out(2, 'init_shutdown.check_install ')
    from lib import settings
    from userid import identity
    from crypt import key

    keyfilename = settings.KeyFileName()
    keyfilenamelocation = settings.KeyFileNameLocation()
    if os.path.exists(keyfilenamelocation):
        keyfilename = bpio.ReadTextFile(keyfilenamelocation)
        if not os.path.exists(keyfilename):
            keyfilename = settings.KeyFileName()
    idfilename = settings.LocalIdentityFilename()
    
    if not os.path.exists(keyfilename) or not os.path.exists(idfilename):
        lg.out(2, 'init_shutdown.check_install local key or local id not exists')
        return False

    current_key = bpio.ReadBinaryFile(keyfilename)
    current_id = bpio.ReadBinaryFile(idfilename)

    if current_id == '':
        lg.out(2, 'init_shutdown.check_install local identity is empty ')
        return False

    if current_key == '':
        lg.out(2, 'init_shutdown.check_install private key is empty ')
        return False

    try:
        key.InitMyKey()
    except:
        lg.out(2, 'init_shutdown.check_install fail loading private key ')
        return False

    try:
        ident = identity.identity(xmlsrc=current_id)
    except:
        lg.out(2, 'init_shutdown.check_install fail init local identity ')
        return False

    try:
        res = ident.Valid()
    except:
        lg.out(2, 'init_shutdown.check_install wrong data in local identity   ')
        return False

    if not res:
        lg.out(2, 'init_shutdown.check_install local identity is not valid ')
        return False

    lg.out(2, 'init_shutdown.check_install done')
    return True


