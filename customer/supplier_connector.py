#!/usr/bin/env python
# supplier_connector.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (supplier_connector.py) is part of BitDust Software.
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
.. module:: supplier.

.. role:: red

BitDust supplier_connector() Automat

.. raw:: html

    <a href="supplier.png" target="_blank">
    <img src="supplier.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`ack`
    * :red:`close`
    * :red:`connect`
    * :red:`disconnect`
    * :red:`fail`
    * :red:`shutdown`
    * :red:`timer-10sec`
    * :red:`timer-20sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import math

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from system import bpio

from main import settings

from lib import strng
from lib import nameurl
from lib import diskspace

from contacts import contactsdb

from userid import global_id

from crypt import my_keys

from p2p import commands
from p2p import p2p_service
from p2p import online_status

from raid import eccmap

from userid import my_id

#------------------------------------------------------------------------------

_SuppliersConnectors = {}

#------------------------------------------------------------------------------

def connectors(customer_idurl=None):
    """
    """
    global _SuppliersConnectors
    if customer_idurl is None:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _SuppliersConnectors:
        _SuppliersConnectors[customer_idurl] = {}
    return _SuppliersConnectors[customer_idurl]


def create(supplier_idurl, customer_idurl=None, needed_bytes=None,
           key_id=None, queue_subscribe=True):
    """
    """
    if customer_idurl is None:
        customer_idurl = my_id.getLocalID()
    assert supplier_idurl not in connectors(customer_idurl)
    connectors(customer_idurl)[supplier_idurl] = SupplierConnector(
        supplier_idurl=supplier_idurl,
        customer_idurl=customer_idurl,
        needed_bytes=needed_bytes,
        key_id=key_id,
        queue_subscribe=queue_subscribe,
    )
    return connectors(customer_idurl)[supplier_idurl]


def is_supplier(supplier_idurl, customer_idurl=None):
    """
    """
    global _SuppliersConnectors
    if customer_idurl is None:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _SuppliersConnectors:
        return False
    if supplier_idurl not in _SuppliersConnectors[customer_idurl]:
        return False
    return True


def by_idurl(supplier_idurl, customer_idurl=None):
    """
    """
    if customer_idurl is None:
        customer_idurl = my_id.getLocalID()
    return connectors(customer_idurl).get(supplier_idurl, None)

#------------------------------------------------------------------------------


class SupplierConnector(automat.Automat):
    """
    This class implements all the functionality of the ``supplier_connector()``
    state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['REFUSE', 'QUEUE?']),
        'timer-20sec': (20.0, ['REQUEST']),
    }

    def __init__(self, supplier_idurl, customer_idurl, needed_bytes,
                 key_id=None, queue_subscribe=True):
        """
        """
        self.supplier_idurl = supplier_idurl
        self.customer_idurl = customer_idurl
        self.needed_bytes = needed_bytes
        self.key_id = key_id
        self.queue_subscribe = queue_subscribe
        self.do_calculate_needed_bytes()
        name = 'supplier_%s_%s' % (
            nameurl.GetName(self.supplier_idurl),
            diskspace.MakeStringFromBytes(self.needed_bytes).replace(' ', ''),
        )
        self.request_packet_id = None
        self.callbacks = {}
        try:
            st = bpio.ReadTextFile(settings.SupplierServiceFilename(
                idurl=self.supplier_idurl,
                customer_idurl=self.customer_idurl,
            )).strip()
        except:
            st = 'DISCONNECTED'
        automat.Automat.__init__(
            self,
            name,
            state=st,
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
        for cb in self.callbacks.values():
            cb(self.supplier_idurl, self.state, self.state)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self._last_known_family_position = None
        self._last_known_ecc_map = None
        self._last_known_family_snapshot = None
        online_status.add_online_status_listener_callback(
            idurl=self.supplier_idurl,
            callback_method=self._on_online_status_state_changed,
        )
        
        # contact_peer = contact_status.getInstance(self.supplier_idurl)
        # if contact_peer:
        #     contact_peer.addStateChangedCallback(self._on_contact_status_state_changed)

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when automat's state were
        changed.
        """
        if newstate in ['CONNECTED', 'DISCONNECTED', 'NO_SERVICE']:
            supplierPath = settings.SupplierPath(self.supplier_idurl, customer_idurl=self.customer_idurl)
            if not os.path.isdir(supplierPath):
                try:
                    os.makedirs(supplierPath)
                except:
                    lg.exc()
                    return
            bpio.WriteTextFile(
                settings.SupplierServiceFilename(self.supplier_idurl, customer_idurl=self.customer_idurl),
                newstate,
            )

    def set_callback(self, name, cb):
        self.callbacks[name] = cb

    def remove_callback(self, name):
        if name in list(self.callbacks.keys()):
            self.callbacks.pop(name)

    def do_calculate_needed_bytes(self):
        if self.needed_bytes is None:
            total_bytes_needed = diskspace.GetBytesFromString(settings.getNeededString(), 0)
            num_suppliers = -1
            if self.customer_idurl == my_id.getLocalIDURL():
                num_suppliers = settings.getSuppliersNumberDesired()
            else:
                known_ecc_map = contactsdb.get_customer_meta_info(self.customer_idurl).get('ecc_map')
                if known_ecc_map:
                    num_suppliers = eccmap.GetEccMapSuppliersNumber(known_ecc_map)
            if num_suppliers > 0:
                self.needed_bytes = int(math.ceil(2.0 * total_bytes_needed / float(num_suppliers)))
            else:
                raise Exception('not possible to determine needed_bytes value to be requested from that supplier')
                # self.needed_bytes = int(math.ceil(2.0 * settings.MinimumNeededBytes() / float(settings.DefaultDesiredSuppliers())))

    def A(self, event, *args, **kwargs):
        #---NO_SERVICE---
        if self.state == 'NO_SERVICE':
            if event == 'connect':
                self.state = 'REQUEST'
                self.GoDisconnect=False
                self.doRequestService(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnect':
                self.doReportNoService(*args, **kwargs)
            elif event == 'ack' and self.isServiceAccepted(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doReportConnect(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'close':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnect':
                self.state = 'REFUSE'
                self.doCancelServiceQueue(*args, **kwargs)
                self.doCancelService(*args, **kwargs)
            elif event == 'fail' or event == 'connect':
                self.state = 'REQUEST'
                self.GoDisconnect=False
                self.doRequestService(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnect':
                self.state = 'REFUSE'
                self.doCancelService(*args, **kwargs)
            elif event == 'connect':
                self.state = 'REQUEST'
                self.GoDisconnect=False
                self.doRequestService(*args, **kwargs)
            elif event == 'fail':
                self.state = 'NO_SERVICE'
                self.doReportNoService(*args, **kwargs)
            elif event == 'ack' and self.isServiceAccepted(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doReportConnect(*args, **kwargs)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'disconnect':
                self.GoDisconnect=True
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-20sec':
                self.state = 'DISCONNECTED'
                self.doCleanRequest(*args, **kwargs)
                self.doReportDisconnect(*args, **kwargs)
            elif event == 'fail' or ( event == 'ack' and not self.isServiceAccepted(*args, **kwargs) and not self.GoDisconnect ):
                self.state = 'NO_SERVICE'
                self.doReportNoService(*args, **kwargs)
            elif event == 'ack' and not self.GoDisconnect and self.isServiceAccepted(*args, **kwargs):
                self.state = 'QUEUE?'
                self.doRequestQueueService(*args, **kwargs)
            elif self.GoDisconnect and event == 'ack' and self.isServiceAccepted(*args, **kwargs):
                self.state = 'REFUSE'
                self.doCancelService(*args, **kwargs)
        #---REFUSE---
        elif self.state == 'REFUSE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCleanRequest(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-10sec' or event == 'fail' or ( event == 'ack' and self.isServiceCancelled(*args, **kwargs) ):
                self.state = 'NO_SERVICE'
                self.doCleanRequest(*args, **kwargs)
                self.doReportNoService(*args, **kwargs)
        #---QUEUE?---
        elif self.state == 'QUEUE?':
            if event == 'disconnect':
                self.GoDisconnect=True
            elif self.GoDisconnect and ( event == 'ack' or event == 'fail' or event == 'timer-10sec' ):
                self.state = 'REFUSE'
                self.doCancelServiceQueue(*args, **kwargs)
                self.doCancelService(*args, **kwargs)
            elif event == 'close':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif not self.GoDisconnect and ( event == 'ack' or event == 'fail' or event == 'timer-10sec' ):
                self.state = 'CONNECTED'
                self.doReportConnect(*args, **kwargs)
        return None

    def isServiceAccepted(self, *args, **kwargs):
        """
        Condition method.
        """
        newpacket = args[0]
        if strng.to_text(newpacket.Payload).startswith('accepted'):
            if _Debug:
                lg.out(6, 'supplier_connector.isServiceAccepted !!! supplier %s connected' % self.supplier_idurl)
            return True
        return False

    def isServiceCancelled(self, *args, **kwargs):
        """
        Condition method.
        """
        newpacket = args[0]
        if newpacket.Command == commands.Ack():
            if strng.to_text(newpacket.Payload).startswith('accepted'):
                if _Debug:
                    lg.out(6, 'supplier_connector.isServiceCancelled !!! supplier %s disconnected' % self.supplier_idurl)
                return True
        return False

    def doRequestService(self, *args, **kwargs):
        """
        Action method.
        """
        service_info = {
            'needed_bytes': self.needed_bytes,
            'customer_id': global_id.UrlToGlobalID(self.customer_idurl),
        }
        my_customer_key_id = my_id.getGlobalID(key_alias='customer')
        if my_keys.is_key_registered(my_customer_key_id):
            service_info['customer_public_key'] = my_keys.get_key_info(
                key_id=my_customer_key_id,
                include_private=False,
            )
        if self.key_id:
            service_info['key_id'] = self.key_id
        self._last_known_ecc_map = kwargs.get('ecc_map')
        if self._last_known_ecc_map is not None:
            service_info['ecc_map'] = self._last_known_ecc_map
        self._last_known_family_position = kwargs.get('family_position')
        if self._last_known_family_position is not None:
            service_info['position'] = self._last_known_family_position
        self._last_known_family_snapshot = kwargs.get('family_snapshot')
        if self._last_known_family_snapshot is not None:
            service_info['family_snapshot'] = self._last_known_family_snapshot
        request = p2p_service.SendRequestService(
            remote_idurl=self.supplier_idurl,
            service_name='service_supplier',
            json_payload=service_info,
            callbacks={
                commands.Ack(): self._supplier_acked,
                commands.Fail(): self._supplier_failed,
            },
        )
        self.request_packet_id = request.PacketID

    def doCancelService(self, *args, **kwargs):
        """
        Action method.
        """
        service_info = {}
        my_customer_key_id = my_id.getGlobalID(key_alias='customer')
        if my_keys.is_key_registered(my_customer_key_id):
            service_info['customer_public_key'] = my_keys.get_key_info(
                key_id=my_customer_key_id,
                include_private=False,
            )
        request = p2p_service.SendCancelService(
            remote_idurl=self.supplier_idurl,
            service_name='service_supplier',
            json_payload=service_info,
            callbacks={
                commands.Ack(): self._supplier_acked,
                commands.Fail(): self._supplier_failed,
            },
        )
        self.request_packet_id = request.PacketID

    def doRequestQueueService(self, *args, **kwargs):
        """
        Action method.
        """
        if not self.queue_subscribe:
            self.automat('fail')
            return
        service_info = {
            'items': [{
                'scope': 'consumer',
                'action': 'start',
                'consumer_id': strng.to_text(my_id.getGlobalID()),
            }, {
                'scope': 'consumer',
                'action': 'add_callback',
                'consumer_id': strng.to_text(my_id.getGlobalID()),
                'method': strng.to_text(my_id.getLocalID()),
            }, {
                'scope': 'consumer',
                'action': 'subscribe',
                'consumer_id': strng.to_text(my_id.getGlobalID()),
                'queue_id': global_id.MakeGlobalQueueID(
                    queue_alias='supplier-file-modified',
                    owner_id=my_id.getGlobalID(),
                    supplier_id=global_id.MakeGlobalID(idurl=self.supplier_idurl),
                ),
            }, ],
        }
        p2p_service.SendRequestService(
            remote_idurl=self.supplier_idurl,
            service_name='service_p2p_notifications',
            json_payload=service_info,
            callbacks={
                commands.Ack(): self._supplier_acked,
                commands.Fail(): self._supplier_failed,
            },
        )

    def doCancelServiceQueue(self, *args, **kwargs):
        """
        Action method.
        """
        service_info = {
            'items': [{
                'scope': 'consumer',
                'action': 'unsubscribe',
                'consumer_id': strng.to_text(my_id.getGlobalID()),
                'queue_id': global_id.MakeGlobalQueueID(
                    queue_alias='supplier-file-modified',
                    owner_id=my_id.getGlobalID(),
                    supplier_id=global_id.MakeGlobalID(idurl=self.supplier_idurl),
                ),
            }, {
                'scope': 'consumer',
                'action': 'remove_callback',
                'consumer_id': strng.to_text(my_id.getGlobalID()),
                'method': strng.to_text(my_id.getLocalID()),
            }, {
                'scope': 'consumer',
                'action': 'stop',
                'consumer_id': strng.to_text(my_id.getGlobalID()),
            }, ],
        }
        p2p_service.SendCancelService(
            remote_idurl=self.supplier_idurl,
            service_name='service_p2p_notifications',
            json_payload=service_info,
            callbacks={
                commands.Ack(): self._supplier_acked,
                commands.Fail(): self._supplier_failed,
            },
        )

    def doCleanRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self.request_packet_id = None

    def doReportConnect(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(14, 'supplier_connector.doReportConnect : %s' % self.supplier_idurl)
        for cb in list(self.callbacks.values()):
            cb(
                self.supplier_idurl,
                'CONNECTED',
                family_position=self._last_known_family_position,
                ecc_map=self._last_known_ecc_map,
                family_snapshot=self._last_known_family_snapshot,
            )
#         if self._last_known_family_position is not None:
#             p2p_service.SendContacts(
#                 remote_idurl=self.supplier_idurl,
#                 json_payload={
#                     'space': 'family_member',
#                     'type': 'supplier_position',
#                     'customer_idurl': my_id.getLocalIDURL(),
#                     'customer_ecc_map': self._last_known_ecc_map,
#                     'supplier_idurl': self.supplier_idurl,
#                     'supplier_position': self._last_known_family_position,
#                     'family_snapshot': self._last_known_family_snapshot,
#                 },
#             )

    def doReportNoService(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(14, 'supplier_connector.doReportNoService : %s' % self.supplier_idurl)
        for cb in list(self.callbacks.values()):
            cb(self.supplier_idurl, 'NO_SERVICE')

    def doReportDisconnect(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'supplier_connector.doReportDisconnect : %s' % self.supplier_idurl)
        for cb in list(self.callbacks.values()):
            cb(self.supplier_idurl, 'DISCONNECTED')

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        online_status.remove_online_status_listener_callbackove_(
            idurl=self.supplier_idurl,
            callback_method=self._on_online_status_state_changed,
        )
        # contact_peer = contact_status.getInstance(self.supplier_idurl)
        # if contact_peer:
        #     contact_peer.removeStateChangedCallback(self._on_contact_status_state_changed)
        connectors(self.customer_idurl).pop(self.supplier_idurl)
        self.request_packet_id = None
        self.supplier_idurl = None
        self.customer_idurl = None
        self.queue_subscribe = None
        self.destroy()

    def _supplier_acked(self, response, info):
        if _Debug:
            lg.out(16, 'supplier_connector._supplier_acked %r %r' % (response, info))
        self.automat(response.Command.lower(), response)

    def _supplier_failed(self, response, info):
        if _Debug:
            lg.out(16, 'supplier_connector._supplier_failed %r %r' % (response, info))
        if response:
            self.automat(response.Command.lower(), response)
        else:
            self.automat('fail', None)

    def _on_online_status_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        if oldstate != newstate and newstate in ['CONNECTED', 'OFFLINE', ]:
            if _Debug:
                lg.out(10, 'supplier_connector._on_online_status_state_changed %s : %s->%s, reconnecting now' % (
                    self.supplier_idurl, oldstate, newstate))
            self.automat('connect')
