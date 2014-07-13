#!/usr/bin/python
#dhnmain.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: dhnmain

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
    
    import lib.dhnio as dhnio
    dhnio.Dprint(6, 'dhnmain.run sys.path=%s' % str(sys.path))
    
    #---settings---
    import lib.settings as settings
    if overDict:
        settings.override_dict(overDict)
    settings.init()
    if not options or options.debug is None:
        dhnio.SetDebug(settings.getDebugLevel())    
    
    #---USE_TRAY_ICON---
    if os.path.isfile(settings.LocalIdentityFilename()) and os.path.isfile(settings.KeyFileName()):
        try:
            from dhnicon import USE_TRAY_ICON
            # dhnio.Dprint(4, 'dhnmain.run USE_TRAY_ICON='+str(USE_TRAY_ICON))
            if dhnio.Linux() and not dhnio.X11_is_running():
                USE_TRAY_ICON = False
            if USE_TRAY_ICON:
                from twisted.internet import wxreactor
                wxreactor.install()
        except:
            USE_TRAY_ICON = False
            dhnio.DprintException()
    else:
        USE_TRAY_ICON = False
    if USE_TRAY_ICON:
        if dhnio.Linux():
            icons_dict = {
                'red':      'icon-red-24x24.png',
                'green':    'icon-green-24x24.png',
                'gray':     'icon-gray-24x24.png', }
        else:
            icons_dict = {
                'red':      'icon-red.png',
                'green':    'icon-green.png',
                'gray':     'icon-gray.png', }
        import dhnicon
        icons_path = str(os.path.abspath(os.path.join(dhnio.getExecutableDir(), 'icons')))
        dhnio.Dprint(4, 'dhnmain.run call dhnicon.init(%s)' % icons_path)
        dhnicon.init(icons_path, icons_dict)
        def _tray_control_func(cmd):
            if cmd == 'exit':
                import shutdowner
                shutdowner.A('stop', 'exit')
        dhnicon.SetControlFunc(_tray_control_func)

    dhnio.Dprint(4, 'dhnmain.run want to import twisted.internet.reactor')
    try:
        from twisted.internet import reactor
    except:
        dhnio.DprintException()
        sys.exit('Error initializing reactor in dhnmain.py\n')

    #---logfile----
    if dhnio.EnableLog and dhnio.LogFile is not None:
        dhnio.Dprint(2, 'dhnmain.run want to switch log files')
        if dhnio.Windows() and dhnio.isFrozen():
            dhnio.StdOutRedirectingStop()
        dhnio.CloseLogFile()
        dhnio.OpenLogFile(settings.MainLogFilename()+'-'+time.strftime('%y%m%d%H%M%S')+'.log')
        if dhnio.Windows() and dhnio.isFrozen():
            dhnio.StdOutRedirectingStart()
            
    #---memdebug---
    if settings.uconfig('logs.memdebug-enable') == 'True':
        try:
            import lib.memdebug as memdebug
            memdebug_port = int(settings.uconfig('logs.memdebug-port'))
            memdebug.start(memdebug_port)
            reactor.addSystemEventTrigger('before', 'shutdown', memdebug.stop)
            dhnio.Dprint(2, 'dhnmain.run memdebug web server started on port %d' % memdebug_port)
        except:
            dhnio.DprintException()  
            
    #---process ID---
    try:
        pid = os.getpid()
        pid_file_path = os.path.join(settings.MetaDataDir(), 'processid')
        dhnio.WriteFile(pid_file_path, str(pid))
        dhnio.Dprint(2, 'dhnmain.run wrote process id [%s] in the file %s' % (str(pid), pid_file_path))
    except:
        dhnio.DprintException()  
            
#    #---reactor.callLater patch---
#    if dhnio.Debug(12):
#        patchReactorCallLater(reactor)
#        monitorDelayedCalls(reactor)

    dhnio.Dprint(2,"dhnmain.run UI=[%s]" % UI)

    if dhnio.Debug(10):
        dhnio.Dprint(0, '\n' + dhnio.osinfofull())

    dhnio.Dprint(4, 'dhnmain.run import automats')

    #---START!---
    import lib.automat as automat
    automat.LifeBegins(dhnio.LifeBeginsTime)
    # automat.OpenLogFile(settings.AutomatsLog())
    
    import initializer
    import shutdowner

    dhnio.Dprint(4, 'dhnmain.run send event "run" to initializer()')
    
    #reactor.callLater(0, initializer.A, 'run', UI)
    initializer.A('run', UI)

    dhnio.Dprint(2, 'dhnmain.run calling reactor.run()')
    reactor.run()

    dhnio.Dprint(2, 'dhnmain.run reactor stopped')
    shutdowner.A('reactor-stopped')

    dhnio.Dprint(2, 'dhnmain.run finished, EXIT')

    automat.CloseLogFile()

