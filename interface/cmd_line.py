#!/usr/bin/python
#cmd_line.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: cmd_line

"""

import os
import sys

from twisted.internet import reactor
from twisted.web import xmlrpc

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
    The program can replace some user options by values passed via command line.
    This method return a dictionary where is stored a key-value pairs for new options.   
    """
    overDict = {}
    if opts.tcp_port:
        overDict['transport.transport-tcp.transport-tcp-port'] = str(opts.tcp_port)
    if opts.no_upnp:
        overDict['services/tcp-connections/upnp-enabled'] = 'false'
    # if opts.tempdir:
    #     overDict['folder.folder-temp'] = opts.tempdir
    if opts.debug or str(opts.debug) == '0':
        overDict['logs.debug-level'] = str(opts.debug)
#    if opts.memdebug:
#        overDict['logs.memdebug-enable'] = str(opts.memdebug)
#        if opts.memdebug_port:
#            overDict['logs.memdebug-port'] = str(opts.memdebug_port)
#        else:
#            overDict['logs.memdebug-port'] = '9996'
    return overDict

#------------------------------------------------------------------------------ 

def print_copyright():
    """
    Prints the copyright string.
    """
    print_text('Copyright BitDust, 2014. All rights reserved.')
    

def print_text(msg, nl='\n'):
    """
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
    """
    print 'print_and_stop', result
    import pprint
    pprint.pprint(result, indent=2,)
    reactor.stop()
    
def fail_and_stop(err):
    try:
        print_text(err.getErrorMessage())
    except:
        print err
    reactor.stop()

#------------------------------------------------------------------------------ 

def call_xmlrpc_method(method, *args):
    """
    Method to communicate with existing BitDust process.
    Reads port number of the local RPC server and do the request.
    """
    from system import bpio
    from main import settings
    try:
        local_port = int(bpio.ReadBinaryFile(settings.LocalXMLRPCPortFilename()))
    except:
        local_port = settings.DefaultXMLRPCPort()
    xml_url = 'http://127.0.0.1:'+str(local_port) 
    proxy = xmlrpc.Proxy(xml_url, allowNone=True)
    return proxy.callRemote(method, *args)


def call_xmlrpc_method_and_stop(method, *args):
    """
    """
    call_xmlrpc_method(method, *args).addCallbacks(print_and_stop, fail_and_stop)
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
    ret = run('', opts, args, overDict)
    bpio.shutdown()
    return ret

#------------------------------------------------------------------------------ 

def cmd_backups(opts, args, overDict):
    if len(args) < 2 or args[1] == 'list':
        return call_xmlrpc_method_and_stop('backups_list')

    elif len(args) < 2 or args[1] == 'idlist':
        return call_xmlrpc_method_and_stop('backups_id_list')

    elif args[1] == 'start' and len(args) >= 3:
        from lib import packetid
        if packetid.Valid(args[2]):
            return call_xmlrpc_method_and_stop('backup_start_id', args[2])
        if not os.path.exists(os.path.abspath(args[2])):
            print_text('path %s not exist\n' % args[2])
            return 1
        return call_xmlrpc_method_and_stop('backup_start_path', args[2])

    elif args[1] == 'add' and len(args) >= 3:
        localpath = os.path.abspath(args[2])
        if not os.path.exists(localpath):
            print_text('path %s not exist\n' % args[2])
            return 1
        from system import bpio
        if bpio.pathIsDir(localpath):
            m = 'backup_dir_add'
        else:
            m = 'backup_file_add'
        return call_xmlrpc_method_and_stop(m, localpath)
    
    elif args[1] == 'addtree' and len(args) >= 3:
        localpath = os.path.abspath(args[2])
        from system import bpio
        if not bpio.pathIsDir(localpath):
            print_text('folder %s not exist\n' % args[2])
            return 1
        return call_xmlrpc_method_and_stop('backup_tree_add', localpath)

    elif args[1] == 'delete' and len(args) >= 3:
        if args[2] == 'local':
            if len(args) < 4:
                return 2
            return call_xmlrpc_method_and_stop('backup_delete_local', args[3].replace('/','_'))
        if packetid.Valid(args[2]):
            return call_xmlrpc_method_and_stop('backup_delete_id', args[2].replace('/','_'))
        return call_xmlrpc_method_and_stop('backup_delete_path', os.path.abspath(args[2]))

    elif args[1] == 'update':
        return call_xmlrpc_method_and_stop('backups_update')
    
    return 2


