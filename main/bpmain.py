#!/usr/bin/env python
# bpmain.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (bpmain.py) is part of BitDust Software.
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
#

"""
.. module:: bpmain.

This is the entry point of the program, see method ``main()`` bellow.
"""

from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import time
import threading

#-------------------------------------------------------------------------------

AppDataDir = ''

#-------------------------------------------------------------------------------


def show():
    """
    Just calls ``p2p.web.control.show()`` to open the GUI.
    """
    from main import control
    # TODO: raise up electron window?
    return 0


def init(UI='', options=None, args=None, overDict=None, executablePath=None):
    """
    In the method ``main()`` program firstly checks the command line arguments
    and then calls this method to start the whole process.

    This initialize some low level modules and finally create an
    instance of ``initializer()`` state machine and send it an event
    "run".
    """
    global AppDataDir

    from logs import lg
    lg.out(4, 'bpmain.run UI="%s"' % UI)

    from system import bpio

    #---settings---
    from main import settings
    if overDict:
        settings.override_dict(overDict)
    settings.init(AppDataDir)
    if not options or options.debug is None:
        lg.set_debug_level(settings.getDebugLevel())
    from main import config
    config.conf().addCallback('logs/debug-level',
                              lambda p, value, o, r: lg.set_debug_level(value))

    #---USE_TRAY_ICON---
    if os.path.isfile(settings.LocalIdentityFilename()) and os.path.isfile(settings.KeyFileName()):
        try:
            from system.tray_icon import USE_TRAY_ICON
            if bpio.Mac() or not bpio.isGUIpossible():
                lg.out(4, '    GUI is not possible')
                USE_TRAY_ICON = False
            if USE_TRAY_ICON:
                from twisted.internet import wxreactor
                wxreactor.install()
                lg.out(4, '    wxreactor installed')
        except:
            USE_TRAY_ICON = False
            lg.exc()
    else:
        lg.out(4, '    local identity or key file is not ready')
        USE_TRAY_ICON = False
    lg.out(4, '    USE_TRAY_ICON=' + str(USE_TRAY_ICON))
    if USE_TRAY_ICON:
        from system import tray_icon
        icons_path = bpio.portablePath(os.path.join(bpio.getExecutableDir(), 'icons'))
        lg.out(4, 'bpmain.run call tray_icon.init(%s)' % icons_path)
        tray_icon.init(icons_path)

        def _tray_control_func(cmd):
            if cmd == 'exit':
                from . import shutdowner
                shutdowner.A('stop', 'exit')
        tray_icon.SetControlFunc(_tray_control_func)

    #---OS Windows init---
    if bpio.Windows():
        try:
            from win32event import CreateMutex  # @UnresolvedImport
            mutex = CreateMutex(None, False, "BitDust")
            lg.out(4, 'bpmain.run created a Mutex: %s' % str(mutex))
        except:
            lg.exc()

    #---twisted reactor---
    lg.out(4, 'bpmain.run want to import twisted.internet.reactor')
    try:
        from twisted.internet import reactor  # @UnresolvedImport
    except:
        lg.exc()
        sys.exit('Error initializing reactor in bpmain.py\n')

    #---logfile----
    if lg.logs_enabled() and lg.log_file():
        lg.out(2, 'bpmain.run want to switch log files')
        if bpio.Windows() and bpio.isFrozen():
            lg.stdout_stop_redirecting()
        lg.close_log_file()
        lg.open_log_file(settings.MainLogFilename())
        # lg.open_log_file(settings.MainLogFilename() + '-' + time.strftime('%y%m%d%H%M%S') + '.log')
        if bpio.Windows() and bpio.isFrozen():
            lg.stdout_start_redirecting()

    #---memdebug---
    if config.conf().getBool('logs/memdebug-enabled'):
        try:
            from logs import memdebug
            memdebug_port = int(config.conf().getData('logs/memdebug-port'))
            memdebug.start(memdebug_port)
            reactor.addSystemEventTrigger('before', 'shutdown', memdebug.stop)  # @UndefinedVariable
            lg.out(2, 'bpmain.run memdebug web server started on port %d' % memdebug_port)
        except:
            lg.exc()

    #---process ID---
    try:
        pid = os.getpid()
        pid_file_path = os.path.join(settings.MetaDataDir(), 'processid')
        bpio.WriteTextFile(pid_file_path, str(pid))
        lg.out(2, 'bpmain.run wrote process id [%s] in the file %s' % (str(pid), pid_file_path))
    except:
        lg.exc()

