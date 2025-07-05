#!/usr/bin/env python
# bpmain.py
#
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import sys
import time
import threading

#-------------------------------------------------------------------------------

_AppDataDir = None

#-------------------------------------------------------------------------------


def print_text(msg, nl='\n'):
    """
    Send some text output to the console.
    """
    sys.stdout.write(msg + nl)
    sys.stdout.flush()


#-------------------------------------------------------------------------------


def show():
    """
    Just calls ``p2p.web.control.show()`` to open the GUI.
    """
    # TODO: to be implemented
    return 0


def init(UI='', options=None, args=None, overDict=None, executablePath=None):
    """
    In the method ``main()`` program firstly checks the command line arguments
    and then calls this method to start the whole process.

    This initialize some low level modules and finally create an
    instance of ``initializer()`` state machine and send it an event
    "run".
    """
    global _AppDataDir

    from bitdust.logs import lg
    if _Debug:
        lg.out(_DebugLevel, 'bpmain.init UI="%s"' % UI)

    from bitdust.system import bpio
    if _Debug:
        lg.out(_DebugLevel, 'bpmain.init ostype=%r' % bpio.ostype())

    #---settings---
    from bitdust.main import initializer
    initializer.init_settings(
        base_dir=_AppDataDir,
        override_configs=overDict,
        enable_debug=(not options or options.debug is None),
    )
    from bitdust.main import settings
    from bitdust.main import config

    #---USE_TRAY_ICON---
    USE_TRAY_ICON = False
    if _Debug:
        lg.out(_DebugLevel, '    USE_TRAY_ICON=' + str(USE_TRAY_ICON))
    if USE_TRAY_ICON:
        from bitdust.system import tray_icon
        icons_path = bpio.portablePath(os.path.join(bpio.getExecutableDir(), 'icons'))
        if _Debug:
            lg.out(_DebugLevel, 'bpmain.init call tray_icon.init(%s)' % icons_path)
        tray_icon.init(icons_path)

        def _tray_control_func(cmd):
            if cmd == 'exit':
                from bitdust.main import shutdowner
                shutdowner.A('stop', 'exit')

        tray_icon.SetControlFunc(_tray_control_func)

    #---OS Windows init---
    if bpio.Windows():
        try:
            from win32event import CreateMutex  # @UnresolvedImport
            mutex = CreateMutex(None, False, 'BitDust')
            if _Debug:
                lg.out(_DebugLevel, 'bpmain.init created a Mutex: %s' % str(mutex))
        except:
            lg.exc()

    #---twisted reactor---
    if _Debug:
        lg.out(_DebugLevel, 'bpmain.init want to import twisted.internet.reactor')
    try:
        from twisted.internet import reactor  # @UnresolvedImport
    except:
        lg.exc()
        sys.exit('Error initializing reactor in bpmain.py\n')
        return

    initializer.init_engine()

    #---memdebug---
    if config.conf().getBool('logs/memdebug-enabled'):
        try:
            from bitdust.logs import memdebug
            memdebug_port = int(config.conf().getData('logs/memdebug-port'))
            memdebug.start(memdebug_port)
            reactor.addSystemEventTrigger('before', 'shutdown', memdebug.stop)  # @UndefinedVariable
            if _Debug:
                lg.out(_DebugLevel, 'bpmain.init memdebug web server started on port %d' % memdebug_port)
        except:
            lg.exc()

    #---process ID---
    try:
        pid = os.getpid()
        pid_file_path = os.path.join(settings.AppDataDir(), 'processid')
        bpio.WriteTextFile(pid_file_path, str(pid))
        if _Debug:
            lg.out(_DebugLevel, 'bpmain.init wrote process id [%s] in the file %s' % (str(pid), pid_file_path))
    except:
        lg.exc()

    #---reactor.callLater patch---
    # if _Debug:
    #     patchReactorCallLater(reactor)
    #     monitorDelayedCalls(reactor)

    if _Debug:
        lg.out(_DebugLevel, '    python executable is: %s' % sys.executable)
        lg.out(_DebugLevel, '    python version is:\n%s' % sys.version)
        lg.out(_DebugLevel, '    python sys.path is:\n                %s' % ('\n                '.join(sys.path)))
        lg.out(_DebugLevel, '\n' + bpio.osinfofull())

    if _Debug:
        lg.out(_DebugLevel, 'bpmain.init going to initialize state machines')

    #---START!---
    initializer.init_automats()

    IA = initializer.A()
    if _Debug:
        lg.out(_DebugLevel, 'bpmain.init is sending event "run" to initializer()')
    if bpio.Android():
        IA.automat('run', UI)
    else:
        reactor.callWhenRunning(IA.automat, 'run', UI)  # @UndefinedVariable
    return IA


