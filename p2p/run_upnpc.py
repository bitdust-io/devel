#!/usr/bin/python
#run_upnpc.py
#
# <<<COPYRIGHT>>>
#
#
#
#

import os
import sys
import re
import string
import subprocess
import random

from twisted.python.win32 import cmdLineQuote

if __name__ == '__main__':
    sys.path.insert(0, os.path.abspath('..'))

import lib.dhnio as dhnio
import lib.nonblocking as nonblocking
import lib.settings as settings

_CurrentProcess = None
_MyPortMapping = {}
_LastUpdateResultDict = {}

#-------------------------------------------------------------------------------

def init():
    global _MyPortMapping
    dhnio.Dprint(4, 'run_upnpc.init ')


def shutdown():
    global _CurrentProcess
    dhnio.Dprint(4, 'run_upnpc.shutdown')
    if _CurrentProcess is not None:
        dhnio.Dprint(6, 'run_upnpc.shutdown going to kill _CurrentProcess')
        try:
            _CurrentProcess.kill()
        except:
            pass


# Windows: executable file "upnpc.exe" must be in same folder
# Ubuntu: miniupnpc must be installed, https://launchpad.net/ubuntu/+source/miniupnpc
def run(args_list):
    global _CurrentProcess
    if _CurrentProcess is not None:
        dhnio.Dprint(4, 'run_upnpc.run WARNING only one process at once')
        return None

    if dhnio.Windows():
        cmdargs = ['upnpc.exe']
    elif dhnio.Linux():
        cmdargs = ['upnpc']
    else:
        return None

    cmdargs += args_list

    if dhnio.Windows():
        # if we run from svn - upnpc.exe is in the p2p folder
        if not os.path.isfile(cmdargs[0]):
            if os.path.isfile(os.path.join('p2p', cmdargs[0])):
                cmdargs[0] = os.path.join('p2p', cmdargs[0])
            else:
                dhnio.Dprint(1, 'run_upnpc.run ERROR can not find executable file ' + cmdargs[0])
                return None

    dhnio.Dprint(6, 'run_upnpc.run is going to execute: %s' % cmdargs)

    try:
        if dhnio.Windows() and dhnio.isFrozen():
            import win32pipe
            _CurrentProcess = win32pipe.popen(subprocess.list2cmdline(cmdargs))
        else:
            _CurrentProcess = nonblocking.Popen(cmdargs, shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,)
    except OSError:
        dhnio.Dprint(1, 'run_upnpc.run ERROR can not start executable file ' + cmdargs[0])
        return None
    except:
        dhnio.DprintException()
        return None

    try:
        if dhnio.Windows() and dhnio.isFrozen():
            out_data = _CurrentProcess.read()
            returncode = _CurrentProcess.close() or 0
        else:
            out_data = _CurrentProcess.communicate()[0]
            returncode = _CurrentProcess.returncode
    except:
        dhnio.DprintException()
        return None

    dhnio.Dprint(6, 'run_upnpc.run %s finished with return code: %s' % (str(_CurrentProcess), str(returncode)))
    _CurrentProcess = None

    return out_data


def info():
    cmd_out = run(('-l',))
    if cmd_out is None:
        return None, None, None
    regexp1 = "^\s*(\d+)\s*(\w+)\s*(\d+)->(\d+\.\d+\.\d+\.\d+):(\d+)\s+(.+)$"
    regexp2 = "^Local LAN ip address : (\d+\.\d+\.\d+\.\d+).*$"
    regexp3 = "^ExternalIPAddress = (\d+\.\d+\.\d+\.\d+).*$"
    regexp4 = "No IGD UPnP Device found on the network"
    upnp_device_not_found = re.search(regexp4, cmd_out, re.MULTILINE)
    if upnp_device_not_found is not None:
        return None, None, None
    l = []
    for i in re.findall(regexp1, cmd_out, re.MULTILINE):
        try:
            l.append((int(i[2]), i[3], i[1], i[5]))
        except:
            continue
    search_local_ip = re.search(regexp2, cmd_out, re.MULTILINE)
    search_external_ip = re.search(regexp3, cmd_out, re.MULTILINE)
    local_ip = ''
    external_ip = ''
    if search_local_ip is not None:
        local_ip = search_local_ip.group(1)
    if search_external_ip is not None:
        external_ip = search_external_ip.group(1)
    return local_ip, external_ip, l