def cmd_restore(opts, args, overDict):
    if len(args) == 2:
        return call_xmlrpc_method_and_stop('restore_single', args[1])
    elif len(args) == 3:
        return call_xmlrpc_method_and_stop('restore_single', args[1], args[2])
    return 2


def cmd_schedule(opts, args, overDict):
    if len(args) < 2:
        return 2
    from system import bpio
    if not bpio.pathIsDir(os.path.abspath(args[1])):
        print_text('folder %s not exist\n' % args[1])
        return 1
    backupDir = os.path.abspath(args[1])
    if len(args) < 3:
        return call_xmlrpc_method_and_stop('getschedule', backupDir)
    from lib import schedule
    shed = schedule.from_compact_string(args[2])
    if shed is None:
        print_text(schedule.format()+'\n')
        return 0
    return call_xmlrpc_method_and_stop(
        'setschedule', backupDir, shed.type, shed.interval, shed.daytime, shed.details,)


def cmd_message(opts, args, overDict):
    if len(args) < 2 or args[1] == 'list':
        return call_xmlrpc_method_and_stop('list_messages')
    if len(args) >= 4 and args[1] in [ 'send', ]:
        return call_xmlrpc_method_and_stop('send_message', args[2], args[3]) 
    return 2


def cmd_friend(opts, args, overDict):
    if len(args) < 2:
        return call_xmlrpc_method_and_stop('list_correspondents')
    elif len(args) > 2 and args[1] == 'find':
        return call_xmlrpc_method_and_stop('find_peer_by_nickname', unicode(args[2]))
    return 2    


#def cmd_suppliers(opts, args, overDict):
#    if len(args) < 2 or args[1] in [ 'list', 'ls' ]:
#        url = webcontrol._PAGE_SUPPLIERS
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#
#    elif args[1] in [ 'call', 'cl' ]:
#        url = webcontrol._PAGE_SUPPLIERS + '?action=call'
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#
#    elif args[1] in [ 'replace', 'rep', 'rp' ] and len(args) >= 3:
#        contacts.init()
#        idurl = args[2].strip()
#        if not idurl.startswith('http://'):
#            try:
#                idurl = contacts.supplier(int(idurl))
#            except:
#                idurl = 'http://'+settings.IdentityServerName()+'/'+idurl+'.xml'
#        if not idurl:
#            print_text('supplier IDURL is None\n')
#            return 0
#        name = nameurl.GetName(idurl)
#        url = webcontrol._PAGE_SUPPLIERS + '?action=replace&idurl=%s' % misc.pack_url_param(idurl)
#        run_url_command(url).addCallback(_wait_replace_supplier_and_stop, name, 0)
#        reactor.run()
#        return 0
#    
#    elif args[1] in [ 'change', 'ch' ] and len(args) >= 4:
#        contacts.init()
#        idurl = args[2].strip()
#        if not idurl.startswith('http://'):
#            try:
#                idurl = contacts.supplier(int(idurl))
#            except:
#                idurl = 'http://'+settings.IdentityServerName()+'/'+idurl+'.xml'
#        if not idurl:
#            print_text('supplier IDURL is None\n')
#            return 0
#        newidurl = args[3].strip()
#        if not newidurl.startswith('http://'):
#            newidurl = 'http://'+settings.IdentityServerName()+'/'+newidurl+'.xml'
#        name = nameurl.GetName(idurl)
#        newname = nameurl.GetName(newidurl)
#        url = webcontrol._PAGE_SUPPLIERS + '?action=change&idurl=%s&newidurl=%s' % (misc.pack_url_param(idurl), misc.pack_url_param(newidurl))
#        run_url_command(url).addCallback(_wait_replace_supplier_and_stop, name, 0)
#        reactor.run()
#        return 0
#    
#    return 2