##    import threading
##    dhnio.Dprint(0, 'threads:')
##    for t in threading.enumerate():
##        dhnio.Dprint(0, '  '+str(t))

    dhnio.CloseLogFile()

    if dhnio.Windows() and dhnio.isFrozen():
        dhnio.StdOutRedirectingStop()

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
                        help='set location for temporary files, default is ~/.dhn/temp',)
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
    group.add_option('--no-cspace',
                        dest='no_cspace',
                        action='store_true',
                        help='do not use transport_cspace',)
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
    #if opts.no_q2q:
        #overDict['transport.transport-q2q.transport-q2q-enable'] = 'False'
    if opts.no_cspace:
        overDict['transport.transport-cspace.transport-cspace-enable'] = 'False'
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
    import lib.dhnio as dhnio
    total_count = 0
    found = False
    while True:
        appList = dhnio.find_process([
            'dhnmain.exe',
            'dhnmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            'dhnview.exe',
            'dhnview.py',
            'dhnbackup.exe',
            'dhnbackup.py',
            'dhntester.exe',
            'dhntester.py',
            'dhnstarter.exe',
            ])
        if len(appList) > 0:
            found = True
        for pid in appList:
            dhnio.Dprint(0, 'trying to stop pid %d' % pid)
            dhnio.kill_process(pid)
        if len(appList) == 0:
            if found:
                dhnio.Dprint(0, 'BitPie.NET stopped\n')
            else:
                dhnio.Dprint(0, 'BitPie.NET was not started\n')
            return 0
        total_count += 1
        if total_count > 10:
            dhnio.Dprint(0, 'some BitPie.NET process found, but can not stop it\n')
            return 1
        time.sleep(1)


def wait_then_kill(x):
    """
    For correct shutdown of the program need to send a URL request to the HTTP server::
        http://localhost:<random port>/?action=exit
        
    After receiving such request the program will call ``p2p.dhninit.shutdown()`` method and stops.
    But if the main process was blocked it needs to be killed with system "kill" procedure.
    This method will wait for 10 seconds and then call method ``kill()``.    
    """
    from twisted.internet import reactor
    import lib.dhnio as dhnio
    total_count = 0
    while True:
        appList = dhnio.find_process([
            'dhnmain.exe',
            'dhnmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            'dhnview.exe',
            'dhnview.py',
            'dhnbackup.exe',
            'dhnbackup.py',
            'dhntester.exe',
            'dhntester.py',
            'dhnstarter.exe',
            ])
        if len(appList) == 0:
            dhnio.Dprint(0, 'DONE')
            reactor.stop()
            return 0
        total_count += 1
        if total_count > 10:
            dhnio.Dprint(0, 'not responding, KILLING ...')
            ret = kill()
            reactor.stop()
            return ret
        time.sleep(1)
        
#------------------------------------------------------------------------------ 

_OriginalCallLater = None
_DelayedCallsIndex = {}
_LastCallableID = 0

class DHN_callable():
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

def DHN_callLater(delay, callable, *args, **kw):
    """
    A wrapper around Twisted ``reactor.callLater()`` method.
    """
    global _OriginalCallLater
    dhn_call = DHN_callable(callable, *args, **kw)
    delayed_call = _OriginalCallLater(delay, dhn_call.call)
    return delayed_call

def patchReactorCallLater(r):
    """
    Replace original ``reactor.callLater()`` with my hacked solution to monitor overall performance.
    """
    global _OriginalCallLater
    _OriginalCallLater = r.callLater
    r.callLater = DHN_callLater 

def monitorDelayedCalls(r):
    """
    Print out all delayed calls.
    """
    global _DelayedCallsIndex
    import lib.dhnio as dhnio
    keys = _DelayedCallsIndex.keys()
    keys.sort(key=lambda cb: -_DelayedCallsIndex[cb][1])
    s = ''
    for i in range(0, min(10, len(_DelayedCallsIndex))):
        cb = keys[i]
        s += '        %d %d %s\n' % ( _DelayedCallsIndex[cb][0], _DelayedCallsIndex[cb][1], cb) 
    dhnio.Dprint(8, '    delayed calls: %d\n%s' % (len(_DelayedCallsIndex), s))
    r.callLater(10, monitorDelayedCalls, r)

