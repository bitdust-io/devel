#!/usr/bin/python
#raid_worker.py
#
# <<<COPYRIGHT>>>
#
#
#
#


"""
.. module:: raid_worker
.. role:: red

BitPie.NET raid_worker Automat

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

import os
import sys

from parallelp import pp

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in raid_worker.py')

from logs import lg

from lib import bpio
from lib import automat

import read
import make
import rebuild

#------------------------------------------------------------------------------ 

_MODULES = (
    'os',
    'cStringIO',
    'struct',
    'logs.lg',
    'raid.read', 
    'raid.make',
    'raid.rebuild', 
    'raid.eccmap',
    'lib.settings', 
    'lib.bpio',
    'lib.misc',
    'lib.packetid',
    )

_VALID_TASKS = {
    'make': make.do_in_memory,
    'read': read.raidread,
    'rebuild': rebuild.rebuild,
}

#------------------------------------------------------------------------------ 

_RaidWorker = None

#------------------------------------------------------------------------------ 

def add_task(cmd, params, callback):
    A('new-task', (cmd, params, callback))
     
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
        _RaidWorker = RaidWorker('raid_worker', 'AT_STARTUP', 6)
    if event is not None:
        _RaidWorker.automat(event, arg)
    return _RaidWorker


class RaidWorker(automat.Automat):
    """
    This class implements all the functionality of the ``raid_worker()`` state machine.

    """

    timers = {
        'timer-1min': (60, ['READY']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.task_id = -1
        self.tasks = []
        self.activetasks = {}
        self.processor = None
        self.callbacks = {}

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'OFF'
                self.doInit(arg)
        #---OFF---
        elif self.state == 'OFF':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doKillProcess(arg)
                self.doDestroyMe(arg)
            elif event == 'process-started' and self.isSomeTasks(arg) :
                self.state = 'WORK'
                self.doStartTask(arg)
            elif event == 'new-task' :
                self.doAddTask(arg)
                self.doStartProcess(arg)
            elif event == 'process-started' and not self.isSomeTasks(arg) :
                self.state = 'READY'
        #---READY---
        elif self.state == 'READY':
            if event == 'new-task' :
                self.state = 'WORK'
                self.doAddTask(arg)
                self.doStartTask(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doKillProcess(arg)
                self.doDestroyMe(arg)
            elif event == 'timer-1min' :
                self.state = 'OFF'
                self.doKillProcess(arg)
        #---WORK---
        elif self.state == 'WORK':
            if event == 'new-task' :
                self.doAddTask(arg)
                self.doStartTask(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doReportTasksFailed(arg)
                self.doKillProcess(arg)
                self.doDestroyMe(arg)
            elif event == 'task-done' and self.isMoreTasks(arg) :
                self.doReportTaskDone(arg)
                self.doStartTask(arg)
            elif event == 'task-started' and self.isMoreTasks(arg) :
                self.doStartTask(arg)
            elif event == 'task-done' and not self.isSomeActive(arg) and not self.isMoreTasks(arg) :
                self.state = 'READY'
                self.doReportTaskDone(arg)
            elif event == 'task-done' and self.isSomeActive(arg) and not self.isMoreTasks(arg) :
                self.doReportTaskDone(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass

    def isSomeTasks(self, arg):
        """
        Condition method.
        """
        return len(self.tasks) > 0

    def isMoreTasks(self, arg):
        """
        Condition method.
        """
        return len(self.tasks) >= 1

    def isSomeActive(self, arg):
        """
        Condition method.
        """
        return len(self.activetasks) > 0
        
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
        self.processor = pp.Server(secret='bitpie')
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
        if len(self.activetasks) >= self.processor.get_ncpus():
            lg.out(12, 'raid_worker.doStartTask SKIP active=%d cpus=%d' % (
                len(self.activetasks), self.processor.get_ncpus()))
            return
        try:
            task_id, cmd, params = self.tasks.pop(0)
            func = _VALID_TASKS[cmd]
        except:
            lg.exc()
            return
        self.activetasks[task_id] = self.processor.submit(func, params,
            modules=_MODULES, 
            callback=lambda result: self._job_done(task_id, cmd, params, result))
        lg.out(12, 'raid_worker.doStartTask %r active=%d cpus=%d' % (
            task_id, len(self.activetasks), self.processor.get_ncpus()))
        reactor.callLater(0.01, self.automat, 'task-started', task_id)

    def doReportTaskDone(self, arg):
        """
        Action method.
        """
        try:
            task_id, cmd, params, result = arg
            cb = self.callbacks.pop(task_id)
            cb(cmd, params, result)
            lg.out(12, 'raid_worker.doReportTaskDone callbacks: %d tasks: %d active: %d' % (
                len(self.callbacks), len(self.tasks), len(self.activetasks)))
        except:
            lg.exc()

    def doReportTasksFailed(self, arg):
        """
        Action method.
        """
        for i in xrange(len(self.tasks)):
            task_id, cmd, params = self.tasks[i]
            cb = self.callbacks.pop(task_id)
            cb(cmd, params, None)
        for task_id in self.activetasks.keys():
            cb = self.callbacks.pop(task_id)
            cb(cmd, params, None)

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        automat.objects().pop(self.index)
        global _RaidWorker
        del _RaidWorker
        _RaidWorker = None

    def _job_done(self, task_id, cmd, params, result):
        self.activetasks.pop(task_id)
        lg.out(12, 'raid_worker._job_done %r : %r active:%r' % (
            task_id, result, self.activetasks.keys()))
        self.automat('task-done', (task_id, cmd, params, result))

    def _kill_processor(self):
        if self.processor:
            self.processor.destroy()
            lg.out(12, 'raid_worker._kill_processor processor was destroyed')
        

#------------------------------------------------------------------------------ 

def main():
    def _cb(cmd, taskdata, result):
        print cmd, taskdata, result 
    bpio.init()
    lg.set_debug_level(20)
    reactor.callWhenRunning(A, 'init')
    reactor.callLater(0.5, A, 'new-task', ('make', _cb, ('sdfsdf', '45', '324', '45')))
    reactor.run()

if __name__ == "__main__":
    main()
