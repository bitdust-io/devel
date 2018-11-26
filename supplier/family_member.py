#!/usr/bin/env python
# family_member.py
#


"""
.. module:: family_member
.. role:: red

BitDust family_member() Automat

EVENTS:
    * :red:`connect`
    * :red:`dht-fail`
    * :red:`dht-ok`
    * :red:`dht-value-exist`
    * :red:`dht-value-not-exist`
    * :red:`disconnect`
    * :red:`init`
    * :red:`instant`
    * :red:`request`
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

from userid import my_id

from dht import dht_relations

#------------------------------------------------------------------------------

_CustomersFamilies = {}

#------------------------------------------------------------------------------

def families():
    """
    """
    global _CustomersFamilies
    return _CustomersFamilies


def create(customer_idurl):
    """
    """
    if customer_idurl not in families():
        raise Exception('FamilyMember for %s already exists' % customer_idurl)
    families()[customer_idurl] = FamilyMember(customer_idurl)
    return families()[customer_idurl]


def by_idurl(customer_idurl):
    return families().get(customer_idurl, None)

#------------------------------------------------------------------------------

class FamilyTransaction(object):

    def __init__(self, cmd, *args, **kwargs):
        self.cmd = cmd
        if self.cmd == 'ecc.set':
            self.new_ecc_name = args[0]
        elif self.cmd == 'supplier.set':
            self.new_supplier_pos = args[0]
        elif self.cmd == 'supplier.add':
            self.new_supplier_add = args[0]

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
            elif event == 'disconnect' or event == 'dht-fail':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'request':
                self.doPush(event, *args, **kwargs)
        #---SUPPLIERS---
        elif self.state == 'SUPPLIERS':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'request':
                self.doPush(event, *args, **kwargs)
            elif event == 'suppliers-ok':
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
            elif event == 'disconnect' or event == 'suppliers-fail':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-ok':
                self.state = 'CONNECTED'
                self.doNotifyConnected(*args, **kwargs)
            elif event == 'disconnect' or event == 'dht-fail':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'request':
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
            elif event == 'request':
                self.doPush(event, *args, **kwargs)
            elif event == 'connect' or ( event == 'instant' and self.isAnyRequests(*args, **kwargs) ):
                self.state = 'DHT_READ'
                self.doPull(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'request':
                self.doPush(event, *args, **kwargs)
            elif event == 'connect' or ( event == 'instant' and self.isAnyRequests(*args, **kwargs) ):
                self.state = 'DHT_READ'
                self.doPull(event, *args, **kwargs)
                self.doDHTRead(*args, **kwargs)
        return None

    def isAnyRequests(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.changes) > 0

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.requests = []
        self.current_request = None
        self.current_family_info = {}
        self.new_family_info = {}

    def doPush(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.requests.append(event)

    def doPull(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.current_request = self.requests.pop(0)

    def doRebuildFamily(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            dht_value = args[0]
            _current_suppliers = dht_value['suppliers']
            dht_value = ''
        except:
            return
        self.current_suppliers = ''

        result = args[0]
        
        if result is None:
            pass

    def doNotifySuppliers(self, *args, **kwargs):
        """
        Action method.
        """

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
        d = dht_relations.write_customer_suppliers(self.customer_idurl, self.new_family)
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
        families().pop(self.customer_idurl)
        self.destroy()

    def _on_dht_read_success(self, dht_result):
        self.automat('dht-ok', dht_result)

    def _on_dht_read_failed(self, err):
        lg.err('doDHTRead FAILED: %s' % err)
        
    def _on_dht_write_success(self, dht_result):
        self.automat('dht-ok', dht_result)

    def _on_dht_write_failed(self, err):
        lg.err('doDHTWrite FAILED: %s' % err)