#def cmd_customers(opts, args, overDict):
#    def _wait_remove_customer_and_stop(src, customer_name, count=0):
#        customers = []
#        for s in find_comments(src):
#            if s.count('[online ]') or s.count('[offline]'):
#                customers.append(s[18:38].strip())
#        if customer_name not in customers:
#            print_text('  customer %s is removed !' % customer_name)
#            print_and_stop(src)
#            return
#        if count >= 20:
#            print_text(' time is out\n')
#            reactor.stop()
#            return
#        else:
#            def _check_again(customer_name, count):
#                sys.stdout.write('.')
#                run_url_command(webcontrol._PAGE_CUSTOMERS).addCallback(_wait_remove_customer_and_stop, customer_name, count)
#            reactor.callLater(1, _check_again, customer_name, count+1)
#
#    if len(args) < 2 or args[1] in [ 'list', 'ls', ]:
#        url = webcontrol._PAGE_CUSTOMERS
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#
#    elif args[1] in [ 'call', 'cl', ]:
#        url = webcontrol._PAGE_CUSTOMERS + '?action=call'
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#
#    elif args[1] in [ 'remove', 'rm', ] and len(args) >= 3:
#        contacts.init()
#        idurl = args[2].strip()
#        if not idurl.startswith('http://'):
#            try:
#                idurl = contacts.customer(int(idurl))
#            except:
#                idurl = 'http://'+settings.IdentityServerName()+'/'+idurl+'.xml'
#        name = nameurl.GetName(idurl)
#        url = webcontrol._PAGE_CUSTOMERS + '?action=remove&idurl=%s' % misc.pack_url_param(idurl)
#        run_url_command(url).addCallback(_wait_remove_customer_and_stop, name, 0)
#        reactor.run()
#        return 0
#    
#    return 2

#def cmd_register(opts, args, overDict):
#    if len(args) < 2:
#        return 2
#    if len(args) >= 3:
#        from main import settings
#        settings.uconfig().set('backup.private-key-size', str(args[2]))
#        settings.uconfig().update()
#    import lib.automat  as automat
#    import initializer
#    import shutdowner
#    initializer.A('run-cmd-line-register', args[1])
#    reactor.run()
#    # shutdowner.A('reactor-stopped')
#    automat.objects().clear()
#    print
#    return 0

#def cmd_recover(opts, args, overDict):
#    if len(args) < 2:
#        return 2
#    src = bpio.ReadBinaryFile(args[1])
#    if len(src) > 1024*10:
#        print_text('file is too big for private key')
#        return 0
#    try:
#        lines = src.split('\n')
#        idurl = lines[0]
#        txt = '\n'.join(lines[1:])
#        if idurl != nameurl.FilenameUrl(nameurl.UrlFilename(idurl)):
#            idurl = ''
#            txt = src
#    except:
#        #exc()
#        idurl = ''
#        txt = src
#    if idurl == '' and len(args) >= 3:
#        idurl = args[2]
#        if not idurl.startswith('http://'):
#            idurl = 'http://'+settings.IdentityServerName()+'/'+idurl+'.xml'
#    if idurl == '':
#        print_text('BitDust need to know your username to recover your account\n')
#        return 2
#    # import lib.automat as automat
#    import initializer
#    import shutdowner
#    initializer.A('run-cmd-line-recover', { 'idurl': idurl, 'keysrc': txt })
#    reactor.run()
#    # automat.objects().clear()
#    print
#    return 0