def lst():
    cmd_out = run(('-l',))
    if cmd_out is None:
        return None
    regexp1 = "^\s*(\d+)\s*(\w+)\s*(\d+)->(\d+\.\d+\.\d+\.\d+):(\d+)\s+(.+)$"
    regexp4 = "No IGD UPnP Device found on the network"
    upnp_device_not_found = re.search(regexp4, cmd_out, re.MULTILINE)
    if upnp_device_not_found is not None:
        return None
    l = []
    for i in re.findall(regexp1, cmd_out, re.MULTILINE):
        try:
            #         port       ip    proto  decription
            l.append((int(i[2]), i[3], i[1],  i[5]))
        except:
            continue
    return l


def add(port, proto):
    global _MyPortMapping
    cmd_out = run(('-r', str(port), str(proto)))
    # cmd_out = run(('-e', 'BitPie.NET', '-r', str(port), str(proto)))
    if cmd_out is None:
        return None
    _MyPortMapping[str(port)] = str(proto)
    return cmd_out


def dlt(port, proto):
    global _MyPortMapping
    cmd_out = run(('-d', str(port), str(proto)))
    if cmd_out is None:
        return None
    _MyPortMapping.pop(str(port), '')
    return cmd_out


def clear():
    s = ''
    l = lst()
    for i in l:
        s += str(dlt(i[0], i[2])) + '\n'
    return s


def update(port, attempt=0, new_port= -1):
    global _MyPortMapping
    global _LastUpdateResultDict
    dhnio.Dprint(4, 'run_upnpc.update %s attempt=%s new_port=%s' % (str(port), str(attempt), str(new_port)))

    local_ip, external_ip, port_map = info()

    if local_ip is None or external_ip is None or port_map is None:
        _LastUpdateResultDict[port] = 'upnp-not-found'
        return 'upnp-not-found', port

    local_ports = {}
    for i in port_map:
        if i[1] == local_ip and str(i[3]).find('libminiupnpc') >= 0:
            local_ports[i[0]] = (i[2], i[3])

    dhnio.Dprint(6, 'run_upnpc.update local_ports=%s' % str(local_ports.keys()))

    if int(port) in local_ports.keys():
        _MyPortMapping[str(port)] = 'TCP'
        dhnio.Dprint(6, 'run_upnpc.update port %s mapped. all port maps: %s' % (str(port), str(_MyPortMapping.keys())))
        _LastUpdateResultDict[port] = 'upnp-done'
        return 'upnp-done', port

    if int(new_port) in local_ports.keys():
        _MyPortMapping[str(new_port)] = 'TCP'
        dhnio.Dprint(6, 'run_upnpc.update new port %s mapped. all port maps: %s' % (str(port), str(_MyPortMapping.keys())))
        _LastUpdateResultDict[new_port] = 'upnp-done'
        return 'upnp-done', new_port

    if attempt == 0:
        add(port, 'TCP')

    elif attempt == 1:
        closest_port = -1
        closest_value = 99999999
        for p in local_ports.keys():
            v = abs(int(p) - int(port))
            if v < closest_value:
                closest_value = v
                closest_port = p
        if closest_port >= 0:
            dlt(closest_port, 'TCP')
            add(port, 'TCP')
        else:
            new_port = int(port) + random.randint(1, 100)
            add(new_port, 'TCP')

    else:
        _LastUpdateResultDict[port] = 'upnp-error'
        return 'upnp-error', port

    result, port = update(port, attempt + 1, new_port)
    _LastUpdateResultDict[port] = result
    return result, port


def last_result(proto):
    global _LastUpdateResultDict
    return _LastUpdateResultDict.get(proto, 'upnp-no-info')

#-------------------------------------------------------------------------------


def main():
    import pprint
    dhnio.SetDebug(14)
    if sys.argv.count('list'):
        pprint.pprint(lst())
    elif sys.argv.count('info'):
        pprint.pprint(info())
    elif sys.argv.count('add'):
        print add(sys.argv[2], 'TCP')
    elif sys.argv.count('del'):
        print dlt(sys.argv[2], 'TCP')
    elif sys.argv.count('update'):
        dhnio.init()
        settings.init()
        init()
        pprint.pprint(update(sys.argv[2]))
    elif sys.argv.count('clear'):
        print clear()
    else:
        print 'usage:'
        print 'run_upnpc.py info'
        print 'run_upnpc.py list'
        print 'run_upnpc.py add [port]'
        print 'run_upnpc.py del [port]'
        print 'run_upnpc.py update [port]'
        print 'run_upnpc.py clear'


if __name__ == "__main__":
    main()


