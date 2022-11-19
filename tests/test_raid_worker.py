import os
import base64

from twisted.trial.unittest import TestCase
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred
from twisted.internet.base import DelayedCall

DelayedCall.debug = True

from bitdust.raid import raid_worker

from bitdust.logs import lg

from bitdust.system import bpio

from bitdust.main import settings


class TestRaidWorker(TestCase):

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

    def tearDown(self):
        settings.shutdown()
        bpio.rmdir_recursive('/tmp/.bitdust_tmp')

    def _test_make_rebuild_read(self, target_ecc_map, num_suppliers, dead_suppliers, read_success, rebuild_one_success, filesize, try_rebuild=False):
        test_result = Deferred()

        curdir = os.getcwd()
        if curdir.count('_trial_temp'):
            os.chdir(os.path.abspath(os.path.join(curdir, '..')))

        def _read_done(cmd, taskdata, result):
            final_result = False
            source_data = bpio.ReadBinaryFile('/tmp/source.txt')
            reconstructed_data = bpio.ReadBinaryFile('/tmp/destination.txt')
            if read_success:
                final_result = (source_data == reconstructed_data)
            else:
                final_result = (source_data != reconstructed_data)
            os.system('rm -rf /tmp/source.txt')
            os.system('rm -rf /tmp/destination.txt')
            os.system('rm -rf /tmp/raidtest')
            reactor.callLater(0, raid_worker.A, 'shutdown')  # @UndefinedVariable
            if final_result:
                reactor.callLater(0.1, test_result.callback, True)  # @UndefinedVariable
            else:
                if read_success:
                    reactor.callLater(0.1, test_result.errback, Exception('reconstructed data is not the same as source data'))  # @UndefinedVariable
                else:
                    reactor.callLater(  # @UndefinedVariable
                        0.1, test_result.errback, Exception('reconstructed data is the same as source data, but expect to fail the raid read')
                    )
            return True

        def _rebuild_done(cmd, taskdata, result):
            newData = result[0]
            if rebuild_one_success:
                if not newData:
                    os.system('rm -rf /tmp/source.txt')
                    os.system('rm -rf /tmp/raidtest')
                    reactor.callLater(0, raid_worker.A, 'shutdown')  # @UndefinedVariable
                    reactor.callLater(0.1, test_result.errback, Exception('rebuild expected to succeed but new data was not created'))  # @UndefinedVariable
                    return
            else:
                if newData:
                    os.system('rm -rf /tmp/source.txt')
                    os.system('rm -rf /tmp/raidtest')
                    reactor.callLater(0, raid_worker.A, 'shutdown')  # @UndefinedVariable
                    reactor.callLater(0.1, test_result.errback, Exception('rebuild expected to fail but new data was created'))  # @UndefinedVariable
                    return
            # try to read all fragments now
            reactor.callLater(  # @UndefinedVariable
                0.5,
                raid_worker.add_task,
                'read',
                (
                    '/tmp/destination.txt',
                    target_ecc_map,
                    'F12345678',
                    '5',
                    '/tmp/raidtest/master$alice@somehost.com/0',
                ),
                _read_done,
            )
            return True

        def _make_done(cmd, taskdata, result):
            if list(result) != [num_suppliers, num_suppliers]:
                os.system('rm -rf /tmp/source.txt')
                os.system('rm -rf /tmp/raidtest')
                reactor.callLater(0, raid_worker.A, 'shutdown')  # @UndefinedVariable
                reactor.callLater(0.1, test_result.callback, False)  # @UndefinedVariable
                return
            # remove few fragments and try to rebuild the whole block
            for supplier_position in range(dead_suppliers):
                os.system("rm -rf '/tmp/raidtest/master$alice@somehost.com/0/F12345678/5-%d-Data'" % supplier_position)
                os.system("rm -rf '/tmp/raidtest/master$alice@somehost.com/0/F12345678/5-%d-Parity'" % supplier_position)
            alive_suppliers = num_suppliers - dead_suppliers
            remote_fragments = {
                'D': [
                    0,
                ] * dead_suppliers + [
                    1,
                ] * alive_suppliers,
                'P': [
                    0,
                ] * dead_suppliers + [
                    1,
                ] * alive_suppliers,
            }
            local_fragments = {
                'D': [
                    0,
                ] * dead_suppliers + [
                    1,
                ] * alive_suppliers,
                'P': [
                    0,
                ] * dead_suppliers + [
                    1,
                ] * alive_suppliers,
            }
            if not try_rebuild:
                reactor.callLater(  # @UndefinedVariable
                    0.5,
                    raid_worker.add_task,
                    'read',
                    (
                        '/tmp/destination.txt',
                        target_ecc_map,
                        'F12345678',
                        '5',
                        '/tmp/raidtest/master$alice@somehost.com/0',
                    ),
                    _read_done,
                )
            else:
                reactor.callLater(  # @UndefinedVariable
                    0.5,
                    raid_worker.add_task,
                    'rebuild',
                    (
                        'master$alice@somehost.com:0/F12345678',
                        '5',
                        target_ecc_map,
                        [
                            1,
                        ] * num_suppliers,
                        remote_fragments,
                        local_fragments,
                        '/tmp/raidtest',
                    ),
                    _rebuild_done,
                )
            return True

        os.system('rm -rf /tmp/source.txt')
        os.system('rm -rf /tmp/destination.txt')
        os.system('rm -rf /tmp/raidtest')
        os.system("mkdir -p '/tmp/raidtest/master$alice@somehost.com/0/F12345678'")
        bpio.WriteBinaryFile('/tmp/source.txt', base64.b64encode(os.urandom(filesize)))
        reactor.callWhenRunning(raid_worker.A, 'init')  # @UndefinedVariable
        reactor.callLater(  # @UndefinedVariable
            0.5,
            raid_worker.add_task,
            'make',
            (
                '/tmp/source.txt',
                target_ecc_map,
                'F12345678',
                '5',
                '/tmp/raidtest/master$alice@somehost.com/0/F12345678',
            ),
            _make_done,
        )
        return test_result

    def test_ecc2x2_with_0_dead_suppliers_success(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/2x2',
            num_suppliers=2,
            dead_suppliers=0,
            rebuild_one_success=False,
            read_success=True,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc2x2_with_1_dead_supplier_success_no_rebuild(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/2x2',
            num_suppliers=2,
            dead_suppliers=1,
            rebuild_one_success=True,
            read_success=True,
            filesize=50,
            try_rebuild=False,
        )

    def test_ecc2x2_with_1_dead_supplier_success(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/2x2',
            num_suppliers=2,
            dead_suppliers=1,
            rebuild_one_success=True,
            read_success=True,
            filesize=50,
            try_rebuild=False,
        )

    def test_ecc2x2_with_2_dead_suppliers_failed(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/2x2',
            num_suppliers=2,
            dead_suppliers=2,
            rebuild_one_success=False,
            read_success=False,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc4x4_with_2_dead_suppliers_success(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/4x4',
            num_suppliers=4,
            dead_suppliers=2,
            rebuild_one_success=True,
            read_success=True,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc4x4_with_3_dead_suppliers_failed(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/4x4',
            num_suppliers=4,
            dead_suppliers=3,
            rebuild_one_success=False,
            read_success=False,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc4x4_with_2_dead_suppliers_success_no_rebuild(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/4x4',
            num_suppliers=4,
            dead_suppliers=2,
            rebuild_one_success=True,
            read_success=True,
            filesize=50,
            try_rebuild=False,
        )

    def test_ecc7x7_with_4_dead_suppliers_failed(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/7x7',
            num_suppliers=7,
            dead_suppliers=4,
            rebuild_one_success=False,
            read_success=False,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc18x18_with_5_dead_suppliers_success(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/18x18',
            num_suppliers=18,
            dead_suppliers=5,
            rebuild_one_success=True,
            read_success=True,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc18x18_with_10_dead_suppliers_failed(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/18x18',
            num_suppliers=18,
            dead_suppliers=10,  # TODO: strange, for 18 suppliers max 5 "correctable" errors are possible, see raid/eccmap.py
            rebuild_one_success=True,
            read_success=False,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc18x18_with_14_dead_suppliers_failed(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/18x18',
            num_suppliers=18,
            dead_suppliers=14,
            rebuild_one_success=False,
            read_success=False,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc64x64_with_10_dead_suppliers_success(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/64x64',
            num_suppliers=64,
            dead_suppliers=10,
            rebuild_one_success=True,
            read_success=True,
            filesize=50,
            try_rebuild=True,
        )

    def test_ecc64x64_with_10_dead_suppliers_success_no_rebuild(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/64x64',
            num_suppliers=64,
            dead_suppliers=10,
            rebuild_one_success=True,
            read_success=True,
            filesize=50,
            try_rebuild=False,
        )

    def test_ecc64x64_with_23_dead_suppliers_failed(self):
        return self._test_make_rebuild_read(
            target_ecc_map='ecc/64x64',
            num_suppliers=64,
            dead_suppliers=23,  # TODO: strange, for 64 suppliers max 10 "correctable" errors are possible, see raid/eccmap.py
            rebuild_one_success=True,
            read_success=False,
            filesize=50,
            try_rebuild=True,
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
            final_result = (r == (-1, -1) or r is None)
            os.system('rm -rf /tmp/source1.txt')
            os.system('rm -rf /tmp/raidtest')
            reactor.callLater(0, raid_worker.A, 'shutdown')  # @UndefinedVariable
            if final_result:
                reactor.callLater(0.1, test_result.callback, True)  # @UndefinedVariable
            else:
                reactor.callLater(0.1, test_result.errback, Exception('task expected to fail, but positive result was returned'))  # @UndefinedVariable

        reactor.callLater(  # @UndefinedVariable
            0.5,
            raid_worker.add_task,
            'make',
            (
                '/tmp/source1.txt',
                'ecc/64x64',
                'F12345678',
                '5',
                '/tmp/raidtest/master$alice@somehost.com/0/F12345678',
            ),
            _task_failed,
        )
        reactor.callLater(0.55, raid_worker.cancel_task, 'make', '/tmp/source1.txt')  # @UndefinedVariable

        return test_result