#def cmd_key(opts, args, overDict):
#    if len(args) == 2:
#        if args[1] == 'copy':
#            from crypt import key 
#            TextToSave = misc.getLocalID() + "\n" + key.MyPrivateKey()
#            misc.setClipboardText(TextToSave)
#            print_text('now you can "paste" with Ctr+V your private key where you want.')
#            del TextToSave
#            return 0
#        elif args[1] == 'print':
#            from crypt import key 
#            TextToSave = misc.getLocalID() + "\n" + key.MyPrivateKey()
#            print 
#            print_text(TextToSave)
#            return 0
#    elif len(args) == 3:
#        if args[1] == 'copy':
#            filenameto = args[2]
#            from crypt import key 
#            TextToSave = misc.getLocalID() + "\n" + key.MyPrivateKey()
#            if not bpio.AtomicWriteFile(filenameto, TextToSave):
#                print_text('error writing to %s' % filenameto)
#                return 1
#            print_text('your private key were copied to file %s' % filenameto)
#            del TextToSave
#            return 0
#    return 2
#    
    
#def cmd_stats(opts, args, overDict):
#    if len(args) == 2:
#        if not packetid.Valid(args[1]):
#            print_text('not valid backup ID')
#            return 0
#        url = '%s/%s%s' % (webcontrol._PAGE_MAIN, webcontrol._PAGE_BACKUP, args[1].replace('/','_'))
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#    elif len(args) >= 3 and args[1] == 'remote': 
#        url = '%s/%s%s' % (webcontrol._PAGE_MAIN, webcontrol._PAGE_BACKUP_REMOTE_FILES, args[2].replace('/','_'))
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#    elif len(args) >= 3 and args[1] == 'local': 
#        url = '%s/%s%s' % (webcontrol._PAGE_MAIN, webcontrol._PAGE_BACKUP_LOCAL_FILES, args[2].replace('/','_'))
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#    return 2


#def cmd_states(opts, args, overDict):
#    url = '%s' % (webcontrol._PAGE_AUTOMATS)
#    return call_xmlrpc_method_and_stop()
#    reactor.run()
#    return 0


#def cmd_cache(opts, args, overDict):
#    if len(args) < 2:
#        run_url_command(webcontrol._PAGE_MAIN+'?action=cache').addCallback(print_and_stop)
#        reactor.run()
#        return 0
#    elif len(args) == 2 and args[1] == 'clear':
#        run_url_command(webcontrol._PAGE_MAIN+'?action=cacheclear').addCallback(print_and_stop)
#        reactor.run()
#        return 0
#    return 2

#def cmd_reconnect(opts, args, overDict):
#    url = webcontrol._PAGE_MAIN + '?action=reconnect'
#    return call_xmlrpc_method_and_stop()
#    reactor.run()
#    return 0


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


#def cmd_set_directly(opts, args, overDict):
#    def print_all_settings():
#        from lib import userconfig
#        for path in userconfig.all_options():
#            if path.strip() == '':
#                continue
#            if path not in userconfig.public_options():
#                continue
#            value = settings.uconfig().data.get(path, '').replace('\n', ' ')
#            label = settings.uconfig().labels.get(path, '')
#            info = settings.uconfig().infos.get(path, '')
#            print_text('  %s    %s' % (path.ljust(50), value.ljust(20)))
#        return 0
#    name = args[1].lower()
#    if name in [ 'list' ]:
#        return print_all_settings() 
#    path = '' if len(args) < 2 else args[1]
#    path = option_name_to_path(name, path)
#    if path != '':
#        if not settings.uconfig().has(path):
#            print_text('  key "%s" not found' % path)
#        else:
#            old_is = settings.uconfig().get(path)
#            if len(args) > 2:
#                value = ' '.join(args[2:])
#                settings.uconfig().set(path, unicode(value))
#                settings.uconfig().update()
#            info = str(settings.uconfig().get(path, 'info')).replace('None', '').replace('<br>', '\n')
#            info = re.sub(r'<[^>]+>', '', info)
#            label = str(settings.uconfig().get(path, 'label')).replace('None', '')
#            print_text('  XML path: %s' % path)
#            print_text('  label:    %s' % label)
#            print_text('  info:     %s' % info)
#            print_text('  value:    %s' % settings.uconfig().get(path))
#            if len(args) > 2:
#                print_text('  modified: [%s]->[%s]' % (old_is, value))
#        return 0
    
