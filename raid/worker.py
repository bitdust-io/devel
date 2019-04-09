    #!/usr/bin/env python
# rebuild.py
#
# Copyright (C) 2008-2019 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (rebuild.py) is part of BitDust Software.
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

#------------------------------------------------------------------------------

from __future__ import absolute_import
import six

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import time
import traceback
import multiprocessing

from collections import OrderedDict

from threading import Thread, Lock

#------------------------------------------------------------------------------

from logs import lg

#------------------------------------------------------------------------------

_WorkerQueue = multiprocessing.Queue()
_WorkerLock = Lock()

#------------------------------------------------------------------------------

class my_decorator_class(object):

    def __init__(self, target):
        self.target = target

    def __call__(self, *args, **kwargs):
        task_id = args[-1]
        args = args[:-1]
        res = None

        try:
            res = self.target(*args)
        except Exception as e:
            traceback.print_exc()
            res = e
        finally:
            try:
                _WorkerQueue.put(1)
            except Exception:
                print('worker got Exception in queue -- exiting')

        return res


def func_thread(tasks, pool):
    while True:
        try:
            _WorkerQueue.get()
        except (EOFError, OSError, IOError):
            print('publisher got EOFError or OSError or IOError -- exiting')
            break

        with _WorkerLock:
            try:
                task = tasks.popitem(last=False)
            except KeyError:
                task = None

        if task:
            func, params, callback, error_callback, task_id = task[1]
            if _Debug:
                lg.out(_DebugLevel, 'raid.worker.func_thread is going to apply task %s' % task_id)
            if six.PY3:
                pool.apply_async(func=func, args=params + (task_id,), callback=callback, error_callback=error_callback)
            else:
                pool.apply_async(func=func, args=params + (task_id,), callback=callback)
        else:
            try:
                _WorkerQueue.put(1)
            except Exception:
                print('publisher got Exception with queue -- exiting')
                break

            time.sleep(0.1)

    pool.terminate()


class Task(object):

    def __init__(self, task_id):
        self.task_id = task_id
        if _Debug:
            lg.out(_DebugLevel, 'raid.worker.Task created  task_id=%s' % task_id)

    @property
    def tid(self):
        return self.task_id


class Manager(object):

    def __init__(self, ncpus):
        self._ncpus = ncpus

        if six.PY34:
            try:
                multiprocessing.set_start_method('spawn')
            except RuntimeError:
                pass

        multiprocessing.util.log_to_stderr(multiprocessing.util.SUBDEBUG)

        from system import bpio
        if bpio.Windows():
            from system import deploy
            deploy.init_base_dir()
            venv_python_path = os.path.join(deploy.current_base_dir(), 'venv', 'Scripts', 'BitDustNode.exe')
            lg.info('will use %s as multiprocessing executable' % venv_python_path)
            multiprocessing.set_executable(venv_python_path)

        self.processor = multiprocessing.Pool(ncpus)

        #: implement queue per Manager instance
        # self.queue = multiprocessing.Queue()

        self.tasks = OrderedDict({})
        self.task_id = 0

        self.thread = Thread(target=func_thread, args=(self.tasks, self.processor))
        self.thread.daemon = True
        self.thread.start()

        self._propagate_queue()

    def _propagate_queue(self):
        for i in range(self.ncpus):
            _WorkerQueue.put(1)

    def submit(self, func, params, callback, error_callback=None):
        with _WorkerLock:
            self.task_id += 1
            self.tasks[self.task_id] = (my_decorator_class(target=func), params, callback, error_callback, self.task_id)
        return Task(self.task_id)

    @property
    def ncpus(self):
        return self._ncpus

    def terminate(self):
        self.processor.terminate()

    def cancel(self, task_id):
        with _WorkerLock:
            try:
                del self.tasks[task_id]
            except KeyError:
                pass
