import multiprocessing
import time
import traceback
from collections import OrderedDict
from threading import Thread, Lock
import six

queue = multiprocessing.Queue()

lock = Lock()


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
                queue.put(1)
            except Exception:
                print('worker got Exception in queue -- exiting')

        return res


# def _initializer_worker(queue_cancel):
#     print(os.getpid(), '_initializer_worker', queue_cancel)
#
#     def func():
#         while True:
#             value = pipea.recv()
#             print(os.getpid(), 'value', value)
#             # tid = joinable_cancel_task.get()
#             process = multiprocessing.current_process()
#             print('kill process %s. tid - %s' % (process.pid, value))
#             os.kill(process.pid, signal.SIGTERM)
#             time.sleep(1)
#
#     thread = Thread(target=func)
#     thread.daemon = True
#     thread.start()


def func_thread(tasks, pool):
    while True:
        try:
            queue.get()
        except (EOFError, OSError, IOError):
            print('publisher got EOFError or OSError or IOError -- exiting')
            break

        with lock:
            try:
                task = tasks.popitem(last=False)
            except KeyError:
                task = None

        if task:
            func, params, callback, error_callback, task_id = task[1]

            if six.PY3:
                pool.apply_async(func=func, args=params + (task_id,), callback=callback, error_callback=error_callback)
            else:
                pool.apply_async(func=func, args=params + (task_id,), callback=callback)
        else:
            try:
                queue.put(1)
            except Exception:
                print('publisher got Exception with queue -- exiting')
                break

            time.sleep(0.1)

    print('close pool')
    pool.terminate()


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

    def _propagate_queue(self):
        for i in range(self.ncpus):
            queue.put(1)

    def submit(self, func, params, callback, error_callback=None):
        with lock:
            self.task_id += 1
            self.tasks[self.task_id] = (my_decorator_class(target=func), params, callback, error_callback, self.task_id)

        return Task(self.task_id)

    @property
    def ncpus(self):
        return self._ncpus

    def terminate(self):
        self.processor.terminate()

    def cancel(self, task_id):
        with lock:
            try:
                del self.tasks[task_id]
            except KeyError:
                pass
