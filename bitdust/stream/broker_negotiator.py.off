#!/usr/bin/env python
# broker_negotiator.py
#
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (broker_negotiator.py) is part of BitDust Software.
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
.. module:: broker_negotiator
.. role:: red

BitDust broker_negotiator() Automat

EVENTS:
    * :red:`broker-accepted`
    * :red:`broker-denied`
    * :red:`broker-failed`
    * :red:`broker-rejected`
    * :red:`broker-rotate-accepted`
    * :red:`broker-rotate-denied`
    * :red:`broker-rotate-failed`
    * :red:`broker-rotate-rejected`
    * :red:`broker-rotate-timeout`
    * :red:`broker-timeout`
    * :red:`connect`
    * :red:`hire-broker-failed`
    * :red:`hire-broker-ok`
    * :red:`init-done`
    * :red:`my-record-busy`
    * :red:`my-record-busy-replace`
    * :red:`my-record-empty`
    * :red:`my-record-empty-replace`
    * :red:`my-record-own`
    * :red:`my-record-own-replace`
    * :red:`my-top-record-busy`
    * :red:`my-top-record-busy-replace`
    * :red:`my-top-record-empty`
    * :red:`my-top-record-empty-replace`
    * :red:`my-top-record-own`
    * :red:`my-top-record-own-replace`
    * :red:`new-broker-rejected`
    * :red:`prev-record-busy`
    * :red:`prev-record-empty`
    * :red:`prev-record-own`
    * :red:`record-busy`
    * :red:`request-invalid`
    * :red:`top-record-busy`
    * :red:`top-record-empty`
    * :red:`top-record-own`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import re
import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in broker_negotiator.py')

from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from bitdust.automats import automat

from bitdust.logs import lg

from bitdust.lib import strng
from bitdust.lib import jsn

from bitdust.main import config

from bitdust.p2p import lookup
from bitdust.p2p import p2p_service_seeker

from bitdust.userid import id_url

#------------------------------------------------------------------------------