#    #---reactor.callLater patch---
#    if lg.is_debug(12):
#        patchReactorCallLater(reactor)
#        monitorDelayedCalls(reactor)

#    #---plugins---
#    from plugins import plug
#    plug.init()
#    reactor.addSystemEventTrigger('before', 'shutdown', plug.shutdown)

    lg.out(2, "    python executable is: %s" % sys.executable)
    lg.out(2, "    python version is:\n%s" % sys.version)
    lg.out(2, "    python sys.path is:\n                %s" % ('\n                '.join(sys.path)))

    lg.out(2, "bpmain.run UI=[%s]" % UI)

    if lg.is_debug(20):
        lg.out(0, '\n' + bpio.osinfofull())

    lg.out(4, 'import automats')

    #---START!---
    from automats import automat
    automat.LifeBegins(lg.when_life_begins())
    automat.OpenLogFile(settings.AutomatsLog())

    from main import events
    events.init()

    from main import initializer
    IA = initializer.A()
    lg.out(4, 'sending event "run" to initializer()')
    reactor.callWhenRunning(IA.automat, 'run', UI)  # @UndefinedVariable
    return IA

#------------------------------------------------------------------------------


def shutdown():
    from logs import lg
    from main import config
    from system import bpio
    lg.out(2, 'bpmain.shutdown')

    from . import shutdowner
    shutdowner.A('reactor-stopped')

    from main import events
    events.shutdown()

    from automats import automat
    automat.objects().clear()
    if len(automat.index()) > 0:
        lg.warn('%d automats was not cleaned' % len(automat.index()))
        for a in automat.index().keys():
            lg.out(2, '    %r' % a)
    else:
        lg.out(2, 'bpmain.shutdown automat.objects().clear() SUCCESS, no state machines left in memory')

    config.conf().removeCallback('logs/debug-level')

    lg.out(2, 'bpmain.shutdown currently %d threads running:' % len(threading.enumerate()))
    for t in threading.enumerate():
        lg.out(2, '    ' + str(t))

    lg.out(2, 'bpmain.shutdown finishing and closing log file, EXIT')

    automat.CloseLogFile()

    lg.close_log_file()

    if bpio.Windows() and bpio.isFrozen():
        lg.stdout_stop_redirecting()

    return 0

#------------------------------------------------------------------------------


def run_twisted_reactor():
    from logs import lg
    try:
        from twisted.internet import reactor  # @UnresolvedImport
    except:
        lg.exc()
        sys.exit('Error initializing reactor in bpmain.py\n')
    lg.out(2, 'bpmain.run_twisted_reactor calling Twisted reactor.run()')
    reactor.run()  # @UndefinedVariable
    lg.out(2, 'bpmain.run_twisted_reactor Twisted reactor stopped')


def run(UI='', options=None, args=None, overDict=None, executablePath=None, start_reactor=True):
    init(UI, options, args, overDict, executablePath)
    if start_reactor:
        run_twisted_reactor()
        result = shutdown()
    else:
        result = True
    return result

#------------------------------------------------------------------------------


def parser():
    """
    Create an ``optparse.OptionParser`` object to read command line arguments.
    """
    from optparse import OptionParser, OptionGroup
    parser = OptionParser(usage=usage_text(), prog='BitDust')
    group = OptionGroup(parser, "Logs")
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
    group.add_option('-a', '--appdir',
                     dest='appdir',
                     type='string',
                     help='set alternative location for application data files, default is ~/.bitdust/',)
#    group.add_option('-t', '--tempdir',
#                        dest='tempdir',
#                        type='string',
#                        help='set location for temporary files, default is ~/.bitdust/temp',)
    group.add_option('--twisted',
                     dest='twisted',
                     action='store_true',
                     help='show twisted log messages too',)
