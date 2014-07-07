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
    * :red:`process-finished`
    * :red:`process-started`
    * :red:`shutdown`
    * :red:`task-done`
    * :red:`timer-1min`
"""

import os
import sys
import base64

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in raid_worker.py')

from twisted.internet import protocol

try:
    import lib.dhnio as dhnio
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    try:
        import lib.dhnio as dhnio
    except:
        sys.exit()

import lib.automat as automat
import lib.child_process as child_process


#------------------------------------------------------------------------------ 

_RaidWorker = None

#------------------------------------------------------------------------------ 

def start_processor():
    return child_process.run(
        'bpraid', ['-u'], process_protocol=RaidProcessProtocol('bpraid'))


def kill_processor(proc_obj=None):
    if proc_obj:
        if child_process.kill_process(proc_obj):
            return True
    child_process.kill_child('bpraid')

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
        _RaidWorker = RaidWorker('raid_worker', 'AT_STARTUP')
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
        self.tasks = []
        self.processor = None
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """

    def state_changed(self, oldstate, newstate):
        """
        Method to to catch the moment when automat's state were changed.
        """

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
            elif event == 'process-finished' :
                self.state = 'OFF'
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doKillProcess(arg)
                self.doDestroyMe(arg)
            elif event == 'timer-1min' :
                self.doKillProcess(arg)
        #---WORK---
        elif self.state == 'WORK':
            if event == 'task-done' and not self.isMoreTasks(arg) :
                self.state = 'READY'
                self.doReportTaskDone(arg)
                self.doRemoveTask(arg)
            elif event == 'process-finished' :
                self.state = 'OFF'
                self.doReportTaskFailed(arg)
                self.doRemoveTask(arg)
            elif event == 'new-task' :
                self.doAddTask(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doReportTaskFailed(arg)
                self.doRemoveTask(arg)
                self.doKillProcess(arg)
                self.doDestroyMe(arg)
            elif event == 'task-done' and self.isMoreTasks(arg) :
                self.doReportTaskDone(arg)
                self.doRemoveTask(arg)
                self.doStartTask(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass

    def isMoreTasks(self, arg):
        """
        Condition method.
        """
        return len(self.tasks) > 1

    def isSomeTasks(self, arg):
        """
        Condition method.
        """
        return len(self.tasks) > 0

    def doInit(self, arg):
        """
        Action method.
        """
        reactor.addSystemEventTrigger('after', 'shutdown', kill_processor)

    def doStartProcess(self, arg):
        """
        Action method.
        """
        self.processor = start_processor()

    def doKillProcess(self, arg):
        """
        Action method.
        """
        kill_processor(self.processor)

    def doAddTask(self, arg):
        """
        Action method.
        """
        self.tasks.append(arg)
        
    def doRemoveTask(self, arg):
        """
        Action method.
        """
        self.tasks.pop(0)

    def doStartTask(self, arg):
        """
        Action method.
        """
        cmd, callback, taskdata = list(self.tasks[0])
        encodedtaskdata = ' '.join(map(lambda e: base64.b64encode(str(e)), taskdata))
        encodedtaskdata = cmd + ' ' + encodedtaskdata
        self.processor.proto.transport.write(encodedtaskdata+'\n')

    def doReportTaskDone(self, arg):
        """
        Action method.
        """
        cmd, callback, taskdata = self.tasks[0]
        callback(cmd, taskdata, arg)

    def doReportTaskFailed(self, arg):
        """
        Action method.
        """
        cmd, callback, taskdata = self.tasks[0]
        callback(cmd, taskdata, None)

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        automat.objects().pop(self.index)
        global _RaidWorker
        del _RaidWorker
        _RaidWorker = None

#------------------------------------------------------------------------------ 

class RaidProcessProtocol(child_process.ChildProcessProtocol):

    def outReceived(self, data):
        try:
            words = data.strip().split()
            cmd = words[0]
            params = words[1:]
        except:
            dhnio.Dprint(4, '[bpraid] %s' % data)
            return
        if cmd == 'process-started':
            A('process-started')
        elif cmd == 'task-done':
            A('task-done', params)
        elif cmd == 'error':
            A('task-done', None)
        else:
            dhnio.Dprint(4, '[bpraid] %s' % data)
        
    def processEnded(self, status):
        A('process-finished', status)

#------------------------------------------------------------------------------ 

def main():
    def _cb(cmd, taskdata, result):
        print cmd, taskdata, result 
    dhnio.init()
    dhnio.SetDebug(20)
    reactor.callWhenRunning(A, 'init')
    reactor.callLater(0.5, A, 'new-task', ('make', _cb, ('sdfsdf', '45', '324', '45')))
    reactor.run()

if __name__ == "__main__":
    main()
