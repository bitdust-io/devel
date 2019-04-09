#!/usr/bin/python
#geth_service.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (geth_service.py) is part of BitDust Software.
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


"""
.. module:: geth_service

"""


#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in geth_service.py')

from twisted.internet import protocol

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

from updates import git_proc


#------------------------------------------------------------------------------

def init():
    """
    """
    lg.out(4, 'geth_service.init')
    try:
        verify_local_install()
    except ValueError:
        deploy(callback=run_geth_node)
    else:
        run_geth_node()


def shutdown():
    """
    """
    lg.out(4, 'geth_service.shutdown')

#------------------------------------------------------------------------------

def verify_local_install():
    """
    """
    ethereum_location = os.path.join(settings.BaseDir(), "ethereum")
    if not os.path.isdir(ethereum_location):
        raise ValueError('Ethereum root location not found: {}'.format(ethereum_location))
    geth_location = os.path.join(ethereum_location, 'go-ethereum')
    if not os.path.isdir(ethereum_location):
        raise ValueError('Ethereum geth process folder not found: {}'.format(ethereum_location))
    geth_bin_path = os.path.join(geth_location, 'build', 'bin', 'geth')
    if not os.path.isfile(geth_bin_path):
        raise ValueError('Ethereum geth process executable not found: {}'.format(geth_bin_path))
    return True

def verify_global_install():
    """
    """
    # TODO: try to run "geth" in shell
    return True

#------------------------------------------------------------------------------

def clone(callback=None):
    """
    """
    ethereum_location = os.path.join(settings.BaseDir(), "ethereum")
    if not os.path.isdir(ethereum_location):
        os.makedirs(ethereum_location)
    geth_location = os.path.join(ethereum_location, 'go-ethereum')
    if os.path.exists(geth_location):
        bpio.rmdir_recursive(geth_location)
    git_proc.run(
        ['clone', '--verbose', '--depth', '1', 'https://github.com/ethereum/go-ethereum', geth_location, ],
        base_dir=ethereum_location,
        env=os.environ,
        callback_func=callback,
    )

def make(callback=None):
    """
    """
    geth_location = os.path.join(settings.BaseDir(), "ethereum", "go-ethereum")
    execute(['make', 'geth'], base_dir=geth_location, env=os.environ, callback=callback)

def deploy(callback=None):
    """
    """
    def _clone(out, retcode):
        make(callback=callback)
    clone(callback=_clone)

#------------------------------------------------------------------------------

def run(cmdargs, callback=None):
    """
    """
    geth_location = os.path.join(settings.BaseDir(), "ethereum", "go-ethereum",)
    cmdargs = ['build/bin/geth', ] + cmdargs
    execute(cmdargs, base_dir=geth_location, env=os.environ, callback=callback)

def run_geth_node():
    """
    """
    geth_datadir = os.path.join(settings.BaseDir(), "ethereum", "datadir")
    if not os.path.isdir(geth_datadir):
        os.makedirs(geth_datadir)
    run(['--datadir="{}"'.format(geth_datadir),
         '--verbosity', '4', '--ipcdisable', '--port', '30300', '--rpcport', '8100', '--networkid', '1'])

#------------------------------------------------------------------------------

def execute(cmdargs, base_dir=None, process_protocol=None, env=None, callback=None):
    """
    """
    global _CurrentProcess
    if _Debug:
        lg.out(_DebugLevel, 'geth_service.execute: "%s" in %s' % (' '.join(cmdargs), base_dir))
    executable = cmdargs[0]
    if bpio.Windows():
        from twisted.internet import _dumbwin32proc
        real_CreateProcess = _dumbwin32proc.win32process.CreateProcess

        def fake_createprocess(_appName, _commandLine, _processAttributes,
                               _threadAttributes, _bInheritHandles, creationFlags,
                               _newEnvironment, _currentDirectory, startupinfo):
            import win32con
            import subprocess
            flags = win32con.CREATE_NO_WINDOW
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return real_CreateProcess(_appName, _commandLine,
                                      _processAttributes, _threadAttributes,
                                      _bInheritHandles, flags, _newEnvironment,
                                      _currentDirectory, startupinfo)
        setattr(_dumbwin32proc.win32process, 'CreateProcess', fake_createprocess)

    if process_protocol is None:
        process_protocol = GethProcessProtocol(callback)
    try:
        _CurrentProcess = reactor.spawnProcess(
            process_protocol, executable, cmdargs, path=base_dir, env=env)
    except:
        lg.exc()
        return None
    if bpio.Windows():
        setattr(_dumbwin32proc.win32process, 'CreateProcess', real_CreateProcess)
    return _CurrentProcess

#------------------------------------------------------------------------------

class GethProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, callback):
        """
        """
        self.callback = callback
        self.out = ''
        self.err = ''

    def errReceived(self, inp):
        """
        """
        self.err += inp
        for line in inp.splitlines():
            if _Debug:
                lg.out(_DebugLevel, '%s' % line)

    def outReceived(self, inp):
        """
        """
        self.out += inp
        for line in inp.splitlines():
            if _Debug:
                lg.out(_DebugLevel, '%s' % line)

    def processEnded(self, reason):
        """
        """
        if _Debug:
            lg.out(_DebugLevel, 'geth process FINISHED : %s' % reason.value.exitCode)
        if self.callback:
            self.callback(self.out, reason.value.exitCode)

#------------------------------------------------------------------------------


if __name__ == "__main__":
    bpio.init()
    lg.set_debug_level(18)
    reactor.callWhenRunning(run_geth_node)
    reactor.run()
