#!/usr/bin/env python
# archive_writer.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
#
# This file (archive_writer.py) is part of BitDust Software.
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
.. module:: archive_writer
.. role:: red

BitDust archive_writer() Automat

EVENTS:
    * :red:`ack`
    * :red:`backup-done`
    * :red:`backup-failed`
    * :red:`block-ready`
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`fail`
    * :red:`packets-delivered`
    * :red:`sending-failed`
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

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.system import bpio

from bitdust.lib import packetid
from bitdust.lib import misc

from bitdust.main import settings

from bitdust.crypt import my_keys

from bitdust.dht import dht_relations

from bitdust.p2p import commands
from bitdust.p2p import p2p_service

from bitdust.raid import eccmap

from bitdust.storage import backup_fs
from bitdust.storage import backup_tar
from bitdust.storage import backup

from bitdust.userid import global_id
from bitdust.userid import my_id

#------------------------------------------------------------------------------


class ArchiveWriter(automat.Automat):
    """
    This class implements all the functionality of ``archive_writer()`` state machine.
    """
    def __init__(self, local_data_callback, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `archive_writer()` state machine.
        """
        self.local_data_callback = local_data_callback
        super(ArchiveWriter, self).__init__(name='archive_writer', state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'DHT_READ?'
                self.doInit(*args, **kwargs)
                self.doDHTReadSuppliers(*args, **kwargs)
        #---DHT_READ?---
        elif self.state == 'DHT_READ?':
            if event == 'dht-read-success':
                self.state = 'BACKUP'
                self.doStartArchiveBackup(*args, **kwargs)
            elif event == 'dht-read-failed':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---BACKUP---
        elif self.state == 'BACKUP':
            if event == 'backup-done':
                self.state = 'SENDING'
                self.doCheckFinished(*args, **kwargs)
            elif event == 'block-ready':
                self.doPushPackets(*args, **kwargs)
            elif event == 'ack' or event == 'fail':
                self.doPullPacket(event, *args, **kwargs)
            elif event == 'backup-failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---SENDING---
        elif self.state == 'SENDING':
            if event == 'packets-delivered':
                self.state = 'DONE'
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack' or event == 'fail':
                self.doPullPacket(event, *args, **kwargs)
                self.doCheckFinished(*args, **kwargs)
            elif event == 'sending-failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.queue_id = kwargs['queue_id']
        self.archive_info = kwargs['archive_info']
        self.archive_folder_path = kwargs['archive_folder_path']
        self.result_defer = kwargs.get('result_defer')
        qa, oid, _ = global_id.SplitGlobalQueueID(self.queue_id)
        self.queue_alias = qa
        self.queue_owner_id = oid
        self.queue_owner_idurl = global_id.glob2idurl(self.queue_owner_id)
        self.group_key_id = my_keys.make_key_id(alias=self.queue_alias, creator_glob_id=self.queue_owner_id)
        self.backup_job = None
        self.backup_max_block_num = None
        self.suppliers_list = []
        self.ecc_map = None
        self.correctable_errors = 0
        self.packets_out = {}

    def doDHTReadSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_relations.read_customer_suppliers(customer_idurl=self.queue_owner_idurl, use_cache=True)
        d.addCallback(self._on_read_queue_owner_suppliers_success)
        d.addErrback(self._on_read_queue_owner_suppliers_failed)

    def doStartArchiveBackup(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_start_archive_backup()

    def doPushPackets(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_send_packets(
            backup_id=kwargs['backup_id'],
            block_num=kwargs['block_num'],
        )

    def doPullPacket(self, event, *args, **kwargs):
        """
        Action method.
        """
        newpacket = kwargs['newpacket']
        _, _, _, block_num, _, _ = packetid.SplitFull(newpacket.PacketID)
        if block_num not in self.packets_out:
            raise Exception('unregistered block number received')
        if newpacket.PacketID not in self.packets_out[block_num]:
            raise Exception('unregistered packet ID received')
        if event == 'ack':
            self.packets_out[block_num][newpacket.PacketID] = True
        else:
            self.packets_out[block_num][newpacket.PacketID] = False
        if _Debug:
            lg.args(_DebugLevel, event=event, block_num=block_num, packet_id=newpacket.PacketID, packets_out=self.packets_out)

    def doCheckFinished(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, backup_job=self.backup_job, backup_max_block_num=self.backup_max_block_num, packets_out=list(self.packets_out.values()))
        if self.backup_job:
            # backup is not finished yet
            return
        if self.backup_max_block_num not in self.packets_out:
            # packets of the last block not sent yet
            return
        packets_in_progress = 0
        for block_num in self.packets_out.keys():
            packets_in_progress += list(self.packets_out[block_num].values()).count(None)
        if packets_in_progress:
            # some packets are still in progress
            return
        for block_num in self.packets_out.keys():
            block_packets_failed = list(self.packets_out[block_num].values()).count(False)
            if block_packets_failed > self.correctable_errors*2:  # because each packet also have Parity()
                lg.err('all packets for block %d are sent, but too many errors: %d' % (block_num, block_packets_failed))
                self.automat('sending-failed')
                return
        self.automat('packets-delivered')

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """
        if self.result_defer:
            self.result_defer.callback(self.archive_info)

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        ret = 'unknown error'
        if event == 'dht-read-failed':
            ret = 'failed reading list of suppliers from DHT'
        elif event == 'backup-failed':
            ret = 'local archive backup is failed'
        elif event == 'sending-failed':
            ret = 'sending archived packets failed'
        if self.result_defer:
            self.result_defer.errback(Exception(ret))

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.queue_id = None
        self.archive_info = None
        self.result_defer = None
        self.suppliers_list = None
        self.ecc_map = None
        self.packets_out = None
        self.block_failed = None
        self.backup_job = None
        self.correctable_errors = None
        self.destroy()

    def _do_start_archive_backup(self):
        archive_id, local_path = self.local_data_callback(self.queue_id, self.archive_info)
        supplier_path_id = os.path.join(self.archive_folder_path, archive_id)
        dataID = misc.NewBackupID()
        backup_id = packetid.MakeBackupID(
            customer=self.queue_owner_id,
            path_id=supplier_path_id,
            key_alias=self.queue_alias,
            version=dataID,
        )
        backup_fs.MakeLocalDir(settings.getLocalBackupsDir(), backup_id)
        compress_mode = 'bz2'
        arcname = os.path.basename(local_path)
        backupPipe = backup_tar.backuptarfile_thread(local_path, arcname=arcname, compress=compress_mode)
        self.backup_job = backup.backup(
            backupID=backup_id,
            pipe=backupPipe,
            blockResultCallback=self._on_archive_backup_block_result,
            finishCallback=self._on_archive_backup_done,
            blockSize=1024*1024*10,
            sourcePath=local_path,
            keyID=self.group_key_id,
            ecc_map=eccmap.eccmap(self.ecc_map),
            creatorIDURL=self.queue_owner_idurl,
        )
        self.backup_job.automat('start')
        if _Debug:
            lg.args(_DebugLevel, job=self.backup_job, backup_id=backup_id, local_path=local_path, group_key_id=self.group_key_id)

    def _do_send_packets(self, backup_id, block_num):
        customer_id, path_id, version_name = packetid.SplitBackupID(backup_id)
        archive_snapshot_dir = os.path.join(settings.getLocalBackupsDir(), customer_id, path_id, version_name)
        if _Debug:
            lg.args(_DebugLevel, backup_id=backup_id, block_num=block_num, archive_snapshot_dir=archive_snapshot_dir)
        if not os.path.isdir(archive_snapshot_dir):
            self.block_failed = True
            lg.err('archive snapshot folder was not found in %r' % archive_snapshot_dir)
            return None
        failed_supliers = 0
        for supplier_num in range(len(self.suppliers_list)):
            supplier_idurl = self.suppliers_list[supplier_num]
            if not supplier_idurl:
                failed_supliers += 1
                lg.warn('unknown supplier supplier_num=%d' % supplier_num)
                continue
            for dataORparity in ('Data', 'Parity'):
                packet_id = packetid.MakePacketID(backup_id, block_num, supplier_num, dataORparity)
                packet_filename = os.path.join(archive_snapshot_dir, '%d-%d-%s' % (block_num, supplier_num, dataORparity))
                if not os.path.isfile(packet_filename):
                    lg.err('%s is not a file' % packet_filename)
                    continue
                packet_payload = bpio.ReadBinaryFile(packet_filename)
                if not packet_payload:
                    lg.err('file %r reading error' % packet_filename)
                    continue
                if block_num not in self.packets_out:
                    self.packets_out[block_num] = {}
                self.packets_out[block_num][packet_id] = None
                p2p_service.SendData(
                    raw_data=packet_payload,
                    ownerID=self.queue_owner_idurl,
                    creatorID=my_id.getIDURL(),
                    remoteID=supplier_idurl,
                    packetID=packet_id,
                    callbacks={
                        commands.Ack(): lambda newpacket, _: self.automat('ack', newpacket=newpacket),
                        commands.Fail(): lambda newpacket, _: self.automat('fail', newpacket=newpacket),
                    },
                )
        if failed_supliers > self.correctable_errors:
            self.block_failed = True
            lg.err('too many failed suppliers %d in block %d' % (failed_supliers, block_num))

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

    def _on_archive_backup_block_result(self, backup_id, block_num, result):
        if not result:
            self.block_failed = True
            return
        self.automat('block-ready', backup_id=backup_id, block_num=block_num)

    def _on_archive_backup_done(self, backup_id, result):
        self.backup_max_block_num = self.backup_job.blockNumber
        self.backup_job = None
        if result != 'done':
            self.automat('backup-failed')
            return
        self.automat('backup-done')