#------------------------------------------------------------------------------ 

def main():
    """
    THIS IS THE ENTRY POINT OF THE PROGRAM!
    """
    try:
        import lib.dhnio as dhnio
    except:
        dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
        sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
        sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))
        try:
            import lib.dhnio as dhnio
        except:
            return 1

    # init IO module, update locale
    dhnio.init()

    # TODO
    # sys.excepthook = dhnio.ExceptionHook
    if not dhnio.isFrozen():
        from twisted.internet.defer import setDebugging
        setDebugging(True)

    # ask dhnio to count time for each line from that moment, not absolute time 
    dhnio.LifeBegins()

    pars = parser()
    (opts, args) = pars.parse_args()

    if opts.no_logs:
        dhnio.DisableLogs()

    #---logpath---
    logpath = os.path.join(os.path.expanduser('~'), '.bitpie', 'logs', 'start.log')
    if opts.output:
        logpath = opts.output

    if logpath != '':
        dhnio.OpenLogFile(logpath)
        dhnio.Dprint(2, 'dhnmain.main log file opened ' + logpath)
        if dhnio.Windows() and dhnio.isFrozen():
            dhnio.StdOutRedirectingStart()
            dhnio.Dprint(2, 'dhnmain.main redirecting started')

    if opts.debug or str(opts.debug) == '0':
        dhnio.SetDebug(opts.debug)

    if opts.quite and not opts.verbose:
        dhnio.DisableOutput()

    if opts.verbose:
        copyright()

    dhnio.Dprint(2, 'dhnmain.main started ' + time.asctime())

    overDict = override_options(opts, args)

    cmd = ''
    if len(args) > 0:
        cmd = args[0].lower()
        
    dhnio.Dprint(2, 'dhnmain.main args=%s' % str(args))

    #---start---
    if cmd == '' or cmd == 'start' or cmd == 'go':
        appList = dhnio.find_process([
            'dhnmain.exe',
            'dhnmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        
#        pid = -1
#        try:
#            if dhnio.Windows():
#                dhn_data_path = os.path.join(os.environ.get('APPDATA', os.path.join(os.path.expanduser('~'), 'Application Data')), 'BitPie.NET')
#                pid_path = os.path.join(dhn_data_path, 'metadata', 'processid')
#            else:
#                pid_path = os.path.join(os.path.expanduser('~'), '.datahaven', 'metadata', 'processid')
#            if os.path.isfile(pid_path):
#                pid = int(dhnio.ReadBinaryFile(pid_path).strip())
#        except:
#            dhnio.DprintException()
        # this is extra protection for Debian release
        # I am nut sure how process name can looks on different systems
        # check the process ID from previous start 
        # it file exists and we found this PID in the currently running apps - DHN is working
        # if file not exists we don't want to start if found some other jobs with same name 
        # PREPRO probably in future we can switch to this line:
        # if len(appList) > 0 and pid != -1 and pid in appList
        # because if we do not have pid - the process is not working
        # but old versions do not have pid file so we need to wait till 
        # all users be updated to this version - revision 7520+
#        if len(appList) > 0 and ( ( pid != -1 and pid in appList ) or ( pid == -1 ) ):

        if len(appList) > 0:
            dhnio.Dprint(0, 'BitPie.NET already started, found another process: %s' % str(appList))
            dhnio.shutdown()
            return 0
        ret = run('', opts, args, overDict)
        dhnio.shutdown()
        return ret

    #---restart---
    elif cmd == 'restart':
        appList = dhnio.find_process([
            'dhnmain.exe',
            'dhnmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        if len(appList) > 0:
            dhnio.Dprint(0, 'found main BitPie.NET process: %s, sending "restart" command ... ' % str(appList), '')
            def done(x):
                dhnio.Dprint(0, 'DONE\n', '')
                from twisted.internet import reactor
                if reactor.running and not reactor._stopped:
                    reactor.stop()
            def failed(x):
                dhnio.Dprint(0, 'FAILED, killing previous process and do restart\n', '')
                try:
                    kill()
                except:
                    dhnio.DprintException()
                from twisted.internet import reactor
                import lib.misc as misc
                reactor.addSystemEventTrigger('after','shutdown', misc.DoRestart)
                reactor.stop()
            try:
                from twisted.internet import reactor
                from command_line import run_url_command
                d = run_url_command('?action=restart', False)
                d.addCallback(done)
                d.addErrback(failed)
                reactor.run()
                dhnio.shutdown()
                return 0
            except:
                dhnio.DprintException()
                dhnio.shutdown()
                return 1
        else:
            ret = run('', opts, args, overDict)
            dhnio.shutdown()
            return ret

    #---show---
    elif cmd == 'show' or cmd == 'open':
        appList_dhnview = dhnio.find_process([
            'dhnview.exe',
            'dhnview.py',
            ])
        appList = dhnio.find_process([
            'dhnmain.exe',
            'dhnmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        if len(appList_dhnview) > 0:
            if len(appList) == 0:
                for pid in appList_dhnview:
                    dhnio.kill_process(pid)
            else:
                dhnio.Dprint(0, 'BitPie.NET GUI already opened, found another process: %s' % str(appList))
                dhnio.shutdown()
                return 0
        if len(appList) == 0:
            ret = run('show', opts, args, overDict)
            dhnio.shutdown()
            return ret
        
        dhnio.Dprint(0, 'found main BitPie.NET process: %s, start the GUI\n' % str(appList))
        ret = show()
        dhnio.shutdown()
        return ret

    #---stop---
    elif cmd == 'stop' or cmd == 'kill' or cmd == 'shutdown':
        appList = dhnio.find_process([
            'dhnmain.exe',
            'dhnmain.py',
            'bitpie.py',
            'regexp:^/usr/bin/python\ +/usr/bin/bitpie.*$',
            ])
        if len(appList) > 0:
            dhnio.Dprint(0, 'found main BitPie.NET process: %s, sending command "exit" ... ' % str(appList), '')
            try:
                from twisted.internet import reactor
                from command_line import run_url_command
                url = '?action=exit'
                run_url_command(url, False).addBoth(wait_then_kill)
                reactor.run()
                dhnio.shutdown()
                return 0
            except:
                dhnio.DprintException()
                ret = kill()
                dhnio.shutdown()
                return ret
        else:
            dhnio.Dprint(0, 'BitPie.NET is not running at the moment')
            dhnio.shutdown()
            return 0

    #---uninstall---
    elif cmd == 'uninstall':
        def do_spawn(x=None):
            from lib.settings import WindowsStarterFileName
            starter_filepath = os.path.join(dhnio.getExecutableDir(), WindowsStarterFileName())
            dhnio.Dprint(0, "dhnmain.main dhnstarter.exe path: %s " % starter_filepath)
            if not os.path.isfile(starter_filepath):
                dhnio.Dprint(0, "dhnmain.main ERROR %s not found" % starter_filepath)
                dhnio.shutdown()
                return 1
            cmdargs = [os.path.basename(starter_filepath), 'uninstall']
            dhnio.Dprint(0, "dhnmain.main os.spawnve cmdargs="+str(cmdargs))
            ret = os.spawnve(os.P_DETACH, starter_filepath, cmdargs, os.environ)
            dhnio.shutdown()
            return ret
        def do_reactor_stop_and_spawn(x=None):
            reactor.stop()
            ret = do_spawn()
            dhnio.shutdown()
            return ret
        dhnio.Dprint(0, 'dhnmain.main UNINSTALL!')
        if not dhnio.Windows():
            dhnio.Dprint(0, 'This command can be used only under OS Windows.')
            dhnio.shutdown()
            return 0
        if not dhnio.isFrozen():
            dhnio.Dprint(0, 'You are running BitPie.NET from sources, uninstall command is available only for binary version.')
            dhnio.shutdown()
            return 0
        appList = dhnio.find_process(['dhnmain.exe',])
        if len(appList) > 0:
            dhnio.Dprint(0, 'found main BitPie.NET process...   ', '')
            try:
                from twisted.internet import reactor
                from command_line import run_url_command
                url = '?action=exit'
                run_url_command(url).addBoth(do_reactor_stop_and_spawn)
                reactor.run()
                dhnio.shutdown()
                return 0
            except:
                dhnio.DprintException()
        ret = do_spawn()
        dhnio.shutdown()
        return ret
        
    #---command_line---
    import command_line
    ret = command_line.run(opts, args, overDict, pars)
    if ret == 2:
        print usage()
    dhnio.shutdown()
    return ret 

#-------------------------------------------------------------------------------


def usage():
    """
    Calls ``p2p.help.usage()`` method to print out how to run DHN software from command line.
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

