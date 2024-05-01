#!/usr/bin/env python
# supplier_connector.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
    * :red:`connect`
    * :red:`disconnect`
    * :red:`fail`
    * :red:`queue-ack`
    * :red:`queue-fail`
    * :red:`queue-skip`
    * :red:`shutdown`
    * :red:`timer-10sec`
    * :red:`timer-30sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------

import os
import math

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.system import bpio

from bitdust.main import settings
from bitdust.main import events

from bitdust.lib import strng
from bitdust.lib import nameurl
from bitdust.lib import diskspace
from bitdust.lib import jsn

from bitdust.contacts import contactsdb

from bitdust.services import driver

from bitdust.p2p import commands
from bitdust.p2p import p2p_service
from bitdust.p2p import online_status

from bitdust.raid import eccmap

from bitdust.storage import accounting

from bitdust.userid import id_url
from bitdust.userid import global_id
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_SuppliersConnectors = {}

#------------------------------------------------------------------------------


def connectors(customer_idurl=None, as_dict=False):
    global _SuppliersConnectors
    if as_dict:
        return _SuppliersConnectors
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _SuppliersConnectors:
        _SuppliersConnectors[customer_idurl] = {}
    return _SuppliersConnectors[customer_idurl]


def create(supplier_idurl, customer_idurl=None, needed_bytes=None, key_id=None, queue_subscribe=True):
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    supplier_idurl = id_url.field(supplier_idurl)
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
    global _SuppliersConnectors
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    if not id_url.is_cached(customer_idurl):
        return False
    if not id_url.is_cached(supplier_idurl):
        return False
    customer_idurl = id_url.field(customer_idurl)
    supplier_idurl = id_url.field(supplier_idurl)
    if customer_idurl not in _SuppliersConnectors:
        return False
    if supplier_idurl not in _SuppliersConnectors[customer_idurl]:
        return False
    return True


def by_idurl(supplier_idurl, customer_idurl=None):
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    supplier_idurl = id_url.field(supplier_idurl)
    return connectors(customer_idurl).get(supplier_idurl, None)


def total_connectors():
    count = 0
    for suppliers_list in _SuppliersConnectors.values():
        count += len(suppliers_list)
    return count


#------------------------------------------------------------------------------


class SupplierConnector(automat.Automat):
    """
    This class implements all the functionality of the ``supplier_connector()``
    state machine.
    """

    timers = {
        'timer-30sec': (30.0, ['REQUEST']),
        'timer-10sec': (10.0, ['REFUSE', 'QUEUE?']),
    }

    def __init__(self, supplier_idurl, customer_idurl, needed_bytes, key_id=None, queue_subscribe=True):
        self.supplier_idurl = supplier_idurl
        self.supplier_id = self.supplier_idurl.to_id()
        self.customer_idurl = customer_idurl
        self.customer_id = self.customer_idurl.to_id()
        self.needed_bytes = needed_bytes
        self.key_id = key_id
        self.queue_subscribe = queue_subscribe
        self.do_calculate_needed_bytes()
        name = 'supplier_%s_%s_%s' % (
            nameurl.GetName(self.supplier_idurl),
            nameurl.GetName(self.customer_idurl),
            diskspace.MakeStringFromBytes(self.needed_bytes).replace(' ', ''),
        )
        self.request_packet_id = None
        self.request_queue_packet_id = None
        self.latest_supplier_ack = None
        self.callbacks = {}
        self.storage_contract = None
        try:
            st = bpio.ReadTextFile(settings.SupplierServiceFilename(
                supplier_idurl=self.supplier_idurl,
                customer_idurl=self.customer_idurl,
            )).strip()
        except:
            lg.exc()
        st = st or 'DISCONNECTED'
        automat.Automat.__init__(
            self,
            name,
            state=st,
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
        for cb_list in self.callbacks.values():
            for cb in cb_list:
                cb(self.supplier_idurl, self.state, self.state)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self._last_known_family_position = None
        self._last_known_ecc_map = None
        self._last_known_family_snapshot = None
        self._supplier_connected_event_sent = False
        online_status.add_online_status_listener_callback(
            idurl=self.supplier_idurl,
            callback_method=self._on_online_status_state_changed,
        )

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when automat's state was changed.
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
                settings.SupplierServiceFilename(supplier_idurl=self.supplier_idurl, customer_idurl=self.customer_idurl),
                newstate,
            )
        if newstate == 'CONNECTED':
            if id_url.is_the_same(self.customer_idurl, my_id.getIDURL()):
                #TODO: receive and process contract details: "pay_before" field
                pass
            if not self._supplier_connected_event_sent:
                self._supplier_connected_event_sent = True
                events.send('supplier-connected', data=dict(
                    supplier_idurl=self.supplier_idurl,
                    customer_idurl=self.customer_idurl,
                    needed_bytes=self.needed_bytes,
                    key_id=self.key_id,
                ))
        if newstate in ['DISCONNECTED', 'NO_SERVICE']:
            self._supplier_connected_event_sent = False

    def set_callback(self, name, cb):
        if name not in self.callbacks:
            self.callbacks[name] = []
        if cb in self.callbacks[name]:
            lg.warn('callback %r is already registered in %r with name %s' % (cb, self, name))
        self.callbacks[name].append(cb)

    def remove_callback(self, name, cb=None):
        if name in self.callbacks:
            if cb:
                while cb in self.callbacks[name]:
                    self.callbacks[name].remove(cb)
            else:
                self.callbacks.pop(name)
        else:
            lg.warn('callback with name %s not registered in %r' % (name, self))

    def do_calculate_needed_bytes(self):
        if self.needed_bytes is None:
            total_bytes_needed = diskspace.GetBytesFromString(settings.getNeededString(), 0)
            num_suppliers = -1
            if self.customer_idurl == my_id.getIDURL():
                num_suppliers = settings.getSuppliersNumberDesired()
            else:
                known_ecc_map = contactsdb.get_customer_meta_info(self.customer_idurl).get('ecc_map')
                if known_ecc_map:
                    num_suppliers = eccmap.GetEccMapSuppliersNumber(known_ecc_map)
            if num_suppliers > 0:
                self.needed_bytes = int(math.ceil(2.0*total_bytes_needed/float(num_suppliers)))
            else:
                raise Exception('not possible to determine needed_bytes value to be requested from that supplier')
                # self.needed_bytes = int(math.ceil(2.0 * settings.MinimumNeededBytes() / float(settings.DefaultDesiredSuppliers())))

    def A(self, event, *args, **kwargs):
        #---NO_SERVICE---
        if self.state == 'NO_SERVICE':
            if event == 'connect':
                self.state = 'REQUEST'
                self.GoDisconnect = False
                self.doPingRequestService(*args, **kwargs)
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
            if event == 'disconnect':
                self.state = 'REFUSE'
                self.doCancelServiceQueue(*args, **kwargs)
                self.doCancelService(*args, **kwargs)
            elif event == 'fail' or event == 'connect':
                self.state = 'REQUEST'
                self.GoDisconnect = False
                self.doPingRequestService(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
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
                self.GoDisconnect = False
                self.doPingRequestService(*args, **kwargs)
            elif event == 'fail':
                self.state = 'NO_SERVICE'
                self.doReportNoService(*args, **kwargs)
            elif event == 'ack' and self.isServiceAccepted(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doReportConnect(*args, **kwargs)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'disconnect':
                self.GoDisconnect = True
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'fail' or (event == 'ack' and not self.isServiceAccepted(*args, **kwargs) and not self.GoDisconnect):
                self.state = 'NO_SERVICE'
                self.doReportNoService(*args, **kwargs)
            elif event == 'ack' and not self.GoDisconnect and self.isServiceAccepted(*args, **kwargs):
                self.state = 'QUEUE?'
                self.doRequestQueueService(*args, **kwargs)
            elif self.GoDisconnect and event == 'ack' and self.isServiceAccepted(*args, **kwargs):
                self.state = 'REFUSE'
                self.doCancelService(*args, **kwargs)
            elif event == 'timer-30sec':
                self.state = 'DISCONNECTED'
                self.doCleanRequest(*args, **kwargs)
                self.doReportDisconnect(*args, **kwargs)
        #---REFUSE---
        elif self.state == 'REFUSE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doCleanRequest(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-10sec' or event == 'fail' or (event == 'ack' and self.isServiceCancelled(*args, **kwargs)):
                self.state = 'NO_SERVICE'
                self.doCleanRequest(*args, **kwargs)
                self.doReportNoService(*args, **kwargs)
        #---QUEUE?---
        elif self.state == 'QUEUE?':
            if event == 'disconnect':
                self.GoDisconnect = True
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif self.GoDisconnect and (event == 'queue-ack' or event == 'queue-fail' or event == 'queue-skip' or event == 'timer-10sec'):
                self.state = 'REFUSE'
                self.doCancelServiceQueue(*args, **kwargs)
                self.doCancelService(*args, **kwargs)
            elif not self.GoDisconnect and (event == 'queue-ack' or event == 'queue-fail' or event == 'queue-skip' or event == 'timer-10sec'):
                self.state = 'CONNECTED'
                self.doReportConnect(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isServiceAccepted(self, *args, **kwargs):
        """
        Condition method.
        """
        newpacket = args[0]
        if strng.to_text(newpacket.Payload).startswith('accepted'):
            if _Debug:
                lg.dbg(_DebugLevel, 'supplier %s accepted my request and will be connected' % self.supplier_idurl)
            return True
        if _Debug:
            lg.dbg(_DebugLevel, 'supplier %s refused my request' % self.supplier_idurl)
        return False

    def isServiceCancelled(self, *args, **kwargs):
        """
        Condition method.
        """
        newpacket = args[0]
        if newpacket.Command == commands.Ack():
            if strng.to_text(newpacket.Payload).startswith('accepted'):
                if _Debug:
                    lg.out(_DebugLevel, 'supplier_connector.isServiceCancelled !!! supplier %s disconnected' % self.supplier_idurl)
                return True
        return False

    def doPingRequestService(self, *args, **kwargs):
        """
        Action method.
        """
        ecc_map = kwargs.get('ecc_map')
        family_position = kwargs.get('family_position')
        family_snapshot = kwargs.get('family_snapshot')
        d = online_status.ping(
            idurl=self.supplier_idurl,
            channel='supplier_connector',
            keep_alive=True,
            ping_retries=3,
        )
        d.addCallback(lambda ok: self._do_request_supplier_service(
            ecc_map=ecc_map,
            family_position=family_position,
            family_snapshot=family_snapshot,
        ))
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='supplier_connector.doPingRequestService')
        d.addErrback(lambda err: self.automat('fail', err))

    def doCancelService(self, *args, **kwargs):
        """
        Action method.
        """
        service_info = {}
        # TODO: re-think again about the customer key, do we really need it?
        # my_customer_key_id = my_id.getGlobalID(key_alias='customer')
        # if my_keys.is_key_registered(my_customer_key_id):
        #     service_info['customer_public_key'] = my_keys.get_key_info(
        #         key_id=my_customer_key_id,
        #         include_private=False,
        #         include_signature=False,
        #         generate_signature=False,
        #     )
        ecc_map = kwargs.get('ecc_map')
        if ecc_map:
            service_info['ecc_map'] = ecc_map
        request = p2p_service.SendCancelService(
            remote_idurl=self.supplier_idurl,
            service_name='service_supplier',
            json_payload=service_info,
            callbacks={
                commands.Ack(): self._supplier_service_acked,
                commands.Fail(): self._supplier_service_failed,
            },
        )
        self.request_packet_id = request.PacketID

    def doRequestQueueService(self, *args, **kwargs):
        """
        Action method.
        """
        if not self.queue_subscribe:
            reactor.callLater(0, self.automat, 'queue-skip')  # @UndefinedVariable
            return
        queue_id = global_id.MakeGlobalQueueID(
            queue_alias='supplier-file-modified',
            owner_id=self.customer_id,
            supplier_id=self.supplier_id,
        )
        service_info = {
            'items': [
                {
                    'scope': 'consumer',
                    'action': 'start',
                    'consumer_id': self.customer_id,
                },
                {
                    'scope': 'consumer',
                    'action': 'add_callback',
                    'consumer_id': self.customer_id,
                    'method': self.customer_idurl,
                    'queues': [
                        'supplier-file-modified',
                    ],
                },
                {
                    'scope': 'consumer',
                    'action': 'subscribe',
                    'consumer_id': self.customer_id,
                    'queue_id': queue_id,
                },
            ],
        }
        request = p2p_service.SendRequestService(
            remote_idurl=self.supplier_idurl,
            service_name='service_p2p_notifications',
            json_payload=service_info,
            callbacks={
                commands.Ack(): self._supplier_queue_acked,
                commands.Fail(): self._supplier_queue_failed,
            },
        )
        self.request_queue_packet_id = request.PacketID

    def doCancelServiceQueue(self, *args, **kwargs):
        """
        Action method.
        """
        service_info = {
            'items': [
                {
                    'scope': 'consumer',
                    'action': 'unsubscribe',
                    'consumer_id': self.customer_id,
                    'queue_id': global_id.MakeGlobalQueueID(
                        queue_alias='supplier-file-modified',
                        owner_id=self.customer_id,
                        supplier_id=self.supplier_id,
                    ),
                },
                {
                    'scope': 'consumer',
                    'action': 'remove_callback',
                    'consumer_id': self.customer_id,
                    'method': self.customer_id,
                },
                {
                    'scope': 'consumer',
                    'action': 'stop',
                    'consumer_id': self.customer_id,
                },
            ],
        }
        p2p_service.SendCancelService(
            remote_idurl=self.supplier_idurl,
            service_name='service_p2p_notifications',
            json_payload=service_info,
            callbacks={
                commands.Ack(): self._supplier_queue_cancelled,
                commands.Fail(): self._supplier_queue_failed,
            },
        )

    def doCleanRequest(self, *args, **kwargs):
        """
        Action method.
        """
        self.request_packet_id = None
        self.request_queue_packet_id = None

    def doReportNoService(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'supplier_connector.doReportNoService : %s' % self.supplier_idurl)
        for cb_list in list(self.callbacks.values()):
            for cb in cb_list:
                cb(self.supplier_idurl, 'NO_SERVICE')

    def doReportDisconnect(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'supplier_connector.doReportDisconnect : %s' % self.supplier_idurl)
        for cb_list in list(self.callbacks.values()):
            for cb in cb_list:
                cb(self.supplier_idurl, 'DISCONNECTED')

    def doReportConnect(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'supplier_connector.doReportConnect : %s' % self.supplier_idurl)
        for cb_list in list(self.callbacks.values()):
            for cb in cb_list:
                cb(
                    self.supplier_idurl,
                    'CONNECTED',
                    family_position=self._last_known_family_position,
                    ecc_map=self._last_known_ecc_map,
                    family_snapshot=self._last_known_family_snapshot,
                )

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        online_status.remove_online_status_listener_callback(
            idurl=self.supplier_idurl,
            callback_method=self._on_online_status_state_changed,
        )
        connectors(self.customer_idurl).pop(self.supplier_idurl)
        self.latest_supplier_ack = None
        self.request_packet_id = None
        self.request_queue_packet_id = None
        self.supplier_idurl = None
        self.customer_idurl = None
        self.queue_subscribe = None
        self.destroy()

    def _supplier_service_acked(self, response, info):
        if not self.request_packet_id:
            lg.warn('received "old" response : %r' % response)
            return
        if response.PacketID != self.request_packet_id:
            lg.warn('received "unexpected" response : %r' % response)
            return
        self.latest_supplier_ack = response
        if driver.is_on('service_customer_contracts'):
            the_contract = None
            try:
                if strng.to_text(response.Payload).startswith('accepted:{'):
                    the_contract = jsn.loads_text(strng.to_text(response.Payload)[9:])
            except:
                lg.exc()
            if _Debug:
                lg.args(_DebugLevel, response=response, info=info, contract=the_contract)
            self.storage_contract = the_contract
            if the_contract:
                if not accounting.verify_storage_contract(the_contract):
                    lg.err('received storage contract from %r is not valid' % self.supplier_idurl)
                    self.latest_supplier_ack = None
                    self.automat('fail', None)
                    return
                from bitdust.customer import payment
                payment.save_storage_contract(self.supplier_idurl, the_contract)
        self.automat('ack', response)

    def _supplier_service_failed(self, response, info):
        if _Debug:
            lg.args(_DebugLevel, response=response, info=info)
        self.automat('fail', response or None)

    def _supplier_queue_acked(self, response, info):
        if not self.request_queue_packet_id:
            lg.warn('received "old" queue response : %r' % response)
            return
        if response.PacketID != self.request_queue_packet_id:
            lg.warn('received "unexpected" queue response : %r' % response)
            return
        # start_consumer(self.customer_id, self.supplier_id)
        self.automat('queue-ack', response)

    def _supplier_queue_cancelled(self, response, info):
        # stop_consumer(self.customer_id, self.supplier_id)
        self.automat('queue-stopped', response)

    def _supplier_queue_failed(self, response, info):
        if _Debug:
            lg.args(_DebugLevel, response=response, info=info)
        self.automat('queue-fail', response or None)

    def _on_online_status_state_changed(self, oldstate, newstate, event_string, *args, **kwargs):
        if oldstate != newstate and newstate in ['CONNECTED', 'OFFLINE']:
            if not (oldstate == 'PING?' and newstate == 'OFFLINE'):
                if _Debug:
                    lg.out(_DebugLevel, 'supplier_connector._on_online_status_state_changed %s : %s->%s, reconnecting now' % (self.supplier_idurl, oldstate, newstate))
                reactor.callLater(0, self.automat, 'connect')  # @UndefinedVariable

    def _do_request_supplier_service(self, ecc_map, family_position, family_snapshot):
        if _Debug:
            lg.args(_DebugLevel, supplier_idurl=self.supplier_idurl, ecc_map=ecc_map, family_position=family_position, family_snapshot=family_snapshot)
        if not self.supplier_idurl:
            lg.warn('supplier idurl is empty, SKIP sending supplier_service request')
            return
        service_info = {
            'customer_id': self.customer_id,
            'needed_bytes': self.needed_bytes,
            # 'minimum_duration_hours': 6,
            # 'maximum_duration_hours': 24*30,
        }
        # TODO: re-think again about the customer key, do we really need it?
        # my_customer_key_id = my_id.getGlobalID(key_alias='customer')
        # if my_keys.is_key_registered(my_customer_key_id):
        #     service_info['customer_public_key'] = my_keys.get_key_info(
        #         key_id=my_customer_key_id,
        #         include_private=False,
        #         include_signature=True,
        #         generate_signature=True,
        #     )
        # else:
        #     lg.warn('my own customer key is not registered: %r' % my_customer_key_id)
        if self.key_id:
            service_info['key_id'] = self.key_id
        self._last_known_ecc_map = ecc_map
        if self._last_known_ecc_map is not None:
            service_info['ecc_map'] = self._last_known_ecc_map
        self._last_known_family_position = family_position
        if self._last_known_family_position is not None:
            service_info['position'] = self._last_known_family_position
        self._last_known_family_snapshot = family_snapshot
        if self._last_known_family_snapshot is not None:
            service_info['family_snapshot'] = id_url.to_bin_list(self._last_known_family_snapshot)
        request = p2p_service.SendRequestService(
            remote_idurl=self.supplier_idurl,
            service_name='service_supplier',
            json_payload=service_info,
            callbacks={
                commands.Ack(): self._supplier_service_acked,
                commands.Fail(): self._supplier_service_failed,
            },
        )
        self.request_packet_id = request.PacketID
