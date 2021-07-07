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
    * :red:`connect`
    * :red:`cur-broker-accepted`
    * :red:`cur-broker-failed`
    * :red:`cur-broker-rejected`
    * :red:`cur-broker-timeout`
    * :red:`hire-broker-failed`
    * :red:`hire-broker-ok`
    * :red:`my-record-invalid`
    * :red:`my-record-missing`
    * :red:`prev-broker-accepted`
    * :red:`prev-broker-failed`
    * :red:`prev-broker-rejected`
    * :red:`prev-broker-timeout`
    * :red:`prev-record-busy`
    * :red:`prev-record-empty`
    * :red:`prev-record-own`
    * :red:`record-busy`
    * :red:`record-empty`
    * :red:`record-own`
    * :red:`record-rotate`
    * :red:`request-invalid`
    * :red:`top-place-busy`
    * :red:`top-place-empty`
    * :red:`top-place-own`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import re

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in broker_negotiator.py')

from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from automats import automat

from logs import lg

from lib import strng
from lib import jsn

from main import config

from p2p import lookup
from p2p import p2p_service_seeker

from userid import id_url

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
        self.broker_idurl = None
        self.broker_id = None
        self.my_position = None
        self.desired_position = None
        self.cooperated_brokers = None
        self.dht_brokers = None
        self.customer_idurl = None
        self.customer_id = None
        self.queue_id = None
        self.archive_folder_path = None
        self.requestor_known_brokers = None
        self.group_key_info = None
        super(BrokerNegotiator, self).__init__(
            name="broker_negotiator",
            state="AT_STARTUP",
            debug_level=debug_level or _DebugLevel,
            log_events=log_events or _Debug,
            log_transitions=log_transitions or _Debug,
            publish_events=publish_events,
            **kwargs
        )

    def __repr__(self):
        return '%s[%s:%s](%s)' % (
            self.id,
            '?' if self.my_position in [None, -1, ] else self.my_position,
            '?' if self.desired_position in [None, -1, ] else self.desired_position, self.state)

    def to_json(self):
        j = super().to_json()
        j.update({
            'customer_id': self.customer_id,
            'broker_id': self.broker_id,
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
                self.state = 'VERIFY'
                self.doInit(*args, **kwargs)
                self.doVerifyMyRecord(*args, **kwargs)
        #---VERIFY---
        elif self.state == 'VERIFY':
            if event == 'record-own':
                self.state = 'PLACE_OWN'
                self.doVerifyPrevRecord(*args, **kwargs)
            elif event == 'record-empty':
                self.state = 'PLACE_EMPTY'
                self.doVerifyPrevRecord(*args, **kwargs)
            elif event == 'request-invalid' or event == 'my-record-missing' or event == 'my-record-invalid':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'record-rotate':
                self.state = 'PLACE_ROTATE'
                self.doVerifyRotatedRecord(*args, **kwargs)
            elif event == 'record-busy':
                self.state = 'THIS_BROKER?'
                self.doRequestThisBroker(*args, **kwargs)
        #---PLACE_OWN---
        elif self.state == 'PLACE_OWN':
            if event == 'prev-record-busy':
                self.state = 'PREV_BROKER?'
                self.doRequestPrevBroker(*args, **kwargs)
            elif event == 'prev-record-own' or event == 'prev-record-empty':
                self.state = 'NEW_BROKER!'
                self.doHirePrevBroker(*args, **kwargs)
            elif event == 'top-place-empty' or event == 'top-place-own':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'top-place-busy':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---PLACE_EMPTY---
        elif self.state == 'PLACE_EMPTY':
            if event == 'prev-record-empty':
                self.state = 'NEW_BROKER!'
                self.doHirePrevBroker(*args, **kwargs)
            elif event == 'top-place-busy' or event == 'prev-record-busy':
                self.state = 'PREV_BROKER?'
                self.doRequestPrevBroker(*args, **kwargs)
            elif event == 'top-place-own' or event == 'top-place-empty':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---PREV_BROKER?---
        elif self.state == 'PREV_BROKER?':
            if event == 'prev-broker-accepted':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'prev-broker-rejected':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'prev-broker-failed' or event == 'prev-broker-timeout':
                self.state = 'NEW_BROKER!'
                self.doHirePrevBroker(*args, **kwargs)
        #---THIS_BROKER?---
        elif self.state == 'THIS_BROKER?':
            if event == 'cur-broker-failed' or event == 'cur-broker-timeout':
                self.state = 'PLACE_EMPTY'
                self.doVerifyPrevRecord(*args, **kwargs)
            elif event == 'cur-broker-accepted' or event == 'cur-broker-rejected':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---NEW_BROKER!---
        elif self.state == 'NEW_BROKER!':
            if event == 'hire-broker-ok':
                self.state = 'ACCEPT'
                self.doAccept(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'hire-broker-failed':
                self.state = 'REJECT'
                self.doReject(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---PLACE_ROTATE---
        elif self.state == 'PLACE_ROTATE':
            if event == 'top-place-busy':
                self.state = 'THIS_BROKER?'
                self.doRequestThisBroker(*args, **kwargs)
            elif event == 'prev-record-busy':
                self.state = 'PREV_BROKER?'
                self.doRequestPrevBroker(*args, **kwargs)
            elif event == 'top-place-own' or event == 'top-place-empty' or event == 'prev-record-own' or event == 'prev-record-empty':
                self.state = 'ACCEPT'
                self.doRotateMyRecord(event, *args, **kwargs)
                self.doAccept(event, *args, **kwargs)
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
        self.my_position = kwargs['my_position']
        self.cooperated_brokers = kwargs['cooperated_brokers'] or {}
        self.dht_brokers = kwargs['dht_brokers']
        self.customer_idurl = kwargs['customer_idurl']
        self.broker_idurl = kwargs['broker_idurl']
        self.connect_request = kwargs['connect_request']
        self.result_defer = kwargs['result']
        self.desired_position = self.connect_request['desired_position']
        self.requestor_known_brokers = self.connect_request['known_brokers'] or {}

    def doVerifyMyRecord(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, desired=self.desired_position, dht=self.dht_brokers, me=self.broker_idurl)
        if self.my_position is not None and self.my_position >= 0:
            if self.my_position not in self.dht_brokers:
                self.automat('my-record-missing')
                return
            if id_url.is_cached(self.dht_brokers[self.my_position]) and id_url.field(self.dht_brokers[self.my_position]) != self.broker_idurl:
                lg.err('my record in DHT is not valid (idurl already cached): %r ~ %r' % (self.dht_brokers[self.my_position], self.broker_idurl))
                self.automat('my-record-invalid')
                return
            if id_url.to_bin(self.dht_brokers[self.my_position]) != self.broker_idurl.to_bin():
                lg.err('my record in DHT is not valid: %r ~ %r' % (self.dht_brokers[self.my_position], self.broker_idurl))
                self.automat('my-record-invalid')
                return
            if self.desired_position != self.my_position:
                if self.desired_position == self.my_position - 1:
                    self.automat('record-rotate')
                    return
                lg.err('desired position %d mismatch, current position is: %d' % (self.desired_position, self.my_position, ))
                self.automat('request-invalid', Exception('position mismatch, current position is: %d' % self.my_position))
                return
        if self.desired_position not in self.dht_brokers or not self.dht_brokers[self.desired_position]:
            self.automat('record-empty')
        else:
            if id_url.is_cached(self.dht_brokers[self.desired_position]) and id_url.field(self.dht_brokers[self.desired_position]) == self.broker_idurl:
                self.automat('record-own')
            elif id_url.to_bin(self.dht_brokers[self.desired_position]) == self.broker_idurl.to_bin():
                self.automat('record-own')
            else:
                self.automat('record-busy')

    def doVerifyPrevRecord(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, desired=self.desired_position, dht=self.dht_brokers)
        if self.desired_position == 0:
            if self.desired_position not in self.dht_brokers or not self.dht_brokers[self.desired_position]:
                self.automat('top-place-empty')
            else:
                if id_url.is_cached(self.dht_brokers[self.desired_position]) and id_url.field(self.dht_brokers[self.desired_position]) == self.broker_idurl:
                    self.automat('top-place-own')
                else:
                    if id_url.to_bin(self.dht_brokers[self.desired_position]) == self.broker_idurl.to_bin():
                        self.automat('top-place-own')
                    else:
                        self.automat('top-place-busy')
            return
        if self.my_position is not None and self.my_position >= 0:
            prev_position = self.my_position - 1
        else:
            prev_position = self.desired_position - 1
        if prev_position not in self.dht_brokers or not self.dht_brokers[prev_position]:
            self.automat('prev-record-empty')
        else:
            if id_url.is_cached(self.dht_brokers[prev_position]) and id_url.field(self.dht_brokers[prev_position]) == self.broker_idurl:
                # TODO: how come ?!
                self.automat('prev-record-own')
            else:
                if id_url.to_bin(self.dht_brokers[prev_position]) == self.broker_idurl.to_bin():
                    # TODO: how come ?!
                    self.automat('prev-record-own')
                else:
                    self.automat('prev-record-busy')

    def doVerifyRotatedRecord(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, desired=self.desired_position, dht=self.dht_brokers)
        rotated_position = self.desired_position
        if rotated_position == 0:
            if rotated_position not in self.dht_brokers or not self.dht_brokers[rotated_position]:
                self.automat('top-place-empty')
            else:
                if id_url.is_cached(self.dht_brokers[rotated_position]) and id_url.field(self.dht_brokers[rotated_position]) == self.broker_idurl:
                    self.automat('top-place-own')
                else:
                    if id_url.to_bin(self.dht_brokers[rotated_position]) == self.broker_idurl.to_bin():
                        self.automat('top-place-own')
                    else:
                        self.automat('top-place-busy')
            return
        if rotated_position not in self.dht_brokers or not self.dht_brokers[rotated_position]:
            self.automat('prev-record-empty')
        else:
            if id_url.is_cached(self.dht_brokers[rotated_position]) and id_url.field(self.dht_brokers[rotated_position]) == self.broker_idurl:
                self.automat('prev-record-own')
            else:
                if id_url.to_bin(self.dht_brokers[rotated_position]) == self.broker_idurl.to_bin():
                    self.automat('prev-record-own')
                else:
                    self.automat('prev-record-busy')

    def doRequestPrevBroker(self, *args, **kwargs):
        """
        Action method.
        """
        target_pos = self.desired_position - 1
        if self.my_position is not None and self.my_position >= 0:
            target_pos = self.my_position - 1
        if target_pos < 0:
            target_pos = 0
        broker_idurl = id_url.field(self.dht_brokers[target_pos])
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, desired=self.desired_position, target_pos=target_pos, broker_idurl=broker_idurl)
        result = p2p_service_seeker.connect_known_node(
            remote_idurl=broker_idurl,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params_prev_broker(idurl, target_pos),
            request_service_timeout=15,
        )
        result.addCallback(self._on_prev_broker_connected, target_pos)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='broker_negotiator.doRequestPrevBroker')
        result.addErrback(self._on_prev_broker_connect_failed, target_pos)

    def doRequestThisBroker(self, *args, **kwargs):
        """
        Action method.
        """
        target_pos = self.desired_position
        broker_idurl = id_url.field(self.dht_brokers[target_pos])
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, desired=self.desired_position, target_pos=target_pos, broker_idurl=broker_idurl)
        d = p2p_service_seeker.connect_known_node(
            remote_idurl=broker_idurl,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params_this_broker(idurl, target_pos),
            request_service_timeout=15,
        )
        d.addCallback(self._on_this_broker_connected, target_pos)
        if _Debug:
            d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='broker_negotiator.doRequestThisBroker')
        d.addErrback(self._on_this_broker_connect_failed, target_pos)

    def doHirePrevBroker(self, *args, **kwargs):
        """
        Action method.
        """
        target_pos = self.desired_position - 1
        if self.my_position is not None and self.my_position >= 0:
            target_pos = self.my_position - 1
        if target_pos < 0:
            target_pos = 0
        exclude_brokers = list(id_url.to_bin_list(filter(None, self.dht_brokers.values())))
        preferred_brokers = []
        preferred_brokers_raw = config.conf().getData('services/message-broker/preferred-brokers').strip()
        if preferred_brokers_raw:
            preferred_brokers_list = re.split('\n|,|;| ', preferred_brokers_raw)
            preferred_brokers.extend(preferred_brokers_list)
            preferred_brokers = id_url.to_bin_list(preferred_brokers)
        if preferred_brokers:
            preferred_brokers = [x for x in preferred_brokers if x not in exclude_brokers]
        if _Debug:
            lg.args(_DebugLevel, my=self.my_position, desired=self.desired_position, target=target_pos, exclude=exclude_brokers, preferred=preferred_brokers)
        if preferred_brokers:
            preferred_broker_idurl = id_url.field(preferred_brokers[0])
            if preferred_broker_idurl and id_url.is_not_in(preferred_broker_idurl, exclude_brokers, as_field=False):
                result = p2p_service_seeker.connect_known_node(
                    remote_idurl=preferred_broker_idurl,
                    service_name='service_message_broker',
                    service_params=lambda idurl: self._do_prepare_service_request_params_hire_broker(idurl, target_pos),
                    request_service_timeout=15,
                    exclude_nodes=list(exclude_brokers),
                )
                result.addCallback(self._on_prev_broker_hired, target_pos)
                if _Debug:
                    result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='broker_negotiator.doHirePrevBroker')
                result.addErrback(self._on_prev_broker_lookup_failed, target_pos)
                return
        result = p2p_service_seeker.connect_random_node(
            lookup_method=lookup.random_message_broker,
            service_name='service_message_broker',
            service_params=lambda idurl: self._do_prepare_service_request_params_hire_broker(idurl, target_pos),
            request_service_timeout=15,
            exclude_nodes=list(exclude_brokers),
        )
        result.addCallback(self._on_prev_broker_hired, target_pos)
        if _Debug:
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='broker_negotiator.doHirePrevBroker')
        result.addErrback(self._on_prev_broker_lookup_failed, target_pos)

    def doRotateMyRecord(self, *args, **kwargs):
        """
        Action method.
        """
        self.my_position -= 1

    def doAccept(self, event, *args, **kwargs):
        """
        Action method.
        """
        if self.requestor_known_brokers:
            # TODO: add an additional validation here
            self.cooperated_brokers.update(self.requestor_known_brokers)
        if event in ['hire-broker-ok', ]:
            self.cooperated_brokers.update(kwargs.get('cooperated_brokers', {}) or {})
        self.cooperated_brokers[self.desired_position] = self.broker_idurl
        self.result_defer.callback(self.cooperated_brokers)

    def doReject(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.result_defer.errback(Exception(event, args, kwargs))

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.broker_idurl = None
        self.my_position = None
        self.cooperated_brokers = None
        self.dht_brokers = None
        self.customer_idurl = None
        self.connect_request = None
        self.requestor_known_brokers = None
        self.result_defer = None
        self.destroy()

    def _do_prepare_service_request_params_prev_broker(self, possible_broker_idurl, desired_broker_position):
        known_brokers = self.cooperated_brokers or {}
        known_brokers.update(self.requestor_known_brokers)
        if self.my_position is not None and self.my_position >= 0:
            known_brokers[self.my_position] = self.broker_idurl
        else:
            known_brokers[self.desired_position] = self.broker_idurl
        req = {
            'action': 'queue-connect-follow',
            # 'queue_id': self.connect_request['queue_id'],
            'consumer_id': self.connect_request['consumer_id'],
            'producer_id': self.connect_request['producer_id'],
            'group_key': self.connect_request['group_key_info'],
            'position': desired_broker_position,
            'archive_folder_path': self.connect_request['archive_folder_path'],
            'last_sequence_id': self.connect_request['last_sequence_id'],
            'known_brokers': known_brokers,
        }
        if _Debug:
            lg.args(_DebugLevel, broker_idurl=possible_broker_idurl, desired=desired_broker_position, req=req)
        return req

    def _do_prepare_service_request_params_this_broker(self, possible_broker_idurl, desired_broker_position):
        known_brokers = self.cooperated_brokers or {}
        known_brokers.update(self.requestor_known_brokers)
        if self.my_position is not None and self.my_position >= 0:
            known_brokers[self.my_position] = self.broker_idurl
        else:
            known_brokers[self.desired_position] = self.broker_idurl
        req = {
            'action': 'queue-connect-follow',
            # 'queue_id': self.connect_request['queue_id'],
            'consumer_id': self.connect_request['consumer_id'],
            'producer_id': self.connect_request['producer_id'],
            'group_key': self.connect_request['group_key_info'],
            'position': desired_broker_position,
            'archive_folder_path': self.connect_request['archive_folder_path'],
            'last_sequence_id': self.connect_request['last_sequence_id'],
            'known_brokers': known_brokers,
        }
        if _Debug:
            lg.args(_DebugLevel, broker_idurl=possible_broker_idurl, desired=desired_broker_position, req=req)
        return req

    def _do_prepare_service_request_params_hire_broker(self, possible_broker_idurl, desired_broker_position):
        known_brokers = self.cooperated_brokers or {}
        known_brokers.update(self.requestor_known_brokers)
        if self.my_position is not None and self.my_position >= 0:
            known_brokers[self.my_position] = self.broker_idurl
        else:
            known_brokers[self.desired_position] = self.broker_idurl
        req = {
            'action': 'queue-connect-follow',
            # 'queue_id': self.connect_request['queue_id'],
            'consumer_id': self.connect_request['consumer_id'],
            'producer_id': self.connect_request['producer_id'],
            'group_key': self.connect_request['group_key_info'],
            'position': desired_broker_position,
            'archive_folder_path': self.connect_request['archive_folder_path'],
            'last_sequence_id': self.connect_request['last_sequence_id'],
            'known_brokers': known_brokers,
        }
        if _Debug:
            lg.args(_DebugLevel, broker_idurl=possible_broker_idurl, desired=desired_broker_position, req=req)
        return req

    def _on_prev_broker_connected(self, response_info, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, resp=response_info, broker_pos=broker_pos, args=args, kwargs=kwargs)
        try:
            # skip leading "accepted:" marker
            cooperated_brokers = jsn.loads(strng.to_text(response_info[0].Payload)[9:])
            cooperated_brokers = {int(k): id_url.field(v) for k,v in cooperated_brokers.items()}
        except:
            lg.exc()
            self.automat('prev-broker-failed')
            return
        self.automat('prev-broker-accepted', cooperated_brokers=cooperated_brokers)

    def _on_prev_broker_connect_failed(self, err, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, broker_pos=broker_pos, args=args, kwargs=kwargs)
        if isinstance(err, Failure):
            try:
                evt, _, _ = err.value.args
            except:
                lg.exc()
                return
            if evt == 'request-failed':
                self.automat('prev-broker-rejected')
                return
        self.automat('prev-broker-failed')

    def _on_this_broker_connected(self, response_info, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, resp=response_info, broker_pos=broker_pos, args=args, kwargs=kwargs)
        self.automat('cur-broker-accepted')

    def _on_this_broker_connect_failed(self, err, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, broker_pos=broker_pos, args=args, kwargs=kwargs)
        if isinstance(err, Failure):
            try:
                evt, _, _ = err.value.args
            except:
                lg.exc()
                return
            if evt == 'request-failed':
                self.automat('cur-broker-rejected')
                return
        self.automat('cur-broker-failed')

    def _on_prev_broker_hired(self, response_info, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, resp=response_info, broker_pos=broker_pos, args=args, kwargs=kwargs)
        try:
            # skip leading "accepted:" marker
            cooperated_brokers = jsn.loads(strng.to_text(response_info[0].Payload)[9:])
            cooperated_brokers = {int(k): id_url.field(v) for k,v in cooperated_brokers.items()}
        except:
            lg.exc()
            self.automat('hire-broker-failed')
            return
        self.automat('hire-broker-ok', cooperated_brokers=cooperated_brokers)

    def _on_prev_broker_lookup_failed(self, err, broker_pos, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, err=err, broker_pos=broker_pos)
        self.automat('hire-broker-failed')
