import multiprocessing
import os


def _worker_main(queue):
    """

    :param queue: multiprocessing.Queue
    :return:
    """
    while True:
        item = queue.get(block=True)
        func = item['func']
        callback = item['callback']
        params = item['params']

        res = func(**params)
        print(os.getpid(), "got", item)
        callback(res)


class Manager(object):
    def __init__(self, ncpus):
        self.the_queue = multiprocessing.Queue()

        self._ncpus = ncpus

        self.processor = multiprocessing.Pool(ncpus, _worker_main, (self.the_queue, ))

    def submit(self, func, params, callback, value):
        obj = {'func': func, 'params': params, 'callback': callback}
        self.the_queue.put(obj)

    @property
    def ncpus(self):
        return self.ncpus

    def terminate(self):
        self.processor.terminate()

    def cancel(self, task_id):

        pass