#------------------------------------------------------------------------------


def shutdown():
    from bitdust.logs import lg
    # from bitdust.main import config
    # from bitdust.system import bpio
    if _Debug:
        lg.out(_DebugLevel, 'bpmain.shutdown')

    from bitdust.main import shutdowner
    shutdowner.A('reactor-stopped')

    shutdowner.shutdown_automats()

    # from bitdust.main import listeners
    # listeners.shutdown()

    #     from bitdust.main import events
    #     events.shutdown()

    #     from bitdust.automats import automat
    #     automat.objects().clear()
    #     if len(automat.index()) > 0:
    #         lg.warn('%d automats was not cleaned' % len(automat.index()))
    #         for a in automat.index().keys():
    #             if _Debug:
    #                 lg.out(_DebugLevel, '    %r' % a)
    #     else:
    #         if _Debug:
    #             lg.out(_DebugLevel, 'bpmain.shutdown automat.objects().clear() SUCCESS, no state machines left in memory')

    if _Debug:
        lg.out(_DebugLevel, 'bpmain.shutdown currently %d threads running:' % len(threading.enumerate()))
    for t in threading.enumerate():
        if _Debug:
            lg.out(_DebugLevel, '    ' + str(t))

    if _Debug:
        lg.out(_DebugLevel, 'bpmain.shutdown finishing and closing log file, EXIT')

    shutdowner.shutdown_settings()

    # automat.CloseLogFile()
    # automat.SetExceptionsHandler(None)
    # automat.SetLogOutputHandler(None)

    lg.close_log_file()
    lg.close_intercepted_log_file()

    lg.stdout_stop_redirecting()
    lg.stderr_stop_redirecting()

    # from bitdust.main import settings
    # settings.shutdown()

    return 0


#------------------------------------------------------------------------------


def run_twisted_reactor():
    from bitdust.logs import lg
    try:
        from twisted.internet import reactor  # @UnresolvedImport
    except:
        lg.exc()
        sys.exit('Error initializing reactor in bpmain.py\n')
    if _Debug:
        lg.out(_DebugLevel, 'bpmain.run_twisted_reactor calling Twisted reactor.run()')
    reactor.run()  # @UndefinedVariable
    if _Debug:
        lg.out(_DebugLevel, 'bpmain.run_twisted_reactor Twisted reactor stopped')


def run(UI='', options=None, args=None, overDict=None, executablePath=None, start_reactor=True):
    if options and options.cpu_profile:
        import cProfile, pstats, io
        from pstats import SortKey  # @UnresolvedImport
        pr = cProfile.Profile()
        pr.enable()

    init(UI, options, args, overDict, executablePath)

    if start_reactor:
        run_twisted_reactor()
        result = shutdown()
    else:
        result = True

    if options and options.cpu_profile:
        pr.disable()
        s = io.StringIO()
        sortby = SortKey.CUMULATIVE
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        open('/tmp/bitdust.profile', 'w').write(s.getvalue())

    return result


#------------------------------------------------------------------------------


