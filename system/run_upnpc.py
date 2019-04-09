#!/usr/bin/python
# run_upnpc.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (run_upnpc.py) is part of BitDust Software.
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

module:: run_upnpc
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import sys
import re
import random

#------------------------------------------------------------------------------

if __name__ == "__main__":
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

#------------------------------------------------------------------------------

_CurrentProcess = None
_MyPortMapping = {}
_LastUpdateResultDict = {}

#-------------------------------------------------------------------------------


def init():
    global _MyPortMapping
    if _Debug:
        lg.out(_DebugLevel, 'run_upnpc.init ')


def shutdown():
    global _CurrentProcess
    if _Debug:
        lg.out(_DebugLevel, 'run_upnpc.shutdown')
    if _CurrentProcess is not None:
        if _Debug:
            lg.out(_DebugLevel, '    going to kill _CurrentProcess=%s' % _CurrentProcess)
        try:
            _CurrentProcess.kill()
            if _Debug:
                lg.out(_DebugLevel, '    killed')
        except:
            lg.exc()
    else:
        if _Debug:
            lg.out(_DebugLevel, '    not started')

#------------------------------------------------------------------------------


def execute_in_shell(cmdargs, base_dir=None):
    global _CurrentProcess
    from system import nonblocking
    import subprocess
    if _Debug:
        lg.out(_DebugLevel, 'run_upnpc.execute_in_shell: "%s"' % (' '.join(cmdargs)))
    in_shell = True
    if bpio.Mac():
        in_shell = False
    _CurrentProcess = nonblocking.Popen(
        cmdargs,
        shell=in_shell,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,)
    out_data = _CurrentProcess.communicate()[0]
    returncode = _CurrentProcess.returncode
    if _Debug:
        lg.out(_DebugLevel, 'run_upnpc.execute_in_shell returned: %s and %d bytes output' % (returncode, len(out_data)))
    if returncode > 0:
        if _Debug:
            lg.out(_DebugLevel, '\n' + out_data)
    return (out_data, returncode)  # _CurrentProcess

#------------------------------------------------------------------------------

# Windows: executable file "upnpc.exe" must be in same folder or system sub folder
# Ubuntu: miniupnpc must be installed, https://launchpad.net/ubuntu/+source/miniupnpc


def run(args_list, base_dir=None, callback=None):
    # TODO: Currently disabled
    return None
    
    global _CurrentProcess
    if _CurrentProcess is not None:
        lg.warn('only one process at once')
        return None

    if bpio.Windows():
        cmdargs = ['upnpc-static.exe', ]
    elif bpio.Linux():
        cmdargs = ['upnpc', ]
    elif bpio.Mac():
        cmdargs = ['upnpc', ]
    else:
        return None

    if bpio.Windows():
        # if we run windows binaries - upnpc-static.exe can be in the system sub folder
        if not os.path.isfile(cmdargs[0]):
            if os.path.isfile(os.path.join('system', cmdargs[0])):
                cmdargs[0] = os.path.join('system', cmdargs[0])
            else:
                lg.warn('can not find executable file ' + cmdargs[0])
                return None

    cmdargs += args_list

    if _Debug:
        lg.out(_DebugLevel, 'run_upnpc.run is going to execute: %s' % cmdargs)

    try:
        out_data, returncode = execute_in_shell(cmdargs)
    except:
        lg.exc()
        return None

    if _Debug:
        lg.out(_DebugLevel, '    %s finished with return code: %s' % (str(_CurrentProcess), str(returncode)))
    _CurrentProcess = None

    return out_data

#------------------------------------------------------------------------------


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

#------------------------------------------------------------------------------


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
            l.append((int(i[2]), i[3], i[1], i[5]))
        except:
            continue
    return l

#------------------------------------------------------------------------------


def add(port, proto):
    global _MyPortMapping
    # cmd_out = run(('-r', str(port), str(proto)))
    cmd_out = run(('-e', '"BitDust TCP on port %s"' % (port), '-r', str(port), str(proto)))
    if cmd_out is None:
        return None
    _MyPortMapping[str(port)] = str(proto)
    return cmd_out

