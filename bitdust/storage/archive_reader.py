#!/usr/bin/env python
# archive_reader.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
#
# This file (archive_reader.py) is part of BitDust Software.
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
"""
.. module:: archive_reader
.. role:: red

BitDust archive_reader() Automat

EVENTS:
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`extract-all-done`
    * :red:`extract-failed`
    * :red:`list-files-collected`
    * :red:`list-files-failed`
    * :red:`restore-done`
    * :red:`restore-failed`
    * :red:`start`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import packetid
from bitdust.lib import serialization

from bitdust.system import tmpfile
from bitdust.system import local_fs

from bitdust.crypt import my_keys

from bitdust.dht import dht_relations

from bitdust.contacts import contactsdb

from bitdust.raid import eccmap

from bitdust.p2p import commands
from bitdust.p2p import p2p_service

from bitdust.access import groups

from bitdust.storage import restore_worker
from bitdust.storage import backup_fs
from bitdust.storage import backup_matrix
from bitdust.storage import backup_tar

from bitdust.userid import global_id
from bitdust.userid import my_id

#------------------------------------------------------------------------------


class ArchiveReader(automat.Automat):
    """
    This class implements all the functionality of ``archive_reader()`` state machine.
    """
    def __init__(self, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `archive_reader()` state machine.
        """
        super(ArchiveReader, self).__init__(name='archive_reader', state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' and not self.isMyOwnArchive(*args, **kwargs):
                self.state = 'DHT_READ?'
                self.doInit(*args, **kwargs)
                self.doDHTReadSuppliers(*args, **kwargs)
            elif event == 'start' and self.isMyOwnArchive(*args, **kwargs):
                self.state = 'LIST_FILES?'
                self.doInit(*args, **kwargs)
                self.doRequestMyListFiles(*args, **kwargs)
        #---DHT_READ?---
        elif self.state == 'DHT_READ?':
            if event == 'dht-read-success':
                self.state = 'LIST_FILES?'
                self.doRequestTheirListFiles(*args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---LIST_FILES?---
        elif self.state == 'LIST_FILES?':
            if event == 'list-files-collected':
                self.state = 'RESTORE'
                self.doStartRestoreWorker(*args, **kwargs)
            elif event == 'list-files-failed':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---RESTORE---
        elif self.state == 'RESTORE':
            if event == 'extract-all-done':
                self.state = 'DONE'
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'restore-failed' or event == 'extract-failed':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'restore-done':
                self.doExtractArchive(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def isMyOwnArchive(self, *args, **kwargs):
        """
        Condition method.
        """
        _, queue_owner_id, _ = global_id.SplitGlobalQueueID(kwargs['queue_id'])
        return my_id.getID() == queue_owner_id

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.queue_id = kwargs['queue_id']
        self.start_sequence_id = kwargs['start_sequence_id']
        self.end_sequence_id = kwargs['end_sequence_id']
        self.archive_folder_path = kwargs['archive_folder_path']
        self.result_defer = kwargs.get('result_defer')
        qa, oid, _ = global_id.SplitGlobalQueueID(self.queue_id)
        self.queue_alias = qa
        self.queue_owner_id = oid
        self.queue_owner_idurl = global_id.glob2idurl(self.queue_owner_id)
        self.group_key_id = my_keys.make_key_id(alias=self.queue_alias, creator_glob_id=self.queue_owner_id)
        self.suppliers_list = []
        self.selected_backups = []
        self.ecc_map = None
        self.correctable_errors = 0
        self.requested_list_files = {}
        self.extracted_messages = []
        self.request_list_files_timer = None

    def doDHTReadSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_relations.read_customer_suppliers(customer_idurl=self.queue_owner_idurl, use_cache=True)
        d.addCallback(self._on_read_queue_owner_suppliers_success)
        d.addErrback(self._on_read_queue_owner_suppliers_failed)

    def doRequestTheirListFiles(self, *args, **kwargs):
        """
        Action method.
        """
        groups.create_archive_folder(self.group_key_id, force_path_id=self.archive_folder_path)
        self._do_request_list_files(self.suppliers_list)

    def doRequestMyListFiles(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_request_list_files(contactsdb.suppliers())

    def doStartRestoreWorker(self, *args, **kwargs):
        """
        Action method.
        """
        if self._do_select_archive_snapshots():
            self._do_restore_next_backup(0)

    def doExtractArchive(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_extract_archive(backup_id=kwargs['backup_id'], tarfilename=kwargs['tarfilename'], backup_index=kwargs['backup_index'])

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """
        if self.result_defer:
            self.result_defer.callback(args[0])

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        err = None
        if event == 'dht-read-failed':
            err = Exception('failed reading DHT records for customer family')
        elif event == 'list-files-failed':
            err = Exception('list files request failed')
        elif event == 'restore-failed':
            err = Exception('archive snapshot restore task failed')
        elif event == 'extract-failed':
            err = Exception('archive snapshot extract failed')
        if self.result_defer:
            self.result_defer.errback(err)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.queue_id = None
        self.start_sequence_id = None
        self.end_sequence_id = None
        self.archive_folder_path = None
        self.result_defer = None
        self.queue_alias = None
        self.queue_owner_id = None
        self.queue_owner_idurl = None
        self.group_key_id = None
        self.suppliers_list = None
        self.selected_backups = None
        self.ecc_map = None
        self.correctable_errors = 0
        self.requested_list_files = None
        self.extracted_messages = None
        self.request_list_files_timer = None
        self.destroy()

    def _do_request_list_files(self, suppliers_list):
        backup_matrix.add_list_files_query_callback(
            customer_idurl=self.queue_owner_idurl,
            query_path=self.queue_alias,
            callback_method=self._on_list_files_response,
        )
        self.correctable_errors = eccmap.GetCorrectableErrors(len(suppliers_list))
        for supplier_pos, supplier_idurl in enumerate(suppliers_list):
            if not supplier_idurl:
                self.requested_list_files[supplier_pos] = False
                continue
            outpacket = p2p_service.SendListFiles(
                target_supplier=supplier_idurl,
                key_id=self.group_key_id,
                query_items=[self.queue_alias],
                callbacks={
                    commands.Fail(): lambda resp, info: self._on_list_files_failed(supplier_pos),
                    None: lambda pkt_out: self._on_list_files_failed(supplier_pos),
                },
            )
            self.requested_list_files[supplier_pos] = None if outpacket else False
        if _Debug:
            lg.args(_DebugLevel, queue_alias=self.queue_alias, requested=self.requested_list_files)
        self.request_list_files_timer = reactor.callLater(30, self._on_request_list_files_timeout)  # @UndefinedVariable

    def _do_select_archive_snapshots(self):
        iterID_and_path = backup_fs.WalkByID(self.archive_folder_path, iterID=backup_fs.fsID(self.queue_owner_idurl, self.queue_alias))
        if iterID_and_path is None:
            lg.err('did not found archive folder in the catalog: %r' % self.archive_folder_path)
            self.automat('restore-failed')
            return False
        iterID, _ = iterID_and_path
        known_archive_snapshots_list = backup_fs.ListAllBackupIDsFull(iterID=iterID)
        if not known_archive_snapshots_list:
            lg.err('failed to restore data from archive, no snapshots found in folder: %r' % self.archive_folder_path)
            self.automat('restore-failed')
            return False
        snapshots_list = []
        for archive_item in known_archive_snapshots_list:
            snapshots_list.append(archive_item[1])
        if _Debug:
            lg.args(_DebugLevel, snapshots_list=snapshots_list)
        if not snapshots_list:
            lg.err('no available snapshots found in archive list: %r' % known_archive_snapshots_list)
            self.automat('restore-failed')
            return False
        snapshot_sequence_ids = []
        for backup_id in snapshots_list:
            _, path_id, _ = packetid.SplitBackupID(backup_id)
            if not path_id:
                continue
            try:
                snapshot_sequence_id = int(path_id.split('/')[-1])
            except:
                lg.exc()
                continue
            if self.start_sequence_id is not None and self.start_sequence_id > snapshot_sequence_id:
                continue
            if self.end_sequence_id is not None and self.end_sequence_id < snapshot_sequence_id:
                continue
            snapshot_sequence_ids.append((
                snapshot_sequence_id,
                backup_id,
            ))
        snapshot_sequence_ids.sort(key=lambda item: int(item[0]))
        if _Debug:
            lg.args(_DebugLevel, snapshot_sequence_ids=snapshot_sequence_ids)
        self.selected_backups = [item[1] for item in snapshot_sequence_ids]
        if not self.selected_backups:
            lg.err('no backups selected from snapshot list')
            self.automat('restore-failed')
            return False
        if _Debug:
            lg.args(_DebugLevel, selected_backups=self.selected_backups)
        return True

    def _do_restore_next_backup(self, backup_index):
        if _Debug:
            lg.args(_DebugLevel, backup_index=backup_index, selected_backups=len(self.selected_backups))
        if backup_index >= len(self.selected_backups):
            lg.info('all selected backups are processed')
            self.automat('extract-all-done', self.extracted_messages)
            return
        backup_id = self.selected_backups[backup_index]
        alias = backup_id.split('$')[0]
        outfd, outfilename = tmpfile.make(
            'restore',
            extension='.tar.gz',
            prefix=alias + '_',
        )
        rw = restore_worker.RestoreWorker(backup_id, outfd, KeyID=self.group_key_id)
        rw.MyDeferred.addCallback(self._on_restore_done, backup_id, outfd, outfilename, backup_index)
        rw.MyDeferred.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='archive_reader.doStartRestoreWorker')
        rw.MyDeferred.addErrback(self._on_restore_failed, backup_id, outfd, outfilename, backup_index)
        rw.automat('init')

    def _do_extract_archive(self, backup_id, tarfilename, backup_index):
        snapshot_dir = tmpfile.make_dir('restore', extension='.msg')
        d = backup_tar.extracttar_thread(tarfilename, snapshot_dir)
        d.addCallback(self._on_extract_done, backup_id, tarfilename, snapshot_dir, backup_index)
        d.addErrback(self._on_extract_failed, backup_id, tarfilename, snapshot_dir)
        return d

    def _on_read_queue_owner_suppliers_success(self, dht_value):
        # TODO: add more validations of dht_value
        if dht_value and isinstance(dht_value, dict) and len(dht_value.get('suppliers', [])) > 0:
            self.suppliers_list = dht_value['suppliers']
            self.ecc_map = dht_value['ecc_map']
            self.correctable_errors = eccmap.GetCorrectableErrors(len(self.suppliers_list))
        if _Debug:
            lg.args(_DebugLevel, suppliers_list=self.suppliers_list, ecc_map=self.ecc_map)
        if not self.suppliers_list or not self.ecc_map:
            self.automat('dht-read-failed', None)
            return None
        self.automat('dht-read-success')
        return None

    def _on_read_queue_owner_suppliers_failed(self, err):
        lg.err('failed to read customer suppliers: %r' % err)
        self.automat('dht-read-failed', err)
        return None

    def _on_list_files_response(self, supplier_num, new_files_count):
        if not self.requested_list_files:
            lg.warn('skip ListFiles() response, requested_list_files object is empty')
            return
        if self.requested_list_files.get(supplier_num) is not None:
            lg.warn('skip ListFiles() response, supplier record at position %d already set to %r' % (supplier_num, self.requested_list_files.get(supplier_num)))
            return
        self.requested_list_files[supplier_num] = True
        lst = list(self.requested_list_files.values())
        if _Debug:
            lg.args(_DebugLevel, requested_list_files=lst, supplier_num=supplier_num, new_files_count=new_files_count)
        if lst.count(None) == 0:
            if self.request_list_files_timer and self.request_list_files_timer.active():
                self.request_list_files_timer.cancel()
                self.request_list_files_timer = None
            backup_matrix.remove_list_files_query_callback(
                customer_idurl=self.queue_owner_idurl,
                query_path=self.queue_alias,
                callback_method=self._on_list_files_response,
            )
            success_list_files = lst.count(True)
            if success_list_files:
                self.automat('list-files-collected')
            else:
                self.automat('list-files-failed')
        return None

    def _on_list_files_failed(self, supplier_num):
        if not self.requested_list_files:
            lg.warn('skip ListFiles() response, requested_list_files object is empty')
            return
        if self.requested_list_files.get(supplier_num) is not None:
            lg.warn('skip ListFiles() response, supplier record at position %d already set to %r' % (supplier_num, self.requested_list_files.get(supplier_num)))
            return
        self.requested_list_files[supplier_num] = False
        lst = list(self.requested_list_files.values())
        if _Debug:
            lg.args(_DebugLevel, requested_list_files=lst, supplier_num=supplier_num)
        if lst.count(None) == 0:
            if self.request_list_files_timer and self.request_list_files_timer.active():
                self.request_list_files_timer.cancel()
                self.request_list_files_timer = None
            backup_matrix.remove_list_files_query_callback(
                customer_idurl=self.queue_owner_idurl,
                query_path=self.queue_alias,
                callback_method=self._on_list_files_response,
            )
            success_list_files = lst.count(True)
            if success_list_files:
                self.automat('list-files-collected')
            else:
                self.automat('list-files-failed')
        return None

    def _on_request_list_files_timeout(self):
        self.request_list_files_timer = None
        for supplier_num in self.requested_list_files:
            if self.requested_list_files[supplier_num] is None:
                self.requested_list_files[supplier_num] = False
        lst = list(self.requested_list_files.values())
        if _Debug:
            lg.args(_DebugLevel, requested_list_files=lst)
        backup_matrix.remove_list_files_query_callback(
            customer_idurl=self.queue_owner_idurl,
            query_path=self.queue_alias,
            callback_method=self._on_list_files_response,
        )
        success_list_files = lst.count(True)
        if success_list_files:
            self.automat('list-files-collected')
        else:
            self.automat('list-files-failed')

    def _on_restore_done(self, result, backup_id, outfd, tarfilename, backup_index):
        try:
            os.close(outfd)
        except:
            lg.exc()
        if result == 'done':
            lg.info('archive %r restore success from %r' % (backup_id, tarfilename))
        else:
            lg.err('archive %r restore failed from %r with : %r' % (backup_id, tarfilename, result))
        if result != 'done':
            tmpfile.throw_out(tarfilename, 'restore ' + result)
            self.automat('restore-failed', backup_id=backup_id, tarfilename=tarfilename)
            return None
        self.automat('restore-done', backup_id=backup_id, tarfilename=tarfilename, backup_index=backup_index)
        return

    def _on_restore_failed(self, err, backupID, outfd, tarfilename, backup_index):
        lg.err('archive %r restore failed with : %r' % (backupID, err))
        try:
            os.close(outfd)
        except:
            lg.exc()
        self.automat('restore-failed')
        return None

    def _on_extract_failed(self, err, backupID, source_filename, output_location):
        lg.err('archive %r extract failed from %r to %r with: %r' % (backupID, source_filename, output_location, err))
        tmpfile.throw_out(source_filename, 'file extract failed')
        self.automat('extract-failed', err)
        return None

    def _on_extract_done(self, retcode, backupID, source_filename, output_location, backup_index):
        tmpfile.throw_out(source_filename, 'file extracted')
        for snapshot_filename in os.listdir(output_location):
            snapshot_path = os.path.join(output_location, snapshot_filename)
            snapshot_data = serialization.BytesToDict(local_fs.ReadBinaryFile(snapshot_path), values_to_text=True)
            for archive_message in snapshot_data.get('items', []):
                if self.start_sequence_id is not None:
                    if self.start_sequence_id > archive_message['sequence_id']:
                        continue
                if self.end_sequence_id is not None:
                    if self.end_sequence_id < archive_message['sequence_id']:
                        continue
                self.extracted_messages.append(archive_message)
        if _Debug:
            lg.dbg(_DebugLevel, 'archive snapshot %r extracted successfully to %r, extracted %d archive messages so far' % (source_filename, output_location, len(self.extracted_messages)))
        self._do_restore_next_backup(backup_index + 1)
        return retcode