#def cmd_set_request(opts, args, overDict):
#    name = args[1].lower()
#    if name in [ 'list' ]:
#        return print_all_settings_and_stop() 
#    path = '' if len(args) < 2 else args[1]
#    path = option_name_to_path(name, path)    
#    if len(args) == 2:
#        return print_single_setting_and_stop(path)
#    action = 'action='
#    leafs = path.split('.')
#    name = leafs[-1]
#    webcontrol.InitSettingsTreePages()
#    cls = webcontrol._SettingsTreeNodesDict.get(name, None)
#    input = ' '.join(args[2:])
#    if cls is None:
#        return 2
#    if cls in [ webcontrol.SettingsTreeTextNode,
#                webcontrol.SettingsTreeUStringNode,
#                webcontrol.SettingsTreePasswordNode,
#                webcontrol.SettingsTreeNumericNonZeroPositiveNode,
#                webcontrol.SettingsTreeNumericPositiveNode,] :
#        action = 'text=' + misc.pack_url_param(input)
#    elif cls in [ webcontrol.SettingsTreeDiskSpaceNode, ]:
#        number = misc.DigitsOnly(input, '.')
#        suffix = input.lstrip('0123456789.-').strip()
#        action = 'number=%s&suffix=%s' % (number, suffix)
#    elif cls in [ webcontrol.SettingsTreeComboboxNode, ]:
#        number = misc.DigitsOnly(input)
#        action = 'choice=%s' % number
#    elif cls in [ webcontrol.SettingsTreeYesNoNode, ]:
#        trueORfalse = 'True' if input.lower().strip() == 'true' else 'False'
#        action = 'choice=%s' % trueORfalse
#    url = webcontrol._PAGE_SETTINGS + '/' + path + '?' + action
#    run_url_command(url).addCallback(lambda src: print_single_setting_and_stop(path, False)) #.addCallback(print_and_stop)
#    reactor.run()
#    return 0

#def cmd_memory(opts, args, overDict):
#    url = webcontrol._PAGE_MEMORY
#    return call_xmlrpc_method_and_stop()
#    reactor.run()
#    return 0

#def cmd_storage(opts, args, overDict):
#    url = webcontrol._PAGE_STORAGE
#    return call_xmlrpc_method_and_stop()
#    reactor.run()
#    return 0

#def cmd_money(opts, args, overDict):
#    if len(args) == 1:
#        url = webcontrol._PAGE_MONEY
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#
#    elif len(args) >= 2 and args[1] == 'receipts': 
#        url = webcontrol._PAGE_RECEIPTS
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#
#    elif len(args) >= 3 and args[1] == 'receipt': 
#        url = '%s/%s' % (webcontrol._PAGE_RECEIPTS, args[2])
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#    
#    elif len(args) >= 4 and args[1] == 'transfer':
#        recipient = args[2].strip()
#        if not recipient.startswith('http://'):
#            recipient = 'http://'+settings.IdentityServerName()+'/'+recipient+'.xml'
#        url = '%s?action=commit&recipient=%s&amount=%s' % (webcontrol._PAGE_TRANSFER, misc.pack_url_param(recipient), args[3]) 
#        return call_xmlrpc_method_and_stop()
#        reactor.run()
#        return 0
#    
#    return 2
#    