#------------------------------------------------------------------------------


def dlt(port, proto):
    global _MyPortMapping
    cmd_out = run(('-d', str(port), str(proto)))
    if cmd_out is None:
        return None
    _MyPortMapping.pop(str(port), '')
    return cmd_out

#------------------------------------------------------------------------------


def clear():
    s = ''
    l = lst()
    for i in l:
        s += str(dlt(i[0], i[2])) + '\n'
    return s

#------------------------------------------------------------------------------


def update(requested_port, attempt=0, new_port=-1):
    global _MyPortMapping
    global _LastUpdateResultDict
    port = requested_port
    requested_port_busy = False
    if _Debug:
        lg.out(_DebugLevel, 'run_upnpc.update %s attempt=%s new_port=%s' % (str(port), str(attempt), str(new_port)))

    local_ip, external_ip, port_map = info()

    if local_ip is None or external_ip is None or port_map is None:
        _LastUpdateResultDict[port] = 'upnp-not-found'
        return 'upnp-not-found', port

    local_ports = {}
    for i in port_map:
        if str(i[0]).strip() == str(requested_port):
            requested_port_busy = True
        if i[1] == local_ip and (str(i[3]).find('libminiupnpc') >= 0 or str(i[3]).find('BitDust') >= 0):
            local_ports[i[0]] = (i[2], i[3])

    if _Debug:
        lg.out(_DebugLevel, 'run_upnpc.update requested_port_busy=%s local_ports=%s' % (
            requested_port_busy, str(list(local_ports.keys()))))

    if int(port) in list(local_ports.keys()):
        _MyPortMapping[str(port)] = 'TCP'
        if _Debug:
            lg.out(_DebugLevel, 'run_upnpc.update PORT %s mapped SUCCESSFULLY!!! all port maps: %s' % (str(port), str(list(_MyPortMapping.keys()))))
        _LastUpdateResultDict[port] = 'upnp-done'
        return 'upnp-done', port

    if int(new_port) > 0 and int(new_port) in list(local_ports.keys()):
        _MyPortMapping[str(new_port)] = 'TCP'
        if _Debug:
            lg.out(_DebugLevel, 'run_upnpc.update NEW PORT %s mapped SUCCESSFULLY!!! all port maps: %s' % (str(port), str(list(_MyPortMapping.keys()))))
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
            if requested_port_busy:
                new_port = int(port) + random.randint(1, 100)
                add(new_port, 'TCP')
                port = new_port
                new_port = -1
            else:
                add(port, 'TCP')
        else:
            new_port = int(port) + random.randint(1, 100)
            add(new_port, 'TCP')
            port = new_port
            new_port = -1

    else:
        _LastUpdateResultDict[port] = 'upnp-error'
        return 'upnp-error', port

    result, port = update(port, attempt + 1, new_port)
    _LastUpdateResultDict[port] = result
    return result, port

#------------------------------------------------------------------------------


def last_result(proto):
    global _LastUpdateResultDict
    return _LastUpdateResultDict.get(proto, 'upnp-no-info')

#-------------------------------------------------------------------------------


def main():
    import pprint
    lg.set_debug_level(14)
    if sys.argv.count('list'):
        maps = lst()
        for itm in maps:
            pprint.pprint(itm)
    elif sys.argv.count('info'):
        locip, extip, maps = info()
        pprint.pprint(locip)
        pprint.pprint(extip)
        for itm in maps:
            pprint.pprint(itm)
    elif sys.argv.count('add'):
        print(add(sys.argv[2], 'TCP'))
    elif sys.argv.count('del'):
        print(dlt(sys.argv[2], 'TCP'))
    elif sys.argv.count('update'):
        bpio.init()
        settings.init()
        init()
        pprint.pprint(update(sys.argv[2]))
    elif sys.argv.count('clear'):
        print(clear())
    else:
        print('usage:')
        print('run_upnpc.py info')
        print('run_upnpc.py list')
        print('run_upnpc.py add [port]')
        print('run_upnpc.py del [port]')
        print('run_upnpc.py update [port]')
        print('run_upnpc.py clear')


if __name__ == "__main__":
    main()
