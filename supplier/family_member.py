#!/usr/bin/env python
# family_member.py
#


"""
.. module:: family_member
.. role:: red

BitDust family_member() Automat

EVENTS:
    * :red:`dht-fail`
    * :red:`dht-ok`
    * :red:`dht-value-exist`
    * :red:`dht-value-not-exist`
    * :red:`disconnect`
    * :red:`family-join`
    * :red:`family-leave`
    * :red:`family-refresh`
    * :red:`init`
    * :red:`instant`
    * :red:`shutdown`
    * :red:`suppliers-fail`
    * :red:`suppliers-ok`
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import nameurl
from lib import strng

from contacts import contactsdb

from dht import dht_relations

from userid import my_id

from raid import eccmap

from p2p import p2p_service

#------------------------------------------------------------------------------

_CustomersFamilies = {}

_ValidRequests = ['family-refresh', 'family-join', 'family-leave', ]

#------------------------------------------------------------------------------

def families():
    """
    """
    global _CustomersFamilies
    return _CustomersFamilies


def create_family(customer_idurl):
    """
    """
    if customer_idurl in families():
        raise Exception('FamilyMember for %s already exists' % customer_idurl)
    families()[customer_idurl] = FamilyMember(customer_idurl)
    return families()[customer_idurl]


def delete_family(customer_idurl):
    if customer_idurl not in families():
        raise Exception('FamilyMember for %s not exist' % customer_idurl)
    families().pop(customer_idurl)
    return True


def by_customer_idurl(customer_idurl):
    return families().get(customer_idurl, None)


#------------------------------------------------------------------------------


class FamilyMember(automat.Automat):
    """
    This class implements all the functionality of ``family_member()`` state machine.
    """

    def __init__(
            self,
            customer_idurl,
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
            publish_events=False,
            **kwargs
        ):
        """
        Builds `family_member()` state machine.
        """
        self.customer_idurl = customer_idurl
        self.supplier_idurl = my_id.getLocalIDURL()
        super(FamilyMember, self).__init__(
            name="family_member_%s" % nameurl.GetName(self.customer_idurl),
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `family_member()` state were changed.
        """
        if newstate in ['CONNECTED', 'DISCONNECTED', ]:
            self.automat('instant')

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `family_member()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'DISCONNECTED'
                self.doInit(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-value-exist' or event == 'dht-value-not-exist':
                self.state = 'SUPPLIERS'
                self.doRebuildFamily(*args, **kwargs)
                self.doNotifySuppliers(*args, **kwargs)
            elif event == 'dht-fail':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
        #---SUPPLIERS---
        elif self.state == 'SUPPLIERS':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'suppliers-ok':
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
            elif event == 'suppliers-fail':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-ok':
                self.state = 'CONNECTED'
                self.doNotifyConnected(*args, **kwargs)
            elif event == 'dht-fail':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'disconnect':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'instant' and self.isAnyRequests(*args, **kwargs):
                self.state = 'DHT_READ'
                self.doPull(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'instant' and self.isAnyRequests(*args, **kwargs):
                self.state = 'DHT_READ'
                self.doPull(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
        return None

    def isAnyRequests(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.requests) > 0

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.local_customer_meta_info = None
        self.requests = []
        self.current_request = None
        self.dht_known_family_info = None
        self.dht_new_family_info = None

    def doPush(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event not in _ValidRequests:
            raise Exception('Invalid request: %r' % args)
        request = args[0] or {}
        request['command'] = event
        self.requests.append(request)

    def doPull(self, *args, **kwargs):
        """
        Action method.
        """
        self.current_request = self.requests.pop(0)

    def doRebuildFamily(self, *args, **kwargs):
        """
        Action method.
        """
        self.dht_known_family_info = args[0]
        if not self.dht_known_family_info:
            self.local_customer_meta_info = contactsdb.get_customer_meta_info(self.customer_idurl)
            self.dht_known_family_info = {
                'suppliers': [],
                'ecc_map': self.local_customer_meta_info.get('ecc_map'),
                'customer_idurl': self.customer_idurl,
            }
        self.dht_new_family_info = self.dht_known_family_info.copy()
        if self.dht_new_family_info['ecc_map']:
            total_suppliers = eccmap.GetEccMapSuppliersNumber(self.dht_new_family_info['ecc_map'])
            if len(self.dht_new_family_info['suppliers']) < total_suppliers:
                self.dht_new_family_info['suppliers'] += [b'', ] * (total_suppliers - len(self.dht_new_family_info['suppliers']))
            elif len(self.dht_new_family_info['suppliers']) > total_suppliers:
                self.dht_new_family_info['suppliers'][:total_suppliers]
        if self.current_request['command'] == 'family-join':
            if self.current_request['position']:
                if self.current_request['position'] > len(self.dht_new_family_info['suppliers']):
                    self.dht_new_family_info['suppliers'] += [b'', ] * (1 + self.current_request['position'] - len(self.dht_new_family_info['suppliers']))
                self.dht_new_family_info['suppliers'][self.current_request['position']] = self.current_request['supplier_idurl']
            else:
                if self.current_request['supplier_idurl'] not in self.dht_new_family_info['suppliers']:
                    self.dht_new_family_info['suppliers'].append(self.current_request['supplier_idurl'])
        elif self.current_request['command'] == 'family-leave':
            known_position = self.dht_new_family_info['suppliers'].index(self.current_request['supplier_idurl'])
            if known_position >= 0:
                self.dht_new_family_info['suppliers'][known_position] = b''
        if _Debug:
            lg.out(_DebugLevel, 'family_member.doRebuildFamily dht_new_family_info=%r' % self.dht_new_family_info)

    def doNotifySuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        for supplier_idurl in self.dht_new_family_info['suppliers']:
            if not supplier_idurl:
                continue
            p2p_service.SendContacts(
                remote_idurl=supplier_idurl,
                space='family_member:%s' % strng.to_text(self.customer_idurl),
                contacts_list=self.dht_new_family_info['suppliers'],
                payload={
                    'ecc_map': self.dht_new_family_info['ecc_map'],
                    'customer_idurl': self.customer_idurl,
                },
            )
        self.automat('suppliers-ok')

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_relations.read_customer_suppliers(self.customer_idurl)
        d.addCallback(self._on_dht_read_success)
        d.addErrback(self._on_dht_read_failed)

    def doDHTWrite(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_relations.write_customer_suppliers(
            customer_idurl=self.customer_idurl,
            suppliers_list=self.dht_new_family_info['suppliers'],
            ecc_map=self.dht_new_family_info['ecc_map'],
        )
        d.addCallback(self._on_dht_write_success)
        d.addErrback(self._on_dht_write_failed)

    def doNotifyConnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doNotifyDisconnected(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.requests = []
        self.current_request = None
        self.local_customer_meta_info = None
        delete_family(self.customer_idurl)
        self.destroy()

    def _on_dht_read_success(self, dht_result):
        if dht_result:
            self.automat('dht-value-exist', dht_result)
        else:
            self.automat('dht-value-not-exist', None)

    def _on_dht_read_failed(self, err):
        lg.err('doDHTRead FAILED: %s' % err)
        
    def _on_dht_write_success(self, dht_result):
        self.automat('dht-ok', dht_result)

    def _on_dht_write_failed(self, err):
        lg.err('doDHTWrite FAILED: %s' % err)
