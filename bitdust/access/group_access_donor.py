#!/usr/bin/env python
# group_access_donor.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
#
# This file (group_access_donor.py) is part of BitDust Software.
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
.. module:: group_access_donor
.. role:: red

BitDust group_access_donor() Automat

EVENTS:
    * :red:`audit-ok`
    * :red:`fail`
    * :red:`init`
    * :red:`private-key-shared`
    * :red:`shook-hands`
    * :red:`timer-15sec`
    * :red:`timer-30sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import strng

from bitdust.main import events

from bitdust.p2p import handshaker

from bitdust.crypt import my_keys

from bitdust.userid import global_id
from bitdust.userid import id_url

from bitdust.access import key_ring

#------------------------------------------------------------------------------


class GroupAccessDonor(automat.Automat):

    """
    This class implements all the functionality of ``group_access_donor()`` state machine.
    """

    timers = {
        'timer-15sec': (15.0, ['AUDIT']),
        'timer-30sec': (30.0, ['PRIV_KEY']),
    }

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `group_access_donor()` state machine.
        """
        super(GroupAccessDonor,
              self).__init__(name='group_access_donor', state='AT_STARTUP', debug_level=debug_level or _DebugLevel, log_events=log_events or _Debug, log_transitions=log_transitions or _Debug, publish_events=publish_events, **kwargs)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `group_access_donor()` machine.
        """
        self.log_transitions = _Debug
        self.group_key_id = None
        self.result_defer = None

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'HANDSHAKE!'
                self.doInit(*args, **kwargs)
                self.doHandshake(*args, **kwargs)
        #---HANDSHAKE!---
        elif self.state == 'HANDSHAKE!':
            if event == 'fail':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'shook-hands':
                self.state = 'AUDIT'
                self.doAuditUserMasterKey(*args, **kwargs)
        #---AUDIT---
        elif self.state == 'AUDIT':
            if event == 'audit-ok':
                self.state = 'PRIV_KEY'
                self.doSendPrivKeyToUser(*args, **kwargs)
            elif event == 'fail' or event == 'timer-15sec':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---PRIV_KEY---
        elif self.state == 'PRIV_KEY':
            if event == 'private-key-shared':
                self.state = 'SUCCESS'
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'fail' or event == 'timer-30sec':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---SUCCESS---
        elif self.state == 'SUCCESS':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.remote_idurl = id_url.field(kwargs['trusted_idurl'])
        self.group_key_id = strng.to_text(kwargs['group_key_id'])
        self.result_defer = kwargs.get('result_defer', None)

    def doHandshake(self, *args, **kwargs):
        """
        Action method.
        """
        d = handshaker.ping(idurl=self.remote_idurl, channel='group_access_donor', keep_alive=True, force_cache=True)
        d.addCallback(lambda ok: self.automat('shook-hands'))
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_access_donor.doHandshake')
        d.addErrback(lambda err: self.automat('fail'))

    def doAuditUserMasterKey(self, *args, **kwargs):
        """
        Action method.
        """
        master_key_id = my_keys.make_key_id(alias='master', creator_idurl=self.remote_idurl)
        d = key_ring.audit_private_key(master_key_id, self.remote_idurl)
        d.addCallback(lambda audit_result: (self.automat('audit-ok') if audit_result else self.automat('fail', Exception('remote user master key audit process failed'))))
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='group_access_donor.doAuditUserMasterKey')
        d.addErrback(lambda err: self.automat('fail', err))

    def doSendPrivKeyToUser(self, *args, **kwargs):
        """
        Action method.
        """
        d = key_ring.share_key(self.group_key_id, self.remote_idurl, include_private=True, include_signature=True)
        d.addCallback(self._on_user_priv_key_shared)
        d.addErrback(self._on_user_priv_key_failed)

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """
        lg.info('share group key [%s] with %r finished with success' % (self.group_key_id, self.remote_idurl))
        events.send('group-key-shared', data=dict(
            global_id=global_id.UrlToGlobalID(self.remote_idurl),
            remote_idurl=self.remote_idurl,
            group_key_id=self.group_key_id,
        ))
        if self.result_defer:
            self.result_defer.callback(True)

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        lg.warn('share group key [%s] with %s failed: %s' % (self.group_key_id, self.remote_idurl, args))
        reason = 'group key transfer failed with unknown reason'
        if args and args[0]:
            reason = args[0]
        else:
            if event.count('timer-'):
                reason = 'group key transfer failed because of network connection timeout'
        events.send('group-key-share-failed', data=dict(global_id=global_id.UrlToGlobalID(self.remote_idurl), remote_idurl=self.remote_idurl, group_key_id=self.group_key_id, reason=reason))
        if self.result_defer:
            self.result_defer.errback(Exception(reason))

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    def _on_user_priv_key_shared(self, response):
        lg.info('private group key %s was sent to %s' % (self.group_key_id, self.remote_idurl))
        self.automat('private-key-shared', response)
        return None

    def _on_user_priv_key_failed(self, err):
        lg.warn(err)
        self.automat('fail', Exception('private group key delivery failed to remote node'))
        return None
