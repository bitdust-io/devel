import multiprocessing
import functools
import time
from collections import OrderedDict
from threading import Thread, Lock

queue = multiprocessing.Queue()


class my_decorator_class(object):

    def __init__(self, target):
        self.target = target

        try:
            functools.update_wrapper(self, target)
        except:
            pass

    def __call__(self, *args, **kwargs):
        res = self.target(*args)
        queue.put(1)
        return res


def func_thread(tasks, pool):
    while True:
        queue.get()
        try:
            task = tasks.popitem(last=False)
        except KeyError:
            queue.put(1)
            time.sleep(0.5)
        else:
            func, params, callback = task[1]

            pool.apply_async(func=func, args=params, callback=callback)


class Task(object):
    def __init__(self, task_id):
        self.task_id = task_id

    @property
    def tid(self):
        return self.task_id


class Manager(object):
    def __init__(self, ncpus):
        self._ncpus = ncpus

        self.processor = multiprocessing.Pool(ncpus)
        #: implement queue per Manager instance
        # self.queue = multiprocessing.Queue()

        self.tasks = OrderedDict({})
        self.task_id = 0

        self.thread = Thread(target=func_thread, args=(self.tasks, self.processor))
        self.thread.daemon = True
        self.thread.start()

        self._propagate_queue()

        self._lock = Lock()

    def _propagate_queue(self):
        for i in range(self.ncpus):
            queue.put(1)

    def submit(self, func, params, callback):
        with self._lock:
            self.task_id += 1
            self.tasks[self.task_id] = (my_decorator_class(target=func), params, callback)
        return Task(self.task_id)

    @property
    def ncpus(self):
        return self._ncpus

    def terminate(self):
        self.processor.terminate()

    def cancel(self, task_id):
        with self._lock:
            try:
                del self.tasks[task_id]
            except KeyError:
                pass
