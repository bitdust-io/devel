#!/usr/bin/env python
# customer_assistant.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (customer_assistant.py) is part of BitDust Software.
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
.. module:: customer_assistant
.. role:: red

BitDust customer_assistant() Automat

EVENTS:
    * :red:`ack`
    * :red:`connect`
    * :red:`disconnect`
    * :red:`fail`
    * :red:`init`
    * :red:`propagate`
    * :red:`shutdown`
    * :red:`timer-10sec`
    * :red:`timer-5min`


TODO: periodically send Request service Customer to be sure that i am still your supplier
if not - remove that customer and stop assistant

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from automats import automat

from logs import lg

from lib import nameurl
from lib import packetid
from lib import diskspace

from main import settings

from crypt import my_keys

from p2p import p2p_service
from p2p import commands

from supplier import list_files

from storage import accounting

#------------------------------------------------------------------------------

_CustomerAssistants = {}

#------------------------------------------------------------------------------

def assistants():
    """
    """
    global _CustomerAssistants
    return _CustomerAssistants


def create(customer_idurl):
    """
    """
    if customer_idurl in assistants():
        raise Exception('CustomerAssistant for %s already exists' % customer_idurl)
    assistants()[customer_idurl] = CustomerAssistant(customer_idurl)
    return assistants()[customer_idurl]


def by_idurl(customer_idurl):
    return assistants().get(customer_idurl, None)

#------------------------------------------------------------------------------

class CustomerAssistant(automat.Automat):
    """
    This class implements all the functionality of the ``customer_assistant()`` state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['PING?']),
        'timer-5min': (300, ['CONNECTED']),
    }

    def __init__(self, customer_idurl):
        """
        Create customer_assistant() state machine for given customer.
        """
        self.customer_idurl = customer_idurl
        self.donated_bytes = accounting.get_customer_quota(self.customer_idurl)
        name = "customer_%s_%s" % (
            nameurl.GetName(self.customer_idurl),
            diskspace.MakeStringFromBytes(self.donated_bytes).replace(' ', ''),
        )
        super(CustomerAssistant, self).__init__(
            name=name,
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=False,
            log_transitions=_Debug,
        )

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of customer_assistant() machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when customer_assistant() state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the customer_assistant()
        but its state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(*args, **kwargs)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'connect':
                self.state = 'PING?'
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'propagate':
                self.state = 'PING?'
        #---PING?---
        elif self.state == 'PING?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack':
                self.state = 'CONNECTED'
                self.doSendHisFiles(*args, **kwargs)
            elif event == 'timer-10sec' or event == 'disconnect' or event == 'fail':
                self.state = 'OFFLINE'
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'disconnect':
                self.state = 'OFFLINE'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-5min':
                self.state = 'PING?'
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'propagate':
                self.state = 'PING?'
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.customer_idurl, wide=True, callbacks={
            commands.Ack(): self._customer_acked,
            commands.Fail(): self._customer_failed,
        })

    def doSendHisFiles(self, *args, **kwargs):
        """
        Action method.
        """
        customer_key_id = my_keys.make_key_id(alias='customer', creator_idurl=self.customer_idurl)
        if my_keys.is_key_registered(customer_key_id):
            list_files.send(
                customer_idurl=self.customer_idurl,
                packet_id='%s:%s' % (customer_key_id, packetid.UniqueID(), ),
                format_type=settings.ListFilesFormat(),
                key_id=customer_key_id,
                remote_idurl=self.customer_idurl,  # send to the customer
            )
        else:
            lg.err('key %s is not registered, not able to send his files' % customer_key_id)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        assistants().pop(self.customer_idurl)
        self.destroy()

    def _customer_acked(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'customer_assistant._customer_acked %r %r' % (response, info))
        self.automat(response.Command.lower(), response)

    def _customer_failed(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'customer_assistant._customer_failed %r %r' % (response, info))
        event_id = 'fail'
        if response:
            event_id = response.Command.lower()
        self.automat(event_id, response)
