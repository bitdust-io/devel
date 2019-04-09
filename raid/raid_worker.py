#!/usr/bin/python
# raid_worker.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (raid_worker.py) is part of BitDust Software.
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
.. module:: raid_worker.

.. role:: red

BitDust raid_worker Automat

.. raw:: html

    <a href="raid_worker.png" target="_blank">
    <img src="raid_worker.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`init`
    * :red:`new-task`
    * :red:`process-started`
    * :red:`shutdown`
    * :red:`task-done`
    * :red:`task-started`
    * :red:`timer-1min`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys
import threading

from six.moves import range

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in raid_worker.py')

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from system import bpio

from main import settings

from raid import read
from raid import make
from raid import rebuild

#------------------------------------------------------------------------------

_MODULES = (
    'raid.read',
    'raid.make',
    'raid.rebuild',
    'raid.eccmap',
    'raid.raidutils',
    'os',
    'sys',
    'copy',
    'array',
    'traceback',
    'six',
    'io',
)

_VALID_TASKS = {
    'make': (make.do_in_memory, (make.RoundupFile, make.ReadBinaryFile, make.WriteFile, make.ReadBinaryFileAsArray, )),
    'read': (read.raidread, (read.RebuildOne, read.ReadBinaryFile, )),
    'rebuild': (rebuild.rebuild, ()),
}

#------------------------------------------------------------------------------

_RaidWorker = None

#------------------------------------------------------------------------------


def add_task(cmd, params, callback):
    lg.out(10, 'raid_worker.add_task [%s] %s' % (cmd, str(params)[:80]))
    A('new-task', (cmd, params, callback))


def cancel_task(cmd, first_parameter):
    if not A():
        lg.out(10, 'raid_worker.cancel_task SKIP _RaidWorker is not started')
        return False
    task_id = None
    found = False
    for t_id, t_cmd, t_params in A().tasks:
        if cmd == t_cmd and first_parameter == t_params[0]:
            try:
                A().tasks.remove(t_id, t_cmd, t_params)
                lg.out(10, 'raid_worker.cancel_task found pending task %d, canceling %s' % (t_id, first_parameter))
            except:
                lg.warn('failed removing pending task %d, %s' % (t_id, first_parameter))
            found = True
            break
