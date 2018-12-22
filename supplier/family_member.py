#!/usr/bin/env python
# family_member.py
#


"""
.. module:: family_member
.. role:: red

BitDust family_member() Automat

EVENTS:
    * :red:`contacts-received`
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
        if event != 'instant' and newstate in ['CONNECTED', 'DISCONNECTED', ]:
            self.automat('instant')

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `family_member()`
        but automat state was not changed.
        """
        if event != 'instant' and curstate in ['CONNECTED', 'DISCONNECTED', ]:
            self.automat('instant')

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
                self.doSendContactsToSuppliers(*args, **kwargs)
            elif event == 'dht-fail':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
        #---SUPPLIERS---
        elif self.state == 'SUPPLIERS':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'suppliers-fail':
                self.state = 'DISCONNECTED'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
            elif event == 'suppliers-ok' and not self.isFamilyModified(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doNotifyConnected(*args, **kwargs)
            elif event == 'suppliers-ok' and self.isFamilyModified(*args, **kwargs):
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
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
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
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
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
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
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
        return None

    def isAnyRequests(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.requests) > 0

    def isFamilyModified(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.transaction is not None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.requests = []
        self.current_request = None
        self.known_info = None
        self.transaction = None

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
        self._do_build_family_transaction(args[0])

    def doSendContactsToSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        if self.transaction:
            for supplier_idurl in self.transaction['suppliers']:
                if not supplier_idurl:
                    continue
                p2p_service.SendContacts(
                    remote_idurl=supplier_idurl,
                    json_payload={
                        'space': 'family_member',
                        'type': 'suppliers_list',
                        'customer_idurl': self.customer_idurl,
                        'suppliers_list': self.transaction['suppliers'],
                        'ecc_map': self.transaction['ecc_map'],
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
            suppliers_list=self.transaction['suppliers'],
            ecc_map=self.transaction['ecc_map'],
            revision=self.transaction['revision'],
            publisher=self.transaction['publisher'],
        )
        d.addCallback(self._on_dht_write_success)
        d.addErrback(self._on_dht_write_failed)

    def doNotifyConnected(self, *args, **kwargs):
        """
        Action method.
        """
        self.current_request = None

    def doNotifyDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        self.current_request = None

    def doCheckReply(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_check_reply_incoming_contacts(args[0])

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.requests = []
        self.current_request = None
        self.known_info = None
        self.transaction = None
        delete_family(self.customer_idurl)
        self.destroy()

    #------------------------------------------------------------------------------

    def _on_dht_read_success(self, dht_result):
        if dht_result:
            self.automat('dht-value-exist', dht_result)
        else:
            self.automat('dht-value-not-exist', None)

    def _on_dht_read_failed(self, err):
        lg.err('doDHTRead FAILED: %s' % err)
        self.known_info = None
        
    def _on_dht_write_success(self, dht_result):
        self.known_info = self.transaction.copy()
        self.transaction = None
        self.automat('dht-ok', dht_result)

    def _on_dht_write_failed(self, err):
        lg.err('doDHTWrite FAILED: %s' % err)
        self.known_info = None
        self.transaction = None
        self.automat('dht-fail')

    def _do_check_reply_incoming_contacts(self, inp):
        try:
            contacts_type = inp['type']
            incoming_packet = inp['packet']
        except:
            lg.exc()
            return

        if not self.known_info:
            # current DHT info is not yet known, skip
            return p2p_service.SendAck(incoming_packet)

        if self.state in ['DISCONNECTED', 'DHT_READ', ]:
            # currently this family member is not ready yet, skip
            return p2p_service.SendAck(incoming_packet)

        if contacts_type == 'suppliers_list':
            try:
                suppliers_list = inp['suppliers']
                ecc_map = inp['ecc_map']
            except:
                lg.exc()
                return
            if my_id.getLocalIDURL() not in suppliers_list:
                # user trying to remove myself from the family!
                return p2p_service.SendFail(incoming_packet, 'contacts list from remote user does not include my identity')
            if self.known_info['ecc_map'] and ecc_map and self.known_info['ecc_map'] != ecc_map:
                lg.warn('known ecc_map not matching with contacts list received from remote user')
                # TODO: check this later
                # return p2p_service.SendFail(incoming_packet, 'known ecc_map not matching with contacts list received from remote user')
                return p2p_service.SendAck(incoming_packet)
            if len(suppliers_list) != len(self.known_info['suppliers']):
                lg.warn('known number of suppliers not matching with contacts list received from remote user')
                return p2p_service.SendFail(incoming_packet, 'known number of suppliers not matching with contacts list received from remote user')
            return p2p_service.SendAck(incoming_packet)

        elif contacts_type == 'supplier_position':
            try:
                supplier_idurl = inp['supplier_idurl']
                supplier_position = inp['supplier_position']
                ecc_map = inp['ecc_map']
            except:
                lg.exc()
                return
            if supplier_idurl != my_id.getLocalIDURL():
                return p2p_service.SendFail(incoming_packet, 'contacts packet with supplier position not addressed to me')
            try:
                _existing_position = self.known_info['suppliers'].index(supplier_idurl)
            except ValueError:
                _existing_position = -1
            contactsdb.add_customer_meta_info(self.customer_idurl, {
                'ecc_map': ecc_map,
                'position': supplier_position,
            })
            if _existing_position >=0 and _existing_position != supplier_position:
                self.automat('family-join', {
                    'supplier_idurl': supplier_idurl,
                    'ecc_map': ecc_map,
                    'position': supplier_position,
                })
            return p2p_service.SendAck(incoming_packet)

        return p2p_service.SendFail(incoming_packet, 'invalid contacts type')

    def _do_build_family_transaction(self, dht_info):
        modified = False
        expected_suppliers_count = None
        self.known_info = dht_info
        _local_customer_meta_info = contactsdb.get_customer_meta_info(self.customer_idurl)

        if _Debug:
            lg.out(_DebugLevel, 'family_member._do_build_family_transaction  known_info=%s' % self.known_info)

        if not self.known_info:
            self.known_info = {
                'revision': 1,
                'publisher': my_id.getLocalIDURL(),
                'suppliers': [],
                'ecc_map': _local_customer_meta_info.get('ecc_map'),
                'customer_idurl': self.customer_idurl,
            }
            modified = True

        if not self.known_info.get('revision'):
            self.known_info['revision'] = 1

        self.transaction = self.known_info.copy()

        if self.transaction['ecc_map']:
            expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(self.transaction['ecc_map'])
            if len(self.transaction['suppliers']) < expected_suppliers_count:
                self.transaction['suppliers'] += [b'', ] * (expected_suppliers_count - len(self.transaction['suppliers']))
                modified = True
            elif len(self.transaction['suppliers']) > expected_suppliers_count:
                self.transaction['suppliers'] = self.transaction['suppliers'][:expected_suppliers_count]
                modified = True
        else:
            self.transaction['ecc_map'] = _local_customer_meta_info.get('ecc_map')

        if self.current_request['command'] == 'family-join':
            if self.transaction['ecc_map'] and self.current_request['ecc_map']:
                if self.current_request['ecc_map'] != self.transaction['ecc_map']:
                    lg.warn('family-join request must not change ecc_map')
                    self.transaction = None
                    modified = False
                    return
            try:
                _existing_position = self.transaction['suppliers'].index(self.current_request['supplier_idurl'])
            except ValueError:
                _existing_position = -1
            if self.current_request['position'] is not None and self.current_request['position'] >= 0:
                if expected_suppliers_count and self.current_request['position'] >= expected_suppliers_count:
                    lg.warn('family-join request is not valid, supplier position greater than expected suppliers count')
                    self.transaction = None
                    modified = False
                    return
                if _existing_position >= 0 and _existing_position != self.current_request['position']:
                    self.transaction['suppliers'][_existing_position] = b''
                    lg.warn('found my idurl on %d position and will move it on %d position' % (_existing_position, self.current_request['position'], ))
                    modified = True
                if self.current_request['position'] >= len(self.transaction['suppliers']):
                    self.transaction['suppliers'] += [b'', ] * (1 + self.current_request['position'] - len(self.transaction['suppliers']))
                    modified = True
                if self.transaction['suppliers'][self.current_request['position']] != self.current_request['supplier_idurl']:
                    self.transaction['suppliers'][self.current_request['position']] = self.current_request['supplier_idurl']
                    modified = True
            else:
                if self.current_request['supplier_idurl'] not in self.transaction['suppliers']:
                    if b'' in self.transaction['suppliers']:
                        _empty_position = self.transaction['suppliers'].index(b'')
                        self.transaction['suppliers'][_empty_position] = self.current_request['supplier_idurl']
                    else:
                        self.transaction['suppliers'].append(self.current_request['supplier_idurl'])
                    modified = True

        elif self.current_request['command'] == 'family-leave':
            try:
                _existing_position = self.transaction['suppliers'].index(self.current_request['supplier_idurl'])
            except ValueError:
                _existing_position = -1
            if _existing_position >= 0:
                self.transaction['suppliers'][_existing_position] = b''
                modified = True
            else:
                lg.warn('did not found supplier idurl %r in customer family %r' % (
                    self.current_request['supplier_idurl'], self.customer_idurl, ))
                self.transaction = None
                modified = False
                return

        elif self.current_request['command'] == 'family-refresh':
            modified = False

        if not modified:
            self.transaction = None
        else:
            self.transaction['revision'] += 1
            self.transaction['publisher'] = my_id.getLocalIDURL()

        if _Debug:
            lg.out(_DebugLevel, 'family_member._do_build_family_transaction   modified=%s  transaction=%r' % (modified, self.transaction, ))
