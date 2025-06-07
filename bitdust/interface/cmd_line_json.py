#!/usr/bin/python
# cmd_line_json.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (cmd_line_json.py) is part of BitDust Software.
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
"""
..

module:: cmd_line_json
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
from six.moves import range

#------------------------------------------------------------------------------

_Debug = False

#------------------------------------------------------------------------------

import os
import sys
import time

#------------------------------------------------------------------------------

from bitdust.lib import jsontemplate
from bitdust.lib import strng
from bitdust.lib import jsn
from bitdust.lib import net_misc

from bitdust.interface import cmd_line_json_templates as templ

#------------------------------------------------------------------------------


def parser():
    """
    Create an ``optparse.OptionParser`` object to read command line arguments.
    """
    from optparse import OptionParser, OptionGroup
    from bitdust.main.help import usage_text
    parser = OptionParser(usage=usage_text())
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
        '--twisted',
        dest='twisted',
        action='store_true',
        help='show twisted log messages too',
    )
    parser.add_option_group(group)
    return parser


def override_options(opts, args):
    """
    The program can replace some user options by values passed via command
    line.

    This method return a dictionary where is stored a key-value pairs
    for new options.
    """
    overDict = {}
    if opts.debug or str(opts.debug) == '0':
        overDict['logs.debug-level'] = str(opts.debug)
    return overDict


#------------------------------------------------------------------------------


def print_copyright():
    """
    Prints the copyright string.
    """
    print_text('Copyright BitDust, 2014. All rights reserved.')


def print_text(msg, nl='\n'):
    """
    Send some output to the console.
    """
    sys.stdout.write(strng.to_text(msg) + nl)
    sys.stdout.flush()


def print_exception():
    """
    This is second most common method in the project.

    Print detailed info about last exception to the logs.
    """
    import traceback
    _, value, trbk = sys.exc_info()
    try:
        excArgs = value.__dict__['args']
    except KeyError:
        excArgs = ''
    excTb = traceback.format_tb(trbk)
    s = 'Exception: <' + str(value) + '>\n'
    if excArgs:
        s += '  args:' + excArgs + '\n'
    for l in excTb:
        s += l + '\n'
    sys.stdout.write(s)
    sys.stdout.flush()


def print_and_stop(result):
    """
    Print text to console and stop the reactor.
    """
    from twisted.internet import reactor  # @UnresolvedImport
    sys.stdout.write(jsn.dumps(result, indent=2, keys_to_text=True, values_to_text=True, ensure_ascii=True) + '\n')
    reactor.stop()  # @UndefinedVariable


def print_template(result, template):
    """
    Use json template to format the text and print to STDOUT.
    """
    try:
        template.undefined_str = '?'
        raw = template.expand(result)
    except Exception as e:
        print('failed to render output data: %r' % e)
        return
    sys.stdout.write(raw)
    sys.stdout.flush()


def print_template_and_stop(result, template):
    """
    Print text with json template formatting and stop the reactor.
    """
    from twisted.internet import reactor  # @UnresolvedImport
    print_template(result, template)
    reactor.stop()  # @UndefinedVariable


def fail_and_stop(err):
    """
    Send error message to STDOUT and stop the reactor.
    """
    from twisted.internet import reactor  # @UnresolvedImport
    try:
        print_text(err.getErrorMessage())
    except:
        print(err)
    reactor.stop()  # @UndefinedVariable


#------------------------------------------------------------------------------


def call_websocket_method(method, **kwargs):
    """
    Method allows to communicate with an existing BitDust process via WebSocket API interface.
    """
    from twisted.internet.defer import Deferred  # @UnresolvedImport
    from twisted.internet import reactor  # @UnresolvedImport
    from bitdust.lib import websock
    from bitdust.system import deploy
    ret = Deferred()
    _executed = time.time()
    timeout = kwargs.pop('websocket_timeout', None)
    if timeout:
        ret.addTimeout(timeout=(timeout + 1), clock=reactor)

    def _on_result(resp):
        if _Debug:
            print('call_websocket_method._on_result', method, kwargs, resp)
        try:
            websock.stop()
        except Exception as exc:
            if _Debug:
                print('call_websocket_method._on_result', exc)
        if method in [
            'process_stop',
        ]:
            if not ret.called:
                ret.callback({'status': 'OK', 'execution': '%3.6f' % (time.time() - _executed)})
            return None
        if not isinstance(resp, dict):
            if not ret.called:
                ret.errback(resp)
            return None
        if 'payload' not in resp:
            if not ret.called:
                ret.errback(Exception('received an empty response'))
            return None
        if not isinstance(resp['payload'], dict):
            if not ret.called:
                ret.errback(Exception('unexpected response received: %r' % resp['payload']))
            return None
        if 'errors' in resp['payload']:
            if not ret.called:
                ret.errback(Exception(', '.join(resp['payload']['errors'])))
            return None
        try:
            payload_response = resp['payload']['response']
        except Exception as exc:
            ret.errback(exc)
            return None
        payload_response['execution'] = '%3.6f' % (time.time() - _executed)
        ret.callback(payload_response)
        return resp

    def _on_open(ws_inst):
        if _Debug:
            print('call_websocket_method._on_open', method, kwargs, ws_inst)
        websock.ws_call(
            json_data={
                'command': 'api_call',
                'method': method,
                'kwargs': kwargs,
            },
            cb=_on_result,
            timeout=timeout,
        )

    def _on_error(err):
        if _Debug:
            print('call_websocket_method._on_error', method, kwargs, err)
        try:
            websock.stop()
        except Exception as exc:
            if _Debug:
                print('call_websocket_method._on_error', exc)
        if method in [
            'process_stop',
        ]:
            return None
        if not ret.called:
            ret.errback(err)
        return None

    websock.start(
        callbacks={
            'on_open': _on_open,
            'on_error': _on_error,
        },
        api_secret_filepath=os.path.join(deploy.current_base_dir(), 'apisecret'),
    )
    return ret


def call_websocket_method_and_stop(method, **kwargs):
    from twisted.internet import reactor  # @UnresolvedImport
    d = call_websocket_method(method, **kwargs)
    d.addCallback(print_and_stop)
    d.addErrback(fail_and_stop)
    reactor.run()  # @UndefinedVariable
    return 0


def call_websocket_method_template_and_stop(method, template, **kwargs):
    from twisted.internet import reactor  # @UnresolvedImport
    d = call_websocket_method(method, **kwargs)
    d.addCallback(print_template_and_stop, template)
    d.addErrback(fail_and_stop)
    reactor.run()  # @UndefinedVariable
    return 0


def call_websocket_method_transform_template_and_stop(method, template, transform, **kwargs):
    from twisted.internet import reactor  # @UnresolvedImport
    d = call_websocket_method(method, **kwargs)
    d.addCallback(lambda result: print_template_and_stop(transform(result), template))
    d.addErrback(fail_and_stop)
    reactor.run()  # @UndefinedVariable
    return 0


def call_api_method_template_and_stop(method, template, **kwargs):
    from twisted.internet import reactor  # @UnresolvedImport
    from bitdust.main import settings
    from bitdust.interface import api

    def _run():
        settings.init()
        m = getattr(api, method)
        d = m(**kwargs)
        d.addCallback(print_template_and_stop, template)
        d.addErrback(fail_and_stop)

    reactor.callWhenRunning(_run)  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable
    return 0


#------------------------------------------------------------------------------


def kill():
    """
    Kill all running BitDust processes (except current).
    """
    import time
    from bitdust.system import bpio
    total_count = 0
    found = False
    while True:
        appList = bpio.lookup_main_process()
        if len(appList) > 0:
            found = True
        for pid in appList:
            print_text('trying to stop pid %d' % pid)
            bpio.kill_process(pid)
        if len(appList) == 0:
            if found:
                print_text('BitDust stopped\n')
            else:
                print_text('BitDust was not started\n')
            return 0
        total_count += 1
        if total_count > 10:
            print_text('some BitDust process found, but can not stop it\n')
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
    import time
    from twisted.internet import reactor  # @UnresolvedImport
    from bitdust.system import bpio
    total_count = 0
    while True:
        appList = bpio.lookup_main_process()
        if len(appList) == 0:
            print_text('finished successfully')
            reactor.stop()  # @UndefinedVariable
            return 0
        total_count += 1
        if total_count > 10:
            print_text('not responding, going to kill the running process ...')
            ret = kill()
            reactor.stop()  # @UndefinedVariable
            return ret
        time.sleep(1)


#------------------------------------------------------------------------------


def run_now(opts, args):
    from bitdust.system import bpio
    from bitdust.logs import lg
    lg.life_begins()
    if opts.no_logs:
        lg.disable_logs()
    overDict = override_options(opts, args)
    from bitdust.main.bpmain import run
    ui = ''
    if len(args) > 0 and args[0].lower() in [
        'restart',
    ]:
        ui = 'show'
    ret = run(ui, opts, args, overDict)
    bpio.shutdown()
    return ret


#------------------------------------------------------------------------------


def cmd_deploy(opts, args, overDict):
    from bitdust.system import deploy
    return deploy.run(args)


#------------------------------------------------------------------------------


def cmd_reconnect(opts, args, overDict):
    tpl = jsontemplate.Template(templ.TPL_RAW)
    return call_websocket_method_template_and_stop('network_reconnect', tpl)


#------------------------------------------------------------------------------


def cmd_network(opts, args, overDict, running):
    if len(args) >= 3 and args[1] in ['create', 'setup']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        if not running:
            return call_api_method_template_and_stop('network_create', tpl, url=args[2])
        return call_websocket_method_template_and_stop('network_create', tpl, url=args[2])

    if len(args) >= 3 and args[1] in ['select', 'chose', 'set', 'switch']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        if not running:
            return call_api_method_template_and_stop('network_select', tpl, name=args[2])
        return call_websocket_method_template_and_stop('network_select', tpl, name=args[2])

    return 2


#------------------------------------------------------------------------------


def cmd_device(opts, args, overDict, running, executablePath):
    if not running:
        print_text('BitDust is not running at the moment\n')
        return 0

    if len(args) == 1 or (len(args) == 2 and args[1] in ['list', 'ls']):
        tpl = jsontemplate.Template(templ.TPL_DEVICES_LIST)
        return call_websocket_method_template_and_stop('devices_list', tpl)

    if len(args) > 3 and args[1] in ['create', 'new', 'add']:
        if args[2] not in ['routed', 'route', 'direct']:
            print_text('must specify type of the new device: "direct" or "routed"')
            return 1
        routed = args[2] in ['routed', 'route']
        device_name = args[3]
        key_sz = 2048
        if len(args) > 4:
            key_sz = int(args[4])
        from twisted.internet import reactor  # @UnresolvedImport

        def _on_client_code_confirmed(ret):
            if _Debug:
                print('_on_client_code_confirmed', ret)
            print_text('SUCCESS!')
            reactor.stop()  # @UndefinedVariable

        def _device_info_cb(ret):
            if _Debug:
                print('cmd_device._device_info_cb', ret)
            server_code = ret.get('result', {}).get('instance', {}).get('server_code')
            if not server_code:
                reactor.callLater(1, _wait_server_code)  # @UndefinedVariable
                return
            print_text('server code is: %r' % server_code)
            client_code = input('please enter the client code displayed at your device: ')
            d = call_websocket_method('device_authorization_client_code', name=device_name, client_code=client_code)
            d.addCallback(_on_client_code_confirmed)
            d.addErrback(fail_and_stop)

        def _wait_server_code():
            d = call_websocket_method('device_info', name=device_name)
            d.addCallback(_device_info_cb)
            d.addErrback(fail_and_stop)

        def _device_add_cb(ret):
            if _Debug:
                print('cmd_device._device_add_cb', ret)
            connected_routers = ret.get('result', {}).get('instance', {}).get('connected_routers', [])
            if not connected_routers:
                print_text('device configuration failed due to connection error')
                reactor.stop()  # @UndefinedVariable
                return
            route_url = net_misc.pack_device_url(connected_routers[0])
            print_text('enter the following connection info on your mobile device and then be ready to enter 6-digits server code:\n%s' % route_url)
            reactor.callLater(1, _wait_server_code)  # @UndefinedVariable

        def _add():
            d = call_websocket_method('device_add', name=device_name, routed=routed, key_size=key_sz, wait_listening=True)
            d.addCallback(_device_add_cb)
            d.addErrback(fail_and_stop)

        reactor.callWhenRunning(_add)  # @UndefinedVariable
        reactor.run()  # @UndefinedVariable
        return 0

    if len(args) >= 3 and args[1] in ['reset', 'drop', 'revoke', 'pair', 'auth', 'authorize']:
        tpl = jsontemplate.Template(templ.TPL_DEVICES_INFO)
        return call_websocket_method_template_and_stop('device_authorization_reset', tpl, name=args[2])

    if len(args) >= 3 and args[1] in ['info', 'print', 'get', 'show']:
        tpl = jsontemplate.Template(templ.TPL_DEVICES_INFO)
        return call_websocket_method_template_and_stop('device_info', tpl, name=args[2])

    if len(args) >= 3 and args[1] in ['delete', 'erase', 'remove', 'del', 'rm']:
        tpl = jsontemplate.Template(templ.TPL_DEVICES_INFO)
        return call_websocket_method_template_and_stop('device_remove', tpl, name=args[2])

    return 2


#------------------------------------------------------------------------------


def cmd_identity(opts, args, overDict, running, executablePath):
    from bitdust.main import initializer
    from bitdust.main import shutdowner
    from bitdust.main import settings
    from bitdust.userid import my_id
    initializer.init_settings()
    initializer.init_automats()
    my_id.init()

    def _do_cmd():
        if args[0] == 'idurl' and len(args) <= 1:
            if my_id.isLocalIdentityReady():
                print_text(my_id.getIDURL())
            else:
                print_text('local identity is not valid or not exist')
            return 0

        if args[0] in ['globid', 'globalid', 'gid', 'glid'] or (args[0] == 'id' and len(args) <= 1):
            if my_id.isLocalIdentityReady():
                print_text(my_id.getGlobalID())
            else:
                print_text('local identity is not valid or not exist')
            return 0

        if len(args) == 1 or args[1].lower() in ['info', '?', 'show', 'print']:
            if my_id.isLocalIdentityReady():
                print_text(my_id.getLocalIdentity().serialize(as_text=True))
            else:
                print_text('local identity is not valid or not exist')
            return 0

        from twisted.internet import reactor  # @UnresolvedImport

        if args[1] in ['server', 'srv'] and args[0]:

            def _run_standalone_id_server():
                from bitdust.logs import lg
                from bitdust.userid import id_server
                lg.open_log_file(os.path.join(settings.LogsDir(), 'idserver.log'))
                lg.set_debug_level(settings.getDebugLevel())
                reactor.addSystemEventTrigger('before', 'shutdown', id_server.A().automat, 'shutdown')  # @UndefinedVariable
                reactor.callWhenRunning(  # @UndefinedVariable
                    id_server.A,
                    'init',
                    (settings.getIdServerWebPort(), settings.getIdServerTCPPort()),
                )
                reactor.callLater(0, id_server.A, 'start')  # @UndefinedVariable
                reactor.run()  # @UndefinedVariable

            if len(args) <= 2:
                if not running:
                    _run_standalone_id_server()
                    return 0
                tpl = jsontemplate.Template(templ.TPL_SERVICE_INFO)
                return call_websocket_method_template_and_stop('service_info', tpl, service_name='service_identity_server')
            if args[2] == 'stop':
                if not running:
                    print_text('BitDust is not running at the moment\n')
                    return 0
                tpl = jsontemplate.Template(templ.TPL_RAW)
                return call_websocket_method_template_and_stop('service_stop', tpl, service_name='service_identity_server')
            if args[2] == 'start':
                if not running:
                    _run_standalone_id_server()
                    return 0
                tpl = jsontemplate.Template(templ.TPL_RAW)
                return call_websocket_method_template_and_stop('service_start', tpl, service_name='service_identity_server')
            return 2

        def _register():
            if len(args) <= 2:
                return 2
            pksize = settings.getPrivateKeySize()
            if len(args) > 3:
                try:
                    pksize = int(args[3])
                except:
                    print_text('incorrect private key size\n')
                    return 0
            from bitdust.lib import misc
            if not misc.ValidUserName(args[2]):
                print_text('invalid user name')
                return 0
            initializer.A('run-cmd-line-register', {'username': args[2], 'pksize': pksize})
            reactor.run()  # @UndefinedVariable
            shutdowner.shutdown_automats()
            my_id.loadLocalIdentity()
            if my_id.isLocalIdentityReady():
                print_text('\n' + my_id.getLocalIdentity().serialize(as_text=True))
            else:
                print_text('identity creation failed, please try again later')
            return 0

        def _recover():
            from bitdust.system import bpio
            from bitdust.lib import nameurl
            if len(args) < 3:
                return 2
            src = bpio.ReadTextFile(args[2])
            if len(src) > 1024*10:
                print_text('file is too big for private key')
                return 0
            try:
                lines = src.split('\n')
                idurl = lines[0]
                txt = '\n'.join(lines[1:])
                if idurl != nameurl.FilenameUrl(nameurl.UrlFilename(idurl)):
                    idurl = ''
                    txt = src
            except:
                idurl = ''
                txt = src
            if not idurl and len(args) > 3:
                idurl = args[3]
            if not idurl:
                print_text('BitDust need to know your IDURL to recover your account\n')
                return 2
            initializer.init_automats()
            initializer.A('run-cmd-line-recover', {'idurl': idurl, 'keysrc': txt})
            reactor.run()  # @UndefinedVariable
            shutdowner.shutdown_automats()
            my_id.loadLocalIdentity()
            if my_id.isLocalIdentityReady():
                print_text('\n' + my_id.getLocalIdentity().serialize(as_text=True))
            else:
                print_text('identity recovery FAILED')
            return 0

        if args[1].lower() in ['create', 'new', 'register', 'generate']:
            if my_id.isLocalIdentityReady():
                print_text('local identity [%s] already exist\n' % my_id.getIDName())
                return 1
            if running:
                print_text('BitDust is running at the moment, need to stop the software first\n')
                return 0
            return _register()

        if len(args) >= 2 and args[1].lower() in ['bk', 'backup', 'save']:
            from bitdust.interface import api
            key_id = 'master'
            key_json = api.key_get(key_id=key_id, include_private=True)
            if key_json['status'] != 'OK':
                print_text('\n'.join(key_json['errors']))
                return 1
            TextToSave = key_json['result']['creator'] + u'\n' + key_json['result']['private']
            if args[1] in ['bk', 'backup', 'save']:
                from bitdust.system import bpio
                curpath = os.getcwd()
                os.chdir(executablePath)
                if len(args) >= 3:
                    filenameto = bpio.portablePath(args[2])
                else:
                    key_file_name = key_json['result']['key_id'] + '.key'
                    filenameto = bpio.portablePath(os.path.join(os.path.expanduser('~'), key_file_name))
                    # filenameto = bpio.portablePath(os.path.join(executablePath, key_json['result']['key_id'] + '.key'))
                os.chdir(curpath)
                if not bpio.WriteTextFile(filenameto, TextToSave):
                    del TextToSave
                    print_text('error writing to %s\n' % filenameto)
                    return 1
                print_text('IDURL "%s" and "master" key was stored in "%s"' % (key_json['result']['creator'], filenameto))
                return 0
            return 2

        if args[1].lower() in ['restore', 'recover', 'read', 'load']:
            if running:
                print_text('BitDust is running at the moment, need to stop the software first\n')
                return 0
            return _recover()

        if args[1].lower() in ['delete', 'remove', 'erase', 'del', 'rm', 'kill']:
            if running:
                print_text('BitDust is running at the moment, need to stop the software first\n')
                return 0
            oldname = my_id.getIDName()
            if not oldname:
                print_text('local identity is not exist\n')
                return 0
            my_id.forgetLocalIdentity()
            my_id.eraseLocalIdentity()
            print_text('local identity [%s] is no longer exist\n' % oldname)
            return 0

        return 2

    ret = _do_cmd()
    shutdowner.shutdown_settings()
    return ret


#------------------------------------------------------------------------------


def cmd_key(opts, args, overDict, running, executablePath):
    if not running:
        print_text('BitDust is not running at the moment\n')
        return 0

    if len(args) == 1 or (len(args) == 2 and args[1] in ['list', 'ls']):
        tpl = jsontemplate.Template(templ.TPL_KEYS_LIST)
        return call_websocket_method_template_and_stop('keys_list', tpl, include_private=False)

    if len(args) >= 3 and args[1] in ['create', 'new', 'gen', 'generate', 'make']:
        key_id = args[2]
        key_sz = 4096
        if len(args) > 3:
            key_sz = int(args[3])
        tpl = jsontemplate.Template(templ.TPL_KEY_CREATE)
        return call_websocket_method_template_and_stop('key_create', tpl, key_alias=key_id, key_size=key_sz)

    if len(args) >= 2 and args[1] in ['copy', 'cp', 'bk', 'backup', 'save']:
        from twisted.internet import reactor  # @UnresolvedImport

        def _on_key(key_json):
            TextToSave = key_json['result']['creator'] + u'\n' + key_json['result']['private']
            if len(args) >= 4 and args[1] in ['bk', 'backup', 'save']:
                from bitdust.system import bpio
                curpath = os.getcwd()
                os.chdir(executablePath)
                filenameto = bpio.portablePath(args[3])
                os.chdir(curpath)
                if not bpio.WriteTextFile(filenameto, TextToSave):
                    del TextToSave
                    print_text('error writing to %s\n' % filenameto)
                    reactor.stop()  # @UndefinedVariable
                    return 1
                print_text('private key "%s" was stored in "%s"' % (key_json['result']['key_id'], filenameto))
            else:
                from bitdust.lib import misc
                misc.setClipboardText(TextToSave)
                print_text('key "%s" was sent to clipboard, you can use Ctrl+V to paste your private key where you want' % key_json['result']['key_id'])
            del TextToSave
            if key_json['result']['alias'] == 'master':
                print_text('WARNING! keep your "master" key in safe place, do not publish it!\n')
            reactor.stop()  # @UndefinedVariable
            return

        key_id = 'master' if len(args) < 3 else args[2]
        d = call_websocket_method('key_get', key_id=key_id, include_private=True)
        d.addCallback(_on_key)
        d.addErrback(fail_and_stop)
        reactor.run()  # @UndefinedVariable
        return 0

    if len(args) >= 2 and args[1] in ['print', 'get', 'show']:
        tpl = jsontemplate.Template(templ.TPL_KEY_GET)
        key_id = 'master' if len(args) < 3 else args[2]
        return call_websocket_method_template_and_stop('key_get', tpl, key_id=key_id, include_private=True)

    if len(args) >= 3 and args[1] in ['delete', 'erase', 'remove', 'clear', 'del', 'rm', 'kill']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('key_erase', tpl, key_id=args[2])

    if len(args) >= 4 and args[1] in ['share', 'send', 'transfer', 'access']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('key_share', tpl, key_id=args[2], idurl=args[3])

    return 2


#------------------------------------------------------------------------------


def cmd_api(opts, args, overDict, executablePath):
    if len(args) < 2:
        try:
            import inspect
            from bitdust.interface import api
        except:
            print_text('failed to import "interface.api" module')
            return 1
        for item in dir(api):
            if item.startswith('_'):
                continue
            if item in [
                'ERROR',
                'OK',
                'RESULT',
                'driver',
                'lg',
                'absolute_import',
                'Failure',
                'Deferred',
                'os',
                'time',
                'on_api_result_prepared',
                'succeed',
                'sys',
                'strng',
                'map',
                'jsn',
                'json',
                'gc',
                'config',
            ]:
                continue
            method = getattr(api, item, None)
            if not method:
                continue
            try:
                params = inspect.getargspec(method)
            except:
                print_text('    %s()' % item)
                continue
            doc_line = method.__doc__
            if not doc_line:
                doc_line = ''
            else:
                doc_line = doc_line.strip().split('\n')[0]
            print_text('\n    %s(%s)' % (
                item,
                ', '.join(params.args),
            ))
            print_text('        %s' % doc_line)
        return 0

    def _clean_value(v):
        if isinstance(v, str) and v in ['true', 'True']:
            return True
        return v

    try:
        pairs = [i.split('=') for i in args[2:]]
        kwargs = {k: _clean_value(v) for k, v in pairs}
    except Exception as e:
        print_text('failed reading input arguments: %s\n' % e)
        return 1
    return call_websocket_method_and_stop(args[1], **kwargs)


#------------------------------------------------------------------------------


def cmd_file(opts, args, overDict, executablePath):
    if args[0] in [
        'dir',
        'folder',
    ]:
        if len(args) > 2 and args[1] in ['create', 'make', 'cr', 'mk', 'add', 'bind', 'map']:
            tpl = jsontemplate.Template(templ.TPL_RAW)
            return call_websocket_method_template_and_stop('file_create', tpl, remote_path=args[2], as_folder=True)
        return 2

    if len(args) < 2 or args[1] in ['list', 'ls']:
        remote_path = args[2] if len(args) > 2 else None
        tpl = jsontemplate.Template(templ.TPL_BACKUPS_LIST)
        return call_websocket_method_template_and_stop('files_list', tpl, remote_path=remote_path)

    if len(args) == 2 and args[1] in ['update', 'upd', 'refresh', 'sync']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('files_sync', tpl)

    if len(args) >= 2 and args[1] in ['running', 'progress', 'status', 'prog']:
        if len(args) >= 3:
            if args[2] in ['download', 'down']:
                tpl = jsontemplate.Template(templ.TPL_BACKUPS_TASKS_LIST)
                return call_websocket_method_template_and_stop('files_downloads', tpl)
            elif args[2] in ['upload', 'up']:
                tpl = jsontemplate.Template(templ.TPL_BACKUPS_RUNNING_LIST)
                return call_websocket_method_template_and_stop('files_uploads', tpl)
            return 2
        tpl = jsontemplate.Template(templ.TPL_BACKUPS_RUNNING_LIST)
        return call_websocket_method_template_and_stop('files_uploads', tpl)

    if len(args) > 2 and args[1] in ['create', 'make', 'cr', 'mk', 'add', 'bind', 'map']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('file_create', tpl, remote_path=args[2], as_folder=False)

    if len(args) > 3 and args[1] in ['upload', 'up', 'store', 'start', 'send', 'write']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        if not os.path.exists(os.path.abspath(args[2])):
            print_text('path %s not exist\n' % args[2])
            return 1
        return call_websocket_method_template_and_stop('file_upload_start', tpl, local_path=args[2], remote_path=args[3], wait_result=False)

    if len(args) > 2 and args[1] in ['download', 'down', 'load', 'request', 'read', 'restore']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        if len(args) > 3:
            local_path = args[3]
        else:
            local_path = os.path.join(os.getcwd(), os.path.basename(args[2]))
        return call_websocket_method_template_and_stop('file_download_start', tpl, remote_path=args[2], destination_path=local_path)

    if len(args) > 2 and args[1] in ['delete', 'del', 'rm', 'remove', 'erase']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('file_delete', tpl, remote_path=args[2])

    if len(args) >= 3 and args[1] in ['cancel', 'abort']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        if len(args) > 3:
            if args[2] in ['download', 'down']:
                return call_websocket_method_template_and_stop('file_download_stop', tpl, remote_path=args[3])
            elif args[2] in ['upload', 'up']:
                return call_websocket_method_template_and_stop('file_upload_stop', tpl, remote_path=args[3])
            return 2
        return call_websocket_method_template_and_stop('file_upload_stop', tpl, remote_path=args[2])

    return 2


#------------------------------------------------------------------------------


def option_name_to_path(name, default=''):
    path = default
    if name in ['donated', 'shared', 'given']:
        path = 'services/supplier/donated-space'
    elif name in ['needed']:
        path = 'services/customer/needed-space'
    elif name in ['suppliers']:
        path = 'services/customer/suppliers-number'
    elif name in ['debug']:
        path = 'logs/debug-level'
    elif name in ['block-size']:
        path = 'services/backups/block-size'
    elif name in ['block-size-max', 'max-block-size']:
        path = 'services/backups/max-block-size'
    elif name in ['max-backups', 'max-copies', 'copies']:
        path = 'services/backups/max-copies'
    elif name in ['local-backups', 'local-data', 'keep-local-data']:
        path = 'services/backups/keep-local-copies-enabled'
    elif name in ['tcp']:
        path = 'services/tcp-transport/enabled'
    elif name in ['tcp-port']:
        path = 'services/tcp-connections/tcp-port'
    elif name in ['udp']:
        path = 'services/udp-transport/enabled'
    elif name in ['udp-port']:
        path = 'services/udp-datagrams/udp-port'
    elif name in ['proxy']:
        path = 'services/proxy-transport/enabled'
    elif name in ['http']:
        path = 'services/http-transport/enabled'
    elif name in ['http-port']:
        path = 'services/http-connections/http-port'
    elif name in ['dht-port']:
        path = 'services/entangled-dht/udp-port'
    elif name in ['limit-send']:
        path = 'services/network/send-limit'
    elif name in ['limit-receive']:
        path = 'services/network/receive-limit'
    elif name in ['weblog']:
        path = 'logs/stream-enable'
    elif name in ['weblog-port']:
        path = 'logs/stream-port'
    return path


def cmd_set(opts, args, overDict):
    from bitdust.main import initializer
    from bitdust.main import shutdowner
    from bitdust.interface import api
    initializer.init_settings()
    name = args[1].lower()
    if name in ['list', 'ls', 'all', 'show', 'print']:
        # sort = True if (len(args) > 2 and args[2] in ['sort', 'sorted', ]) else False
        sort = True
        result = api.configs_list(sort=sort)
        for i in range(len(result['result'])):
            val = result['result'][i]['value']
            if strng.is_string(val) and len(val) > 60:
                result['result'][i]['value'] = val[:60].replace('\n', '') + '...'
        tpl = jsontemplate.Template(templ.TPL_OPTIONS_LIST_KEY_TYPE_VALUE)
        print_template(result, tpl)
        shutdowner.shutdown_settings()
        return 0
    path = '' if len(args) < 2 else args[1]
    path = option_name_to_path(name, path)
    if path != '':
        if len(args) > 2:
            value = ' '.join(args[2:])
            result = api.config_set(path, strng.text_type(value))
        else:
            result = api.config_get(path)
        tpl = jsontemplate.Template(templ.TPL_OPTION_MODIFIED)
        print_template(result, tpl)
        shutdowner.shutdown_settings()
        return 0

    shutdowner.shutdown_settings()
    return 2


def cmd_set_request(opts, args, overDict):
    print_text('connecting to already started BitDust process ...')
    name = args[1].lower()
    if name in ['list', 'ls', 'all', 'show', 'print']:
        # sort = True if (len(args) > 2 and args[2] in ['sort', 'sorted', ]) else False
        sort = True
        tpl = jsontemplate.Template(templ.TPL_OPTIONS_LIST_KEY_TYPE_VALUE)

        def _limit_length(result):
            for i in range(len(result['result'])):
                val = result['result'][i]['value']
                if strng.is_string(val) and len(val) > 60:
                    result['result'][i]['value'] = val[:60].replace('\n', '') + '...'
            return result

        return call_websocket_method_transform_template_and_stop('configs_list', tpl, _limit_length, sort=sort)
    path = '' if len(args) < 2 else args[1]
    path = option_name_to_path(name, path)
    if len(args) == 2:
        tpl = jsontemplate.Template(templ.TPL_OPTION_SINGLE)
        return call_websocket_method_template_and_stop('config_get', tpl, key=path)
    value = ' '.join(args[2:])
    tpl = jsontemplate.Template(templ.TPL_OPTION_MODIFIED)
    return call_websocket_method_template_and_stop('config_set', tpl, key=path, value=value)


#------------------------------------------------------------------------------


def cmd_suppliers(opts, args, overDict):
    if len(args) < 2 or args[1] in ['list', 'ls']:
        tpl = jsontemplate.Template(templ.TPL_SUPPLIERS)
        return call_websocket_method_template_and_stop('suppliers_list', tpl)

    elif args[1] in ['ping', 'test', 'call', 'cl']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('suppliers_ping', tpl)

    elif args[1] in ['fire', 'replace', 'rep', 'rp'] and len(args) >= 3:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('supplier_change', tpl, position=args[2])

    elif args[1] in ['hire', 'change', 'ch'] and len(args) >= 4:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('supplier_change', tpl, position=args[2], new_supplier_id=args[3])

    return 2


#------------------------------------------------------------------------------


def cmd_customers(opts, args, overDict):
    if len(args) < 2 or args[1] in ['list', 'ls']:
        tpl = jsontemplate.Template(templ.TPL_CUSTOMERS)
        return call_websocket_method_template_and_stop('customers_list', tpl)

    elif args[1] in ['ping', 'test', 'call', 'cl']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('customers_ping', tpl)

    elif args[1] in ['reject', 'refuse', 'remove', 'delete', 'rm', 'free', 'del'] and len(args) >= 3:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('customer_reject', tpl, customer_id=args[2])

    return 2


#------------------------------------------------------------------------------


def cmd_storage(opts, args, overDict):
    if len(args) < 2:
        from twisted.internet import reactor  # @UnresolvedImport

        def _got_local(result3, result2, result1):
            result = {
                'status': 'OK',
                'execution': float(result1['execution']) + float(result2['execution']) + float(result3['execution']),
                'result': [{
                    'donated': result1['result'],
                    'consumed': result2['result'],
                    'local': result3['result'],
                }],
            }
            print_template(result, jsontemplate.Template(templ.TPL_STORAGE))
            reactor.stop()  # @UndefinedVariable

        def _got_needed(result2, result1):
            d2 = call_websocket_method('space_local')
            d2.addCallback(_got_local, result2, result1)
            d2.addErrback(fail_and_stop)

        def _got_donated(result1):
            d2 = call_websocket_method('space_consumed')
            d2.addCallback(_got_needed, result1)
            d2.addErrback(fail_and_stop)

        d1 = call_websocket_method('space_donated')
        d1.addCallback(_got_donated)
        d1.addErrback(fail_and_stop)
        reactor.run()  # @UndefinedVariable
        return 0
    return 2


#------------------------------------------------------------------------------


def cmd_automats(opts, args, overDict):
    if len(args) < 2 or args[1] == 'list':
        tpl = jsontemplate.Template(templ.TPL_AUTOMATS)

        def _automats_list_update(result):
            for i in range(len(result['result'])):
                r = result['result'][i]
                r['_past'] = '->'.join(r['past'])
                result['result'][i] = r
            return result

        return call_websocket_method_transform_template_and_stop('automats_list', tpl, _automats_list_update)
    return 2


#------------------------------------------------------------------------------


def cmd_services(opts, args, overDict):
    if len(args) < 2 or args[1] in ['list', 'ls']:

        def _services_update(result):
            for i in range(len(result['result'])):
                r = result['result'][i]
                r['enabled_label'] = 'ENABLED' if r['enabled'] else 'DISABLED'
                r['num_depends'] = len(r['depends'])
                result['result'][i] = r
            return result

        tpl = jsontemplate.Template(templ.TPL_SERVICES)
        return call_websocket_method_transform_template_and_stop('services_list', tpl, _services_update)

    if len(args) == 2 and args[1] in ['tree', 'tr']:

        def _services_update(result):
            for i in range(len(result['result'])):
                r = result['result'][i]
                r['enabled_label'] = 'ENABLED' if r['enabled'] else 'DISABLED'
                r['depends'] = ', '.join(r['depends']) if r['depends'] else 'no dependencies'
                r['offset'] = '| '*r['root_distance']
                result['result'][i] = r
            return result

        tpl = jsontemplate.Template(templ.TPL_SERVICES_TREE)
        return call_websocket_method_transform_template_and_stop('services_list', tpl, _services_update, as_tree=True)

    if len(args) >= 3 and args[1] in ['start', 'enable', 'on']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('service_start', tpl, service_name=args[2])

    if len(args) >= 3 and args[1] in ['stop', 'disable', 'off']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('service_stop', tpl, service_name=args[2])

    if len(args) >= 2:
        tpl = jsontemplate.Template(templ.TPL_SERVICE_INFO)
        return call_websocket_method_template_and_stop('service_info', tpl, service_name=args[1])

    return 2


#------------------------------------------------------------------------------


def cmd_message(opts, args, overDict):
    from twisted.internet import reactor  # @UnresolvedImport
    #     if len(args) < 2 or args[1] == 'list':
    #         tpl = jsontemplate.Template(templ.TPL_RAW)
    #         return call_websocket_method_template_and_stop('list_messages', tpl)
    if len(args) >= 4 and args[1] in ['send', 'to']:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('message_send', tpl, recipient_id=args[2], data=args[3])

    if len(args) < 2 or args[1] in ['listen', 'read']:
        from bitdust.chat import terminal_chat

        def _send_message(to, msg):
            return call_websocket_method('message_send', recipient_id=to, data=msg)

        def _search_user(inp):
            return call_websocket_method('user_search', nickname=inp)

        terminal_chat.init(
            do_send_message_func=_send_message,
            do_search_user_func=_search_user,
        )
        errors = []

        def _stop(x=None):
            reactor.callInThread(terminal_chat.stop)  # @UndefinedVariable
            reactor.stop()  # @UndefinedVariable
            return True

        def _error(x):
            if str(x).count('ResponseNeverReceived'):
                return x
            errors.append(str(x))
            _stop()
            return x

        def _consume(x=None):
            if x:
                if x['status'] != 'OK':
                    if 'errors' in x:
                        errors.extend(x['errors'])
                    _stop()
                    return x
                for msg in x['result']:
                    terminal_chat.on_incoming_message(msg)

            d = call_websocket_method('message_receive', consumer_callback_id='terminal_chat')
            d.addCallback(_consume)
            d.addErrback(_error)
            return x

        _consume()
        reactor.callInThread(terminal_chat.run)  # @UndefinedVariable
        reactor.run()  # @UndefinedVariable
        terminal_chat.shutdown()
        if len(errors):
            print('\n'.join(errors))
        return 0

    return 2


#------------------------------------------------------------------------------


def cmd_friend(opts, args, overDict):
    tpl_lookup = jsontemplate.Template(templ.TPL_FRIEND_LOOKUP)
    tpl_add = jsontemplate.Template(templ.TPL_RAW)
    if len(args) < 2:
        tpl = jsontemplate.Template(templ.TPL_FRIEND_LOOKUP_REPEATED_SECTION)
        return call_websocket_method_template_and_stop('list_correspondents', tpl)
    elif len(args) > 2 and args[1] in ['check', 'nick', 'nickname', 'test']:
        return call_websocket_method_template_and_stop('user_search', tpl_lookup, nickname=strng.text_type(args[2]))
    elif len(args) > 2 and args[1] in ['add', 'append']:
        inp = strng.text_type(args[2])
        if inp.startswith('http://'):
            return call_websocket_method_template_and_stop('friend_add', tpl_add, trusted_user_id=inp)

        def _lookup(result):
            try:
                if result['result'] == 'exist':
                    print_template(result, tpl_lookup)
                    d = call_websocket_method('friend_add', trusted_user_id=result['idurl'])
                    d.addCallback(print_template_and_stop, tpl_add)
                    d.addErrback(fail_and_stop)
                    return 0
                else:
                    return print_template_and_stop(result, tpl_lookup)
            except:
                from bitdust.logs import lg
                lg.exc()
                return 0

        d = call_websocket_method('user_search', nickname=inp)
        d.addCallback(_lookup)
        d.addErrback(fail_and_stop)
        reactor.run()  # @UndefinedVariable
        return 0
    return 2


#------------------------------------------------------------------------------


def cmd_dhtseed(opts, args, overDict):
    from bitdust.lib import misc
    from bitdust.system import bpio
    from bitdust.main import initializer
    from bitdust.main import shutdowner
    initializer.init_settings()

    if len(args) > 1 and args[1] in ['daemon', 'background', 'detach', 'spawn']:
        appList = bpio.find_main_process()
        if len(appList) > 0:
            print_text('main BitDust process already started: %s' % str(appList))
            shutdowner.shutdown_settings()
            return 0
        print_text('starting Distributed Hash Table seed node and detach main BitDust process')
        result = misc.DoRestart(
            param='dhtseed',
            detach=True,
        )
        try:
            result = result.pid
        except:
            result = str(result)
        shutdowner.shutdown_settings()
        return 0

    from bitdust.dht import dht_service
    from bitdust.logs import lg
    initializer.init_settings()
    dht_service.main(args=args[1:])
    shutdowner.shutdown_settings()
    return 0


#------------------------------------------------------------------------------


def run(opts, args, pars=None, overDict=None, executablePath=None):
    cmd = ''
    if len(args) > 0:
        cmd = args[0].lower()

    from bitdust.system import bpio
    bpio.init()

    #---install---
    if cmd in ['deploy', 'install', 'venv', 'virtualenv']:
        return cmd_deploy(opts, args, overDict)

    #---start---
    if not cmd or cmd == 'start' or cmd == 'go' or cmd == 'run':
        appList = bpio.find_main_process()
        if len(appList) > 0:
            print_text('BitDust already started, found another process: %s' % str(appList))
            return 0
        return run_now(opts, args)

    #---detach---
    elif cmd == 'detach':
        appList = bpio.find_main_process()
        if len(appList) > 0:
            print_text('main BitDust process already started: %s' % str(appList))
            return 0
        from bitdust.lib import misc
        print_text('run and detach main BitDust process')
        result = misc.DoRestart(detach=True, )
        try:
            result = result.pid
        except:
            result = str(result)
        print_text(result)
        return 0

    #---restart---
    elif cmd == 'restart' or cmd == 'reboot':
        appList = bpio.find_main_process()
        if len(appList) == 0:
            return run_now(opts, args)
        ui = False
        if cmd == 'restart':
            ui = True
        print_text('found main BitDust process: %s, executing "api.process_stop()" via WebSocket ... ' % str(appList))

        def done(x):
            print_text('DONE\n', '')
            from twisted.internet import reactor  # @UnresolvedImport
            if reactor.running and not reactor._stopped:  # @UndefinedVariable
                reactor.stop()  # @UndefinedVariable

        def failed(x):
            print_text('soft restart failed, trying to kill running process and force the restart')
            try:
                kill()
            except:
                print_exception()
            from twisted.internet import reactor  # @UnresolvedImport
            reactor.addSystemEventTrigger(  # @UndefinedVariable
                'after',
                'shutdown',
                misc.DoRestart,
                param='show' if ui else '',
                detach=True,
            )
            reactor.stop()  # @UndefinedVariable

        try:
            from twisted.internet import reactor  # @UnresolvedImport
            call_websocket_method('process_restart', websocket_timeout=5).addCallbacks(done, failed)
            reactor.run()  # @UndefinedVariable
        except:
            print_exception()
            return 1

        return 0

    #---show---
    elif cmd == 'show' or cmd == 'open':
        appList_bpgui = bpio.find_process(['bpgui.exe', 'bpgui.py'])
        appList = bpio.find_main_process()
        if len(appList_bpgui) > 0:
            if len(appList) == 0:
                for pid in appList_bpgui:
                    bpio.kill_process(pid)
            else:
                print_text('BitDust GUI already opened, found another process: %s' % str(appList))
                return 0
        if len(appList) == 0:
            print_text('run and detach main BitDust process')
            result = misc.DoRestart('show', detach=True)
            try:
                result = result.pid
            except:
                pass
            print_text(result)
            return 0
        # print_text('found main BitDust process: %s, sending command "show" to start the GUI\n' % str(appList))
        # call_websocket_method('show')
        return 0

    #---stop---
    elif cmd == 'stop' or cmd == 'kill' or cmd == 'shutdown':
        appList = bpio.find_main_process()
        if appList:
            print_text('found main BitDust process: %r ... ' % appList, '')
            try:
                from twisted.internet import reactor  # @UnresolvedImport
                call_websocket_method('process_stop', websocket_timeout=5).addBoth(wait_then_kill)
                reactor.run()  # @UndefinedVariable
                return 0
            except:
                print_exception()
                ret = kill()
                return ret
        else:
            appListAllChilds = bpio.find_main_process(
                check_processid_file=False,
                extra_lookups=[],
            )
            if appListAllChilds:
                print_text('found child BitDust processes: %s, perform "kill process" action ... ' % str(appList), '')
                ret = kill()
                return ret

            print_text('BitDust is not running at the moment')
            return 0

    #---help---
    elif cmd in ['help', 'h', 'hlp', '?']:
        from bitdust.main import help
        if len(args) >= 2 and args[1].lower() == 'schedule':
            print_text(help.schedule_format())
        elif len(args) >= 2 and args[1].lower() == 'settings':
            from bitdust.main import config
            for k in config.conf().listAllEntries():
                print(k, config.conf().getData(k))
        else:
            print_text(help.help_text())
            print_text(pars.format_option_help())
        return 0

    appList = bpio.find_main_process()
    running = (len(appList) > 0)

    overDict = override_options(opts, args)

    #---identity---
    if cmd in ['device', 'devices', 'dev']:
        return cmd_device(opts, args, overDict, running, executablePath)

    #---identity---
    elif cmd in ['identity', 'id', 'idurl', 'globalid', 'globid', 'glid', 'gid']:
        return cmd_identity(opts, args, overDict, running, executablePath)

    #---key---
    elif cmd in ['key', 'keys', 'pk', 'private_key', 'priv']:
        return cmd_key(opts, args, overDict, running, executablePath)

    #---ping---
    elif cmd == 'ping' or cmd == 'call' or cmd == 'sendid':
        if len(args) < 1:
            return 2
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_websocket_method_template_and_stop('user_ping', tpl, user_id=args[1])

    #---config---
    elif cmd in ['set', 'get', 'conf', 'config', 'option', 'setting']:
        if len(args) == 1 or args[1].lower() in ['help', '?']:
            from bitdust.main import help
            print_text(help.settings_help())
            return 0
        if not running:
            return cmd_set(opts, args, overDict)
        return cmd_set_request(opts, args, overDict)

    #---reconnect---
    elif cmd in ['reconnect', 'rejoin', 'connect']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_reconnect(opts, args, overDict)

    #---api---
    elif cmd in ['api', 'call']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_api(opts, args, overDict, executablePath)

    #---messages---
    elif cmd in ['msg', 'message', 'messages', 'chat', 'talk']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_message(opts, args, overDict)

    #---suppliers---
    elif cmd in ['suppliers', 'supplier', 'sup', 'supp', 'sp']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_suppliers(opts, args, overDict)

    #---customers---
    elif cmd in ['customers', 'customer', 'cus', 'cust', 'cu']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_customers(opts, args, overDict)

    #---storage---
    elif cmd in ['storage', 'space']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_storage(opts, args, overDict)

    #---storage---
    elif cmd in ['network', 'net', 'nw']:
        return cmd_network(opts, args, overDict, running)

    #---automats---
    elif cmd in ['st', 'state', 'automats', 'aut', 'states', 'machines']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_automats(opts, args, overDict)

    #---services---
    elif cmd in ['services', 'service', 'svc', 'serv', 'srv']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_services(opts, args, overDict)

    #---friends---
    elif cmd == 'friend' or cmd == 'friends' or cmd == 'buddy' or cmd == 'correspondent' or cmd == 'contact' or cmd == 'peer':
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_friend(opts, args, overDict)

    #---file---
    elif cmd in ['file', 'files', 'fi', 'fs', 'f', 'folder', 'dir']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_file(opts, args, overDict, executablePath)

    #---dhtseed---
    elif cmd == 'dhtseed':
        appList = bpio.find_main_process(
            check_processid_file=False,
            extra_lookups=[],
        )
        running = (len(appList) > 0)
        if running:
            print_text('BitDust is running at the moment, need to stop the software first\n')
            return 0
        return cmd_dhtseed(opts, args, overDict)

    #---version---
    elif cmd in ['version', 'v', 'ver']:
        from bitdust.main import settings
        from bitdust.lib import misc
        ver = bpio.ReadTextFile(settings.VersionNumberFile()).strip()
        chksum = bpio.ReadTextFile(settings.CheckSumFile()).strip()
        # repo, location = misc.ReadRepoLocation()
        print_text('checksum:   %s' % chksum)
        print_text('version:    %s' % ver)
        # print_text('repository: %s' % repo)
        # print_text('location:   %s' % location)
        return 0

    return 2


#------------------------------------------------------------------------------


def main():
    try:
        from bitdust.system import bpio
    except:
        dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
        sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
        from distutils.sysconfig import get_python_lib
        sys.path.append(os.path.join(get_python_lib(), 'bitdust'))
        try:
            from bitdust.system import bpio
        except:
            print_text('ERROR! can not import working code.  Python Path:\n')
            print_text('\n'.join(sys.path))
            return 1

    pars = parser()
    (opts, args) = pars.parse_args()

    if opts.verbose:
        print_copyright()

    return run(opts, args)


#------------------------------------------------------------------------------