#def cmd_uninstall(opts, args, overDict):
#    if not bpio.Windows():
#        print_text('This command can be used only under OS Windows.')
#        return 0
#    if not bpio.isFrozen():
#        print_text('You are running BitDust from sources, uninstall command is available only for binary version.')
#        return 0
#    def do_uninstall():
#        lg.out(0, 'command_line.do_uninstall')
#        # batfilename = misc.MakeBatFileToUninstall()
#        # misc.UpdateRegistryUninstall(True)
#        # misc.RunBatFile(batfilename, 'c:/out2.txt')
#    def kill():
#        lg.out(0, 'kill')
#        total_count = 0
#        found = False
#        while True:
#            appList = bpio.find_process([
#                'bitdust.exe',
#                'bpmain.py',
#                'bitdust.py',
#                'regexp:^/usr/bin/python.*bitdust.*$',
#                'bpgui.exe',
#                'bpgui.py',
#                'bppipe.exe',
#                'bppipe.py',
#                'bptester.exe',
#                'bptester.py',
#                'bitstarter.exe',
#                ])
#            if len(appList) > 0:
#                found = True
#            for pid in appList:
#                lg.out(0, 'trying to stop pid %d' % pid)
#                bpio.kill_process(pid)
#            if len(appList) == 0:
#                if found:
#                    lg.out(0, 'BitDust stopped\n')
#                else:
#                    lg.out(0, 'BitDust was not started\n')
#                return 0
#            total_count += 1
#            if total_count > 10:
#                lg.out(0, 'some BitDust process found, but can not stop it\n')
#                return 1
#            time.sleep(1)            
#    def wait_then_kill(x):
#        lg.out(0, 'wait_then_kill')
#        total_count = 0
#        #while True:
#        def _try():
#            lg.out(0, '_try')
#            appList = bpio.find_process([
#                'bitdust.exe',
#                'bpgui.exe',
#                'bppipe.exe',
#                'bptester.exe',
#                'bitstarter.exe',
#                ])
#            lg.out(0, 'appList:' + str(appList))
#            if len(appList) == 0:
#                lg.out(0, 'finished')
#                reactor.stop()
#                do_uninstall()
#                return 0
#            total_count += 1
#            lg.out(0, '%d' % total_count)
#            if total_count > 10:
#                lg.out(0, 'not responding')
#                ret = kill()
#                reactor.stop()
#                if ret == 0:
#                    do_uninstall()
#                return ret
#            reactor.callLater(1, _try)
#        _try()
##            time.sleep(1)
#    appList = bpio.find_process([
#        'bitdust.exe',
#        'bpgui.exe',
#        'bppipe.exe',
#        'bptester.exe',
#        'bitstarter.exe',
#        ])
#    if len(appList) == 0:
#        lg.out(0, 'uninstalling BitDust ...   ')
#        do_uninstall()
#        return 0
#    lg.out(0, 'found BitDust processes ...   ')
#    try:
#        url = webcontrol._PAGE_ROOT+'?action=exit'
#        run_url_command(url).addCallback(wait_then_kill)
#        #reactor.addSystemEventTrigger('before', 'shutdown', do_uninstall)
#        reactor.run()
#        return 0
#    except:
#        lg.exc()
#        ret = kill()
#        if ret == 0:
#            do_uninstall()
#        return ret


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
            python bitdust.py $*
    If this is sterted without root permissions, it should create a file ~/bin/bitdust.
    """
    def print_text(msg, nl='\n'):
        """
        """
        sys.stdout.write(msg+nl)
    from system import bpio
    if bpio.Windows():
        print_text('this feature is not yet available in OS Windows.')
        return 0
    curpath = bpio.getExecutableDir()
    cmdpath = '/usr/local/bin/bitdust'
    src = "#!/bin/sh\n"
    src += "cd %s\n" % curpath
    src += "python bitdust.py $*\n"
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

def run(opts, args, pars=None, overDict=None): 
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
    elif cmd == 'restart':
        appList = bpio.find_process([
            'bitdust.exe',
            'bpmain.py',
            'bitdust.py',
            'regexp:^/usr/bin/python.*bitdust.*$',
            ])
        if len(appList) == 0:
            return run_now()
        print_text('found main BitDust process: %s, sending "restart" command ... ' % str(appList), '')
        def done(x):
            print_text('DONE\n', '')
            from twisted.internet import reactor
            if reactor.running and not reactor._stopped:
                reactor.stop()
        def failed(x):
            print_text('FAILED, killing previous process and do restart\n', '')
            try:
                kill()
            except:
                print_exception()
            from twisted.internet import reactor
            from lib import misc
            reactor.addSystemEventTrigger('after','shutdown', misc.DoRestart)
            reactor.stop()
        try:
            from twisted.internet import reactor
            call_xmlrpc_method('restart').addCallbacks(done, failed)
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
        call_xmlrpc_method('show')
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
            print_text('found main BitDust process: %s, sending command "exit"' % str(appList))
            try:
                from twisted.internet import reactor
                call_xmlrpc_method('stop').addBoth(wait_then_kill)
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

    #---set---
#    if cmd == 'set':
#        if len(args) == 1 or args[1].lower() in [ 'help', '?' ]:
#            from main import help
#            print_text(help.settings_help())
#            return 0
#        if not running:
#            cmd_set_directly(opts, args, overDict)
#            return 0
#        return cmd_set_request(opts, args, overDict)
    
    #---backup---
    if cmd in ['backup', 'backups', 'bk']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_backups(opts, args, overDict)

    #---restore---
    elif cmd in ['restore', 're']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_restore(opts, args, overDict)

    #---messages---
    elif cmd == 'msg' or cmd == 'message' or cmd == 'messages':
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_message(opts, args, overDict)
    
    #---friends---
    elif cmd == 'friend' or cmd == 'friends' or cmd == 'buddy':
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_friend(opts, args, overDict)

    #---integrate---
    elif cmd == 'integrate':
        return cmd_integrate(opts, args, overDict)

    #---schedule---
    elif cmd in ['schedule', 'shed', 'sched', 'sh']:
        if not running:
            print_text('BitDust is not running at the moment\n')
            return 0
        return cmd_schedule(opts, args, overDict)



    #---suppliers---
#    elif cmd in [ 'suppliers', 'supplier', 'sup', 'supp', 'sp', ]:
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_suppliers(opts, args, overDict)
    
    #---customers---
#    elif cmd in [ 'customers', 'customer', 'cus', 'cust', 'cs', ]:
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_customers(opts, args, overDict)

    #---register---
#    elif cmd == 'register':
#        if running:
#            print_text('BitDust already started.\n')
#            return 0
#        return cmd_register(opts, args, overDict)

    #---recover---
#    elif cmd == 'recover':
#        if running:
#            print_text('BitDust already started.\n')
#            return 0
#        return cmd_recover(opts, args, overDict)

    #---key---
#    elif cmd == 'key':
#        return cmd_key(opts, args, overDict)

    #---stats---
#    elif cmd in [ 'stats', 'st' ]:
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_stats(opts, args, overDict)

    #---version---
    elif cmd in [ 'version', 'v', 'ver' ]:
        from main import settings
        ver = bpio.ReadTextFile(settings.VersionNumberFile()).strip()
        chksum = bpio.ReadTextFile(settings.CheckSumFile()).strip()
        repo, location = misc.ReadRepoLocation()
        print_text('checksum:   %s' % chksum )
        print_text('version:    %s' % ver)
        print_text('repository: %s' % repo)
        print_text('location:   %s' % location)
        return 0

    #---states---
#    elif cmd in [ 'states', 'sta', 'automats', 'auto' ]:
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_states(opts, args, overDict)
    
    #---cache---
#    elif cmd in [ 'cache' ]:
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_cache(opts, args, overDict)

    #---reconnect---
#    elif cmd in [ 'reconnect', ]:
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_reconnect(opts, args, overDict)
        
    #---memory---
#    elif cmd == 'memory':
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_memory(opts, args, overDict)
    
    #---money---
#    elif cmd == 'money':
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_money(opts, args, overDict)
    
#    elif cmd == 'storage':
#        if not running:
#            print_text('BitDust is not running at the moment\n')
#            return 0
#        return cmd_storage(opts, args, overDict)
    
   
#    elif cmd == 'uninstall':
#        return cmd_uninstall(opts, args, overDict)
    
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

