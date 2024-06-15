import os
from unittest import TestCase
import time
import mock

from bitdust.raid.worker import Manager
from bitdust.system import bpio


def heavy_task(tsk_id):
    time.sleep(2)
    open('/tmp/heavy_task_is_done_%s' % tsk_id, 'w').write('ok')
    return tsk_id


class TestManager(TestCase):

    def setUp(self):
        if bpio.Mac():
            return
        self.manager = Manager(2)

    def tearDown(self):
        if bpio.Mac():
            return
        self.manager.terminate()

    def test_callback(self):
        if bpio.Mac():
            return
        if os.path.isfile('/tmp/heavy_task_is_done_0'):
            os.remove('/tmp/heavy_task_is_done_0')
        heavy_task_1_callback = mock.Mock()
        self.manager.submit(func=heavy_task, params=(0,), callback=heavy_task_1_callback)
        time.sleep(5)
        heavy_task_1_callback.assert_called_once_with(0)
        os.remove('/tmp/heavy_task_is_done_0')

    def test_cancellation(self):
        if bpio.Mac():
            return
        for i in range(1, 10):
            if os.path.isfile('/tmp/heavy_task_is_done_%d' % i):
                os.remove('/tmp/heavy_task_is_done_%d' % i)
        heavy_task_1_callback = mock.Mock()
        heavy_task_2_callback = mock.Mock()
        heavy_task_3_callback = mock.Mock()
        heavy_task_4_callback = mock.Mock()
        heavy_task_5_callback = mock.Mock()
        heavy_task_6_callback = mock.Mock()
        heavy_task_7_callback = mock.Mock()
        heavy_task_8_callback = mock.Mock()
        heavy_task_9_callback = mock.Mock()
        r1 = self.manager.submit(func=heavy_task, params=(1,), callback=heavy_task_1_callback)
        r2 = self.manager.submit(func=heavy_task, params=(2,), callback=heavy_task_2_callback)
        r3 = self.manager.submit(func=heavy_task, params=(3,), callback=heavy_task_3_callback)
        r4 = self.manager.submit(func=heavy_task, params=(4,), callback=heavy_task_4_callback)
        r5 = self.manager.submit(func=heavy_task, params=(5,), callback=heavy_task_5_callback)
        r6 = self.manager.submit(func=heavy_task, params=(6,), callback=heavy_task_6_callback)
        r7 = self.manager.submit(func=heavy_task, params=(7,), callback=heavy_task_7_callback)
        r8 = self.manager.submit(func=heavy_task, params=(8,), callback=heavy_task_8_callback)
        r9 = self.manager.submit(func=heavy_task, params=(9,), callback=heavy_task_9_callback)
        self.manager.cancel(r3.tid)
        self.manager.cancel(r7.tid)
        counter = 0
        while True:
            if os.path.isfile('/tmp/heavy_task_is_done_9'):
                break
            time.sleep(1)
            counter += 1
            print('counter', counter)
            if counter > 30:
                for i in range(1, 10):
                    if os.path.isfile('/tmp/heavy_task_is_done_%d' % i):
                        os.remove('/tmp/heavy_task_is_done_%d' % i)
                assert False, 'failed!'
        heavy_task_1_callback.assert_called_once()
        heavy_task_2_callback.assert_called_once()
        heavy_task_3_callback.assert_not_called()
        heavy_task_4_callback.assert_called_once()
        heavy_task_5_callback.assert_called_once()
        heavy_task_6_callback.assert_called_once()
        heavy_task_7_callback.assert_not_called()
        heavy_task_8_callback.assert_called_once()
        heavy_task_9_callback.assert_called_once()
        for i in range(1, 10):
            if os.path.isfile('/tmp/heavy_task_is_done_%d' % i):
                os.remove('/tmp/heavy_task_is_done_%d' % i)
