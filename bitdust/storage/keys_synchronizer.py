#!/usr/bin/env python
# keys_synchronizer.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (keys_synchronizer.py) is part of BitDust Software.
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
#
#
#
#
"""
.. module:: keys_synchronizer
.. role:: red

BitDust keys_synchronizer() Automat

EVENTS:
    * :red:`backup-ok`
    * :red:`clean-ok`
    * :red:`disconnected`
    * :red:`error`
    * :red:`init`
    * :red:`instant`
    * :red:`restore-ok`
    * :red:`run`
    * :red:`shutdown`
    * :red:`sync`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 20

#------------------------------------------------------------------------------

import sys

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in keys_synchronizer.py')

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred, DeferredList
from twisted.python import failure

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.crypt import my_keys

from bitdust.storage import backup_fs
from bitdust.storage import restore_monitor

from bitdust.main import events

from bitdust.raid import eccmap

from bitdust.access import key_ring

#------------------------------------------------------------------------------

_KeysSynchronizer = None

#------------------------------------------------------------------------------


def is_synchronized():
    if not A():
        return False
    return A().state == 'IN_SYNC!'


#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with `keys_synchronizer()` machine.
    """
    global _KeysSynchronizer
    if event is None:
        return _KeysSynchronizer
    if _KeysSynchronizer is None:
        _KeysSynchronizer = KeysSynchronizer(
            name='keys_synchronizer',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _KeysSynchronizer.automat(event, *args, **kwargs)
    return _KeysSynchronizer


#------------------------------------------------------------------------------


class KeysSynchronizer(automat.Automat):

    """
    This class implements all the functionality of ``keys_synchronizer()`` state machine.
    """

    fast = False

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `keys_synchronizer()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `keys_synchronizer()` state were changed.
        """
        if newstate == 'NO_INFO' and event != 'instant':
            self.automat('instant')

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'NO_INFO'
                self.doInit(*args, **kwargs)
                self.SyncAgain = False
        #---NO_INFO---
        elif self.state == 'NO_INFO':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'run':
                self.state = 'RESTORE'
                self.doPrepare(*args, **kwargs)
                self.doRestoreKeys(*args, **kwargs)
            elif event == 'sync' or (event == 'instant' and self.SyncAgain):
                self.SyncAgain = False
                self.doSaveCallback(*args, **kwargs)
                self.doCheckAndRun(*args, **kwargs)
        #---IN_SYNC!---
        elif self.state == 'IN_SYNC!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnected':
                self.state = 'NO_INFO'
            elif event == 'sync' or (event == 'instant' and self.SyncAgain):
                self.state = 'RESTORE'
                self.SyncAgain = False
                self.doSaveCallback(*args, **kwargs)
                self.doPrepare(*args, **kwargs)
                self.doRestoreKeys(*args, **kwargs)
        #---RESTORE---
        elif self.state == 'RESTORE':
            if event == 'restore-ok':
                self.state = 'BACKUP'
                self.doBackupKeys(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'error' or event == 'disconnected':
                self.state = 'NO_INFO'
                self.doReportNoInfo(*args, **kwargs)
            elif event == 'sync':
                self.doSaveCallback(*args, **kwargs)
                self.SyncAgain = True
        #---BACKUP---
        elif self.state == 'BACKUP':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'backup-ok':
                self.state = 'CLEAN'
                self.doCleanKeys(*args, **kwargs)
            elif event == 'error' or event == 'disconnected':
                self.state = 'NO_INFO'
                self.doReportNoInfo(*args, **kwargs)
            elif event == 'sync':
                self.doSaveCallback(*args, **kwargs)
                self.SyncAgain = True
        #---CLEAN---
        elif self.state == 'CLEAN':
            if event == 'clean-ok':
                self.state = 'IN_SYNC!'
                self.doReportSync(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnected':
                self.state = 'NO_INFO'
                self.doReportNoInfo(*args, **kwargs)
            elif event == 'sync':
                self.doSaveCallback(*args, **kwargs)
                self.SyncAgain = True
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.result_callbacks = []

    def doSaveCallback(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            self.result_callbacks.append(args[0])

    def doCheckAndRun(self, *args, **kwargs):
        """
        Action method.
        """
        from bitdust.customer import list_files_orator
        from bitdust.customer import fire_hire
        from bitdust.storage import backup_monitor
        list_files_orator_is_ready = list_files_orator.A().state == 'SAW_FILES'
        backup_monitor_is_ready = backup_monitor.A().state == 'READY'
        fire_hire_is_ready = fire_hire.A().state == 'READY'
        if list_files_orator_is_ready and backup_monitor_is_ready and fire_hire_is_ready:
            self.automat('run')
        else:
            reactor.callLater(5, self.automat, 'sync')  # @UndefinedVariable

    def doPrepare(self, *args, **kwargs):
        """
        Action method.
        """
        self.restored_count = 0
        self.saved_count = 0
        self.deleted_count = 0
        self.stored_keys = {}
        self.not_stored_keys = {}
        self.unreliable_keys = {}
        self.keys_to_upload = set()
        self.keys_to_erase = {}
        self.keys_to_rename = {}
        lookup = backup_fs.ListChildsByPath(path='.keys', recursive=False, backup_info_callback=restore_monitor.GetBackupStatusInfo)
        minimum_reliable_percent = eccmap.GetCorrectablePercent(eccmap.Current().suppliers_number)
        if _Debug:
            lg.args(_DebugLevel, minimum_reliable_percent=minimum_reliable_percent, lookup=lookup)
        if isinstance(lookup, list):
            for i in lookup:
                if i['path'].endswith('.public'):
                    stored_key_id = i['path'].replace('.public', '').replace('.keys/', '')
                    is_private = False
                else:
                    stored_key_id = i['path'].replace('.private', '').replace('.keys/', '')
                    is_private = True
                if not my_keys.is_valid_key_id(stored_key_id):
                    lg.warn('not able to recognize stored key_id from item: %r' % i)
                    continue
                stored_key_id = my_keys.latest_key_id(stored_key_id)
                is_reliable = False
                for v in i['versions']:
                    try:
                        reliable = float(v['reliable'].replace('%', ''))
                    except:
                        lg.exc()
                        reliable = 0.0
                    if reliable >= minimum_reliable_percent:
                        is_reliable = True
                        break
                if _Debug:
                    lg.args(_DebugLevel, i=i, stored_key_id=stored_key_id, is_reliable=is_reliable)
                if is_reliable:
                    self.stored_keys[stored_key_id] = is_private
                else:
                    if is_private and my_keys.is_key_private(stored_key_id):
                        self.not_stored_keys[stored_key_id] = is_private
                    elif not is_private and my_keys.is_key_registered(stored_key_id):
                        self.not_stored_keys[stored_key_id] = is_private
                    else:
                        self.unreliable_keys[stored_key_id] = is_private
                    if _Debug:
                        lg.args(_DebugLevel, i=i)
        if _Debug:
            lg.args(_DebugLevel, stored_keys=len(self.stored_keys), not_stored_keys=list(self.not_stored_keys.keys()), unreliable_keys=len(self.unreliable_keys))

    def doRestoreKeys(self, *args, **kwargs):
        """
        Action method.
        """
        is_any_private_key_unreliable = bool(True in self.unreliable_keys.values())
        if is_any_private_key_unreliable and not self.stored_keys:
            if _Debug:
                lg.args(_DebugLevel, unreliable_keys=self.unreliable_keys)
            lg.err('not possible to restore any keys, all backup copies unreliable stored_keys=%d not_stored_keys=%d unreliable_keys=%d' % (len(self.stored_keys), len(self.not_stored_keys), len(self.unreliable_keys)))
            self.automat('error', Exception('not possible to restore any keys, all backup copies unreliable'))
            return
        keys_to_be_restored = []
        for key_id, is_private in self.stored_keys.items():
            latest_key_id = my_keys.latest_key_id(key_id)
            if latest_key_id != key_id:
                self.keys_to_rename[key_id] = (
                    latest_key_id,
                    is_private,
                )
            if my_keys.is_key_registered(key_id):
                if _Debug:
                    lg.out(_DebugLevel, '        skip restoring already known key_id=%r' % key_id)
                continue
            if my_keys.is_key_registered(latest_key_id):
                if _Debug:
                    lg.out(_DebugLevel, '        skip restoring already known latest key_id=%r' % latest_key_id)
                continue
            keys_to_be_restored.append((
                key_id,
                is_private,
            ))

        if _Debug:
            lg.args(_DebugLevel, keys_to_be_restored=len(keys_to_be_restored))

        def _on_restored_one(res, pos, key_id):
            self.restored_count += 1
            _do_restore_one(pos + 1)
            return None

        def _on_failed_one(err, pos, key_id):
            lg.err('failed to restore key %r : %r' % (key_id, err))
            _do_restore_one(pos + 1)
            return None

        def _do_restore_one(pos):
            if pos >= len(keys_to_be_restored):
                self.automat('restore-ok', True)
                return
            key_id, is_private = keys_to_be_restored[pos]
            res = key_ring.do_restore_key(key_id, is_private, wait_result=True)
            res.addCallback(_on_restored_one, pos, key_id)
            res.addErrback(_on_failed_one, pos, key_id)

        _do_restore_one(0)

    def doBackupKeys(self, *args, **kwargs):
        """
        Action method.
        """
        for old_key_id in list(self.keys_to_rename.keys()):
            new_key_id, is_private = self.keys_to_rename[old_key_id]
            if old_key_id in self.stored_keys and new_key_id not in self.stored_keys:
                self.keys_to_upload.add(new_key_id)
            if new_key_id in self.stored_keys and old_key_id in self.stored_keys:
                self.keys_to_erase[old_key_id] = is_private
        for key_id in my_keys.known_keys().keys():
            if key_id not in self.stored_keys or key_id in self.not_stored_keys:
                self.keys_to_upload.add(key_id)
        keys_saved = []
        for key_id in self.keys_to_upload:
            res = key_ring.do_backup_key(key_id)
            keys_saved.append(res)
            self.saved_count += 1
        if _Debug:
            lg.args(_DebugLevel, keys_saved=len(keys_saved))
        wait_all_saved = DeferredList(keys_saved, fireOnOneErrback=False, consumeErrors=True)
        wait_all_saved.addCallback(lambda ok: self.automat('backup-ok', ok))
        wait_all_saved.addErrback(lambda err: self.automat('error', err))

    def doCleanKeys(self, *args, **kwargs):
        """
        Action method.
        """
        keys_deleted = []
        for key_id, is_private in self.stored_keys.items():
            if not my_keys.is_key_registered(key_id):
                self.keys_to_erase[key_id] = is_private
        for key_id, is_private in self.keys_to_erase.items():
            res = key_ring.do_delete_key(key_id, is_private)
            keys_deleted.append(res)
            self.deleted_count += 1
        if _Debug:
            lg.args(_DebugLevel, restored=self.restored_count, saved=self.saved_count, deleted=self.deleted_count)
        self.automat('clean-ok')

    def doReportSync(self, *args, **kwargs):
        """
        Action method.
        """
        for cb in self.result_callbacks:
            if isinstance(cb, Deferred):
                cb.callback(True)
            else:
                cb(True)
        self.result_callbacks = []

    def doReportNoInfo(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            err = args[0]
        else:
            err = Exception('failed to synchronize my keys')
        for cb in self.result_callbacks:
            if isinstance(cb, Deferred):
                cb.errback(err)
            else:
                cb(err)
        err_msg = ''
        if isinstance(err, failure.Failure):
            err_msg = err.getErrorMessage()
        else:
            err_msg = str(err)
        events.send('my-keys-synchronize-failed', data=dict(error=err_msg))
        self.result_callbacks = []

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.result_callbacks = []
        self.restored_count = 0
        self.saved_count = 0
        self.deleted_count = 0
        self.stored_keys = None
        self.keys_to_upload = None
        self.keys_to_erase = None
        self.keys_to_rename = None
        self.destroy()
        global _KeysSynchronizer
        del _KeysSynchronizer
        _KeysSynchronizer = None
