import os
import base64

from twisted.trial.unittest import TestCase
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred
from twisted.internet.base import DelayedCall
DelayedCall.debug = True


class TestRaidWorker(TestCase):

    def _test_make_rebuild_read(self, target_ecc_map, num_suppliers, dead_suppliers, read_success, rebuild_one_success, filesize):
        test_result = Deferred()

        curdir = os.getcwd()
        if curdir.count('_trial_temp'):
            os.chdir(os.path.abspath(os.path.join(curdir, '..')))

        from raid import raid_worker

        from logs import lg
        lg.set_debug_level(20)

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
            self.assertEqual(result, [num_suppliers, num_suppliers])
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