def parser():
    """
    Create an ``optparse.OptionParser`` object to read command line arguments.
    """
    from optparse import OptionParser, OptionGroup
    parser = OptionParser(usage=usage_text(), prog='BitDust')
    group = OptionGroup(parser, 'Logs')
    group.add_option(
        '-d',
        '--debug',
        dest='debug',
        type='int',
        help='set debug level',
    )
    group.add_option(
        '-q',
        '--quite',
        dest='quite',
        action='store_true',
        help='quite mode, do not print any messages to stdout',
    )
    group.add_option(
        '-v',
        '--verbose',
        dest='verbose',
        action='store_true',
        help='verbose mode, print more messages',
    )
    group.add_option(
        '--coverage',
        dest='coverage',
        action='store_true',
        help='record code coverage',
    )
    group.add_option('--coverage_config', dest='coverage_config', type='string', help='coverage configuration file path')
    group.add_option('--coverage_report', dest='coverage_report', type='string', help='file path to be used to store coverage report')
    group.add_option(
        '-n',
        '--no-logs',
        dest='no_logs',
        action='store_true',
        help='do not use logs',
    )
    group.add_option(
        '-o',
        '--output',
        dest='output',
        type='string',
        help='print log messages to the file',
    )
    group.add_option(
        '-a',
        '--appdir',
        dest='appdir',
        type='string',
        help='set alternative location for application data files, default is ~/.bitdust/',
    )
    #    group.add_option('-t', '--tempdir',
    #                        dest='tempdir',
    #                        type='string',
    #                        help='set location for temporary files, default is ~/.bitdust/temp',)
    group.add_option(
        '--twisted',
        dest='twisted',
        action='store_true',
        help='show twisted log messages too',
    )
    group.add_option(
        '--cpu-profile',
        dest='cpu_profile',
        action='store_true',
        help='use cProfile to profile performance, output is in the file /tmp/bitdust.profile',
    )
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
    from bitdust.system import bpio
    total_count = 0
    found = False
    while True:
        appList = bpio.lookup_main_process()
        if len(appList) > 0:
            found = True
        for pid in appList:
            print_text('trying to kill process %d' % pid)
            bpio.kill_process(pid)
        if len(appList) == 0:
            if found:
                print_text('BitDust stopped\n', nl='')
            else:
                print_text('BitDust was not started\n', nl='')
            return 0
        total_count += 1
        if total_count > 10:
            print_text('some BitDust process found, but can not be stoped\n', nl='')
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
    from bitdust.system import bpio
    total_count = 0
    while True:
        appList = bpio.lookup_main_process()
        if len(appList) == 0:
            print_text('DONE')
            reactor.stop()  # @UndefinedVariable
            return 0
        total_count += 1
        if total_count > 10:
            print_text('not responding, killing the process now ...')
            ret = kill()
            reactor.stop()  # @UndefinedVariable
            return ret
        time.sleep(1)


#------------------------------------------------------------------------------

_OriginalCallLater = None
_LastCallableID = 0


class _callable():

    """
    This class shows my experiments with performance monitoring.

    I tried to decrease the number of delayed calls.
    """

    def __init__(self, delay, callabl, *args, **kw):
        self.callabl = callabl
        self.to_call = lambda: self.run(*args, **kw)

    def run(self, *args, **kw):
        from bitdust.logs import measure_it
        measure_it.run(self.callabl, *args, **kw)

    def call(self):
        self.to_call()


def _callLater(delay, callabl, *args, **kw):
    """
    A wrapper around Twisted ``reactor.callLater()`` method.
    """
    global _OriginalCallLater
    _call = _callable(delay, callabl, *args, **kw)
    delayed_call = _OriginalCallLater(delay, _call.call)
    return delayed_call


def patchReactorCallLater(r, apply=True):
    """
    Replace original ``reactor.callLater()`` with my hacked solution to monitor
    overall performance.
    """
    global _OriginalCallLater
    if apply:
        _OriginalCallLater = r.callLater
        r.callLater = _callLater
    else:
        r.callLater = _OriginalCallLater
        _OriginalCallLater = None


def monitorDelayedCalls(r):
    """
    Print out all delayed calls.
    """
    from bitdust.logs import measure_it
    from bitdust.logs import lg
    stats = measure_it.top_calls()
    if _Debug:
        lg.out(_DebugLevel, '\nslowest calls:\n%s' % stats)
    r.callLater(30, monitorDelayedCalls, r)


#------------------------------------------------------------------------------


