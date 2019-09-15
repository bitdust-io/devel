#!/usr/bin/env python
# holler.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (online_status.py) is part of BitDust Software.
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


"""
.. module:: holler
.. role:: red

BitDust holler() Automat

EVENTS:
    * :red:`ack-received`
    * :red:`ack-timeout`
    * :red:`cache-and-ping`
    * :red:`fail-received`
    * :red:`ping`
    * :red:`remote-identity-cached`
    * :red:`remote-identity-failed`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from lib import strng
from lib import packetid

from automats import automat

from contacts import identitycache

from crypt import signed

from p2p import commands

from transport import packet_out
from transport import gateway

from userid import global_id
from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

_OpenedHollers = {}
_KnownChannels = {}

#------------------------------------------------------------------------------

def ping(idurl,
         ack_timeout=10, cache_timeout=5, cache_retries=2, ping_retries=2,
         force_cache=False, skip_outbox=False, keep_alive=True,
         fake_identity=None,
         channel='identity', channel_counter=True,
    ):
    """
    Doing peer-to-peer ping with acknowledgment and return `Deferred` object to receive result.
    First read remote identity file from `idurl` location.
    Then sending my own identity to remote node and wait for ack.
    If Ack() packet from remote node times out (or another error happened)
    should return failed result in the result `Deferred`.
    """
    global _OpenedHollers
    remote_idurl = id_url.field(idurl).to_bin()
    result = Deferred()
    if remote_idurl in _OpenedHollers:
        _OpenedHollers[remote_idurl].append(result)
        if _Debug:
            lg.args(_DebugLevel, already_opened=True, idurl=remote_idurl, channel=channel, skip_outbox=skip_outbox, )
        return result
    _OpenedHollers[remote_idurl] = [result, ]
    if _Debug:
        lg.args(_DebugLevel, already_opened=False, idurl=remote_idurl, channel=channel, skip_outbox=skip_outbox, )
    h = Holler(
        remote_idurl=remote_idurl,
        ack_timeout=ack_timeout,
        cache_timeout=cache_timeout,
        cache_retries=cache_retries,
        ping_retries=ping_retries,
        skip_outbox=skip_outbox,
        keep_alive=keep_alive,
        fake_identity=fake_identity,
        channel=channel,
        channel_counter=channel_counter,
        debug_level=_DebugLevel,
        log_events=_Debug,
        log_transitions=_Debug,
    )
    if force_cache:
        h.automat('cache-and-ping')
    else:
        h.automat('ping')
    return result

#------------------------------------------------------------------------------

class Holler(automat.Automat):
    """
    This class implements all the functionality of ``holler()`` state machine.
    """

    def __init__(self,
                 remote_idurl,
                 ack_timeout, cache_timeout,
                 cache_retries, ping_retries,
                 skip_outbox, keep_alive, fake_identity, channel, channel_counter,
                 debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `holler()` state machine.
        """
        global _KnownChannels
        self.remote_idurl = remote_idurl
        self.ack_timeout = ack_timeout
        self.cache_timeout = cache_timeout
        self.cache_retries = cache_retries
        self.ping_retries = ping_retries
        self.skip_outbox = skip_outbox
        self.keep_alive = keep_alive
        self.fake_identity = fake_identity
        self.channel = channel
        self.channel_counter = channel_counter
        if self.channel not in _KnownChannels:
            _KnownChannels[self.channel] = 0
        _KnownChannels[self.channel] += 1
        super(Holler, self).__init__(
            name="holler_%s_%d_%s" % (self.channel, _KnownChannels[self.channel],
                                      global_id.idurl2glob(self.remote_idurl)),
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
        at creation phase of `holler()` machine.
        """
        self.cache_attempts = 0
        self.ping_attempts = 0

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `holler()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `holler()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'cache-and-ping' or ( event == 'ping' and not self.isCached(*args, **kwargs) ):
                self.state = 'CACHE'
                self.doInit(*args, **kwargs)
                self.doCacheRemoteIDURL(*args, **kwargs)
            elif event == 'ping' and self.isCached(*args, **kwargs):
                self.state = 'ACK?'
                self.doInit(*args, **kwargs)
                self.doSendMyIdentity(*args, **kwargs)
        #---CACHE---
        elif self.state == 'CACHE':
            if event == 'remote-identity-failed' and not self.isMoreCacheRetries(*args, **kwargs):
                self.state = 'NO_IDENT'
                self.doReportNoIdentity(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'remote-identity-failed' and self.isMoreCacheRetries(*args, **kwargs):
                self.doCacheRemoteIDURL(*args, **kwargs)
            elif event == 'remote-identity-cached':
                self.state = 'ACK?'
                self.doSendMyIdentity(*args, **kwargs)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'fail-received':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-received':
                self.state = 'SUCCESS'
                self.doReportSuccess(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-timeout' and not self.isMorePingRetries(*args, **kwargs):
                self.state = 'TIMEOUT'
                self.doReportTimeOut(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-timeout' and self.isMorePingRetries(*args, **kwargs):
                self.doSendMyIdentity(*args, **kwargs)
        #---SUCCESS---
        elif self.state == 'SUCCESS':
            pass
        #---TIMEOUT---
        elif self.state == 'TIMEOUT':
            pass
        #---NO_IDENT---
        elif self.state == 'NO_IDENT':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass


    def isCached(self, *args, **kwargs):
        """
        Condition method.
        """
        return identitycache.HasKey(self.remote_idurl)

    def isMoreCacheRetries(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.cache_attempts <= self.cache_retries

    def isMorePingRetries(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.ping_attempts <= self.ping_retries

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doCacheRemoteIDURL(self, *args, **kwargs):
        """
        Action method.
        """
        self.cache_attempts += 1
        idcache_defer = identitycache.immediatelyCaching(strng.to_text(self.remote_idurl), timeout=self.cache_timeout)
        idcache_defer.addCallback(lambda src: self.automat('remote-identity-cached', src))
        idcache_defer.addErrback(lambda err: self.automat('remote-identity-failed', err))

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        global _KnownChannels
        self.ping_attempts += 1
        if self.fake_identity:
            identity_object = self.fake_identity
        else:
            identity_object = my_id.getLocalIdentity()
        if not identity_object.Valid():
            raise Exception('can not use invalid identity for ping')
        if self.channel_counter:
            packet_id = '%s:%d:%d' % (self.channel, _KnownChannels[self.channel], self.ping_attempts)
        else:
            packet_id = '%s:%s:%d' % (self.channel, packetid.UniqueID(), self.ping_attempts)
        ping_packet = signed.Packet(
            Command=commands.Identity(),
            OwnerID=my_id.getLocalID(),
            CreatorID=my_id.getLocalID(),
            PacketID=packet_id,
            Payload=strng.to_bin(identity_object.serialize()),
            RemoteID=self.remote_idurl,
        )
        if self.skip_outbox:
            packet_out.create(
                outpacket=ping_packet,
                wide=True,
                response_timeout=self.ack_timeout,
                callbacks={
                    commands.Ack(): lambda response, info: self.automat('ack-received', response, info),
                    commands.Fail(): lambda response, info: self.automat('fail-received', response, info),
                    None: lambda pkt_out: self.automat('ack-timeout', pkt_out),
                },
                keep_alive=self.keep_alive,
            )
        else:
            gateway.outbox(
                outpacket=ping_packet,
                wide=True,
                response_timeout=self.ack_timeout,
                callbacks={
                    commands.Ack(): lambda response, info: self.automat('ack-received', response, info),
                    commands.Fail(): lambda response, info: self.automat('fail-received', response, info),
                    None: lambda pkt_out: self.automat('ack-timeout', pkt_out),
                },
                keep_alive=self.keep_alive,
            )
        if _Debug:
            lg.args(_DebugLevel, packet_id=packet_id, remote_idurl=self.remote_idurl, ping_attempts=self.ping_attempts)

    def doReportNoIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        global _OpenedHollers
        lg.warn('failed to cache remote identity %r after %d attempts' % (
            self.remote_idurl, self.cache_attempts, ))
        for result_defer in _OpenedHollers[self.remote_idurl]:
            result_defer.errback(Exception('failed to cache remote identity %r after %d attempts' % (
                self.remote_idurl, self.cache_attempts, )))

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        global _OpenedHollers
        lg.warn('ping failed because received Fail() from remote user %r' % self.remote_idurl)
        for result_defer in _OpenedHollers[self.remote_idurl]:
            result_defer.errback(Exception('ping failed because received Fail() from remote user %r' % self.remote_idurl))

    def doReportTimeOut(self, *args, **kwargs):
        """
        Action method.
        """
        global _OpenedHollers
        lg.warn('remote user %r did not responded after %d ping attempts' % (self.remote_idurl, self.ping_attempts, ))
        for result_defer in _OpenedHollers[self.remote_idurl]:
            result_defer.errback(Exception('remote user %r did not responded after %d ping attempts' % (
                self.remote_idurl, self.ping_attempts, )))

    def doReportSuccess(self, *args, **kwargs):
        """
        Action method.
        """
        global _OpenedHollers
        if _Debug:
            lg.args(_DebugLevel, channel=self.channel, idurl=self.remote_idurl, ack_packet=args[0], info=args[1])
        for result_defer in _OpenedHollers[self.remote_idurl]:
            result_defer.callback((args[0], args[1], ))

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _OpenedHollers
        if self.remote_idurl in _OpenedHollers:
            _OpenedHollers.pop(self.remote_idurl)
        else:
            lg.warn('did not found my registered opened instance')
        self.remote_idurl = None
        self.ack_timeout = None
        self.cache_timeout = None
        self.cache_retries = None
        self.ping_retries = None
        self.skip_outbox = None
        self.fake_identity = None
        self.channel = None
        self.channel_counter = None
        self.destroy()

