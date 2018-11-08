#!/usr/bin/python
# raid_worker.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys

from six.moves import range

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in raid_worker.py')

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from automats import automat

from main import settings

from raid.worker import Manager

from . import read
from . import make
from . import rebuild

#------------------------------------------------------------------------------

_MODULES = (
    'os',
    'sys',
    'StringIO',
    'struct',
    'logs.lg',
    'raid.read',
    'raid.make',
    'raid.rebuild',
    'raid.eccmap',
    'raid.utils',
    'main.settings',
    'system.bpio',
    'lib.misc',
    'lib.packetid',
    'copy',
    'array',
)

_VALID_TASKS = {
    'make': (make.do_in_memory,
             (make.RoundupFile, make.ReadBinaryFile, make.WriteFile, make.ReadBinaryFileAsArray)),
    'read': (read.raidread,
             (read.RebuildOne, read.ReadBinaryFile,)),
    'rebuild': (rebuild.rebuild,
                ()),
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


def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _RaidWorker
    if _RaidWorker is None:
        if event is None or event != 'init':
            return None
        # set automat name and starting state here
        _RaidWorker = RaidWorker('raid_worker', 'AT_STARTUP', 6, True)
    if event is not None:
        _RaidWorker.automat(event, arg)
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

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFF'
                self.doInit(arg)
        #---OFF---
        elif self.state == 'OFF':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doKillProcess(arg)
                self.doDestroyMe(arg)
            elif event == 'new-task':
                self.doAddTask(arg)
                self.doStartProcess(arg)
            elif event == 'process-started' and self.isMoreTasks(arg):
                self.state = 'WORK'
                self.doStartTask(arg)
            elif event == 'process-started' and not self.isMoreTasks(arg):
                self.state = 'READY'
        #---READY---
        elif self.state == 'READY':
            if event == 'new-task':
                self.state = 'WORK'
                self.doAddTask(arg)
                self.doStartTask(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doKillProcess(arg)
                self.doDestroyMe(arg)
            elif event == 'timer-1min':
                self.state = 'OFF'
                self.doKillProcess(arg)
        #---WORK---
        elif self.state == 'WORK':
            if event == 'new-task':
                self.doAddTask(arg)
                self.doStartTask(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doReportTasksFailed(arg)
                self.doKillProcess(arg)
                self.doDestroyMe(arg)
            elif event == 'task-done' and self.isMoreTasks(arg):
                self.doReportTaskDone(arg)
                self.doPopTask(arg)
                self.doStartTask(arg)
            elif event == 'task-started' and self.isMoreTasks(arg):
                self.doStartTask(arg)
            elif event == 'task-done' and not self.isMoreActive(arg) and not self.isMoreTasks(arg):
                self.state = 'READY'
                self.doReportTaskDone(arg)
                self.doPopTask(arg)
            elif event == 'task-done' and self.isMoreActive(arg) and not self.isMoreTasks(arg):
                self.doReportTaskDone(arg)
                self.doPopTask(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isMoreTasks(self, arg):
        """
        Condition method.
        """
        return len(self.tasks) > 0

    def isMoreActive(self, arg):
        """
        Condition method.
        """
        return len(self.activetasks) > 1

    def doPopTask(self, arg):
        """
        Action method.
        """
        task_id, cmd, params, result = arg
        self.activetasks.pop(task_id)

    def doInit(self, arg):
        """
        Action method.
        """
        reactor.addSystemEventTrigger('after', 'shutdown', self._kill_processor)

    def doStartProcess(self, arg):
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

        self.processor = Manager(ncpus=ncpus)

        self.automat('process-started')

    def doKillProcess(self, arg):
        """
        Action method.
        """
        self._kill_processor()
        self.processor = None
        self.automat('process-finished')

    def doAddTask(self, arg):
        """
        Action method.
        """
        cmd, params, callback = arg
        self.task_id += 1
        self.tasks.append((self.task_id, cmd, params))
        self.callbacks[self.task_id] = callback

    def doStartTask(self, arg):
        """
        Action method.
        """
        global _VALID_TASKS
        global _MODULES

        if len(self.activetasks) >= self.processor.ncpus:
            lg.out(12, 'raid_worker.doStartTask SKIP active=%d cpus=%d' % (
                len(self.activetasks), self.processor.ncpus))
            return

        try:
            task_id, cmd, params = self.tasks.pop(0)
            func, depfuncs = _VALID_TASKS[cmd]
        except:
            lg.exc()
            return

        proc = self.processor.submit(
            func,
            params,
            callback=lambda result: self._job_done(task_id, cmd, params, result),
        )

        self.activetasks[task_id] = (proc, cmd, params)
        lg.out(12, 'raid_worker.doStartTask %r active=%d cpus=%d' % (
            task_id, len(self.activetasks), self.processor.ncpus))
        reactor.callLater(0.01, self.automat, 'task-started', task_id)

    def doReportTaskDone(self, arg):
        """
        Action method.
        """
        try:
            task_id, cmd, params, result = arg
            cb = self.callbacks.pop(task_id)
            reactor.callLater(0, cb, cmd, params, result)
            if result is not None:
                lg.out(12, 'raid_worker.doReportTaskDone callbacks: %d tasks: %d active: %d' % (
                    len(self.callbacks), len(self.tasks), len(self.activetasks)))
            else:
                lg.out(12, 'raid_worker.doReportTaskDone result=None !!!!! callbacks: %d tasks: %d active: %d' % (
                    len(self.callbacks), len(self.tasks), len(self.activetasks)))
        except:
            lg.exc()

    def doReportTasksFailed(self, arg):
        """
        Action method.
        """
        for i in range(len(self.tasks)):
            task_id, cmd, params = self.tasks[i]
            cb = self.callbacks.pop(task_id)
            reactor.callLater(0, cb, cmd, params, None)
        for task_id, task_data in self.activetasks.items():
            cb = self.callbacks.pop(task_id)
            _, cmd, params = task_data
            reactor.callLater(0, cb, cmd, params, None)

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()
        global _RaidWorker
        del _RaidWorker
        _RaidWorker = None

    def _job_done(self, task_id, cmd, params, result):
        lg.out(6, 'raid_worker._job_done %r : %r active:%r' % (
            task_id, result, list(self.activetasks.keys())))
        self.automat('task-done', (task_id, cmd, params, result))

    def _kill_processor(self):
        if self.processor:
            self.processor.terminate()
            lg.out(12, 'raid_worker._kill_processor processor was destroyed')


#------------------------------------------------------------------------------


def main():
    def _cb(cmd, taskdata, result):
        print(cmd, taskdata, result)
    bpio.init()
    lg.set_debug_level(20)
    reactor.callWhenRunning(A, 'init')
    reactor.callLater(0.5, A, 'new-task', ('make', _cb, ('sdfsdf', '45', '324', '45')))
    reactor.run()

if __name__ == "__main__":
    main()
