#!/usr/bin/python
#cmd_line_json.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: cmd_line_json

"""

import os
import sys

from twisted.internet import reactor

from lib.fastjsonrpc.client import Proxy as jsonProxy  
from lib import jsontemplate

from interface import cmd_line_json_templates as templ

#------------------------------------------------------------------------------ 

def parser():
    """
    Create an ``optparse.OptionParser`` object to read command line arguments.
    """
    from optparse import OptionParser, OptionGroup
    from main.help import usage
    parser = OptionParser(usage=usage())
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
    group.add_option('--twisted',
                        dest='twisted',
                        action='store_true',
                        help='show twisted log messages too',)
    parser.add_option_group(group)
    return parser


def override_options(opts, args):
    """
    The program can replace some user options by values passed via command line.
    This method return a dictionary where is stored a key-value pairs for new options.   
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
    sys.stdout.write(msg+nl)


def print_exception():
    """
    This is second most common method in the project.
    Print detailed info about last exception to the logs.
    """
    import traceback
    cla, value, trbk = sys.exc_info()
    try:
        excArgs = value.__dict__["args"]
    except KeyError:
        excArgs = ''
    excTb = traceback.format_tb(trbk)    
    s = 'Exception: <' + str(value) + '>\n'
    if excArgs:
        s += '  args:' + excArgs + '\n'
    for l in excTb:
        s += l + '\n'
    sys.stdout.write(s)


def print_and_stop(result):
    """
    Print text to console and stop the reactor.
    """
    import pprint
    pprint.pprint(result, indent=2,)
    reactor.stop()


def print_template(result, template):
    """
    Use json template to format the text and print to STDOUT.
    """
    # print result
    # print template
    sys.stdout.write(template.expand(result))
    # import pprint
    # sys.stdout.write(pprint.pformat(result, 4, 80))


def print_template_and_stop(result, template):
    """
    Print text with json template formatting and stop the reactor.
    """
    print_template(result, template)
    reactor.stop()


def fail_and_stop(err):
    """
    Send error message to STDOUT and stop the reactor.
    """
    try:
        print_text(err.getErrorMessage())
    except:
        print err
    reactor.stop()

#------------------------------------------------------------------------------ 

def call_jsonrpc_method(method, *args):
    """
    Method to communicate with existing BitDust process.
    Reads port number of the local RPC server and do the request.
    """
    from system import bpio
    from main import settings
    try:
        local_port = int(bpio.ReadBinaryFile(settings.LocalJsonRPCPortFilename()))
    except:
        local_port = settings.DefaultJsonRPCPort() 
    proxy = jsonProxy('http://127.0.0.1:'+str(local_port))
    return proxy.callRemote(method, *args)


def call_jsonrpc_method_and_stop(method, *args):
    """
    """
    d = call_jsonrpc_method(method, *args)
    d.addCallback(print_and_stop)
    d.addErrback(fail_and_stop) 
    reactor.run()
    return 0

def call_jsonrpc_method_template_and_stop(method, template, *args):
    """
    """
    d = call_jsonrpc_method(method, *args)
    d.addCallback(print_template_and_stop, template)
    d.addErrback(fail_and_stop) 
    reactor.run()
    return 0

#------------------------------------------------------------------------------ 

