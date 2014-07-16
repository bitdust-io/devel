#!/usr/bin/python
#child_process.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: child_process

BitPie.NET executes periodically several slaves:
    - bppipe
    - bptester
    - bpgui
They are started as a separated processes and managed from the main process: 
    bpmain.
"""

import os
import sys
import subprocess

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in child_process.py')

from twisted.internet import protocol

import bpio
import nonblocking


#------------------------------------------------------------------------------ 

class ChildProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, name):
        self.name = name
                    
    def errReceived(self, inp):
        for line in inp.splitlines():
            bpio.log(2, '[%s]: %s' % (self.name, line))
            
    def processEnded(self, reason):
        bpio.log(2, 'child process [%s] FINISHED')
        

def run(child_name, params=[], base_dir='.', process_protocol=None):
    """
    This is another portable solution to execute a process.
    """
    if bpio.isFrozen() and bpio.Windows():
        progpath = os.path.abspath(os.path.join(base_dir, child_name + '.exe'))
        executable = progpath
        cmdargs = [progpath]
        cmdargs.extend(params)
    else:
        progpath = os.path.abspath(os.path.join(base_dir, child_name + '.py'))
        executable = sys.executable
        cmdargs = [executable, progpath]
        cmdargs.extend(params)
    if not os.path.isfile(executable):
        bpio.log(1, 'child_process.run ERROR %s not found' % executable)
        return None
    if not os.path.isfile(progpath):
        bpio.log(1, 'child_process.run ERROR %s not found' % progpath)
        return None
    bpio.log(6, 'child_process.run: "%s"' % (' '.join(cmdargs)))

    if bpio.Windows():
        from twisted.internet import _dumbwin32proc
        real_CreateProcess = _dumbwin32proc.win32process.CreateProcess
        def fake_createprocess(_appName, _commandLine, _processAttributes,
                            _threadAttributes, _bInheritHandles, creationFlags,
                            _newEnvironment, _currentDirectory, startupinfo):
            import win32con
            flags = win32con.CREATE_NO_WINDOW 
            return real_CreateProcess(_appName, _commandLine,
                            _processAttributes, _threadAttributes,
                            _bInheritHandles, flags, _newEnvironment,
                            _currentDirectory, startupinfo)        
        setattr(_dumbwin32proc.win32process, 'CreateProcess', fake_createprocess)
    
    if process_protocol is None:
        process_protocol = ChildProcessProtocol(child_name)    
    try:
        Process = reactor.spawnProcess(process_protocol, executable, cmdargs, path=base_dir)
    except:
        bpio.log(1, 'child_process.run ERROR executing: %s' % str(cmdargs))
        bpio.exception()
        return None
    
    if bpio.Windows():
        setattr(_dumbwin32proc.win32process, 'CreateProcess', real_CreateProcess)

    bpio.log(6, 'child_process.run [%s] pid=%d' % (child_name, Process.pid))
    return Process    


def kill_process(process):
    """
    Send signal "KILL" to the given ``process``. 
    """
    try:
        process.signalProcess('KILL')
        bpio.log(6, 'child_process.kill_process sent signal "KILL" to %s the process %d' % process.pid)
    except:
        return False
    return True


def kill_child(child_name):
    """
    Search (by "pid") for BitPie.NET child process with name ``child_name`` and tries to kill it.
    """
    killed = False
    for pid in bpio.find_process([child_name+'.']): 
        bpio.kill_process(pid)
        bpio.log(6, 'child_process.kill_child pid %d' % pid)
        killed = True
    return killed


def pipe(cmdargs):
    """
    Execute a process in different way, create a Pipe to do read/write operations with child process.
    See ``lib.nonblocking`` module.
    """
    bpio.log(14, "child_process.pipe %s" % str(cmdargs))
    try:
        if bpio.Windows():
            import win32process
            p = nonblocking.Popen(
                cmdargs,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
                creationflags = win32process.CREATE_NO_WINDOW,)
        else:
            p = nonblocking.Popen(
                cmdargs,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,)
    except:
        bpio.log(1, 'child_process.pipe ERROR executing: ' + str(cmdargs) + '\n' + str(bpio.formatExceptionInfo()))
        return None
    return p