#    group.add_option('--memdebug',
#                        dest='memdebug',
#                        action='store_true',
#                        help='start web server to debug memory usage, need cherrypy and dozer modules',)
    parser.add_option_group(group)
#    group = OptionGroup(parser, "Network")
#    group.add_option('--tcp-port',
#                        dest='tcp_port',
#                        type='int',
#                        help='set tcp port number for incoming connections',)
#    group.add_option('--no-upnp',
#                        dest='no_upnp',
#                        action='store_true',
#                        help='do not use UPnP',)
#    group.add_option('--memdebug-port',
#                        dest='memdebug_port',
#                        type='int',
#                        default=9996,
#                        help='set port number for memdebug web server, default is 9995',)
#    parser.add_option_group(group)
    return parser


def override_options(opts, args):
    """
    The program can replace some user options by values passed via command
    line.

    This method return a dictionary where is stored a key-value pairs
    for new options.
    """
    overDict = {}
#    if opts.tcp_port:
#        overDict['services/tcp-connections/tcp-port'] = str(opts.tcp_port)
#    if opts.no_upnp:
#        overDict['services/tcp-connections/upnp-enabled'] = 'false'
    if opts.debug or str(opts.debug) == '0':
        overDict['logs/debug-level'] = str(opts.debug)
#    if opts.memdebug:
#        overDict['logs/memdebug-enable'] = str(opts.memdebug)
#        if opts.memdebug_port:
#            overDict['logs/memdebug-port'] = str(opts.memdebug_port)
#        else:
#            overDict['logs/memdebug-port'] = '9996'
    return overDict

#------------------------------------------------------------------------------


def kill():
    """
    Kill all running BitDust processes (except current).
    """
    from logs import lg
    from system import bpio
    total_count = 0
    found = False
    while True:
        appList = bpio.find_process([
            'regexp:^.*python.*bitdust.py.*?$',
            'bitdustnode.exe',
            'BitDustNode.exe',
            'BitDustConsole.exe',
            'bpmain.py',
            'bppipe.py',
            'bptester.py',
        ])
        if len(appList) > 0:
            found = True
        for pid in appList:
            lg.out(0, 'trying to stop pid %d' % pid)
            bpio.kill_process(pid)
        if len(appList) == 0:
            if found:
                lg.out(0, 'BitDust stopped\n')
            else:
                lg.out(0, 'BitDust was not started\n')
            return 0
        total_count += 1
        if total_count > 10:
            lg.out(0, 'some BitDust process found, but can not stop it\n')
            return 1
        time.sleep(1)


def wait_then_kill(x):
    """
    For correct shutdown of the program need to send a URL request to the HTTP
    server:: http://localhost:<random port>/?action=exit.

    After receiving such request the program will call
    ``p2p.init_shutdown.shutdown()`` method and stops. But if the main
    process was blocked it needs to be killed with system "kill"
    procedure. This method will wait for 10 seconds and then call method
    ``kill()``.
    """
    from twisted.internet import reactor  # @UnresolvedImport
    from logs import lg
    from system import bpio
    total_count = 0
    while True:
        appList = bpio.find_process([
            'regexp:^.*python.*bitdust.py.*?$',
            'bitdustnode.exe',
            'BitDustNode.exe',
            'BitDustConsole.exe',
            'bpmain.py',
            'bppipe.py',
            'bptester.py',
        ])
        if len(appList) == 0:
            lg.out(0, 'DONE')
            reactor.stop()  # @UndefinedVariable
            return 0
        total_count += 1
        if total_count > 10:
            lg.out(0, 'not responding, KILLING ...')
            ret = kill()
            reactor.stop()  # @UndefinedVariable
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

    def __init__(self, callabl, *args, **kw):
        global _DelayedCallsIndex
        self.callabl = callabl
        if self.callabl not in _DelayedCallsIndex:
            _DelayedCallsIndex[self.callabl] = [0, 0.0]
        self.to_call = lambda: self.run(*args, **kw)

    def run(self, *args, **kw):
        tm = time.time()
        self.callabl(*args, **kw)
        exec_time = time.time() - tm
        _DelayedCallsIndex[self.callabl][0] += 1
        _DelayedCallsIndex[self.callabl][1] += exec_time

    def call(self):
        self.to_call()


