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

from logs import lg

from automats import automat

from lib import utime
from lib import packetid

from main import events
from main import config

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

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `archive_reader()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `archive_reader()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `archive_reader()`
        but automat state was not changed.
        """

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
        self.correctable_errors = eccmap.GetCorrectableErrors(len(self.suppliers_list))
        for supplier_idurl in self.suppliers_list:
            if supplier_idurl:
                outpacket = p2p_service.SendListFiles(
                    target_supplier=supplier_idurl,
                    key_id=self.group_key_id,
                    query_items=[self.group_queue_alias, ],
                    callbacks={
                        commands.Files(): self._on_list_files_response,
                        commands.Fail(): self._on_list_files_failed,
                        None: lambda pkt_out: self._on_list_files_failed(None, None, outpacket=pkt_out),
                    }
                )
                if outpacket:
                    self.requested_list_files[outpacket.PacketID] = None

    def doRequestMyListFiles(self, *args, **kwargs):
        """
        Action method.
        """
        self.correctable_errors = eccmap.GetCorrectableErrors(contactsdb.num_suppliers())
        for supplier_idurl in contactsdb.suppliers():
            if supplier_idurl:
                outpacket = p2p_service.SendListFiles(
                    target_supplier=supplier_idurl,
                    key_id=self.group_key_id,
                    query_items=[self.group_queue_alias, ],
                    callbacks={
                        commands.Files(): self._on_list_files_response,
                        commands.Fail(): self._on_list_files_failed,
                        None: lambda pkt_out: self._on_list_files_failed(None, None, outpacket=pkt_out),
                    }
                )
                if outpacket:
                    self.requested_list_files[outpacket.PacketID] = None

    def doStartRestoreWorker(self, *args, **kwargs):
        """
        Action method.
        """

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

    def _on_list_files_response(self, response, info):
        self.requested_list_files[response.PacketID] = True
        lst = list(self.requested_list_files.values())
        if _Debug:
            lg.args(_DebugLevel, requested_list_files=lst, response=response)
        packets_pending_or_failed = lst.count(None) + lst.count(False)
        if packets_pending_or_failed < self.correctable_errors * 2:  # because each packet also have Parity()
            self.automat('list-files-collected')
        return None

    def _on_list_files_failed(self, response, info, outpacket=None):
        if outpacket:
            self.requested_list_files[outpacket.outpacket.PacketID]
        else:
            self.requested_list_files[response.PacketID] = False
        lst = list(self.requested_list_files.values())
        if _Debug:
            lg.args(_DebugLevel, requested_list_files=lst, response=response, outpacket=outpacket)
        if not lst.count(None):
            self.automat('list-files-failed')
        return None