def kill():
    """
    Kill all running BitDust processes (except current).
    """
    import time
    from system import bpio
    total_count = 0
    found = False
    while True:
        appList = bpio.find_process([
            'bitdust.exe',
            'bpmain.py',
            'bitdust.py',
            'regexp:^/usr/bin/python.*bitdust.*$',
            'bpgui.exe',
            'bpgui.py',
            'bppipe.exe',
            'bppipe.py',
            'bptester.exe',
            'bptester.py',
            'bitstarter.exe',
            ])
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
    For correct shutdown of the program need to send a URL request to the HTTP server::
        http://localhost:<random port>/?action=exit
        
    After receiving such request the program will call ``p2p.init_shutdown.shutdown()`` method and stops.
    But if the main process was blocked it needs to be killed with system "kill" procedure.
    This method will wait for 10 seconds and then call method ``kill()``.    
    """
    import time
    from twisted.internet import reactor
    from logs import lg
    from system import bpio
    total_count = 0
    while True:
        appList = bpio.find_process([
            'bitdust.exe',
            'bpmain.py',
            'bitdust.py',
            'regexp:^/usr/bin/python.*bitdust.*$',
            'bpgui.exe',
            'bpgui.py',
            'bppipe.exe',
            'bppipe.py',
            'bptester.exe',
            'bptester.py',
            'bitstarter.exe',
            ])
        if len(appList) == 0:
            print_text('DONE')
            reactor.stop()
            return 0
        total_count += 1
        if total_count > 10:
            print_text('not responding, KILLING ...')
            ret = kill()
            reactor.stop()
            return ret
        time.sleep(1)

#------------------------------------------------------------------------------ 

def run_now(opts, args):
    from system import bpio
    from logs import lg
    lg.life_begins()
    if opts.no_logs:
        lg.disable_logs()
    overDict = override_options(opts, args)
    from main.bpmain import run
    ui = ''
    if len(args) > 0 and args[0].lower() in ['restart',]:
        ui = 'show'
    ret = run(ui, opts, args, overDict)
    bpio.shutdown()
    return ret

#------------------------------------------------------------------------------ 

def cmd_identity(opts, args, overDict, running):
    from userid import my_id
    from main import settings
    settings.init()
    my_id.init()    

    if len(args) == 1 or args[1].lower() in [ 'info', '?', 'show', 'print' ]:
        if my_id.isLocalIdentityReady():
            print_text(my_id.getLocalIdentity().serialize())
        else:
            print_text('local identity is not exist')
        return 0
    
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
        from automats import automat
        from main import initializer
        initializer.A('run-cmd-line-register', {'username': args[2], 'pksize': pksize})
        reactor.run()
        automat.objects().clear()
        if my_id.isLocalIdentityReady():
            print_text('new identity created:')
            print_text(my_id.getLocalIdentity().serialize())
        else:
            print_text('identity creation FAILED')
        return 0
    
    def _recover():
        from system import bpio
        from lib import nameurl
        if len(args) < 3:
            return 2
        src = bpio.ReadBinaryFile(args[2])
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
        if idurl == '' and len(args) > 3:
            idurl = args[3]
        if idurl == '':
            print_text('BitDust need to know your IDURL to recover your account\n')
            return 2
        from automats import automat
        from main import initializer
        initializer.A('run-cmd-line-recover', { 'idurl': idurl, 'keysrc': txt })
        reactor.run()
        automat.objects().clear()
        if my_id.isLocalIdentityReady():
            print_text('your identity were restored:')
            print_text(my_id.getLocalIdentity().serialize())
        else:
            print_text('identity recovery FAILED')
        return 0

    if args[1].lower() in ['create', 'new', 'register', 'generate', ]:
        if my_id.isLocalIdentityReady():
            print_text('local identity [%s] already exist\n' % my_id.getIDName())
            return 1
        if running:
            print_text('BitDust is running at the moment, need to stop the software at first\n')
            return 0
        return _register()

    if args[1].lower() in ['restore', 'recover', 'read', 'load', ]:
        if running:
            print_text('BitDust is running at the moment, need to stop the software at first\n')
            return 0
        return _recover()

    if args[1].lower() in ['delete', 'remove', 'erase', 'del', 'rm', 'kill']:
        if running:
            print_text('BitDust is running at the moment, need to stop the software at first\n')
            return 0
        oldname = my_id.getIDName()
        my_id.forgetLocalIdentity()
        my_id.eraseLocalIdentity()
        print_text('local identity [%s] is no longer exist\n' % oldname)
        return 0

    return 2

#------------------------------------------------------------------------------ 

def cmd_key(opts, args, overDict, running, executablePath):
    from main import settings
    from lib import misc
    from system import bpio
    from userid import my_id
    from crypt import key
    settings.init()
    my_id.init()
    
    if not key.LoadMyKey():
        print_text('private key not exist or is not valid\n')
        return 0
    if not my_id.isLocalIdentityReady():
        print_text('local identity not exist, your key worth nothing\n')
        return 0
    
    if len(args) == 2:
        if args[1] == 'copy':
            TextToSave = my_id.getLocalID() + "\n" + key.MyPrivateKey()
            misc.setClipboardText(TextToSave)
            del TextToSave
            print_text('now you can "paste" with Ctr+V your private key where you want')
            print_text('WARNING! keep your key in safe place, do not publish it!\n')
            return 0
        elif args[1] == 'print':
            TextToSave = my_id.getLocalID() + "\n" + key.MyPrivateKey()
            print_text('\n' + TextToSave + '\n')
            del TextToSave
            print_text('WARNING! keep your key in safe place, do not publish it!\n')
            return 0        
    elif len(args) == 3:
        if args[1] == 'copy' or args[1] == 'save' or args[1] == 'backup':
            from system import bpio
            curpath = os.getcwd()
            os.chdir(executablePath)
            filenameto = bpio.portablePath(args[2])
            os.chdir(curpath)
            TextToSave = my_id.getLocalID() + "\n" + key.MyPrivateKey()
            if not bpio.AtomicWriteFile(filenameto, TextToSave):
                del TextToSave
                print_text('error writing to %s\n' % filenameto)
                return 1
            del TextToSave
            print_text('your private key were copied to file %s' % filenameto)
            print_text('WARNING! keep your key in safe place, do not publish it!\n')
            return 0

    return 2
 
#------------------------------------------------------------------------------ 

def cmd_api(opts, args, overDict, executablePath):
    return call_jsonrpc_method_and_stop(args[1], *args[2:])

#------------------------------------------------------------------------------ 

def cmd_backup(opts, args, overDict, executablePath):
    if len(args) < 2 or args[1] in ['list', 'ls']:
        tpl = jsontemplate.Template(templ.TPL_BACKUPS_LIST)
        return call_jsonrpc_method_template_and_stop('backups_list', tpl)

    if len(args) == 1 and args[1] in ['idlist', 'ids']:
        tpl = jsontemplate.Template(templ.TPL_BACKUPS_LIST_IDS)
        return call_jsonrpc_method_template_and_stop('backups_id_list', tpl)

    if len(args) == 1 and args[1] in ['update', 'upd', 'refresh', 'sync']:
        return call_jsonrpc_method_template_and_stop('backups_update', tpl)
    
    if len(args) >= 2 and args[1] in ['running', 'progress', 'status']:
        tpl = jsontemplate.Template(templ.TPL_BACKUPS_RUNNING_LIST)
        return call_jsonrpc_method_template_and_stop('backups_running', tpl)

    if len(args) >= 2 and args[1] in ['queue', 'pending', 'qu', 'tasks']:
        tpl = jsontemplate.Template(templ.TPL_BACKUPS_TASKS_LIST)
        return call_jsonrpc_method_template_and_stop('backups_queue', tpl)

    tpl = jsontemplate.Template(templ.TPL_RAW)
    if len(args) >= 2 and args[1] == 'add':
        if os.path.isdir(args[2]):
            return call_jsonrpc_method_template_and_stop('backup_dir_add', tpl, args[2])
        elif os.path.isfile(args[2]):
            return call_jsonrpc_method_template_and_stop('backup_file_add', tpl, args[2])
        print_text('path %s not exist\n' % args[2])
        return 1
    
    if len(args) >= 2 and args[1] == 'addtree':
        if not os.path.isdir(args[2]):
            print_text('path %s not exist\n' % args[2])
            return 1
        return call_jsonrpc_method_template_and_stop('backup_tree_add', tpl, args[2])        
        
    from lib import packetid
    if len(args) >= 3 and args[1] in ['delete', 'del', 'rm', 'remove', 'erase', ]:
        if args[2] == 'local':
            if len(args) < 4:
                return 2
            return call_jsonrpc_method_template_and_stop('backup_delete_local', tpl, args[3])
        if packetid.Valid(args[2]):
            return call_jsonrpc_method_template_and_stop('backup_delete_id', tpl, args[2])
        return call_jsonrpc_method_template_and_stop('backup_delete_path', tpl, args[2])

    if len(args) > 2 and args[1] in ['cancel', 'abort']:
        if packetid.IsBackupIDCorrect(args[2]):
            return call_jsonrpc_method_template_and_stop('backup_abort_running', tpl, args[2])
        if packetid.IsPathIDCorrect(args[2]):
            return call_jsonrpc_method_template_and_stop('backup_cancel_pending', tpl, args[2])
        print_text('path %s not exist\n' % args[2])
        return 1

    if len(args) > 2 and args[1] == 'start':
        if packetid.Valid(args[2]):
            return call_jsonrpc_method_template_and_stop('backup_start_id', tpl, args[2])
        if not os.path.exists(os.path.abspath(args[2])):
            print_text('path %s not exist\n' % args[2])
            return 1
        return call_jsonrpc_method_template_and_stop('backup_start_path', tpl, args[2])

    if len(args) == 2:
        if packetid.Valid(args[1]):
            return call_jsonrpc_method_template_and_stop('backup_start_id', tpl, args[1])
        if not os.path.exists(os.path.abspath(args[1])):
            print_text('path %s not exist\n' % args[1])
            return 1
        return call_jsonrpc_method_template_and_stop('backup_start_path', tpl, args[1])

    return 2

#------------------------------------------------------------------------------ 

def cmd_restore(opts, args, overDict, executablePath):
    if len(args) < 2 or args[1] in ['list', 'ls']:
        tpl = jsontemplate.Template(templ.TPL_BACKUPS_LIST_IDS)
        return call_jsonrpc_method_template_and_stop('backups_id_list', tpl)

    if len(args) >= 2 and args[1] in ['running', 'progress', 'status']:
        tpl = jsontemplate.Template(templ.TPL_RESTORES_RUNNING_LIST)
        return call_jsonrpc_method_template_and_stop('restores_running', tpl)
    
    tpl = jsontemplate.Template(templ.TPL_RAW)
    if len(args) > 2 and args[1] in ['cancel', 'abort']:
        return call_jsonrpc_method_template_and_stop('restore_abort', tpl, args[2])

    if len(args) > 2 and args[1] in ['start',]:
        return call_jsonrpc_method_template_and_stop('restore_single', tpl, args[2])

    if len(args) == 2:
        return call_jsonrpc_method_template_and_stop('restore_single', tpl, args[1])
    
    if len(args) == 3:
        return call_jsonrpc_method_template_and_stop('restore_single', tpl, args[1], args[2])
    
    return 2    

#------------------------------------------------------------------------------ 

def cmd_integrate(opts, args, overDict):
    """
    A platform-dependent method to make a "system" command called "bitdust".
    Than you can 
    
    Run: 
        sudo python bitdust.py integrate
    
    Ubuntu: 
        This will create an executable file /usr/local/bin/bitdust with such content:
            #!/bin/sh
            cd [path to `bitdust` folder]
            python bitdust.py "$@"
    If this is sterted without root permissions, it should create a file ~/bin/bitdust.
    """
    def print_text(msg, nl='\n'):
        sys.stdout.write(msg+nl)
    from system import bpio
    if bpio.Windows():
        print_text('this feature is not yet available in OS Windows.')
        return 0
    curpath = bpio.getExecutableDir()
    cmdpath = '/usr/local/bin/bitdust'
    src = "#!/bin/sh\n"
    # src += "cd %s\n" % curpath
    src += 'python %s/bitdust.py "$@"\n' % curpath
    print_text('creating a command script : %s ... ' % cmdpath, nl='')
    result = False
    try:
        f = open(cmdpath, 'w')
        f.write(src)
        f.close()
        os.chmod(cmdpath, 0755)
        result = True
        print_text('SUCCESS')
    except:
        print_text('FAILED')
    if not result:
        cmdpath = os.path.join(os.path.expanduser('~'), 'bin', 'bitdust')
        print_text('try to create a command script in user home folder : %s ... ' % cmdpath, nl='')
        try:
            if not os.path.isdir(os.path.join(os.path.expanduser('~'), 'bin')):
                os.mkdir(os.path.join(os.path.expanduser('~'), 'bin'))
            f = open(cmdpath, 'w')
            f.write(src)
            f.close()
            os.chmod(cmdpath, 0755)
            result = True
            print_text('SUCCESS')
        except:
            print_text('FAILED')
            return 0
    if result:
        print_text('now use "bitdust" command to access the BitDust software.\n')
    return 0

#------------------------------------------------------------------------------ 

def option_name_to_path(name, default=''):
    path = default
    if name in [ 'donated', 'shared', 'given', ]:
        path = 'services/supplier/donated-space'
    elif name in [ 'needed', ]:
        path = 'services/customer/needed-space'
    elif name in [ 'suppliers', ]:
        path = 'services/customer/suppliers-number'
    elif name in [ 'debug' ]:
        path = 'logs/debug-level'
    elif name in [ 'block-size', ]:
        path = 'services/backups/block-size'
    elif name in [ 'block-size-max', 'max-block-size', ]:
        path = 'services/backups/max-block-size'
    elif name in [ 'max-backups', 'max-copies', 'copies' ]:
        path = 'services/backups/max-copies'
    elif name in [ 'local-backups', 'local-data', 'keep-local-data', ]:
        path = 'services/backups/keep-local-copies-enabled'
    elif name in [ 'tcp' ]:
        path = 'services/tcp-transport/enabled'
    elif name in [ 'tcp-port' ]:
        path = 'services/tcp-connections/tcp-port'
    elif name in [ 'udp' ]:
        path = 'services/udp-transport/enabled'
    elif name in [ 'udp-port' ]:
        path = 'services/udp-datagrams/udp-port'
    elif name in [ 'proxy' ]:
        path = 'services/proxy-transport/enabled'
    elif name in [ 'dht-port' ]:
        path = 'services/entangled-dht/udp-port'
    elif name in [ 'limit-send' ]:
        path = 'services/network/send-limit'
    elif name in [ 'limit-receive' ]:
        path = 'services/network/receive-limit'
    elif name in [ 'weblog' ]:
        path = 'logs/stream-enable'
    elif name in [ 'weblog-port' ]:
        path = 'logs/stream-port'
    return path

def cmd_set(opts, args, overDict):
    from main import settings
    from interface import api
    name = args[1].lower()
    if name in [ 'list', 'ls', 'all', 'show', 'print', ]:
        settings.init()
        sort = True if (len(args) > 2 and args[2] in ['sort', 'sorted', ]) else False 
        result = api.config_list(sort)
        tpl = jsontemplate.Template(templ.TPL_OPTIONS_LIST_KEY_TYPE_VALUE)
        print_template(result, tpl)
        return 0 
    path = '' if len(args) < 2 else args[1]
    path = option_name_to_path(name, path)
    if path != '':
        settings.init()
        if len(args) > 2:
            value = ' '.join(args[2:])
            result = api.config_set(path, unicode(value))
        else:
            result = api.config_get(path)
        tpl = jsontemplate.Template(templ.TPL_OPTION_MODIFIED)
        print_template(result, tpl)
        return 0
    return 2

def cmd_set_request(opts, args, overDict):
    print_text('connecting to already started BitDust process ...')
    name = args[1].lower()
    if name in [ 'list', 'ls', 'all', 'show', 'print', ]:
        sort = True if (len(args) > 2 and args[2] in ['sort', 'sorted', ]) else False 
        tpl = jsontemplate.Template(templ.TPL_OPTIONS_LIST_KEY_TYPE_VALUE)
        return call_jsonrpc_method_template_and_stop('config_list', tpl, sort)
    path = '' if len(args) < 2 else args[1]
    path = option_name_to_path(name, path)    
    if len(args) == 2:
        tpl = jsontemplate.Template(templ.TPL_OPTION_SINGLE)
        return call_jsonrpc_method_template_and_stop('config_get', tpl, path)
    value = ' '.join(args[2:])
    tpl = jsontemplate.Template(templ.TPL_OPTION_MODIFIED)
    return call_jsonrpc_method_template_and_stop('config_set', tpl, path, value)

#------------------------------------------------------------------------------ 

def cmd_suppliers(opts, args, overDict):
    if len(args) < 2 or args[1] in [ 'list', 'ls' ]:
        tpl = jsontemplate.Template(templ.TPL_SUPPLIERS)
        return call_jsonrpc_method_template_and_stop('suppliers_list', tpl)

    elif args[1] in [ 'ping', 'test', 'call', 'cl' ]:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_jsonrpc_method_template_and_stop('suppliers_ping', tpl)
 
    elif args[1] in [ 'fire', 'replace', 'rep', 'rp' ] and len(args) >= 3:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_jsonrpc_method_template_and_stop('supplier_replace', tpl, args[2])

    elif args[1] in [ 'hire', 'change', 'ch', ] and len(args) >= 4:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_jsonrpc_method_template_and_stop('supplier_change', tpl, args[2], args[3])
    return 2

#------------------------------------------------------------------------------ 

def cmd_customers(opts, args, overDict):
    if len(args) < 2 or args[1] in [ 'list', 'ls' ]:
        tpl = jsontemplate.Template(templ.TPL_CUSTOMERS)
        return call_jsonrpc_method_template_and_stop('customers_list', tpl)

    elif args[1] in [ 'ping', 'test', 'call', 'cl' ]:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_jsonrpc_method_template_and_stop('customers_ping', tpl)
 
    elif args[1] in [ 'reject', 'refuse', 'remove', 'delete', 'rm', 'free', 'del', ] and len(args) >= 3:
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_jsonrpc_method_template_and_stop('customer_reject', tpl, args[2])

    return 2

#------------------------------------------------------------------------------ 

def cmd_message(opts, args, overDict):
    if len(args) < 2 or args[1] == 'list':
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_jsonrpc_method_template_and_stop('list_messages', tpl)
    if len(args) >= 4 and args[1] in [ 'send', ]:
        tpl = jsontemplate.Template(templ.TPL_MESSAGE_SENDING)
        return call_jsonrpc_method_template_and_stop('send_message', tpl, args[2], args[3]) 
    return 2

#------------------------------------------------------------------------------ 

def cmd_friend(opts, args, overDict):
    tpl_lookup = jsontemplate.Template(templ.TPL_FRIEND_LOOKUP)
    tpl_add = jsontemplate.Template(templ.TPL_RAW)
    if len(args) < 2:
        tpl = jsontemplate.Template(templ.TPL_FRIEND_LOOKUP_REPEATED_SECTION)
        return call_jsonrpc_method_template_and_stop('list_correspondents', tpl)
    elif len(args) > 2 and args[1] in [ 'check', 'nick', 'nickname', 'test', ]:
        return call_jsonrpc_method_template_and_stop('find_peer_by_nickname', tpl_lookup, unicode(args[2]))
    elif len(args) > 2 and args[1] in [ 'add', 'append', ]:
        inp = unicode(args[2])
        if inp.startswith('http://'):
            return call_jsonrpc_method_template_and_stop('add_correspondent', tpl_add, inp)
        def _lookup(result):
            try:
                if result['result'] == 'exist':
                    print_template(result, tpl_lookup)
                    d = call_jsonrpc_method('add_correspondent', result['idurl'])
                    d.addCallback(print_template_and_stop, tpl_add)
                    d.addErrback(fail_and_stop) 
                    return 0
                else:                                                    
                    return print_template_and_stop(result, tpl_lookup)
            except:
                from logs import lg
                lg.exc()
                return 0
        d = call_jsonrpc_method('find_peer_by_nickname', inp)
        d.addCallback(_lookup)
        d.addErrback(fail_and_stop) 
        reactor.run()
        return 0
    return 2    

#------------------------------------------------------------------------------ 

def run(opts, args, pars=None, overDict=None, executablePath=None):
    cmd = ''
    if len(args) > 0:
        cmd = args[0].lower()

    from system import bpio
    bpio.init()

    #---start---
    if cmd == '' or cmd == 'start' or cmd == 'go' or cmd == 'run':
        appList = bpio.find_process([
            'bitdust.exe',
            'bpmain.py',
            'bitdust.py',
            'regexp:^/usr/bin/python.*bitdust.*$',
            ])
        if len(appList) > 0:
            print_text('BitDust already started, found another process: %s' % str(appList))
            return 0
        return run_now(opts, args)

    #---detach---
    elif cmd == 'detach':
        appList = bpio.find_process([
            'bitdust.exe',
            'bpmain.py',
            'bitdust.py',
            'regexp:^/usr/bin/python.*bitdust.*$',
            ])
        if len(appList) > 0:
            print_text('main BitDust process already started: %s' % str(appList))
            return 0
        from lib import misc
        print_text('run and detach main BitDust process')
        result = misc.DoRestart(detach=True)
        try:
            result = result.pid
        except:
            pass
        print_text(result)
        return 0

    #---restart---
    elif cmd == 'restart' or cmd == 'reboot':
        appList = bpio.find_process([
            'bitdust.exe',
            'bpmain.py',
            'bitdust.py',
            'regexp:^/usr/bin/python.*bitdust.*$',
            ])
        if len(appList) == 0:
            return run_now(opts, args)
        ui = False
        if cmd == 'restart':
            ui = True
        print_text('found main BitDust process: %s, sending "restart" command' % str(appList))
        def done(x):
            print_text('DONE\n', '')
            from twisted.internet import reactor
            if reactor.running and not reactor._stopped:
                reactor.stop()
        def failed(x):
            print_text('soft restart FAILED, now killing previous process and do restart')
            try:
                kill()
            except:
                print_exception()
            from twisted.internet import reactor
            from lib import misc
            reactor.addSystemEventTrigger('after', 'shutdown', misc.DoRestart, param='show' if ui else '', detach=True)
            reactor.stop()
        try:
            from twisted.internet import reactor
            call_jsonrpc_method('restart', ui).addCallbacks(done, failed)
            reactor.run()
        except:
            print_exception()
            return 1
        return 0

    #---show---
    elif cmd == 'show' or cmd == 'open':
        appList_bpgui = bpio.find_process([
            'bpgui.exe',
            'bpgui.py',
            ])
        appList = bpio.find_process([
            'bitdust.exe',
            'bpmain.py',
            'bitdust.py',
            'regexp:^/usr/bin/python.*bitdust.*$',
            ])
        if len(appList_bpgui) > 0:
            if len(appList) == 0:
                for pid in appList_bpgui:
                    bpio.kill_process(pid)
            else:
                print_text('BitDust GUI already opened, found another process: %s' % str(appList))
                return 0
        if len(appList) == 0:
            from lib import misc
            print_text('run and detach main BitDust process')
            result = misc.DoRestart('show', detach=True)
            try:
                result = result.pid
            except:
                pass
            print_text(result)
            return 0
        print_text('found main BitDust process: %s, sending command "show" to start the GUI\n' % str(appList))
        call_jsonrpc_method('show')
        return 0

    #---stop---
    elif cmd == 'stop' or cmd == 'kill' or cmd == 'shutdown':
        appList = bpio.find_process([
            'bitdust.exe',
            'bpmain.py',
            'bitdust.py',
            'regexp:^/usr/bin/python.*bitdust.*$',
            ])
        if len(appList) > 0:
            print_text('found main BitDust process: %s, sending command "exit" ... ' % str(appList), '')
            try:
                from twisted.internet import reactor
                call_jsonrpc_method('stop').addBoth(wait_then_kill)
                reactor.run()
                return 0
            except:
                print_exception()
                ret = kill()
                return ret
        else:
            print_text('BitDust is not running at the moment')
            return 0

    #---help---
    elif cmd in ['help', 'h', 'hlp', '?']:
        from main import help
        if len(args) >= 2 and args[1].lower() == 'schedule':
            print_text(help.schedule_format())
        elif len(args) >= 2 and args[1].lower() == 'settings':
            # from main import settings
            # settings.uconfig().print_all()
            from main import config
            for k in config.conf().listAllEntries():
                print k, config.conf().getData(k)
        else:
            print_text(help.help())
            print_text(pars.format_option_help())
        return 0
    
    appList = bpio.find_process([
        'bitdust.exe',
        'bpmain.py',
        'bitdust.py',
        'regexp:^/usr/bin/python.*bitdust.*$',
        ])
    running = len(appList) > 0
    overDict = override_options(opts, args)
            
    #---identity---
    if cmd == 'identity' or cmd == 'id':
        return cmd_identity(opts, args, overDict, running)

    #---key---
    elif cmd == 'key':
        return cmd_key(opts, args, overDict, running, executablePath)

    #---ping---
    if cmd == 'ping' or cmd == 'call' or cmd == 'sendid':
        if len(args) < 1:
            return 2
        tpl = jsontemplate.Template(templ.TPL_RAW)
        return call_jsonrpc_method_template_and_stop('ping', tpl, args[1])            
                
    #---set---
    elif cmd in ['set', 'get', 'conf', 'config', 'option', 'setting',]:
        if len(args) == 1 or args[1].lower() in [ 'help', '?' ]:
            from main import help
            print_text(help.settings_help())
            return 0
        if not running:
            return cmd_set(opts, args, overDict)
        return cmd_set_request(opts, args, overDict)    
    
    #---api---
    elif cmd in ['api', 'call', ]:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_api(opts, args, overDict, executablePath)
    
    #---messages---
    elif cmd == 'msg' or cmd == 'message' or cmd == 'messages':
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_message(opts, args, overDict)

    #---suppliers---
    elif cmd in [ 'suppliers', 'supplier', 'sup', 'supp', 'sp']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_suppliers(opts, args, overDict)
    
    #---customers---
    elif cmd in [ 'customers', 'customer', 'cus', 'cust', 'cu']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_customers(opts, args, overDict)

    #---friends---
    elif cmd == 'friend' or cmd == 'friends' or cmd == 'buddy' or cmd == 'correspondent' or cmd == 'contact' or cmd == 'peer':
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_friend(opts, args, overDict)
    
    #---backup---
    elif cmd in ['backup', 'backups', 'bk', 'up', 'upload', 'uploads',]:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_backup(opts, args, overDict, executablePath)

    #---restore---
    elif cmd in ['restore', 'rest', 'download', 'down',]:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_restore(opts, args, overDict, executablePath)

    #---version---
    elif cmd in [ 'version', 'v', 'ver' ]:
        from main import settings
        from lib import misc
        ver = bpio.ReadTextFile(settings.VersionNumberFile()).strip()
        chksum = bpio.ReadTextFile(settings.CheckSumFile()).strip()
        repo, location = misc.ReadRepoLocation()
        print_text('checksum:   %s' % chksum )
        print_text('version:    %s' % ver)
        print_text('repository: %s' % repo)
        print_text('location:   %s' % location)
        return 0

    #---integrate---
    elif cmd == 'integrate' or cmd == 'alias':
        return cmd_integrate(opts, args, overDict)
    
    return 2

#------------------------------------------------------------------------------ 

def main():
    try:
        from system import bpio
    except:
        dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
        sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
        from distutils.sysconfig import get_python_lib
        sys.path.append(os.path.join(get_python_lib(), 'bitdust'))
        try:
            from system import bpio
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