class TwistedUnhandledErrorsObserver:

    def __init__(self, level):
        self.level = level

    def __call__(self, event_dict):
        if event_dict.get('log_level') == self.level:
            if 'log_failure' in event_dict:
                f = event_dict['log_failure']
                from bitdust.logs import lg
                lg.exc(msg=f'Unhandled error in Deferred:\n{event_dict.get("debugInfo", "")}', exc_info=(f.type, f.value, f.getTracebackObject()))


#-------------------------------------------------------------------------------


def usage_text():
    """
    Calls ``p2p.help.usage_text()`` method to print out how to run BitDust software
    from command line.
    """
    try:
        from bitdust.main import help
        return help.usage_text()
    except:
        return ''


def help_text():
    """
    Same thing, calls ``p2p.help.help_text()`` to show detailed instructions.
    """
    try:
        from bitdust.main import help
        return help.help_text()
    except:
        return ''


def backup_schedule_format():
    """
    See ``p2p.help.schedule_format()`` method.
    """
    try:
        from bitdust.main import help
        return help.schedule_format()
    except:
        return ''


def copyright_text():
    """
    Prints the copyright string.
    """
    print('Copyright (C) 2008 Veselin Penev, https://bitdust.io')


#--- THE ENTRY POINT
def main(executable_path=None, start_reactor=True, appdir=None):
    """
    THE ENTRY POINT
    """
    global _AppDataDir

    if _Debug:
        print_text('ENTRY POINT: executable_path=%s appdir=%s' % (
            executable_path,
            appdir,
        ))

    pars = parser()
    (opts, args) = pars.parse_args()

    if not appdir:
        appdir = opts.appdir

    if opts.coverage:
        import coverage  # @UnresolvedImport
        cov = coverage.Coverage(config_file=opts.coverage_config)
        cov.start()

    overDict = override_options(opts, args)

    cmd = ''
    if len(args) > 0:
        cmd = args[0].lower()

    try:
        from bitdust.system import deploy
    except:
        dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
        sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
        from distutils.sysconfig import get_python_lib
        sys.path.append(os.path.join(get_python_lib(), 'bitdust'))
        try:
            from bitdust.system import deploy
        except:
            print_text('ERROR! can not import working code.  Python Path:')
            print_text('\n'.join(sys.path))
            return 1

    #---install---
    if cmd in ['deploy', 'install', 'venv', 'virtualenv']:
        from bitdust.system import deploy
        if cmd == 'install' and len(args) > 1 and args[1].lower() == 'crontab':
            from bitdust.system import crontab
            base_dir = deploy.init_base_dir()
            try:
                ret = crontab.check_install_crontab_record(base_dir)
            except Exception as exc:
                print_text(str(exc))
                return 1
            print_text(ret)
            return 0
        return deploy.run(args)

    #---integrate---
    if cmd == 'integrate' or cmd == 'alias' or cmd == 'shell':
        """
        This is a helper command to make a "system-wide" command called "bitdust" for fast access to the app.

        Run:
            python3 bitdust.py alias > /usr/local/bin/bitdust
            chmod +x /usr/local/bin/bitdust

        This will create an executable file /usr/local/bin/bitdust with such content:
            #!/bin/sh
            python3 [path to `bitdust` folder]/bitdust.py "$@"
        """
        from bitdust.system import bpio
        if bpio.Windows():
            # TODO:
            # src = u"""@echo off
            # C:\Users\veselin\BITDUS~2\venv\Scripts\python.exe C:\Users\veselin\BITDUS~2\src\bitdust.py %*
            # """
            print_text('this feature is not yet available for Windows')
            return 0
        python_path = os.path.abspath(os.path.join(os.path.expanduser('~'), '.bitdust', 'venv', 'bin', 'python'))
        curpath = os.path.abspath(os.path.join(bpio.getExecutableDir(), '..'))
        src = '#!/bin/sh\n'
        src += '# This is a very short shell script to help you create an alias "bitdust" in your OS for the BitDust software.\n'
        src += '# NOTICE: BitDust do not require root permissions to run, please always start it as normal user.\n'
        src += '# Run:\n'
        src += '#     python3 bitdust.py alias > /usr/local/bin/bitdust\n'
        src += '#     chmod +x /usr/local/bin/bitdust\n'
        src += '%s %s/bitdust.py "$@"\n' % (python_path, curpath)
        print_text(src)
        return 0

    if appdir:
        appdata = appdir
        _AppDataDir = appdata

    else:
        curdir = os.getcwd()
        appdatafile = os.path.join(curdir, 'appdata')
        defaultappdata = deploy.default_base_dir_portable()
        appdata = defaultappdata
        if os.path.isfile(appdatafile):
            try:
                appdata = os.path.abspath(open(appdatafile, 'rb').read().strip())
            except:
                appdata = defaultappdata
            if not os.path.isdir(appdata):
                appdata = defaultappdata
        _AppDataDir = appdata

    if _Debug:
        print_text('_AppDataDir: %s' % _AppDataDir)
        print_text('default_base_dir_portable(): %s' % deploy.default_base_dir_portable())

    #---BitDust Home
    try:
        result_app_dir = deploy.init_base_dir(base_dir=_AppDataDir)
    except Exception as e:
        print_text('failed to initialize application data folder: %e' % e)
        return 1

    if _Debug:
        print_text('app data dir prepared in %s' % result_app_dir)

    from bitdust.logs import lg

    #---init IO module
    from bitdust.system import bpio
    bpio.init()

    appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'processid'))

    if bpio.Android():
        from android.storage import app_storage_path  # @UnresolvedImport
        android_log_file = os.path.join(app_storage_path(), '.bitdust', 'logs', 'android.log')
        if _Debug:
            print_text('redirecting log output to %s' % android_log_file)
        lg.close_intercepted_log_file()
        lg.open_intercepted_log_file(android_log_file)

    # sys.excepthook = lg.exception_hook

    #---init logging
    from twisted.internet.defer import setDebugging  # @UnresolvedImport
    if _Debug:
        if bpio.isFrozen():
            setDebugging(False)
        else:
            setDebugging(True)
    else:
        setDebugging(False)

    from twisted.logger import globalLogPublisher, LogLevel
    tw_log_observer = TwistedUnhandledErrorsObserver(level=LogLevel.critical)
    globalLogPublisher.addObserver(tw_log_observer)

    #---life begins!
    # ask logger to count time for each log line from that moment, not absolute time
    lg.life_begins()

    # try to read debug level value at the early stage - no problem if fail here
    try:
        if cmd == '' or cmd == 'start' or cmd == 'go' or cmd == 'show' or cmd == 'open':
            lg.set_debug_level(int(bpio.ReadTextFile(os.path.abspath(os.path.join(appdata, 'config', 'logs', 'debug-level')))))
    except:
        pass

    if opts.no_logs:
        lg.disable_logs()

    if opts.debug or str(opts.debug) == '0':
        lg.set_debug_level(int(opts.debug))

    #---logpath---
    logpath = None
    if opts.output:
        logpath = opts.output
    else:
        try:
            os.makedirs(os.path.join(appdata, 'logs'), exist_ok=True)
        except:
            pass
        logpath = os.path.join(appdata, 'logs', 'stdout.log')

    need_redirecting = False

    if bpio.Windows() and not bpio.isConsoled():
        need_redirecting = True

    if logpath:
        if not appList:
            if cmd not in [
                'detach',
                'daemon',
                'stop',
                'kill',
                'shutdown',
                'restart',
                'reboot',
                'reconnect',
                'show',
                'open',
            ]:
                lg.open_log_file(logpath)
        if bpio.Windows() and bpio.isFrozen():
            need_redirecting = True

    if bpio.Android():
        need_redirecting = True

    if opts.quite and not opts.verbose:
        lg.disable_output()
    else:
        if need_redirecting:
            lg.stdout_start_redirecting()
            lg.stderr_start_redirecting()

    #---start---
    if cmd == '' or cmd == 'start' or cmd == 'go':
        if appList:
            print_text('BitDust already started, found another process: %s\n' % str(appList), nl='')
            bpio.shutdown()
            return 0

        UI = ''
        try:
            ret = run(UI, opts, args, overDict, executable_path, start_reactor)
        except:
            lg.exc()
            ret = 1
        bpio.shutdown()

        if opts.coverage:
            cov.stop()
            cov.save()
            if opts.coverage_report:
                cov.report(file=open(opts.coverage_report, 'w'))

        return ret

    #---daemon---
    elif cmd == 'detach' or cmd == 'daemon':
        appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'processid'))
        if len(appList) > 0:
            print_text('main BitDust process already started: %s\n' % str(appList), nl='')
            bpio.shutdown()
            if opts.coverage:
                cov.stop()
                cov.save()
                if opts.coverage_report:
                    cov.report(file=open(opts.coverage_report, 'w'))
            return 0
        from bitdust.lib import misc
        print_text('new BitDust process will be started in daemon mode\n', nl='')
        result = misc.DoRestart(detach=True,
                                # std_out=os.path.join(appdata, 'logs', 'stdout.log'),
                                # std_err=os.path.join(appdata, 'logs', 'stderr.log'),
                               )
        if result is not None:
            try:
                result = int(result)
            except:
                try:
                    result = result.pid
                except:
                    pass
        bpio.shutdown()
        if opts.coverage:
            cov.stop()
            cov.save()
            if opts.coverage_report:
                cov.report(file=open(opts.coverage_report, 'w'))
        return 0

    #---restart---
    elif cmd == 'restart' or cmd == 'reboot':
        appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'processid'))
        ui = False
        if len(appList) > 0:
            print_text('found main BitDust process: %r ... ' % appList, nl='')

            def done(x):
                print_text('finished successfully\n', nl='')
                from twisted.internet import reactor  # @UnresolvedImport
                if reactor.running and not reactor._stopped:  # @UndefinedVariable
                    reactor.stop()  # @UndefinedVariable

            def failed(x):
                if isinstance(x, Failure):
                    print_text('finished with: %s\n' % x.getErrorMessage(), nl='')
                else:
                    print_text('finished successfully\n', nl='')
                ok = str(x).count('Connection was closed cleanly') > 0
                from twisted.internet import reactor  # @UnresolvedImport
                if ok and reactor.running and not reactor._stopped:  # @UndefinedVariable
                    # print_text('DONE\n', '')
                    reactor.stop()  # @UndefinedVariable
                    return
                print_text('forcing previous process shutdown\n', nl='')
                try:
                    kill()
                except:
                    lg.exc()
                from bitdust.lib import misc
                reactor.addSystemEventTrigger(  # @UndefinedVariable
                    'after',
                    'shutdown',
                    misc.DoRestart,
                    param='show' if ui else '',
                    detach=True,  # std_out=os.path.join(appdata, 'logs', 'stdout.log'),
                    # std_err=os.path.join(appdata, 'logs', 'stderr.log'),
                )
                reactor.stop()  # @UndefinedVariable

            try:
                from twisted.internet import reactor  # @UnresolvedImport
                # from interface.command_line import run_url_command
                # d = run_url_command('?action=restart', False)
                # from bitdust.interface import cmd_line
                # d = cmd_line.call_xmlrpc_method('restart', ui)
                from bitdust.interface import cmd_line_json
                d = cmd_line_json.call_websocket_method('process_restart', websocket_timeout=5)
                d.addCallback(done)
                d.addErrback(failed)
                reactor.run()  # @UndefinedVariable
                bpio.shutdown()
                if opts.coverage:
                    cov.stop()
                    cov.save()
                    if opts.coverage_report:
                        cov.report(file=open(opts.coverage_report, 'w'))
                return 0
            except:
                lg.exc()
                bpio.shutdown()
                if opts.coverage:
                    cov.stop()
                    cov.save()
                    if opts.coverage_report:
                        cov.report(file=open(opts.coverage_report, 'w'))
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
            if opts.coverage:
                cov.stop()
                cov.save()
                if opts.coverage_report:
                    cov.report(file=open(opts.coverage_report, 'w'))
            return ret

    #---show---
    elif cmd == 'show' or cmd == 'open':
        if not bpio.isGUIpossible():
            print_text('BitDust GUI is turned OFF\n', nl='')
            bpio.shutdown()
            return 0
        if bpio.Linux() and not bpio.X11_is_running():
            print_text('this operating system not supporting X11 interface\n', nl='')
            bpio.shutdown()
            return 0
        appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'processid'))
        if len(appList) == 0:
            try:
                ret = run('show', opts, args, overDict, executable_path)
            except:
                lg.exc()
                ret = 1
            bpio.shutdown()
            return ret
        # print_text('found main BitDust process: %s, start the GUI\n' % str(appList))
        # ret = show()
        bpio.shutdown()
        return ret

    #---stop---
    elif cmd == 'stop' or cmd == 'kill' or cmd == 'shutdown':
        if cmd == 'kill':
            ret = kill()
            bpio.shutdown()
            if opts.coverage:
                cov.stop()
                cov.save()
                if opts.coverage_report:
                    cov.report(file=open(opts.coverage_report, 'w'))
            return ret
        appList = bpio.find_main_process(pid_file_path=os.path.join(appdata, 'processid'))
        if len(appList) > 0:
            if cmd == 'kill':
                print_text('found main BitDust process: %s, about to kill running process ... ' % appList, nl='')
                ret = kill()
                bpio.shutdown()
                if opts.coverage:
                    cov.stop()
                    cov.save()
                    if opts.coverage_report:
                        cov.report(file=open(opts.coverage_report, 'w'))
                return ret
            try:
                from twisted.internet import reactor  # @UnresolvedImport
                from twisted.python.failure import Failure

                def _stopped(x):
                    if _Debug:
                        if isinstance(x, Failure):
                            print_text('finished with: %s\n' % x.getErrorMessage(), nl='')
                        else:
                            print_text('finished with: %s\n' % x, nl='')
                    else:
                        print_text('finished successfully\n', nl='')
                    reactor.stop()  # @UndefinedVariable
                    bpio.shutdown()

                print_text('found main BitDust process: %s ... ' % appList, nl='')
                from bitdust.interface import cmd_line_json
                cmd_line_json.call_websocket_method('process_stop', websocket_timeout=2).addBoth(_stopped)
                reactor.run()  # @UndefinedVariable
                if opts.coverage:
                    cov.stop()
                    cov.save()
                    if opts.coverage_report:
                        cov.report(file=open(opts.coverage_report, 'w'))
                return 0
            except:
                lg.exc()
                ret = kill()
                bpio.shutdown()
                if opts.coverage:
                    cov.stop()
                    cov.save()
                    if opts.coverage_report:
                        cov.report(file=open(opts.coverage_report, 'w'))
                return ret
        else:
            appListAllChilds = bpio.find_main_process(
                check_processid_file=False,
                extra_lookups=[],
            )
            if len(appListAllChilds) > 0:
                print_text('BitDust child processes found: %s, performing "kill process" action ...\n' % appListAllChilds, nl='')
                ret = kill()
                if opts.coverage:
                    cov.stop()
                    cov.save()
                    if opts.coverage_report:
                        cov.report(file=open(opts.coverage_report, 'w'))
                return ret

            print_text('BitDust is not running at the moment\n', nl='')
            bpio.shutdown()
            if opts.coverage:
                cov.stop()
                cov.save()
                if opts.coverage_report:
                    cov.report(file=open(opts.coverage_report, 'w'))
            return 0

    #---command_line---
    from bitdust.interface import cmd_line_json as cmdln
    ret = cmdln.run(opts, args, pars, overDict, executable_path)
    if ret == 2:
        print_text(usage_text())
    bpio.shutdown()

    #---coverage report---
    if opts.coverage:
        cov.stop()
        cov.save()
        if opts.coverage_report:
            cov.report(file=open(opts.coverage_report, 'w'))

    return ret


#------------------------------------------------------------------------------

if __name__ == '__main__':
    ret = main()
    if ret == 2:
        print(usage_text())