def _callLater(delay, callabl, *args, **kw):
    """
    A wrapper around Twisted ``reactor.callLater()`` method.
    """
    global _OriginalCallLater
    _call = _callable(callabl, *args, **kw)
    delayed_call = _OriginalCallLater(delay, _call.call)
    return delayed_call


def patchReactorCallLater(r):
    """
    Replace original ``reactor.callLater()`` with my hacked solution to monitor
    overall performance.
    """
    global _OriginalCallLater
    _OriginalCallLater = r.callLater
    r.callLater = _callLater


def monitorDelayedCalls(r):
    """
    Print out all delayed calls.
    """
    from six.moves import range
    global _DelayedCallsIndex
    from logs import lg
    keys = list(_DelayedCallsIndex.keys())
    keys.sort(key=lambda cb: -_DelayedCallsIndex[cb][1])
    s = ''
    for i in range(0, min(10, len(_DelayedCallsIndex))):
        cb = keys[i]
        s += '        %d %d %s\n' % (_DelayedCallsIndex[cb][0], _DelayedCallsIndex[cb][1], cb)
    lg.out(8, '    delayed calls: %d\n%s' % (len(_DelayedCallsIndex), s))
    r.callLater(10, monitorDelayedCalls, r)

#-------------------------------------------------------------------------------


def usage_text():
    """
    Calls ``p2p.help.usage_text()`` method to print out how to run BitDust software
    from command line.
    """
    try:
        from . import help
        return help.usage_text()
    except:
        return ''


def help_text():
    """
    Same thing, calls ``p2p.help.help_text()`` to show detailed instructions.
    """
    try:
        from . import help
        return help.help_text()
    except:
        return ''


def backup_schedule_format():
    """
    See ``p2p.help.schedule_format()`` method.
    """
    try:
        from . import help
        return help.schedule_format()
    except:
        return ''


def copyright_text():
    """
    Prints the copyright string.
    """
    print('Copyright BitDust, 2014. All rights reserved.')

#--- THIS IS THE ENTRY POINT OF THE PROGRAM! ---------------------------------------------------------


