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
    * :red:`ack`
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`extract-failed`
    * :red:`extract-success`
    * :red:`fail`
    * :red:`list-files-collected`
    * :red:`list-files-failed`
    * :red:`restore-done`
    * :red:`restore-failed`
    * :red:`start`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import utime
from lib import packetid

from main import events
from main import config
from main import settings

from system import tmpfile
from system import bpio

from crypt import my_keys

from dht import dht_relations

from contacts import contactsdb

from stream import message

from raid import eccmap

from p2p import commands
from p2p import p2p_service
from p2p import lookup
from p2p import p2p_service_seeker

from access import groups

from storage import restore_worker
from storage import backup_fs
from storage import backup_matrix
from storage import backup_tar

from userid import global_id
from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

class ArchiveReader(automat.Automat):
    """
    This class implements all the functionality of ``archive_reader()`` state machine.
    """

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `archive_reader()` state machine.
        """
        super(ArchiveReader, self).__init__(
            name="archive_reader",
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

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
            elif event == 'ack' or event == 'fail':
                self.doCollectFiles(event, *args, **kwargs)
        #---RESTORE---
        elif self.state == 'RESTORE':
            if event == 'restore-done':
                self.state = 'EXTRACT'
                self.doExtractArchive(*args, **kwargs)
            elif event == 'restore-failed':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---EXTRACT---
        elif self.state == 'EXTRACT':
            if event == 'extract-success':
                self.state = 'DONE'
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'extract-failed':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
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
        qa, oid, _ = global_id.SplitGlobalQueueID(self.queue_id)
        self.queue_alias = qa
        self.queue_owner_id = oid
        self.queue_owner_idurl = global_id.glob2idurl(self.queue_owner_id)
        self.group_key_id = my_keys.make_key_id(alias=self.queue_alias, creator_glob_id=self.queue_owner_id)
        self.suppliers_list = []
        self.ecc_map = None
        self.correctable_errors = 0
        self.requested_list_files = {}

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
        self._do_request_list_files(contactsdb.num_suppliers())

    def doStartRestoreWorker(self, *args, **kwargs):
        """
        Action method.
        """
        iterID_and_path = backup_fs.WalkByID(self.archive_folder_path, iterID=backup_fs.fsID(self.queue_owner_idurl))
        if iterID_and_path is None:
            lg.err('did not found archive folder in the catalog: %r' % self.archive_folder_path)
            self.automat('restore-failed')
            return
        iterID, path = iterID_and_path
        known_archive_snapshots_list = backup_fs.ListAllBackupIDsFull(iterID=iterID)
        if not known_archive_snapshots_list:
            lg.err('failed to restore data from archive, no snapshots found in folder: %r' % self.archive_folder_path)
            self.automat('restore-failed')
            return
        snapshots_list = []
        for archive_item in known_archive_snapshots_list:
            snapshots_list.append(archive_item[1])
        if _Debug:
            lg.args(_DebugLevel, snapshots_list=snapshots_list)
        if not snapshots_list:
            lg.err('no available snapshots found in archive list: %r' % known_archive_snapshots_list)
            self.automat('restore-failed')
            return
        backupID = snapshots_list[0]
        outfd, outfilename = tmpfile.make(
            'restore',
            extension='.tar.gz',
            prefix=backupID.replace('@', '_').replace('.', '_').replace('/', '_').replace(':', '_') + '_',
        )
        rw = restore_worker.RestoreWorker(backupID, outfd, KeyID=self.group_key_id)
        rw.MyDeferred.addCallback(self._on_restore_done, backupID, outfd, outfilename)
        rw.MyDeferred.addErrback(self._on_restore_failed, backupID, outfd, outfilename)
        if _Debug:
            rw.MyDeferred.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='archive_reader.doStartRestoreWorker')
        rw.automat('init')

    def doCollectFiles(self, event, *args, **kwargs):
        """
        Action method.
        """

    def doExtractArchive(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
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
                query_items=[self.queue_alias, ],
                callbacks={
                #     commands.Files(): self._on_list_files_response,
                    commands.Fail(): lambda resp, info: self._on_list_files_failed(supplier_pos),
                    None: lambda pkt_out: self._on_list_files_failed(supplier_pos),
                },
                timeout=15,
            )
            self.requested_list_files[supplier_pos] = None if outpacket else False

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
        self.requested_list_files[supplier_num] = True
        lst = list(self.requested_list_files.values())
        if _Debug:
            lg.args(_DebugLevel, requested_list_files=lst, supplier_num=supplier_num, new_files_count=new_files_count)
        # packets_pending_or_failed = lst.count(None) + lst.count(False)
        # if packets_pending_or_failed < self.correctable_errors * 2:  # because each packet also have Parity()
        if lst.count(None) == 0:
            backup_matrix.remove_list_files_query_callback(
                customer_idurl=self.queue_owner_idurl,
                query_path=self.queue_alias,
            )
            self.automat('list-files-collected')
        return None

    def _on_list_files_failed(self, supplier_num):
        self.requested_list_files[supplier_num] = False
        lst = list(self.requested_list_files.values())
        if _Debug:
            lg.args(_DebugLevel, requested_list_files=lst, supplier_num=supplier_num)
        if lst.count(None) == 0:
            backup_matrix.remove_list_files_query_callback(
                customer_idurl=self.queue_owner_idurl,
                query_path=self.queue_alias,
            )
            self.automat('list-files-failed')
        return None

    def _on_restore_done(self, result, backupID, outfd, tarfilename):
        try:
            os.close(outfd)
        except:
            lg.exc()
        if result == 'done':
            lg.info('archive %r restore success from %r' % (backupID, tarfilename, ))
        else:
            lg.err('archive %r restore failed from %r with : %r' % (backupID, tarfilename, result, ))
        if result == 'done':
            _, pathID, versionName = packetid.SplitBackupID(backupID)
            service_dir = settings.ServiceDir('service_private_groups')
            queues_dir = os.path.join(service_dir, 'queues')
            queue_dir = os.path.join(queues_dir, self.group_key_id)
            snapshot_dir = os.path.join(queue_dir, pathID, versionName)
            if not os.path.isdir(snapshot_dir):
                bpio._dirs_make(snapshot_dir)
            d = backup_tar.extracttar_thread(tarfilename, snapshot_dir)
            d.addCallback(self._on_extract_done, backupID, tarfilename, snapshot_dir)
            d.addErrback(self._on_extract_failed, backupID, tarfilename, snapshot_dir)
            return d
        tmpfile.throw_out(tarfilename, 'restore ' + result)
        return None

    def _on_restore_failed(self, err, backupID, outfd, tarfilename):
        lg.err('archive %r restore failed with : %r' % (backupID, err, ))
        self.automat('restore-failed')

    def _on_extract_done(self, retcode, backupID, source_filename, output_location):
        lg.info('archive %r snapshot from %r extracted successfully to %r : %r' % (backupID, source_filename, output_location, retcode, ))
        tmpfile.throw_out(source_filename, 'file extracted')
        return retcode

    def _on_extract_failed(self, err, backupID, source_filename, output_location):
        lg.err('archive %r extract failed from %r to %r with: %r' % (backupID, source_filename, output_location, err))
        tmpfile.throw_out(source_filename, 'file extract failed')
        return err
