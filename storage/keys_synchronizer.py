#!/usr/bin/env python
# keys_synchronizer.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
    * :red:`shutdown`
    * :red:`sync`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred, DeferredList

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from crypt import my_keys

from storage import backup_fs

from access import key_ring

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
    if _KeysSynchronizer is None and event != 'shutdown':
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

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `keys_synchronizer()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `keys_synchronizer()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `keys_synchronizer()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'NO_INFO'
                self.doInit(*args, **kwargs)
                self.SyncAgain=False
        #---IN_SYNC!---
        elif self.state == 'IN_SYNC!':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnected':
                self.state = 'NO_INFO'
            elif event == 'sync' or ( event == 'instant' and self.SyncAgain ):
                self.state = 'RESTORE'
                self.SyncAgain=False
                self.doSaveCallback(*args, **kwargs)
                self.doPrepare(*args, **kwargs)
                self.doRestoreKeys(*args, **kwargs)
        #---NO_INFO---
        elif self.state == 'NO_INFO':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'sync' or ( event == 'instant' and self.SyncAgain ):
                self.state = 'RESTORE'
                self.SyncAgain=False
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
                self.SyncAgain=True
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
                self.SyncAgain=True
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
                self.SyncAgain=True
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

    def doPrepare(self, *args, **kwargs):
        """
        Action method.
        """
        self.restored_count = 0
        self.saved_count = 0
        self.deleted_count = 0
        self.stored_keys = {}
        self.keys_to_download = []
        self.keys_to_upload = set()
        self.keys_to_erase = {}
        self.keys_to_rename = {}
        lookup = backup_fs.ListChildsByPath(path='.keys', recursive=False, )
        for i in lookup:
            if i['path'].endswith('.public'):
                stored_key_id = i['path'].replace('.public', '').replace('.keys/', '')
                is_private = False
            else:
                stored_key_id = i['path'].replace('.private', '').replace('.keys/', '')
                is_private = True
            self.stored_keys[stored_key_id] = is_private
        if _Debug:
            lg.args(_DebugLevel, stored_keys=len(self.stored_keys))

    def doRestoreKeys(self, *args, **kwargs):
        """
        Action method.
        """
        for key_id, is_private in self.stored_keys.items():
            latest_key_id = my_keys.latest_key_id(key_id)
            if latest_key_id != key_id:
                self.keys_to_rename[key_id] = (latest_key_id, is_private, )
            if my_keys.is_key_registered(key_id):
                if _Debug:
                    lg.out(_DebugLevel, '        skip restoring already known key_id=%r' % key_id)
                continue
            if my_keys.is_key_registered(latest_key_id):
                if _Debug:
                    lg.out(_DebugLevel, '        skip restoring already known latest key_id=%r' % latest_key_id)
                continue
            res = key_ring.do_restore_key(key_id, is_private, wait_result=True)
            self.restored_count += 1
            self.keys_to_download.append(res)
        if _Debug:
            lg.args(_DebugLevel, keys_to_download=len(self.keys_to_download))
        wait_all_restored = DeferredList(self.keys_to_download, fireOnOneErrback=False, consumeErrors=True)
        wait_all_restored.addCallback(lambda ok: self.automat('restore-ok', ok))
        wait_all_restored.addErrback(lambda err: self.automat('error', err))

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
            if key_id not in self.stored_keys:
                self.keys_to_upload.add(key_id)
        keys_saved = []
        for key_id in self.keys_to_upload:
            res = key_ring.do_backup_key(key_id, wait_result=True)
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
            latest_key_id = my_keys.latest_key_id(key_id)
            if key_id not in my_keys.known_keys() and latest_key_id not in my_keys.known_keys():
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
        if args:
            err = args[0]
        else:
            err = Exception('failed to synchronize my keys')
        for cb in self.result_callbacks:
            if isinstance(cb, Deferred):
                cb.errback(err)
            else:
                cb(err)
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
        self.keys_to_download = None
        self.keys_to_upload = None
        self.keys_to_erase = None
        self.keys_to_rename = None
        self.destroy()
        global _KeysSynchronizer
        del _KeysSynchronizer
        _KeysSynchronizer = None