class BrokerNegotiator(automat.Automat):
    """
    This class implements all the functionality of ``broker_negotiator()`` state machine.
    """
    fast = False

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `broker_negotiator()` state machine.
        """
        self.result_defer = None
        self.my_broker_idurl = None
        self.my_broker_id = None
        self.my_position = None
        self.desired_position = None
        self.cooperated_brokers = None
        self.dht_brokers = None
        self.customer_idurl = None
        self.customer_id = None
        self.queue_id = None
        self.requestor_known_brokers = None
        self.connect_request = None
        super(BrokerNegotiator,
              self).__init__(name='broker_negotiator', state='AT_STARTUP', debug_level=debug_level or _DebugLevel, log_events=log_events or _Debug, log_transitions=log_transitions or _Debug, publish_events=publish_events, **kwargs)

    def __repr__(self):
        return '%s[%s:%s](%s)' % (
            self.id,
            '?' if self.my_position in [
                None,
                -1,
            ] else self.my_position,
            '?' if self.desired_position in [
                None,
                -1,
            ] else self.desired_position,
            self.state,
        )

    def to_json(self):
        j = super().to_json()
        j.update({
            'customer_id': self.customer_id,
            'broker_id': self.my_broker_id,
            'my_position': self.my_position,
            'desired_position': self.desired_position,
            'brokers': self.cooperated_brokers,
        })
        return j

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `broker_negotiator()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `broker_negotiator()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `broker_negotiator()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'connect':
                self.state = 'INIT'
                self.doInit(*args, **kwargs)
        #---INIT---
        elif self.state == 'INIT':
            if event == 'init-done' and self.isAlreadyCooperated(*args, **kwargs):
                self.state = 'VERIFY_DEAL'
                self.doVerifyKnownBrokers(*args, **kwargs)
            elif event == 'init-done' and not self.isAlreadyCooperated(*args, **kwargs):
                self.state = 'VERIFY_DHT'
                self.doVerifyDHTRecords(*args, **kwargs)
        #---VERIFY_DEAL---
        elif self.state == 'VERIFY_DEAL':
            if event == 'request-invalid' or event == 'my-top-record-busy-replace' or event == 'my-top-record-empty-replace' or event == 'my-top-record-own-replace':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doRefreshDHT(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'my-record-busy' or event == 'my-record-empty' or event == 'my-record-own':
                self.state = 'CURRENT?'
                self.doRequestCurBroker(event, *args, **kwargs)
            elif event == 'my-top-record-busy' or event == 'my-top-record-empty' or event == 'my-top-record-own':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'my-record-busy-replace' or event == 'my-record-empty-replace' or event == 'my-record-own-replace':
                self.state = 'ROTATE?'
                self.doRotateRequestCurBroker(*args, **kwargs)
        #---VERIFY_DHT---
        elif self.state == 'VERIFY_DHT':
            if event == 'top-record-own' or event == 'top-record-empty':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'prev-record-empty':
                self.state = 'NEW?'
                self.doHireNewBroker(event, *args, **kwargs)
            elif event == 'record-busy' or event == 'prev-record-busy':
                self.state = 'CURRENT?'
                self.doRequestCurBroker(event, *args, **kwargs)
            elif event == 'top-record-busy' or event == 'prev-record-own':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---CURRENT?---
        elif self.state == 'CURRENT?':
            if event == 'broker-accepted':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'broker-failed' or event == 'broker-timeout':
                self.state = 'NEW?'
                self.doHireNewBroker(event, *args, **kwargs)
            elif event == 'broker-rejected' or event == 'broker-denied':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---NEW?---
        elif self.state == 'NEW?':
            if event == 'hire-broker-ok':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'new-broker-rejected' or event == 'hire-broker-failed':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---ROTATE?---
        elif self.state == 'ROTATE?':
            if event == 'broker-rotate-failed' or event == 'broker-rotate-timeout' or event == 'broker-rotate-accepted':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'broker-rotate-rejected' or event == 'broker-rotate-denied':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doRefreshDHT(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---ACCEPT---
        elif self.state == 'ACCEPT':
            pass
        #---REJECT---
        elif self.state == 'REJECT':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.broker_negotiate_ack_timeout = config.conf().getInt('services/message-broker/broker-negotiate-ack-timeout')
        self.my_position = kwargs['my_position']
        self.cooperated_brokers = kwargs['cooperated_brokers'] or {}
        self.dht_brokers = kwargs['dht_brokers']
        self.customer_idurl = kwargs['customer_idurl']
        self.my_broker_idurl = kwargs['broker_idurl']
        self.my_broker_id = self.my_broker_idurl.to_id()
        self.connect_request = kwargs['connect_request']
        self.result_defer = kwargs['result']
        self.desired_position = self.connect_request['desired_position']
        self.requestor_known_brokers = self.connect_request['known_brokers'] or {}
        self.automat('init-done')

    def isAlreadyCooperated(self, *args, **kwargs):
        return self.my_position is not None and self.my_position >= 0

    def doVerifyDHTRecords(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, desired=self.desired_position, dht=self.dht_brokers)
        if not self.dht_brokers.get(self.desired_position):
            # desired position is empty in DHT
            if self.desired_position == 0:
                self.automat('top-record-empty')
            else:
                prev_position = self.desired_position - 1
                if not self.dht_brokers.get(prev_position):
                    # also previous position in DHT is empty as well
                    self.automat('prev-record-empty')
                else:
                    if id_url.is_the_same(self.dht_brokers[prev_position], self.my_broker_idurl):
                        # found my DHT record on a previous position - request was done on another position
                        self.automat('prev-record-own', dht_brokers=self.dht_brokers)
                    else:
                        # found another broker on the previous position in DHT
                        self.automat('prev-record-busy')
            return
        if id_url.is_the_same(self.dht_brokers[self.desired_position], self.my_broker_idurl):
            # my own record is present in DHT on that position
            if self.desired_position == 0:
                self.automat('top-record-own')
            else:
                prev_position = self.desired_position - 1
                if not self.dht_brokers.get(prev_position):
                    # but the previous position in DHT is empty
                    self.automat('prev-record-empty')
                else:
                    if id_url.is_the_same(self.dht_brokers[prev_position], self.my_broker_idurl):
                        # found my DHT record on a previous position - this is wrong!
                        self.automat('prev-record-own', dht_brokers=self.dht_brokers)
                    else:
                        # found another broker on the previous position in DHT
                        self.automat('prev-record-busy')
                # self.automat('record-own')
            return
        # desired position is occupied by another broker in DHT records
        if self.desired_position == 0:
            self.automat('top-record-busy', dht_brokers=self.dht_brokers)
        else:
            self.automat('record-busy')

    def doVerifyKnownBrokers(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, desired=self.desired_position, cooperated=self.cooperated_brokers)
        # cooperation was done before with other brokers and my own position is known already to me
        if self.desired_position != self.my_position:
            # but the request was done to a wrong position
            lg.warn('requester desired position %d mismatch, my current position is: %d' % (self.desired_position, self.my_position))
            self.automat('request-invalid', Exception('position mismatch, current position is: %d' % self.my_position), cooperated_brokers=self.cooperated_brokers)
            return
        if not self.cooperated_brokers.get(self.my_position):
            # there is no broker present in the cooperation for my position
            lg.err('my current cooperated info is not valid, there is no broker on position %d' % self.my_position)
            self.automat('request-invalid', Exception('current cooperation is not valid, there is no broker on position %d' % self.my_position))
            return
        if not id_url.is_the_same(self.cooperated_brokers[self.my_position], self.my_broker_idurl):
            # looks like my current deal is not correct - another broker is taking my position
            lg.err('my current cooperated info is not correct, another broker is taking my position')
            self.automat('request-invalid', Exception('current cooperation is not valid, another broker is taking position %d' % self.my_position))
            return
        if self.my_position > 0:
            prev_position = self.my_position - 1
            if not self.cooperated_brokers.get(prev_position):
                # but on the previous position there is no broker present in the cooperation
                lg.err('my current cooperated info is not valid, there is no broker on previous position %d' % prev_position)
                self.automat('request-invalid', Exception('current cooperation is not valid, there is no broker on previous position %d' % prev_position))
                return
        # requester is trying to connect to me on the correct position
        if self.requestor_known_brokers.get(self.my_position):
            if not id_url.is_the_same(self.requestor_known_brokers[self.my_position], self.my_broker_idurl):
                # but there is a request to change the cooperation - it looks like a trigger for a brokers rotation
                lg.warn('received a request to change the cooperation, another broker %r going to replace me on position %d' % (self.requestor_known_brokers[self.my_position], self.my_position))
                if not self.dht_brokers.get(self.my_position):
                    # there is no record in DHT for my position
                    # my info is not stored in DHT and another broker is going to replace me
                    # but there is already a cooperation done before and my own position is known to me
                    if self.my_position == 0:
                        self.automat('my-top-record-empty-replace')
                    else:
                        self.automat('my-record-empty-replace')
                    return
                # there is a record in DHT on my expected position while another broker is trying to replace me
                if not id_url.is_the_same(self.dht_brokers[self.my_position], self.my_broker_idurl):
                    # DHT record on my expected position is occupied by another broker
                    lg.warn(
                        'DHT record on my expected position %d is occupied by another broker %r and also another broker is trying to replace me: %r' % (
                            self.my_position,
                            self.dht_brokers[self.my_position],
                            self.requestor_known_brokers[self.my_position],
                        ),
                    )
                    if self.my_position == 0:
                        self.automat('my-top-record-busy-replace')
                    else:
                        self.automat('my-record-busy-replace')
                    return
                # found my own record on the expected position in DHT while another broker is trying to replace me
                if self.my_position == 0:
                    self.automat('my-top-record-own-replace')
                else:
                    self.automat('my-record-own-replace')
                return
        # requester is not going to change the existing cooperation for my own position
        if not self.dht_brokers.get(self.my_position):
            # but in DHT my own record is missing on the expected position
            lg.warn('DHT record on my expected position %d is empty' % self.my_position)
            if self.my_position == 0:
                self.automat('my-top-record-empty')
            else:
                self.automat('my-record-empty')
            return
        # there is a record in DHT on my expected position
        if not id_url.is_the_same(self.dht_brokers[self.my_position], self.my_broker_idurl):
            # DHT record on my expected position is occupied by another broker
            lg.warn('DHT record on my expected position %d is occupied by another broker: %r' % (self.my_position, self.dht_brokers[self.my_position]))
            if self.my_position == 0:
                self.automat('my-top-record-busy')
            else:
                self.automat('my-record-busy')
            return
        # found my own record on expected position in DHT
        if self.my_position == 0:
            self.automat('my-top-record-own')
        else:
            self.automat('my-record-own')

    def doRequestCurBroker(self, event, *args, **kwargs):
        """
        Action method.
        """
        target_pos = self.desired_position
        known_brokers = {}
        known_brokers.update(self.cooperated_brokers or {})
        if event in [
            'record-busy',
        ]:
            # there is no cooperation done yet but current record in DHT on that position belongs to another broker
            target_pos = self.desired_position
            broker_idurl = id_url.field(self.dht_brokers[target_pos])
            known_brokers[self.desired_position] = self.my_broker_idurl
        elif event in [
            'prev-record-busy',
        ]:
            # there is no cooperation done yet but found another broker on the previous position in DHT
            target_pos = self.desired_position - 1
            broker_idurl = id_url.field(self.dht_brokers[target_pos])
            known_brokers[self.desired_position] = self.my_broker_idurl
        elif event in [
            'my-record-busy',
            'my-record-empty',
            'my-record-own',
        ]:
            # me and two other brokers already made a cooperation, connecting again with already known previous broker
            target_pos = self.my_position - 1
            broker_idurl = id_url.field(self.cooperated_brokers[target_pos])
            known_brokers[self.my_position] = self.my_broker_idurl
        if _Debug:
            lg.args(_DebugLevel, e=event, my=self.my_position, desired=self.desired_position, target=target_pos, broker=broker_idurl, known=known_brokers)
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=broker_idurl,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params(idurl, target_pos, known_brokers, event),
            request_service_timeout=self.broker_negotiate_ack_timeout*(target_pos + 1),
            force_handshake=True,
            attempts=1,
        )
        result.addCallback(self._on_cur_broker_connected, target_pos, self.my_position, self.desired_position, event)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='broker_negotiator.doRequestCurBroker')
        result.addErrback(self._on_cur_broker_connect_failed, target_pos, event)

    def doRotateRequestCurBroker(self, *args, **kwargs):
        """
        Action method.
        """
        target_pos = self.my_position - 1
        broker_idurl = id_url.field(self.cooperated_brokers[target_pos])
        known_brokers = {}
        known_brokers.update(self.cooperated_brokers or {})
        known_brokers.update(self.requestor_known_brokers or {})
        known_brokers[target_pos] = self.my_broker_idurl
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, target=target_pos, broker=broker_idurl, known=known_brokers)
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=broker_idurl,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params(idurl, target_pos, known_brokers, None),
            request_service_timeout=self.broker_negotiate_ack_timeout*(target_pos + 1),
            force_handshake=True,
            attempts=1,
        )
        result.addCallback(self._on_rotate_broker_connected, target_pos, None)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='broker_negotiator.doRotateRequestCurBroker')
        result.addErrback(self._on_rotate_broker_connect_failed, target_pos, None)

    def doRefreshDHT(self, event, *args, **kwargs):
        """
        Action method.
        """
        # TODO: write my known record to DHT

    def doHireNewBroker(self, event, *args, **kwargs):
        """
        Action method.
        """
        known_brokers = {}
        known_brokers.update(self.cooperated_brokers or {})
        known_brokers[self.desired_position] = self.my_broker_idurl
        target_pos = self.desired_position - 1
        exclude_brokers = list(id_url.to_bin_list(filter(None, self.dht_brokers.values())))
        exclude_brokers.extend(list(id_url.to_bin_list(filter(None, self.requestor_known_brokers.values()))))
        preferred_brokers = []
        preferred_brokers_raw = config.conf().getString('services/message-broker/preferred-brokers').strip()
        if preferred_brokers_raw:
            preferred_brokers_list = re.split('\n|,|;| ', preferred_brokers_raw)
            preferred_brokers.extend(preferred_brokers_list)
            preferred_brokers = id_url.to_bin_list(preferred_brokers)
        if preferred_brokers:
            preferred_brokers = [x for x in preferred_brokers if x not in exclude_brokers]
        if _Debug:
            lg.args(_DebugLevel, e=event, my=self.my_position, desired=self.desired_position, target=target_pos, exclude=exclude_brokers, preferred=preferred_brokers)
        if preferred_brokers:
            preferred_broker_idurl = id_url.field(preferred_brokers[0])
            if preferred_broker_idurl and id_url.is_not_in(preferred_broker_idurl, exclude_brokers, as_field=False):
                result = p2p_service_seeker.connect_known_node(
                    remote_idurl=preferred_broker_idurl,
                    service_name='service_message_broker',
                    service_params=lambda idurl: self._do_prepare_service_request_params(idurl, target_pos, known_brokers, event),
                    request_service_timeout=self.broker_negotiate_ack_timeout*(target_pos + 1),
                    exclude_nodes=list(exclude_brokers),
                    force_handshake=True,
                    attempts=1,
                )
                result.addCallback(self._on_new_broker_hired, target_pos, self.my_position, self.desired_position)
                result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='broker_negotiator.doHirePrevBroker')
                result.addErrback(self._on_new_broker_lookup_failed, target_pos)
                return
        result = p2p_service_seeker.connect_random_node(
            lookup_method=lookup.random_message_broker,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params(idurl, target_pos, known_brokers, event),
            request_service_timeout=self.broker_negotiate_ack_timeout*(target_pos + 1),
            exclude_nodes=list(exclude_brokers),
            attempts=1,
            force_handshake=True,
        )
        result.addCallback(self._on_new_broker_hired, target_pos, self.my_position, self.desired_position)
        result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='broker_negotiator.doHirePrevBroker')
        result.addErrback(self._on_new_broker_lookup_failed, target_pos)

    def doAccept(self, event, *args, **kwargs):
        """
        Action method.
        """
        # TODO: add an additional validation here (signature, DHT record revisions, order, etc. )
        self.cooperated_brokers.clear()
        if self.requestor_known_brokers:
            self.cooperated_brokers.update(self.requestor_known_brokers)
        if event in [
            'my-top-record-busy',
            'my-top-record-empty',
            'my-top-record-own',
        ]:
            self.cooperated_brokers[self.my_position] = self.my_broker_idurl
        elif event in [
            'top-record-own',
            'top-record-empty',
        ]:
            self.cooperated_brokers[self.desired_position] = self.my_broker_idurl
        elif event in [
            'broker-accepted',
            'hire-broker-ok',
        ]:
            accepted_brokers = kwargs.get('cooperated_brokers', {}) or {}
            accepted_brokers.pop('archive_folder_path', None)
            self.cooperated_brokers.update(accepted_brokers)
            self.cooperated_brokers[self.desired_position] = self.my_broker_idurl
        elif event in [
            'broker-rotate-failed',
            'broker-rotate-timeout',
            'broker-rotate-accepted',
        ]:
            accepted_brokers = kwargs.get('cooperated_brokers', {}) or {}
            accepted_brokers.pop('archive_folder_path', None)
            self.cooperated_brokers.update(accepted_brokers)
            self.cooperated_brokers[self.my_position - 1] = self.my_broker_idurl
        if _Debug:
            lg.args(_DebugLevel, e=event, cooperated_brokers=self.cooperated_brokers)
        reactor.callLater(0, self.result_defer.callback, self.cooperated_brokers)  # @UndefinedVariable

    def doReject(self, event, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, e=event, a=args, kw=kwargs)
        reactor.callLater(0, self.result_defer.errback, Exception(event, args, kwargs))  # @UndefinedVariable

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.my_broker_idurl = None
        self.my_position = None
        self.cooperated_brokers = None
        self.dht_brokers = None
        self.customer_idurl = None
        self.connect_request = None
        self.requestor_known_brokers = None
        self.result_defer = None
        self.destroy()

    def _do_prepare_service_request_params(self, possible_broker_idurl, desired_broker_position, known_brokers, event):
        req = {
            'action': 'queue-connect-follow',
            'consumer_id': self.connect_request['consumer_id'],
            'producer_id': self.connect_request['producer_id'],
            'group_key': self.connect_request['group_key_info'],
            'position': desired_broker_position,
            'archive_folder_path': self.connect_request['archive_folder_path'],
            'last_sequence_id': self.connect_request['last_sequence_id'],
            'known_brokers': known_brokers,
        }
        if _Debug:
            lg.args(_DebugLevel, e=event, broker=possible_broker_idurl, desired=desired_broker_position, known=known_brokers)
        return req

    def _on_cur_broker_connected(self, response_info, broker_pos, my_pos, desired_pos, event, *args, **kwargs):
        try:
            # skip leading "accepted:" marker
            cooperated_brokers = jsn.loads(strng.to_text(response_info[0].Payload)[9:])
            cooperated_brokers.pop('archive_folder_path', None)
            cooperated_brokers = {int(k): id_url.field(v) for k, v in cooperated_brokers.items()}
        except:
            lg.exc()
            self.automat('broker-failed')
            return
        if _Debug:
            lg.args(_DebugLevel, cooperated=cooperated_brokers, target=broker_pos, my=my_pos, desired=desired_pos, e=event, args=args, kwargs=kwargs)
        if my_pos >= 0:
            if id_url.is_the_same(cooperated_brokers.get(my_pos), self.my_broker_idurl):
                self.automat('broker-accepted', cooperated_brokers=cooperated_brokers)
                return
        if desired_pos >= 0:
            if id_url.is_the_same(cooperated_brokers.get(desired_pos), self.my_broker_idurl):
                self.automat('broker-accepted', cooperated_brokers=cooperated_brokers)
                return
        self.automat('broker-rejected', cooperated_brokers=cooperated_brokers)

    def _on_cur_broker_connect_failed(self, err, broker_pos, event, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, pos=broker_pos, e=event, args=args, kwargs=kwargs)
        if isinstance(err, Failure):
            try:
                evt, _, kw = err.value.args
            except:
                lg.exc()
                return
            if _Debug:
                lg.args(_DebugLevel, evt=evt, kw=kw)
            if evt == 'request-failed':
                if kw.get('reason') == 'service-denied':
                    self.automat('broker-denied')
                    return
        self.automat('broker-failed')

    def _on_new_broker_hired(self, response_info, broker_pos, my_pos, desired_pos, *args, **kwargs):
        try:
            # skip leading "accepted:" marker
            cooperated_brokers = jsn.loads(strng.to_text(response_info[0].Payload)[9:])
            cooperated_brokers.pop('archive_folder_path', None)
            cooperated_brokers = {int(k): id_url.field(v) for k, v in cooperated_brokers.items()}
        except:
            lg.exc()
            self.automat('hire-broker-failed')
            return
        if _Debug:
            lg.args(_DebugLevel, cooperated=cooperated_brokers, target=broker_pos, my=my_pos, desired=desired_pos, args=args, kwargs=kwargs)
        if my_pos >= 0:
            if id_url.is_the_same(cooperated_brokers.get(my_pos), self.my_broker_idurl):
                self.automat('hire-broker-ok', cooperated_brokers=cooperated_brokers)
                return
        if desired_pos >= 0:
            if id_url.is_the_same(cooperated_brokers.get(desired_pos), self.my_broker_idurl):
                self.automat('hire-broker-ok', cooperated_brokers=cooperated_brokers)
                return
        lg.warn('new broker is not cooperative, my idurl is not found in the cooperation on the right place')
        self.automat('new-broker-rejected', cooperated_brokers=cooperated_brokers)

    def _on_new_broker_lookup_failed(self, err, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, broker_pos=broker_pos)
        if isinstance(err, Failure):
            try:
                evt, _, kw = err.value.args
            except:
                lg.exc()
                return
            if _Debug:
                lg.args(_DebugLevel, evt=evt, kw=kw)
            if evt == 'request-failed':
                if kw.get('reason') == 'service-denied':
                    self.automat('new-broker-rejected', **kw)
                    return
        self.automat('hire-broker-failed')

    def _on_rotate_broker_connected(self, response_info, broker_pos, event, *args, **kwargs):
        try:
            # skip leading "accepted:" marker
            cooperated_brokers = jsn.loads(strng.to_text(response_info[0].Payload)[9:])
            cooperated_brokers.pop('archive_folder_path', None)
            cooperated_brokers = {int(k): id_url.field(v) for k, v in cooperated_brokers.items()}
        except:
            lg.exc()
            self.automat('broker-rotate-failed')
            return
        if _Debug:
            lg.args(_DebugLevel, cooperated=cooperated_brokers, pos=broker_pos, e=event)
        if id_url.is_the_same(cooperated_brokers.get(broker_pos), self.my_broker_idurl):
            self.automat('broker-rotate-accepted', cooperated_brokers=cooperated_brokers)
            return
        self.automat('broker-rotate-rejected', cooperated_brokers=cooperated_brokers)

    def _on_rotate_broker_connect_failed(self, err, broker_pos, event, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, pos=broker_pos, e=event, args=args, kwargs=kwargs)
        if isinstance(err, Failure):
            try:
                evt, _, kw = err.value.args
            except:
                lg.exc()
                return
            if _Debug:
                lg.args(_DebugLevel, evt=evt, kw=kw)
            if evt == 'request-failed':
                if kw.get('reason') == 'service-denied':
                    self.automat('broker-rotate-denied', **kw)
                    return
        self.automat('broker-rotate-failed')