def main(executable_path=None, start_reactor=True):
    """
    THIS IS THE ENTRY POINT OF THE PROGRAM!
    """
    global AppDataDir

    pars = parser()
    (opts, args) = pars.parse_args()
    overDict = override_options(opts, args)

    cmd = ''
    if len(args) > 0:
        cmd = args[0].lower()

    #---install---
    if cmd in ['deploy', 'install', 'venv', 'virtualenv', ]:
        from system import deploy
        return deploy.run(args)

    try:
        from system import deploy
    except:
        dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
        sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
        # sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))
        from distutils.sysconfig import get_python_lib
        sys.path.append(os.path.join(get_python_lib(), 'bitdust'))
        try:
            from system import deploy
        except:
            print('ERROR! can not import working code.  Python Path:')
            print('\n'.join(sys.path))
            return 1

    if opts.appdir:
        appdata = opts.appdir
        AppDataDir = appdata

    else:
        curdir = os.getcwd()  # os.path.dirname(os.path.abspath(sys.executable))
        appdatafile = os.path.join(curdir, 'appdata')
        # defaultappdata = os.path.join(os.path.expanduser('~'), '.bitdust')
        defaultappdata = deploy.base_dir_portable()
        appdata = defaultappdata
        if os.path.isfile(appdatafile):
            try:
                appdata = os.path.abspath(open(appdatafile, 'rb').read().strip())
            except:
                appdata = defaultappdata
            if not os.path.isdir(appdata):
                appdata = defaultappdata
        AppDataDir = appdata

    #---BitDust Home
    deploy.init_base_dir(base_dir=AppDataDir)

    from logs import lg

    # init IO module, update locale
    from system import bpio
    bpio.init()

    # sys.excepthook = lg.exception_hook

    if not bpio.isFrozen():
        try:
            from twisted.internet.defer import setDebugging
            setDebugging(True)
            # from twisted.python import log as twisted_log
            # twisted_log.startLogging(sys.stdout)
        except:
            lg.warn('python-twisted is not installed')

    # ask to count time for each log line from that moment, not absolute time
    lg.life_begins()
    # try to read debug level value at the early stage - no problem if fail here
    try:
        if cmd == '' or cmd == 'start' or cmd == 'go' or cmd == 'show' or cmd == 'open':
            lg.set_debug_level(int(
                bpio.ReadTextFile(
                    os.path.abspath(
                        os.path.join(appdata, 'config', 'logs', 'debug-level')))))
    except:
        pass

    if opts.no_logs:
        lg.disable_logs()

    #---logpath---
    logpath = os.path.join(appdata, 'logs', 'start.log')
    if opts.output:
        logpath = opts.output

    need_redirecting = False

    if bpio.Windows() and not bpio.isConsoled():
        need_redirecting = True

    if logpath != '':
        lg.open_log_file(logpath)
        lg.out(2, 'bpmain.main log file opened ' + logpath)
        if bpio.Windows() and bpio.isFrozen():
            need_redirecting = True

    if need_redirecting:
        lg.stdout_start_redirecting()
        lg.out(2, 'bpmain.main redirecting started')

    # very basic solution to record run-time errors
    try:
        if os.path.isfile(os.path.join(appdata, 'logs', 'exception.log')):
            os.remove(os.path.join(appdata, 'logs', 'exception.log'))
    except:
        pass

    if opts.debug or str(opts.debug) == '0':
        lg.set_debug_level(opts.debug)

    # if opts.quite and not opts.verbose:
    #     lg.disable_output()

    if opts.verbose:
        copyright_text()

    lg.out(2, 'bpmain.main started ' + time.asctime())
    lg.out(2, 'bpmain.main args=%s' % str(args))

    #---start---
    if cmd == '' or cmd == 'start' or cmd == 'go':
        appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'metadata', 'processid'))
        if appList:
            lg.out(0, 'BitDust already started, found another process: %s\n' % str(appList))
            bpio.shutdown()
            return 0

        UI = ''
        # if cmd == 'show' or cmd == 'open':
        # UI = 'show'
        try:
            ret = run(UI, opts, args, overDict, executable_path, start_reactor)
        except:
            lg.exc()
            ret = 1
        bpio.shutdown()
        return ret

    #---daemon---
    elif cmd == 'detach' or cmd == 'daemon':
        appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'metadata', 'processid'))
        if len(appList) > 0:
            lg.out(0, 'main BitDust process already started: %s\n' % str(appList))
            bpio.shutdown()
            return 0
        from lib import misc
        lg.out(0, 'new BitDust process will be started in daemon mode\n')
        bpio.shutdown()
        result = misc.DoRestart(
            detach=True,
            std_out=os.path.join(appdata, 'logs', 'stdout.log'),
            std_err=os.path.join(appdata, 'logs', 'stderr.log'),
        )
        if result is not None:
            try:
                result = int(result)
            except:
                try:
                    result = result.pid
                except:
                    pass
        return 0

    #---restart---
    elif cmd == 'restart' or cmd == 'reboot':
        appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'metadata', 'processid'))
        ui = False
        if len(appList) > 0:
            lg.out(0, 'found main BitDust process: %s, sending "restart" command ... ' % str(appList), '')

            def done(x):
                lg.out(0, 'DONE\n', '')
                from twisted.internet import reactor  # @UnresolvedImport
                if reactor.running and not reactor._stopped:  # @UndefinedVariable
                    reactor.stop()  # @UndefinedVariable

            def failed(x):
                ok = str(x).count('Connection was closed cleanly') > 0
                from twisted.internet import reactor  # @UnresolvedImport
                if ok and reactor.running and not reactor._stopped:  # @UndefinedVariable
                    lg.out(0, 'DONE\n', '')
                    reactor.stop()  # @UndefinedVariable
                    return
                lg.out(0, 'FAILED while killing previous process - do HARD restart\n', '')
                try:
                    kill()
                except:
                    lg.exc()
                from lib import misc
                reactor.addSystemEventTrigger(  # @UndefinedVariable
                    'after',
                    'shutdown',
                    misc.DoRestart,
                    param='show' if ui else '',
                    detach=True,
                    std_out=os.path.join(appdata, 'logs', 'stdout.log'),
                    std_err=os.path.join(appdata, 'logs', 'stderr.log'),
                )
                reactor.stop()  # @UndefinedVariable
            try:
                from twisted.internet import reactor  # @UnresolvedImport
                # from interface.command_line import run_url_command
                # d = run_url_command('?action=restart', False)
                # from interface import cmd_line
                # d = cmd_line.call_xmlrpc_method('restart', ui)
                from interface import cmd_line_json
                d = cmd_line_json.call_jsonrpc_method('restart', ui)
                d.addCallback(done)
                d.addErrback(failed)
                reactor.run()  # @UndefinedVariable
                bpio.shutdown()
                return 0
            except:
                lg.exc()
                bpio.shutdown()
                return 1
        else:
            ui = ''
            if cmd == 'restart':
                ui = 'show'
            try:
                ret = run(ui, opts, args, overDict, executable_path)
            except:
                lg.exc()
                ret = 1
            bpio.shutdown()
            return ret

    #---show---
    elif cmd == 'show' or cmd == 'open':
        if not bpio.isGUIpossible():
            lg.out(0, 'BitDust GUI is turned OFF\n')
            bpio.shutdown()
            return 0
        if bpio.Linux() and not bpio.X11_is_running():
            lg.out(0, 'this operating system not supported X11 interface\n')
            bpio.shutdown()
            return 0
        appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'metadata', 'processid'))
        if len(appList) == 0:
            try:
                ret = run('show', opts, args, overDict, executable_path)
            except:
                lg.exc()
                ret = 1
            bpio.shutdown()
            return ret
        lg.out(0, 'found main BitDust process: %s, start the GUI\n' % str(appList))
        ret = show()
        bpio.shutdown()
        return ret

    #---stop---
    elif cmd == 'stop' or cmd == 'kill' or cmd == 'shutdown':
        appList = bpio.find_main_process(
            pid_file_path=os.path.join(appdata, 'metadata', 'processid'),
        )
        if len(appList) > 0:
            lg.out(0, 'found main BitDust process: %r, sending command "exit" ... ' % appList, '')
            try:
                from twisted.internet import reactor  # @UnresolvedImport
                # from interface.command_line import run_url_command
                # url = '?action=exit'
                # run_url_command(url, False).addBoth(wait_then_kill)
                # reactor.run()
                # bpio.shutdown()

                def _stopped(x):
                    lg.out(0, 'BitDust process finished correctly\n')
                    reactor.stop()  # @UndefinedVariable
                    bpio.shutdown()
                # from interface import cmd_line
                # cmd_line.call_xmlrpc_method('stop').addBoth(_stopped)
                from interface import cmd_line_json
                cmd_line_json.call_jsonrpc_method('stop').addBoth(_stopped)
                reactor.run()  # @UndefinedVariable
                return 0
            except:
                lg.exc()
                ret = kill()
                bpio.shutdown()
                return ret
        else:
            appListAllChilds = bpio.find_main_process(
                check_processid_file=False,
                extra_lookups=['regexp:^.*python.*bitdust.py.*?$', ],
            )
            if len(appListAllChilds) > 0:
                lg.out(0, 'BitDust child processes found: %r, performing "kill process" actions ...\n' % appListAllChilds, '')
                ret = kill()
                return ret

            lg.out(0, 'BitDust is not running at the moment\n')
            bpio.shutdown()
            return 0

    #---command_line---
    from interface import cmd_line_json as cmdln
    ret = cmdln.run(opts, args, pars, overDict, executable_path)
    if ret == 2:
        print(usage_text())
    bpio.shutdown()
    return ret

#------------------------------------------------------------------------------


if __name__ == "__main__":
    ret = main()
    if ret == 2:
        print(usage_text())
