import os
import base64

from twisted.trial.unittest import TestCase
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred
from twisted.internet.base import DelayedCall
DelayedCall.debug = True


from raid import raid_worker

from logs import lg

from system import bpio

from system import local_fs

from main import settings
from main import config


class _Helper(object):

    def setUp(self):
        try:
            bpio.rmdir_recursive('/tmp/.bitdust_tmp')
        except Exception:
            pass
        settings.init(base_dir='/tmp/.bitdust_tmp')
        lg.set_debug_level(30)
        try:
            os.makedirs('/tmp/.bitdust_tmp/logs')
        except:
            pass
        local_fs.WriteTextFile('/tmp/.bitdust_tmp/logs/parallelp.log', '')
        if self.child_processes_enabled:
            config.conf().setBool('services/rebuilding/child-processes-enabled', True)
        else:
            config.conf().setBool('services/rebuilding/child-processes-enabled', False)

    def tearDown(self):
        bpio.rmdir_recursive('/tmp/.bitdust_tmp')

    def _test_make_rebuild_read(self, target_ecc_map, num_suppliers, dead_suppliers, read_success, rebuild_one_success, filesize, skip_rebuild=False):
        test_result = Deferred()

        curdir = os.getcwd()
        if curdir.count('_trial_temp'):
            os.chdir(os.path.abspath(os.path.join(curdir, '..')))

        def _read_done(cmd, taskdata, result):
            if read_success:
                self.assertEqual(open('/tmp/source.txt', 'r').read(), open('/tmp/destination.txt', 'r').read())
            else:
                self.assertNotEqual(open('/tmp/source.txt', 'r').read(), open('/tmp/destination.txt', 'r').read())
            os.system('rm -rf /tmp/source.txt')
            os.system('rm -rf /tmp/destination.txt')
            os.system('rm -rf /tmp/raidtest')
            reactor.callLater(0, raid_worker.A, 'shutdown')  # @UndefinedVariable
            reactor.callLater(0.1, test_result.callback, True)  # @UndefinedVariable
            return True

        def _rebuild_done(cmd, taskdata, result):
            newData, localData, localParity, reconstructedData, reconstructedParity = result
            if rebuild_one_success:
                self.assertEqual(newData, True)
            else:
                self.assertEqual(newData, False)
            # try to read all fragments now
            reactor.callLater(0.5, raid_worker.add_task, 'read', (  # @UndefinedVariable
                '/tmp/destination.txt', target_ecc_map, 'F12345678', '5', '/tmp/raidtest/master$alice@somehost.com/0'), _read_done)
            return True

        def _make_done(cmd, taskdata, result):
            self.assertEqual(list(result), [num_suppliers, num_suppliers])
            # remove few fragments and try to rebuild the whole block
            for supplier_position in range(dead_suppliers):
                os.system("rm -rf '/tmp/raidtest/master$alice@somehost.com/0/F12345678/5-%d-Data'" % supplier_position)
                os.system("rm -rf '/tmp/raidtest/master$alice@somehost.com/0/F12345678/5-%d-Parity'" % supplier_position)
            alive_suppliers = num_suppliers - dead_suppliers
            remote_fragments = {
                'D': [0, ] * dead_suppliers + [1, ] * alive_suppliers,
                'P': [0, ] * dead_suppliers + [1, ] * alive_suppliers,
            }
            local_fragments = {
                'D': [0, ] * dead_suppliers + [1, ] * alive_suppliers,
                'P': [0, ] * dead_suppliers + [1, ] * alive_suppliers,
            }
            if skip_rebuild:
                reactor.callLater(0.5, raid_worker.add_task, 'read', (  # @UndefinedVariable
                    '/tmp/destination.txt', target_ecc_map, 'F12345678', '5', '/tmp/raidtest/master$alice@somehost.com/0'), _read_done)
            else:
                reactor.callLater(0.5, raid_worker.add_task, 'rebuild', (  # @UndefinedVariable
                    'master$alice@somehost.com:0/F12345678', '5', target_ecc_map, [1, ] * num_suppliers, remote_fragments, local_fragments, '/tmp/raidtest'), _rebuild_done)
            return True

        os.system('rm -rf /tmp/source.txt')
        os.system('rm -rf /tmp/destination.txt')
        os.system('rm -rf /tmp/raidtest')
        os.system("mkdir -p '/tmp/raidtest/master$alice@somehost.com/0/F12345678'")
        open('/tmp/source.txt', 'w').write(base64.b64encode(os.urandom(filesize)).decode())
        reactor.callWhenRunning(raid_worker.A, 'init')  # @UndefinedVariable
        reactor.callLater(0.5, raid_worker.add_task, 'make', (  # @UndefinedVariable
            '/tmp/source.txt', target_ecc_map, 'F12345678', '5', '/tmp/raidtest/master$alice@somehost.com/0/F12345678'), _make_done)
        return test_result

    def test_ecc18x18_with_5_dead_suppliers_success(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/18x18',
            num_suppliers=18,
            dead_suppliers=5,  # for 18 suppliers max 5 "correctable" errors are possible, see raid/eccmap.py
            rebuild_one_success=True,
            read_success=True,
            filesize=10000,
        )

    def test_ecc18x18_with_10_dead_suppliers_failed(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/18x18',
            num_suppliers=18,
            dead_suppliers=10,
            rebuild_one_success=True,
            read_success=False,
            filesize=10000,
        )

    def test_ecc18x18_with_14_dead_suppliers_failed(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/18x18',
            num_suppliers=18,
            dead_suppliers=14,
            rebuild_one_success=False,
            read_success=False,
            filesize=10000,
        )

    def test_ecc64x64_with_10_dead_suppliers_success(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/64x64',
            num_suppliers=64,
            dead_suppliers=10,  # for 64 suppliers max 10 "correctable" errors are possible, see raid/eccmap.py
            rebuild_one_success=True,
            read_success=True,
            filesize=10000,
        )

    def test_ecc64x64_with_10_dead_suppliers_success_no_rebuild(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/64x64',
            num_suppliers=64,
            dead_suppliers=10,  # for 64 suppliers max 10 "correctable" errors are possible, see raid/eccmap.py
            rebuild_one_success=True,
            read_success=True,
            filesize=10000,
            skip_rebuild=True,
        )

    def test_task_cancel(self):
        test_result = Deferred()
        os.system('rm -rf /tmp/source.txt')
        os.system('rm -rf /tmp/destination.txt')
        os.system('rm -rf /tmp/raidtest')
        os.system("mkdir -p '/tmp/raidtest/master$alice@somehost.com/0/F12345678'")
        open('/tmp/source1.txt', 'w').write(base64.b64encode(os.urandom(1000000)).decode())
        reactor.callWhenRunning(raid_worker.A, 'init')  # @UndefinedVariable

        def _task_failed(c, t, r):
            self.assertTrue(r == (-1, -1) or r is None)
            os.system('rm -rf /tmp/source1.txt')
            os.system('rm -rf /tmp/raidtest')
            reactor.callLater(0, raid_worker.A, 'shutdown')  # @UndefinedVariable
            reactor.callLater(0.1, test_result.callback, True)  # @UndefinedVariable

        reactor.callLater(0.5, raid_worker.add_task, 'make', (  # @UndefinedVariable
            '/tmp/source1.txt', 'ecc/64x64', 'F12345678', '5', '/tmp/raidtest/master$alice@somehost.com/0/F12345678'), _task_failed)
        reactor.callLater(0.55, raid_worker.cancel_task, 'make', '/tmp/source1.txt')  # @UndefinedVariable

        return test_result



class TestRaidWorkerWithParallelP(_Helper, TestCase):

    child_processes_enabled = True



class TestRaidWorkerWithThreads(_Helper, TestCase):

    child_processes_enabled = False

