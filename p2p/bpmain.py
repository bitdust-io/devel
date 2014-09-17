#!/usr/bin/python
#bpmain.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: bpmain

This is the entry point of the program, see method ``main()`` bellow.
"""

import os
import sys
import time

#-------------------------------------------------------------------------------

def show():
    """
    Just calls ``p2p.webcontrol.show()`` to open the GUI. 
    """
    import webcontrol
    webcontrol.show()
    
    
    return 0


def run(UI='', options=None, args=None, overDict=None):
    """
    In the method ``main()`` program firstly checks the command line arguments 
    and then calls this method to start the whole process.
    This initialize some low level modules and finally create 
    an instance of ``initializer()`` state machine and send it an event "run".
    """
    
    from logs import lg
    lg.out(6, 'bpmain.run sys.path=%s' % str(sys.path))
    
    from lib import bpio
    
    #---settings---
    from lib import settings
    if overDict:
        settings.override_dict(overDict)
    settings.init()
    if not options or options.debug is None:
        lg.set_debug_level(settings.getDebugLevel())    
    
    #---USE_TRAY_ICON---
    if os.path.isfile(settings.LocalIdentityFilename()) and os.path.isfile(settings.KeyFileName()):
        try:
            from tray_icon import USE_TRAY_ICON
            if bpio.Linux() and not bpio.X11_is_running():
                USE_TRAY_ICON = False
            if USE_TRAY_ICON:
                from twisted.internet import wxreactor
                wxreactor.install()
        except:
            USE_TRAY_ICON = False
            lg.exc()
    else:
        USE_TRAY_ICON = False
    lg.out(4, 'bpmain.run USE_TRAY_ICON='+str(USE_TRAY_ICON))
    if USE_TRAY_ICON:
        if bpio.Linux():
            icons_dict = {
                'red':      'icon-red-24x24.png',
                'yellow':   'icon-yellow-24x24.png',
                'green':    'icon-green-24x24.png',
                'gray':     'icon-gray-24x24.png', }
        else:
            icons_dict = {
                'red':      'icon-red-16x16.png',
                'yellow':   'icon-yellow-16x16.png',
                'green':    'icon-green-16x16.png',
                'gray':     'icon-gray-16x16.png', }
        import tray_icon
        icons_path = str(os.path.abspath(os.path.join(bpio.getExecutableDir(), 'icons')))
        lg.out(4, 'bpmain.run call tray_icon.init(%s)' % icons_path)
        tray_icon.init(icons_path, icons_dict)
        def _tray_control_func(cmd):
            if cmd == 'exit':
                import shutdowner
                shutdowner.A('stop', 'exit')
        tray_icon.SetControlFunc(_tray_control_func)

    lg.out(4, 'bpmain.run want to import twisted.internet.reactor')
    try:
        from twisted.internet import reactor
    except:
        lg.exc()
        sys.exit('Error initializing reactor in bpmain.py\n')

    #---logfile----
    if lg.logs_enabled() and lg.log_file():
        lg.out(2, 'bpmain.run want to switch log files')
        if bpio.Windows() and bpio.isFrozen():
            lg.stdout_stop_redirecting()
        lg.close_log_file()
        lg.open_log_file(settings.MainLogFilename()+'-'+time.strftime('%y%m%d%H%M%S')+'.log')
        if bpio.Windows() and bpio.isFrozen():
            lg.stdout_start_redirecting()
            
    #---memdebug---
    if settings.uconfig('logs.memdebug-enable') == 'True':
        try:
            from logs import memdebug
            memdebug_port = int(settings.uconfig('logs.memdebug-port'))
            memdebug.start(memdebug_port)
            reactor.addSystemEventTrigger('before', 'shutdown', memdebug.stop)
            lg.out(2, 'bpmain.run memdebug web server started on port %d' % memdebug_port)
        except:
            lg.exc()  
            
    #---process ID---
    try:
        pid = os.getpid()
        pid_file_path = os.path.join(settings.MetaDataDir(), 'processid')
        bpio.WriteFile(pid_file_path, str(pid))
        lg.out(2, 'bpmain.run wrote process id [%s] in the file %s' % (str(pid), pid_file_path))
    except:
        lg.exc()  
            
#    #---reactor.callLater patch---
#    if lg.is_debug(12):
#        patchReactorCallLater(reactor)
#        monitorDelayedCalls(reactor)

    lg.out(2,"bpmain.run UI=[%s]" % UI)

    if lg.is_debug(20):
        lg.out(0, '\n' + bpio.osinfofull())

    lg.out(4, 'bpmain.run import automats')

    #---START!---
    import lib.automat as automat
    automat.LifeBegins(lg.when_life_begins())
    # automat.OpenLogFile(settings.AutomatsLog())
    
    import initializer
    import shutdowner

    lg.out(4, 'bpmain.run send event "run" to initializer()')
    
    #reactor.callLater(0, initializer.A, 'run', UI)
    initializer.A('run', UI)

    lg.out(2, 'bpmain.run calling reactor.run()')
    reactor.run()

    lg.out(2, 'bpmain.run reactor stopped')
    shutdowner.A('reactor-stopped')

    lg.out(2, 'bpmain.run finished, EXIT')

    automat.CloseLogFile()

##    import threading
##    lg.out(0, 'threads:')
##    for t in threading.enumerate():
##        lg.out(0, '  '+str(t))

    lg.close_log_file()

    if bpio.Windows() and bpio.isFrozen():
        lg.stdout_stop_redirecting()

    return 0

#------------------------------------------------------------------------------

def parser():
    """
    Create an ``optparse.OptionParser`` object to read command line arguments.
    """
    from optparse import OptionParser, OptionGroup
    parser = OptionParser(usage = usage())
    group = OptionGroup(parser, "Log")
    group.add_option('-d', '--debug',
                        dest='debug',
                        type='int',
                        help='set debug level',)
    group.add_option('-q', '--quite',
                        dest='quite',
                        action='store_true',
                        help='quite mode, do not print any messages to stdout',)
    group.add_option('-v', '--verbose',
                        dest='verbose',
                        action='store_true',
                        help='verbose mode, print more messages',)
    group.add_option('-n', '--no-logs',
                        dest='no_logs',
                        action='store_true',
                        help='do not use logs',)
    group.add_option('-o', '--output',
                        dest='output',
                        type='string',
                        help='print log messages to the file',)
    group.add_option('-t', '--tempdir',
                        dest='tempdir',
                        type='string',
                        help='set location for temporary files, default is ~/.bitpie/temp',)
    group.add_option('--twisted',
                        dest='twisted',
                        action='store_true',
                        help='show twisted log messages too',)
    group.add_option('--memdebug',
                        dest='memdebug',
                        action='store_true',
                        help='start web server to debug memory usage, need cherrypy and dozer modules',)
    parser.add_option_group(group)


    group = OptionGroup(parser, "Network")
    group.add_option('--tcp-port',
                        dest='tcp_port',
                        type='int',
                        help='set tcp port number for incoming connections',)
    group.add_option('--no-upnp',
                        dest='no_upnp',
                        action='store_true',
                        help='do not use UPnP',)
    group.add_option('--memdebug-port',
                        dest='memdebug_port',
                        type='int',
                        default=9996,
                        help='set port number for memdebug web server, default is 9995',)    
    parser.add_option_group(group)
    return parser


def override_options(opts, args):
    """
    The program can replace some user options by values passed via command line.
    This method return a dictionary where is stored a key-value pairs for new options.   
    """
    overDict = {}
    if opts.tcp_port:
        overDict['transport.transport-tcp.transport-tcp-port'] = str(opts.tcp_port)
    if opts.no_upnp:
        overDict['other.upnp-enabled'] = 'False'
    if opts.tempdir:
        overDict['folder.folder-temp'] = opts.tempdir
    if opts.debug or str(opts.debug) == '0':
        overDict['logs.debug-level'] = str(opts.debug)
    if opts.memdebug:
        overDict['logs.memdebug-enable'] = str(opts.memdebug)
        if opts.memdebug_port:
            overDict['logs.memdebug-port'] = str(opts.memdebug_port)
        else:
            overDict['logs.memdebug-port'] = '9996'
    return overDict

#------------------------------------------------------------------------------ 

def kill():
    """
    Kill all running BitPie.NET processes (except current).
    """
    from logs import lg
    from lib import bpio
    total_count = 0
    found = False
    while True:
        appList = bpio.find_process([
            'bitpie.exe',
            'bpmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            'bpgui.exe',
            'bpgui.py',
            'bppipe.exe',
            'bppipe.py',
            'bptester.exe',
            'bptester.py',
            'bpstarter.exe',
            ])
        if len(appList) > 0:
            found = True
        for pid in appList:
            lg.out(0, 'trying to stop pid %d' % pid)
            bpio.kill_process(pid)
        if len(appList) == 0:
            if found:
                lg.out(0, 'BitPie.NET stopped\n')
            else:
                lg.out(0, 'BitPie.NET was not started\n')
            return 0
        total_count += 1
        if total_count > 10:
            lg.out(0, 'some BitPie.NET process found, but can not stop it\n')
            return 1
        time.sleep(1)


def wait_then_kill(x):
    """
    For correct shutdown of the program need to send a URL request to the HTTP server::
        http://localhost:<random port>/?action=exit
        
    After receiving such request the program will call ``p2p.init_shutdown.shutdown()`` method and stops.
    But if the main process was blocked it needs to be killed with system "kill" procedure.
    This method will wait for 10 seconds and then call method ``kill()``.    
    """
    from twisted.internet import reactor
    from logs import lg
    from lib import bpio
    total_count = 0
    while True:
        appList = bpio.find_process([
            'bitpie.exe',
            'bpmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            'bpgui.exe',
            'bpgui.py',
            'bppipe.exe',
            'bppipe.py',
            'bptester.exe',
            'bptester.py',
            'bpstarter.exe',
            ])
        if len(appList) == 0:
            lg.out(0, 'DONE')
            reactor.stop()
            return 0
        total_count += 1
        if total_count > 10:
            lg.out(0, 'not responding, KILLING ...')
            ret = kill()
            reactor.stop()
            return ret
        time.sleep(1)
        
#------------------------------------------------------------------------------ 

_OriginalCallLater = None
_DelayedCallsIndex = {}
_LastCallableID = 0

class _callable():
    """
    This class shows my experiments with performance monitoring.
    I tried to decrease the number of delayed calls.
    """
    def __init__(self, callable, *args, **kw):
        global _DelayedCallsIndex
        self.callable = callable
        if not _DelayedCallsIndex.has_key(self.callable):
            _DelayedCallsIndex[self.callable] = [0, 0.0]
        self.to_call = lambda: self.run(*args, **kw)
    def run(self, *args, **kw):
        tm = time.time()
        self.callable(*args, **kw)
        exec_time = time.time() - tm 
        _DelayedCallsIndex[self.callable][0] += 1
        _DelayedCallsIndex[self.callable][1] += exec_time
    def call(self):
        self.to_call()

def _callLater(delay, callable, *args, **kw):
    """
    A wrapper around Twisted ``reactor.callLater()`` method.
    """
    global _OriginalCallLater
    _call = _callable(callable, *args, **kw)
    delayed_call = _OriginalCallLater(delay, _call.call)
    return delayed_call

def patchReactorCallLater(r):
    """
    Replace original ``reactor.callLater()`` with my hacked solution to monitor overall performance.
    """
    global _OriginalCallLater
    _OriginalCallLater = r.callLater
    r.callLater = _callLater 

def monitorDelayedCalls(r):
    """
    Print out all delayed calls.
    """
    global _DelayedCallsIndex
    from logs import lg
    from lib import bpio
    keys = _DelayedCallsIndex.keys()
    keys.sort(key=lambda cb: -_DelayedCallsIndex[cb][1])
    s = ''
    for i in range(0, min(10, len(_DelayedCallsIndex))):
        cb = keys[i]
        s += '        %d %d %s\n' % ( _DelayedCallsIndex[cb][0], _DelayedCallsIndex[cb][1], cb) 
    lg.out(8, '    delayed calls: %d\n%s' % (len(_DelayedCallsIndex), s))
    r.callLater(10, monitorDelayedCalls, r)

#------------------------------------------------------------------------------ 

def main():
    """
    THIS IS THE ENTRY POINT OF THE PROGRAM!
    """
    try:
        from logs import lg
    except:
        dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
        sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
        # sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))
        from distutils.sysconfig import get_python_lib
        sys.path.append(os.path.join(get_python_lib(), 'bitpie'))
        try:
            from logs import lg
        except:
            print 'ERROR! can not import working code.  Python Path:'
            print '\n'.join(sys.path)
            return 1

    # from logs import lg
    from lib import bpio

    # init IO module, update locale
    bpio.init()
    
    # sys.excepthook = lg.exception_hook
    
    if not bpio.isFrozen():
        from twisted.internet.defer import setDebugging
        setDebugging(True)

    # ask to count time for each log line from that moment, not absolute time 
    lg.life_begins()
    
    pars = parser()
    (opts, args) = pars.parse_args()

    if opts.no_logs:
        lg.disable_logs()

    #---logpath---
    logpath = os.path.join(os.path.expanduser('~'), '.bitpie', 'logs', 'start.log')
    if opts.output:
        logpath = opts.output

    if logpath != '':
        lg.open_log_file(logpath)
        lg.out(2, 'bpmain.main log file opened ' + logpath)
        if bpio.Windows() and bpio.isFrozen():
            lg.stdout_start_redirecting()
            lg.out(2, 'bpmain.main redirecting started')

    try:
        os.remove(os.path.expanduser('~'), '.bitpie', 'logs', 'exception.log')
    except:
        pass

    if opts.debug or str(opts.debug) == '0':
        lg.set_debug_level(opts.debug)

    if opts.quite and not opts.verbose:
        lg.disable_output()

    if opts.verbose:
        copyright()

    lg.out(2, 'bpmain.main started ' + time.asctime())

    overDict = override_options(opts, args)

    cmd = ''
    if len(args) > 0:
        cmd = args[0].lower()
        
    lg.out(2, 'bpmain.main args=%s' % str(args))

    #---start---
    if cmd == '' or cmd == 'start' or cmd == 'go':
        appList = bpio.find_process([
            'bitpie.exe',
            'bpmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        
#        pid = -1
#        try:
#            if bpio.Windows():
#                _data_path = os.path.join(os.environ.get('APPDATA', os.path.join(os.path.expanduser('~'), 'Application Data')), 'BitPie.NET')
#                pid_path = os.path.join(_data_path, 'metadata', 'processid')
#            else:
#                pid_path = os.path.join(os.path.expanduser('~'), '.bitpie', 'metadata', 'processid')
#            if os.path.isfile(pid_path):
#                pid = int(bpio.ReadBinaryFile(pid_path).strip())
#        except:
#            lg.exc()
        # this is extra protection for Debian release
        # I am not sure how process name can looks on different systems
        # check the process ID from previous start 
        # it file exists and we found this PID in the currently running apps - BitPie.NET is working
        # if file not exists we don't want to start if found some other jobs with same name 
        # PREPRO probably in future we can switch to this line:
        # if len(appList) > 0 and pid != -1 and pid in appList
        # because if we do not have pid - the process is not working
        # but old versions do not have pid file so we need to wait till 
        # all users be updated to this version - revision 7520+
#        if len(appList) > 0 and ( ( pid != -1 and pid in appList ) or ( pid == -1 ) ):

        if len(appList) > 0:
            lg.out(0, 'BitPie.NET already started, found another process: %s' % str(appList))
            bpio.shutdown()
            return 0
        try:
            ret = run('', opts, args, overDict)
        except:
            lg.exc()
            ret = 1
        bpio.shutdown()
        return ret

    #---detach---
    elif cmd == 'detach':
        # lg.set_debug_level(20)
        appList = bpio.find_process([
            'bitpie.exe',
            'bpmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        if len(appList) > 0:
            lg.out(0, 'main BitPie.NET process already started: %s' % str(appList))
            bpio.shutdown()
            return 0
        from lib import misc
        # from twisted.internet import reactor
        # def _detach():
        #     result = misc.DoRestart(detach=True)
        #     lg.out(0, 'run and detach main BitPie.NET process: %s' % str(result))
        #     reactor.callLater(2, reactor.stop)
        # reactor.addSystemEventTrigger('after','shutdown', misc.DoRestart, detach=True)
        # reactor.callLater(0.01, _detach)
        # reactor.run()
        lg.out(0, 'run and detach main BitPie.NET process')
        bpio.shutdown()
        result = misc.DoRestart(detach=True)
        try:
            result = result.pid
        except:
            pass
        print result
        return 0

    #---restart---
    elif cmd == 'restart':
        appList = bpio.find_process([
            'bitpie.exe',
            'bpmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        if len(appList) > 0:
            lg.out(0, 'found main BitPie.NET process: %s, sending "restart" command ... ' % str(appList), '')
            def done(x):
                lg.out(0, 'DONE\n', '')
                from twisted.internet import reactor
                if reactor.running and not reactor._stopped:
                    reactor.stop()
            def failed(x):
                lg.out(0, 'FAILED, killing previous process and do restart\n', '')
                try:
                    kill()
                except:
                    lg.exc()
                from twisted.internet import reactor
                from lib import misc
                reactor.addSystemEventTrigger('after','shutdown', misc.DoRestart)
                reactor.stop()
            try:
                from twisted.internet import reactor
                from command_line import run_url_command
                d = run_url_command('?action=restart', False)
                d.addCallback(done)
                d.addErrback(failed)
                reactor.run()
                bpio.shutdown()
                return 0
            except:
                lg.exc()
                bpio.shutdown()
                return 1
        else:
            try:
                ret = run('', opts, args, overDict)
            except:
                lg.exc()
                ret = 1
            bpio.shutdown()
            return ret

    #---show---
    elif cmd == 'show' or cmd == 'open':
        appList_bpgui = bpio.find_process([
            'bpgui.exe',
            'bpgui.py',
            ])
        appList = bpio.find_process([
            'bitpie.exe',
            'bpmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        if len(appList_bpgui) > 0:
            if len(appList) == 0:
                for pid in appList_bpgui:
                    bpio.kill_process(pid)
            else:
                lg.out(0, 'BitPie.NET GUI already opened, found another process: %s' % str(appList))
                bpio.shutdown()
                return 0
        if len(appList) == 0:
            try:
                ret = run('show', opts, args, overDict)
            except:
                lg.exc()
                ret = 1
            bpio.shutdown()
            return ret
        
        lg.out(0, 'found main BitPie.NET process: %s, start the GUI\n' % str(appList))
        ret = show()
        bpio.shutdown()
        return ret

    #---stop---
    elif cmd == 'stop' or cmd == 'kill' or cmd == 'shutdown':
        appList = bpio.find_process([
            'bitpie.exe',
            'bpmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        if len(appList) > 0:
            lg.out(0, 'found main BitPie.NET process: %s, sending command "exit" ... ' % str(appList), '')
            try:
                from twisted.internet import reactor
                from command_line import run_url_command
                url = '?action=exit'
                run_url_command(url, False).addBoth(wait_then_kill)
                reactor.run()
                bpio.shutdown()
                return 0
            except:
                lg.exc()
                ret = kill()
                bpio.shutdown()
                return ret
        else:
            lg.out(0, 'BitPie.NET is not running at the moment')
            bpio.shutdown()
            return 0

    #---uninstall---
    elif cmd == 'uninstall':
        def do_spawn(x=None):
            from lib.settings import WindowsStarterFileName
            starter_filepath = os.path.join(bpio.getExecutableDir(), WindowsStarterFileName())
            lg.out(0, "bpmain.main bpstarter.exe path: %s " % starter_filepath)
            if not os.path.isfile(starter_filepath):
                lg.out(0, "bpmain.main ERROR %s not found" % starter_filepath)
                bpio.shutdown()
                return 1
            cmdargs = [os.path.basename(starter_filepath), 'uninstall']
            lg.out(0, "bpmain.main os.spawnve cmdargs="+str(cmdargs))
            ret = os.spawnve(os.P_DETACH, starter_filepath, cmdargs, os.environ)
            bpio.shutdown()
            return ret
        def do_reactor_stop_and_spawn(x=None):
            reactor.stop()
            ret = do_spawn()
            bpio.shutdown()
            return ret
        lg.out(0, 'bpmain.main UNINSTALL!')
        if not bpio.Windows():
            lg.out(0, 'This command can be used only under OS Windows.')
            bpio.shutdown()
            return 0
        if not bpio.isFrozen():
            lg.out(0, 'You are running BitPie.NET from sources, uninstall command is available only for binary version.')
            bpio.shutdown()
            return 0
        appList = bpio.find_process(['bitpie.exe',])
        if len(appList) > 0:
            lg.out(0, 'found main BitPie.NET process...   ', '')
            try:
                from twisted.internet import reactor
                from command_line import run_url_command
                url = '?action=exit'
                run_url_command(url).addBoth(do_reactor_stop_and_spawn)
                reactor.run()
                bpio.shutdown()
                return 0
            except:
                lg.exc()
        ret = do_spawn()
        bpio.shutdown()
        return ret
        
    #---command_line---
    import command_line
    ret = command_line.run(opts, args, overDict, pars)
    if ret == 2:
        print usage()
    bpio.shutdown()
    return ret 

#-------------------------------------------------------------------------------


def usage():
    """
    Calls ``p2p.help.usage()`` method to print out how to run BitPie.NET software from command line.
    """
    try:
        import help
        return help.usage()
    except:
        return ''
    

def help():
    """
    Same thing, calls ``p2p.help.help()`` to show detailed instructions.
    """
    try:
        import help
        return help.help()
    except:
        return ''


def backup_schedule_format():
    """
    See ``p2p.help.schedule_format()`` method.
    """
    try:
        import help
        return help.schedule_format()
    except:
        return ''


def copyright():
    """
    Prints the copyright string.
    """
    print 'Copyright BitPie.NET, 2014. All rights reserved.'

#------------------------------------------------------------------------------ 


if __name__ == "__main__":
    ret = main()
    if ret == 2:
        print usage()
#    sys.exit(ret)