#    for i in xrange(len(A().tasks)):
#        t_id, t_cmd, t_params = A().tasks[i]
#        if cmd == t_cmd and first_parameter == t_params[0]:
#            lg.out(10, 'raid_worker.cancel_task found pending task %d, canceling' % t_id)
#            A().tasks.pop(i)
#            found = True
#            break
    for task_id, task_data in A().activetasks.items():
        t_proc, t_cmd, t_params = task_data
        if cmd == t_cmd and first_parameter == t_params[0]:
            lg.out(10, 'raid_worker.cancel_task found started task %d, aborting process %d' % (task_id, t_proc.tid))
            A().processor.cancel(t_proc.tid)
            found = True
            break
    if not found:
        lg.warn('task not found: %s %s' % (cmd, first_parameter))
        return False
    return True

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _RaidWorker
    if _RaidWorker is None:
        # small workaround to not create a new instance during shutdown process
        if event is None or event != 'init':
            return None
        # set automat name and starting state here
        _RaidWorker = RaidWorker(
            name='raid_worker',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _RaidWorker.automat(event, *args, **kwargs)
    return _RaidWorker


class RaidWorker(automat.Automat):
    """
    This class implements all the functionality of the ``raid_worker()`` state
    machine.
    """

    timers = {
        'timer-1min': (60, ['READY']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.task_id = -1
        self.tasks = []
        self.activetasks = {}
        self.processor = None
        self.callbacks = {}

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFF'
                self.doInit(*args, **kwargs)
        #---OFF---
        elif self.state == 'OFF':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doKillProcess(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'new-task':
                self.doAddTask(*args, **kwargs)
                self.doStartProcess(*args, **kwargs)
            elif event == 'process-started' and self.isMoreTasks(*args, **kwargs):
                self.state = 'WORK'
                self.doStartTask(*args, **kwargs)
            elif event == 'process-started' and not self.isMoreTasks(*args, **kwargs):
                self.state = 'READY'
        #---READY---
        elif self.state == 'READY':
            if event == 'new-task':
                self.state = 'WORK'
                self.doAddTask(*args, **kwargs)
                self.doStartTask(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doKillProcess(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-1min':
                self.state = 'OFF'
                self.doKillProcess(*args, **kwargs)
        #---WORK---
        elif self.state == 'WORK':
            if event == 'new-task':
                self.doAddTask(*args, **kwargs)
                self.doStartTask(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doReportTasksFailed(*args, **kwargs)
                self.doKillProcess(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'task-done' and self.isMoreTasks(*args, **kwargs):
                self.doReportTaskDone(*args, **kwargs)
                self.doPopTask(*args, **kwargs)
                self.doStartTask(*args, **kwargs)
            elif event == 'task-started' and self.isMoreTasks(*args, **kwargs):
                self.doStartTask(*args, **kwargs)
            elif event == 'task-done' and not self.isMoreActive(*args, **kwargs) and not self.isMoreTasks(*args, **kwargs):
                self.state = 'READY'
                self.doReportTaskDone(*args, **kwargs)
                self.doPopTask(*args, **kwargs)
            elif event == 'task-done' and self.isMoreActive(*args, **kwargs) and not self.isMoreTasks(*args, **kwargs):
                self.doReportTaskDone(*args, **kwargs)
                self.doPopTask(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isMoreTasks(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.tasks) > 0

    def isMoreActive(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.activetasks) > 1

    def doPopTask(self, *args, **kwargs):
        """
        Action method.
        """
        task_id, cmd, params, result = args[0]
        self.activetasks.pop(task_id)

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        reactor.addSystemEventTrigger('after', 'shutdown', self._kill_processor)  # @UndefinedVariable

    def doStartProcess(self, *args, **kwargs):
        """
        Action method.
        """
        os.environ['PYTHONUNBUFFERED'] = '1'
        ncpus = bpio.detect_number_of_cpu_cores()
        if ncpus > 1:
            # do not use all CPU cors at once
            # need to keep at least one for all other operations
            # even decided to use only half of CPUs at the moment
            # TODO: make an option in the software settings
            ncpus = int(ncpus / 2.0)

        if True:
            from parallelp import pp
            self.processor = pp.Server(
                secret='bitdust',
                ncpus=ncpus,
                loglevel=lg.get_loging_level(_DebugLevel),
                logfile=settings.ParallelPLogFilename(),
            )
        else:
            from raid import worker
            self.processor = worker.Manager(ncpus=ncpus)

        self.automat('process-started')

    def doKillProcess(self, *args, **kwargs):
        """
        Action method.
        """
        self._kill_processor()
        self.processor = None
        self.automat('process-finished')

    def doAddTask(self, *args, **kwargs):
        """
        Action method.
        """
        cmd, params, callback = args[0]
        self.task_id += 1
        self.tasks.append((self.task_id, cmd, params))
        self.callbacks[self.task_id] = callback

    def doStartTask(self, *args, **kwargs):
        """
        Action method.
        """
        global _VALID_TASKS
        global _MODULES

        if len(self.activetasks) >= self.processor.get_ncpus():
            lg.warn('SKIP active=%d cpus=%d' % (
                    len(self.activetasks), self.processor.get_ncpus()))
            return

        try:
            task_id, cmd, params = self.tasks.pop(0)
            func, depfuncs = _VALID_TASKS[cmd]
        except:
            lg.exc()
            return

        proc = self.processor.submit(
            func,
            args=params,
            depfuncs=depfuncs,
            modules=_MODULES,
            callback=lambda result: self._job_done(task_id, cmd, params, result),
            # error_callback=lambda err: self._job_failed(task_id, cmd, params, err),
        )

        self.activetasks[task_id] = (proc, cmd, params)
        if _Debug:
            lg.out(_DebugLevel, 'raid_worker.doStartTask %r active=%d cpus=%d %s' % (
                task_id, len(self.activetasks), self.processor.get_ncpus(), threading.currentThread().getName()))

        reactor.callLater(0.01, self.automat, 'task-started', task_id)  # @UndefinedVariable

    def doReportTaskDone(self, *args, **kwargs):
        """
        Action method.
        """
        task_id, cmd, params, result = args[0]
        cb = self.callbacks.pop(task_id)
        reactor.callLater(0, cb, cmd, params, result)  # @UndefinedVariable
        if result is not None:
            if _Debug:
                lg.out(_DebugLevel, 'raid_worker.doReportTaskDone callbacks: %d tasks: %d active: %d' % (
                    len(self.callbacks), len(self.tasks), len(self.activetasks)))
        else:
            if _Debug:
                lg.out(_DebugLevel, 'raid_worker.doReportTaskDone result=None !!!!! callbacks: %d tasks: %d active: %d' % (
                    len(self.callbacks), len(self.tasks), len(self.activetasks)))

    def doReportTasksFailed(self, *args, **kwargs):
        """
        Action method.
        """
        for i in range(len(self.tasks)):
            task_id, cmd, params = self.tasks[i]
            cb = self.callbacks.pop(task_id)
            reactor.callLater(0, cb, cmd, params, None)  # @UndefinedVariable
        for task_id, task_data in self.activetasks.items():
            cb = self.callbacks.pop(task_id)
            _, cmd, params = task_data
            reactor.callLater(0, cb, cmd, params, None)  # @UndefinedVariable

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()
        global _RaidWorker
        del _RaidWorker
        _RaidWorker = None

    def _job_done(self, task_id, cmd, params, result):
        if _Debug:
            lg.out(_DebugLevel, 'raid_worker._job_done %r : %r active:%r cmd=%r params=%r %s' % (
                task_id, result, list(self.activetasks.keys()), cmd, params, threading.currentThread().getName()))
        reactor.callFromThread(self.automat, 'task-done', (task_id, cmd, params, result))  # @UndefinedVariable

    def _job_failed(self, task_id, cmd, params, err):
        lg.err('task %r FAILED : %r   active:%r cmd=%r params=%r' % (
            task_id, err, list(self.activetasks.keys()), cmd, params))
        self.automat('shutdown')

    def _kill_processor(self):
        if self.processor:
            self.processor.destroy()
            if _Debug:
                lg.out(_DebugLevel, 'raid_worker._kill_processor processor was destroyed')


#------------------------------------------------------------------------------

def _read_done(cmd, taskdata, result):
    lg.out(0, '_read_done %r %r %r' % (cmd, taskdata, result))
    A('shutdown')
    reactor.stop()  # @UndefinedVariable


def _make_done(cmd, taskdata, result):
    lg.out(0, '_make_done %r %r %r' % (cmd, taskdata, result))
    reactor.callLater(0.5, add_task, 'read', ('/tmp/destination.txt', 'ecc/18x18', 'F12345678', '5', '/tmp/raidtest'), _read_done)  # @UndefinedVariable


def main():
    import base64

    bpio.init()
    lg.set_debug_level(20)

    os.system('rm -rf /tmp/raidtest')
    os.system('mkdir -p /tmp/raidtest/F12345678')
    open('/tmp/source.txt', 'w').write(base64.b64encode(os.urandom(1000)).decode())

    reactor.callWhenRunning(A, 'init')  # @UndefinedVariable
    reactor.callLater(0.5, add_task, 'make', ('/tmp/source.txt', 'ecc/18x18', 'F12345678', '5', '/tmp/raidtest/F12345678'), _make_done)  # @UndefinedVariable

    reactor.run()  # @UndefinedVariable

if __name__ == "__main__":
    main()
