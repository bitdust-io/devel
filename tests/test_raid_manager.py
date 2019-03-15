from unittest import TestCase
import time
import mock

from raid.worker import Manager


def heavy_task(id):
    time.sleep(2)
    return id


def light_task():
    return None


class TestManager(TestCase):

    def setUp(self):
        self.manager = Manager(2)

    def tearDown(self):
        self.manager.terminate()

    def test_submit(self):
        callback = mock.Mock()

        self.manager.submit(func=light_task, params=(), callback=callback)
        self.manager.submit(func=light_task, params=(), callback=callback)
        self.manager.submit(func=light_task, params=(), callback=callback)
        self.manager.submit(func=light_task, params=(), callback=callback)
        self.manager.submit(func=light_task, params=(), callback=callback)
        self.manager.submit(func=light_task, params=(), callback=callback)
        self.manager.submit(func=light_task, params=(), callback=callback)
        self.manager.submit(func=light_task, params=(), callback=callback)
        self.manager.submit(func=light_task, params=(), callback=callback)

        time.sleep(5)
        assert callback.call_count == 9, callback.call_count

    def test_callback(self):
        heavy_task_1_callback = mock.Mock()
        self.manager.submit(func=heavy_task, params=(1,), callback=heavy_task_1_callback)
        time.sleep(5)
        heavy_task_1_callback.assert_called_once_with(1)

    def test_cancellation(self):
        heavy_task_1_callback = mock.Mock()
        heavy_task_2_callback = mock.Mock()
        heavy_task_3_callback = mock.Mock()
        self.manager.submit(func=heavy_task, params=(1,), callback=heavy_task_1_callback)
        self.manager.submit(func=heavy_task, params=(2,), callback=heavy_task_2_callback)
        r3 = self.manager.submit(func=heavy_task, params=(3,), callback=heavy_task_3_callback)

        self.manager.cancel(r3.tid)
        time.sleep(5)

        heavy_task_1_callback.assert_called_once()
        heavy_task_2_callback.assert_called_once()
        # heavy_task_3_callback.assert_not_called()
