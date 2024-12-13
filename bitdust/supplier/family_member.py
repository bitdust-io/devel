#!/usr/bin/env python
# family_member.py
#
"""
.. module:: family_member
.. role:: red

BitDust family_member() Automat

EVENTS:
    * :red:`all-suppliers-agree`
    * :red:`contacts-received`
    * :red:`dht-read-fail`
    * :red:`dht-value-exist`
    * :red:`dht-value-not-exist`
    * :red:`dht-write-fail`
    * :red:`dht-write-ok`
    * :red:`disconnect`
    * :red:`family-join`
    * :red:`family-leave`
    * :red:`family-refresh`
    * :red:`init`
    * :red:`instant`
    * :red:`one-supplier-not-agree`
    * :red:`shutdown`
    * :red:`timer-10sec`
"""

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import re

from twisted.internet.task import LoopingCall

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.main import settings

from bitdust.lib import serialization
from bitdust.lib import strng
from bitdust.lib import nameurl

from bitdust.contacts import contactsdb

from bitdust.dht import dht_relations

from bitdust.userid import my_id
from bitdust.userid import id_url

from bitdust.raid import eccmap

from bitdust.p2p import p2p_service
from bitdust.p2p import commands

#------------------------------------------------------------------------------

_CustomersFamilies = {}

_ValidRequests = [
    'family-refresh',
    'family-join',
    'family-leave',
]

#------------------------------------------------------------------------------

DHT_RECORD_REFRESH_INTERVAL = 5*60

#------------------------------------------------------------------------------


def families():
    global _CustomersFamilies
    return _CustomersFamilies


def create_family(customer_idurl):
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl in families():
        raise Exception('another FamilyMember for %s already exists' % customer_idurl)
    families()[customer_idurl] = FamilyMember(customer_idurl)
    return families()[customer_idurl]


def delete_family(customer_idurl):
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in families():
        raise Exception('instance of FamilyMember for %s is not exist' % customer_idurl)
    families().pop(customer_idurl)
    return True


def by_customer_idurl(customer_idurl):
    customer_idurl = id_url.field(customer_idurl)
    return families().get(customer_idurl, None)


#------------------------------------------------------------------------------


class FamilyMember(automat.Automat):

    """
    This class implements all the functionality of ``family_member()`` state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['SUPPLIERS']),
    }

    def __init__(self, customer_idurl, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `family_member()` state machine.
        """
        self.customer_idurl = id_url.field(customer_idurl)
        self.supplier_idurl = my_id.getIDURL().to_bin()
        super(FamilyMember, self).__init__(
            name='family_%s_member_%s' % (
                nameurl.GetName(self.customer_idurl),
                nameurl.GetName(self.supplier_idurl),
            ), state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs
        )

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `family_member()` state were changed.
        """
        if event != 'instant' and newstate in [
            'CONNECTED',
            'DISCONNECTED',
        ]:
            self.automat('instant')

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `family_member()`
        but automat state was not changed.
        """
        if event != 'instant' and curstate in [
            'CONNECTED',
            'DISCONNECTED',
        ]:
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
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'instant' and self.isAnyRequests(*args, **kwargs):
                self.state = 'DHT_READ'
                self.Attempts = 0
                self.doPull(*args, **kwargs)
                self.doDHTRead(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
            elif event == 'dht-read-fail':
                self.state = 'DISCONNECTED'
                self.Attempts = 0
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'dht-value-exist' and self.isMyPositionOK(*args, **kwargs) and not self.isLeaving(*args, **kwargs):
                self.state = 'CONNECTED'
                self.Attempts = 0
                self.doNotifyConnected(*args, **kwargs)
            elif event == 'dht-value-not-exist' or (event == 'dht-value-exist' and not self.isMyPositionOK(*args, **kwargs)):
                self.state = 'SUPPLIERS'
                self.Attempts += 1
                self.doRebuildFamily(*args, **kwargs)
                self.doRequestSuppliersReview(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-value-exist' and self.isMyPositionOK(*args, **kwargs) and self.isLeaving(*args, **kwargs):
                self.state = 'DHT_WRITE'
                self.doRebuildFamily(*args, **kwargs)
                self.doDHTWrite(*args, **kwargs)
        #---SUPPLIERS---
        elif self.state == 'SUPPLIERS':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
            elif (event == 'all-suppliers-agree' or event == 'timer-10sec') and not self.isFamilyModified(*args, **kwargs):
                self.state = 'CONNECTED'
                self.Attempts = 0
                self.doNotifyConnected(*args, **kwargs)
            elif (event == 'timer-10sec' or event == 'all-suppliers-agree') and self.isFamilyModified(*args, **kwargs):
                self.state = 'DHT_WRITE'
                self.doDHTWrite(*args, **kwargs)
            elif event == 'one-supplier-not-agree':
                self.doSolveConflict(*args, **kwargs)
                self.doRequestSuppliersReview(*args, **kwargs)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'family-refresh' or event == 'family-join' or event == 'family-leave':
                self.doPush(event, *args, **kwargs)
            elif event == 'contacts-received':
                self.doCheckReply(*args, **kwargs)
            elif event == 'dht-write-fail' and not self.isLeaving(*args, **kwargs) and self.Attempts > 3:
                self.state = 'DISCONNECTED'
                self.Attempts = 0
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'dht-write-fail' and not self.isLeaving(*args, **kwargs) and self.Attempts <= 3:
                self.state = 'DHT_READ'
                self.doDHTRead(*args, **kwargs)
            elif event == 'shutdown' or ((event == 'dht-write-fail' or event == 'dht-write-ok') and self.isLeaving(*args, **kwargs)):
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'dht-write-ok' and not self.isLeaving(*args, **kwargs):
                self.state = 'CONNECTED'
                self.Attempts = 0
                self.doNotifyConnected(*args, **kwargs)
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
                self.Attempts = 0
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

    def isLeaving(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.current_request and self.current_request['command'] == 'family-leave'

    def isMyPositionOK(self, *args, **kwargs):
        """
        Condition method.
        """
        dht_info_valid = self._do_validate_dht_info(args[0])
        if not dht_info_valid:
            return False
        if self.current_request and self.current_request['command'] == 'family-leave':
            if my_id.getIDURL().to_bin() not in dht_info_valid['suppliers']:
                return True
        my_info_valid = self._do_validate_my_info(self.my_info)
        if not my_info_valid:
            return False
        latest_revision = self._do_detect_latest_revision(dht_info_valid, my_info_valid)
        if latest_revision == 0:
            return False
        try:
            my_position = my_info_valid['suppliers'].index(my_id.getIDURL().to_bin())
        except:
            my_position = -1
        if my_position < 0:
            return False
        try:
            existing_position = dht_info_valid['suppliers'].index(my_id.getIDURL().to_bin())
        except:
            existing_position = -1
        return existing_position > 0 and my_position > 0 and existing_position == my_position

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
        self.dht_info = None
        self.my_info = None
        self.transaction = None
        self.dht_value_exists = False
        self.dht_read_use_cache = True
        self.refresh_period = DHT_RECORD_REFRESH_INTERVAL*settings.DefaultDesiredSuppliers()
        self.refresh_task = LoopingCall(self._on_family_refresh_task)

    def doPush(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event not in _ValidRequests:
            raise Exception('Invalid request: %r' % args)
        request = (args[0] if args else {}) or {}
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
        dht_info_valid = self._do_validate_dht_info(args[0])
        my_info_valid = self._do_validate_my_info(self.my_info)
        latest_revision = self._do_detect_latest_revision(dht_info_valid, my_info_valid)
        merged_info = None
        if latest_revision > 0:
            merged_info = self._do_merge_revisions(dht_info_valid, my_info_valid, latest_revision)
        if not merged_info:
            merged_info = self._do_create_first_revision(self.current_request)


#         if not merged_info:
#             lg.err('failed to merge customer family info after reading from DHT, skip transaction')
#             self.transaction = None
#             return
        possible_transaction = self._do_process_request(merged_info, self.current_request)
        if not possible_transaction:
            lg.warn('failed to process customer family %r change request, skip transaction' % self)
            return
        self.transaction = self._do_increment_revision(possible_transaction)
        if _Debug:
            lg.args(_DebugLevel, transaction=self.transaction)
        if self.transaction:
            known_ecc_map = self.transaction.get('ecc_map')
            if known_ecc_map:
                expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(known_ecc_map)
                self.refresh_period = DHT_RECORD_REFRESH_INTERVAL*expected_suppliers_count

    def doRequestSuppliersReview(self, *args, **kwargs):
        """
        Action method.
        """
        if not self.transaction:
            self.automat('all-suppliers-agree')
            return
        self.suppliers_requests = []
        for supplier_idurl in self.transaction['suppliers']:
            if not supplier_idurl:
                continue
            if supplier_idurl == my_id.getIDURL().to_bin():
                continue
            outpacket = p2p_service.SendContacts(
                remote_idurl=supplier_idurl,
                json_payload={
                    'space': 'family_member',
                    'type': 'suppliers_list',
                    'customer_idurl': self.customer_idurl,
                    'customer_ecc_map': self.transaction['ecc_map'],
                    'transaction_revision': self.transaction['revision'],
                    'suppliers_list': self.transaction['suppliers'],
                },
                callbacks={
                    commands.Ack(): self._on_supplier_ack,
                    commands.Fail(): self._on_supplier_fail,
                },
            )
            self.suppliers_requests.append(outpacket.PacketID)
        if not self.suppliers_requests:
            self.automat('all-suppliers-agree')
        else:
            if _Debug:
                lg.out(_DebugLevel, 'family_member.doRequestSuppliersReview sent to transaction for review to %d suppliers' % len(self.suppliers_requests))

    def doSolveConflict(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO: take in account ecc_map while solving the conflict
        # ecc_map = kwargs.get('ecc_map')
        suppliers_list = kwargs.get('suppliers_list')
        another_supplier_idurl = kwargs.get('supplier_idurl')
        try:
            another_supplier_position = suppliers_list.index(another_supplier_idurl)
        except:
            another_supplier_position = -1
        if another_supplier_position < 0:
            # this must never happen actually... only if another supplier is really uncooperative
            # this is dangerous because can lead to infinite loop between me and another supplier
            lg.err('found uncooperative supplier %s who raised the conflict but replied with invalid response' % another_supplier_idurl)
            # TODO: solve later
            self.transaction = None
        if self.transaction:
            if len(self.transaction['suppliers']) <= another_supplier_position:
                lg.warn('another supplier position larger than family size, failed to solve family conflict with supplier %s' % another_supplier_idurl)
                self.transaction = None
            else:
                if self.transaction['suppliers'][another_supplier_position]:
                    lg.warn('given position is not empty, failed to solve family conflict with supplier %s' % another_supplier_idurl)
                    self.transaction = None
                else:
                    self.transaction['suppliers'][another_supplier_position] = another_supplier_idurl
                    lg.info('found desired position %d in the family and solved conflict with supplier %s' % (another_supplier_position, another_supplier_idurl))

    def doDHTRead(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_relations.read_customer_suppliers(self.customer_idurl, as_fields=False, use_cache=False)
        d.addCallback(self._on_dht_read_success)
        d.addErrback(self._on_dht_read_failed)

    def doDHTWrite(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_write_transaction(0)

    def doNotifyConnected(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'family_member.doNotifyConnected\n            my_info=%r\n            dht_info=%r\n            requests=%r' % (self.my_info, self.dht_info, self.requests))
        to_be_closed = False
        if self.current_request['command'] == 'family-leave':
            to_be_closed = True
        self.current_request = None
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.refresh_task.start(self.refresh_period, now=False)
        if to_be_closed:
            self.requests = []
            self.automat('shutdown')

    def doNotifyDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.current_request = None

    def doCheckReply(self, *args, **kwargs):
        """
        Action method.
        """
        self._on_incoming_contacts_packet(args[0])

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.requests = []
        self.current_request = None
        self.my_info = None
        self.dht_info = None
        self.transaction = None
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.refresh_task = None
        delete_family(self.customer_idurl)
        self.destroy()

    #------------------------------------------------------------------------------

    def _do_validate_dht_info(self, inp):
        if _Debug:
            lg.args(_DebugLevel, inp=inp)
        if not inp or not isinstance(inp, dict):
            self.dht_read_use_cache = False
            return None
        out = inp.copy()
        try:
            dht_revision = int(out['revision'])
            out['suppliers'] = id_url.to_bin_list(out['suppliers'])
            ecc_map = out['ecc_map']
            if dht_revision < 1:
                raise Exception('invalid revision')
            if not isinstance(out['suppliers'], list) or len(out['suppliers']) < 1:
                raise Exception('family %r must include some suppliers' % self)
            if ecc_map and ecc_map not in eccmap.EccMapNames():
                raise Exception('invalid ecc_map name in family %r' % self)
            out['publisher_idurl'] = id_url.field(out['publisher_idurl'])
            # TODO: add publisher_signature and Validate method to check publisher signature
            out['customer_idurl'] = id_url.field(out['customer_idurl'])
            # TODO: add customer_signature and Validate method to check customer signature
        except:
            lg.exc()
            lg.warn('skip invalid DHT info and assume DHT record is not exist')
            self.dht_read_use_cache = False
            return None
        return out

    def _do_validate_my_info(self, inp):
        if not inp:
            return None
        if not inp or not isinstance(inp, dict):
            return None
        out = inp.copy()
        try:
            my_revision = int(out['revision'])
            if my_revision < 1:
                raise Exception('invalid revision')
        except Exception as exc:
            lg.warn(str(exc))
            return None
        try:
            out['suppliers'] = id_url.to_bin_list(out['suppliers'])
            if not isinstance(out['suppliers'], list) or len(out['suppliers']) < 1:
                raise Exception('family %r must include some suppliers' % self)
        except Exception as exc:
            lg.warn(str(exc))
            return None
        try:
            ecc_map = out['ecc_map']
            if ecc_map and ecc_map not in eccmap.EccMapNames():
                raise Exception('invalid ecc_map name in family %r' % self)
        except Exception as exc:
            lg.warn(str(exc))
            return None
        try:
            out['publisher_idurl'] = id_url.field(out['publisher_idurl'])
            # TODO: if I am a publisher - revision number must be the same as my info
        except Exception as exc:
            lg.warn(str(exc))
            return None
        try:
            customer_idurl = id_url.field(out['customer_idurl'])
            if customer_idurl != self.customer_idurl:
                raise Exception('invalid customer_idurl')
        except Exception as exc:
            lg.warn(str(exc))
            return None
        return out

    def _do_create_first_revision(self, request):
        merged_info = {
            'revision': 0,
            'publisher_idurl': my_id.getIDURL(),  # I will be a publisher of the first revision
            'suppliers': id_url.to_bin_list(request.get('family_snapshot') or []),
            'ecc_map': request.get('ecc_map'),
            'customer_idurl': self.customer_idurl,
        }
        if _Debug:
            lg.args(_DebugLevel, merged_info=merged_info)
        return merged_info

    def _do_create_possible_revision(self, latest_revision):
        local_customer_meta_info = contactsdb.get_customer_meta_info(self.customer_idurl)
        try:
            possible_position = int(local_customer_meta_info.get('position', -1))
        except:
            possible_position = -1
        possible_suppliers = id_url.to_bin_list(local_customer_meta_info.get('family_snapshot') or [])
        if possible_position >= 0 and my_id.getIDURL().to_bin() not in possible_suppliers:
            if len(possible_suppliers) > possible_position:
                possible_suppliers[possible_position] = my_id.getIDURL().to_bin()
        my_info = {
            'revision': latest_revision,
            'publisher_idurl': my_id.getIDURL(),  # I will be a publisher of that revision
            'suppliers': possible_suppliers,
            'ecc_map': local_customer_meta_info.get('ecc_map'),
            'customer_idurl': self.customer_idurl,
        }
        if _Debug:
            lg.args(_DebugLevel, my_info=my_info)
        return my_info

    def _do_create_revision_from_another_supplier(self, another_revision, another_suppliers, another_ecc_map):
        local_customer_meta_info = contactsdb.get_customer_meta_info(self.customer_idurl)
        try:
            possible_position = int(local_customer_meta_info.get('position', -1))
        except:
            possible_position = -1
        if possible_position >= 0:
            try:
                another_suppliers[possible_position] = my_id.getIDURL().to_bin()
            except:
                lg.exc()
            contactsdb.add_customer_meta_info(
                self.customer_idurl,
                {
                    'ecc_map': another_ecc_map,
                    'position': possible_position,
                    'family_snapshot': id_url.to_bin_list(another_suppliers),
                },
            )
        return {
            'revision': int(another_revision),
            'publisher_idurl': my_id.getIDURL(),  # I will be a publisher of that revision
            'suppliers': id_url.to_bin_list(another_suppliers),
            'ecc_map': another_ecc_map,
            'customer_idurl': self.customer_idurl,
        }

    def _do_detect_latest_revision(self, dht_info, my_info):
        try:
            my_revision = int(my_info['revision'])
        except:
            lg.warn('my own info is unknown or invalid in %r, assume my revision is 0' % self)
            my_revision = 0
        try:
            dht_revision = int(dht_info['revision'])
        except:
            lg.warn('DHT info is unknown or invalid, assume DHT revision is 0')
            dht_revision = 0
        if my_revision == dht_revision:
            return dht_revision
        if my_revision > dht_revision:
            # TODO: SECURITY need to find a solution to prevent cheating here
            # another supplier could publish a record where he is only alone present and with a correct revision
            # that means he actually brutally dropped all other suppliers from the family
            lg.info('known DHT info for customer %s is more fresh, will rewrite DHT record' % self.customer_idurl)
            if my_revision > dht_revision + 1:
                lg.warn('switching revision too far, normally always increase by one on every change')
            return my_revision
        return dht_revision

    def _do_merge_revisions(self, dht_info, my_info, latest_revision):
        if _Debug:
            lg.args(_DebugLevel, dht_info=dht_info, my_info=my_info, latest_revision=latest_revision)
        if dht_info is None or not isinstance(dht_info, dict):
            merged_info = my_info
        else:
            if latest_revision == int(dht_info['revision']):
                if my_info is not None:
                    if latest_revision == int(my_info['revision']):
                        # I have same revision as info from DHT
                        merged_info = dht_info
                    else:
                        if int(my_info['revision']) > int(dht_info['revision']):
                            # here my revision is higher, so I have some changes that needs to be published already
                            merged_info = my_info
                        else:
                            # here my revision is lower, I need to take info from DHT
                            merged_info = dht_info
                else:
                    merged_info = dht_info
            else:
                # here my revision is higher, so I have some changes that needs to be published already
                merged_info = my_info
        if not merged_info:
            return None
        # make sure list of suppliers have correct length according to ecc_map
        if not merged_info['ecc_map']:
            known_ecc_map = contactsdb.get_customer_meta_info(self.customer_idurl).get('ecc_map', None)
            lg.warn('unknown ecc_map, will populate known value: %s' % known_ecc_map)
            merged_info['ecc_map'] = known_ecc_map
        if merged_info['ecc_map']:
            expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(merged_info['ecc_map'])
            if len(merged_info['suppliers']) < expected_suppliers_count:
                merged_info['suppliers'] += [
                    b'',
                ]*(expected_suppliers_count - len(merged_info['suppliers']))
            elif len(merged_info['suppliers']) > expected_suppliers_count:
                merged_info['suppliers'] = merged_info['suppliers'][:expected_suppliers_count]
        if merged_info['revision'] != latest_revision:
            lg.info('will switch known revision %d to the latest: %d' % (merged_info['revision'], latest_revision))
        merged_info['revision'] = latest_revision
        if _Debug:
            lg.out(_DebugLevel, '    merged_info=%r' % merged_info)
        return merged_info

    def _do_increment_revision(self, possible_transaction):
        if self.customer_idurl.to_original() != possible_transaction['customer_idurl'].to_original():
            possible_transaction['customer_idurl'] = self.customer_idurl
            possible_transaction['revision'] += 1
            possible_transaction['publisher_idurl'] = my_id.getIDURL()
            lg.info('incremented family revision after customer %r identity rotated: %r' % (self.customer_idurl, possible_transaction['revision']))
            return possible_transaction
        if self.dht_info:
            if self.dht_info['suppliers'] == possible_transaction['suppliers']:
                if self.dht_info['ecc_map'] == possible_transaction['ecc_map']:
                    if self.current_request and self.current_request['command'] == 'family-leave':
                        if _Debug:
                            lg.out(_DebugLevel, 'family_member._do_increment_revision will re-publish latest DHT info because processing "family-leave" request')
                    else:
                        if _Debug:
                            lg.out(_DebugLevel, 'family_member._do_increment_revision did not found any changes, skip transaction')
                        return None
        possible_transaction['revision'] += 1
        possible_transaction['publisher_idurl'] = my_id.getIDURL()
        return possible_transaction

    def _do_process_family_join_request(self, merged_info, current_request):
        if _Debug:
            lg.args(_DebugLevel, merged_info=merged_info, current_request=current_request)
        current_request_expected_suppliers_count = None
        if current_request['ecc_map']:
            current_request_expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(current_request['ecc_map'])
        if current_request_expected_suppliers_count and current_request.get('position') and current_request['position'] >= current_request_expected_suppliers_count:
            lg.warn('"family-join" request is not valid, supplier position %d greater than expected suppliers count %d for %s' % (current_request['position'], current_request_expected_suppliers_count, current_request['ecc_map']))
            return None

        if merged_info['ecc_map'] and current_request['ecc_map'] and current_request['ecc_map'] != merged_info['ecc_map']:
            lg.info('from "family-join" request, detected ecc_map change %s -> %s for customer %s' % (merged_info['ecc_map'], current_request['ecc_map'], self.customer_idurl))
            merged_info['ecc_map'] = current_request['ecc_map']
        if not merged_info['ecc_map'] and current_request['ecc_map']:
            lg.info('from "family-join" request, detected ecc_map was set to %s for the first time for customer %s' % (current_request['ecc_map'], self.customer_idurl))
            merged_info['ecc_map'] = current_request['ecc_map']
        if not merged_info['ecc_map']:
            known_ecc_map = contactsdb.get_customer_meta_info(self.customer_idurl).get('ecc_map', None)
            if known_ecc_map:
                lg.warn('unknown ecc_map, will populate known value from customer meta info: %s' % known_ecc_map)
                merged_info['ecc_map'] = known_ecc_map
        if not merged_info['ecc_map']:
            lg.warn('still did not found actual ecc_map from DHT or from the request')
            return None

        expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(merged_info['ecc_map'])
        if not merged_info['suppliers']:
            merged_info['suppliers'] = [
                b'',
            ]*expected_suppliers_count

        if len(merged_info['suppliers']) < expected_suppliers_count:
            merged_info['suppliers'] += [
                b'',
            ]*(expected_suppliers_count - len(merged_info['suppliers']))
        else:
            merged_info['suppliers'] = merged_info['suppliers'][:expected_suppliers_count]

        try:
            existing_position = merged_info['suppliers'].index(current_request['supplier_idurl'])
        except:
            existing_position = -1

        if current_request['position'] is not None and current_request['position'] >= 0:
            if current_request['position'] >= expected_suppliers_count:
                lg.warn('"family-join" request is not valid, supplier position greater than expected suppliers count')
                return None
            if existing_position >= 0 and existing_position != current_request['position']:
                merged_info['suppliers'][existing_position] = b''
                merged_info['suppliers'][current_request['position']] = current_request['supplier_idurl']
                if _Debug:
                    lg.out(_DebugLevel, '    found my IDURL on %d position and will move it on %d position in the family of customer %s' % (existing_position, current_request['position'], self.customer_idurl))
            if merged_info['suppliers'][current_request['position']] != current_request['supplier_idurl']:
                if merged_info['suppliers'][current_request['position']]:
                    # TODO: SECURITY need to implement a signature verification and
                    # also build solution to validate that change was approved by customer
                    lg.warn('overwriting another supplier %s with my IDURL at position %d in family of customer %s' % (merged_info['suppliers'][current_request['position']], current_request['position'], self.customer_idurl))
                merged_info['suppliers'][current_request['position']] = current_request['supplier_idurl']
                if _Debug:
                    lg.out(_DebugLevel, '    placed supplier %s at known position %d in the family of customer %s' % (current_request['supplier_idurl'], current_request['position'], self.customer_idurl))

        if current_request['supplier_idurl'] not in merged_info['suppliers']:
            if b'' in merged_info['suppliers']:
                first_empty_position = merged_info['suppliers'].index(b'')
                merged_info['suppliers'][first_empty_position] = current_request['supplier_idurl']
                if _Debug:
                    lg.out(_DebugLevel, '    placed supplier %s at first empty position %d in family of customer %s' % (current_request['supplier_idurl'], first_empty_position, self.customer_idurl))
            else:
                merged_info['suppliers'].append(current_request['supplier_idurl'])
                if _Debug:
                    lg.out(_DebugLevel, '    added supplier %s to family of customer %s' % (current_request['supplier_idurl'], self.customer_idurl))

        if current_request.get('family_snapshot'):
            for supplier_position in range(len(merged_info['suppliers'])):
                if supplier_position < len(current_request['family_snapshot']):
                    if not merged_info['suppliers'][supplier_position] and current_request['family_snapshot'][supplier_position]:
                        merged_info['suppliers'][supplier_position] = current_request['family_snapshot'][supplier_position]
                        if _Debug:
                            lg.out(_DebugLevel, '    found empty supplier at position %d and populated from current request: %s' % (supplier_position, merged_info['suppliers'][supplier_position]))

        return merged_info

    def _do_process_family_leave_request(self, merged_info, current_request):
        if _Debug:
            lg.args(_DebugLevel, merged_info=merged_info, current_request=current_request)
        try:
            existing_position = merged_info['suppliers'].index(current_request['supplier_idurl'])
        except ValueError:
            existing_position = -1

        if current_request.get('ecc_map'):
            if merged_info['ecc_map'] and current_request.get('ecc_map') and current_request.get('ecc_map') != merged_info['ecc_map']:
                lg.info('from "family-leave" request, detected ecc_map change %s -> %s for customer %s' % (merged_info['ecc_map'], current_request['ecc_map'], self.customer_idurl))
                merged_info['ecc_map'] = current_request['ecc_map']
            if not merged_info['ecc_map'] and current_request['ecc_map']:
                lg.info('from "family-leave" request, detected ecc_map was set to %s for the first time for customer %s' % (current_request['ecc_map'], self.customer_idurl))
                merged_info['ecc_map'] = current_request['ecc_map']

        if not merged_info['ecc_map']:
            lg.warn('still did not found actual ecc_map from DHT or from the request')
            return None

        expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(merged_info['ecc_map'])
        if not merged_info['suppliers']:
            merged_info['suppliers'] = [
                b'',
            ]*expected_suppliers_count

        if len(merged_info['suppliers']) < expected_suppliers_count:
            merged_info['suppliers'] += [
                b'',
            ]*(expected_suppliers_count - len(merged_info['suppliers']))
        else:
            merged_info['suppliers'] = merged_info['suppliers'][:expected_suppliers_count]

        if existing_position < 0:
            if _Debug:
                lg.dbg(_DebugLevel, 'supplier %r not found in customer family %r, probably already left' % (current_request['supplier_idurl'], self.customer_idurl))
        else:
            if existing_position < expected_suppliers_count:
                merged_info['suppliers'][existing_position] = b''
                if _Debug:
                    lg.info('erasing supplier %r from customer family %r' % (current_request['supplier_idurl'], self.customer_idurl))
        return merged_info

    def _do_process_family_refresh_request(self, merged_info):
        if _Debug:
            lg.args(_DebugLevel, merged_info=merged_info, my_info=self.my_info)
        if not self.my_info:
            self.my_info = self._do_create_possible_revision(int(merged_info['revision']))
            lg.warn('"family-refresh" request will use "possible" customer meta info: %r' % self.my_info)

        if int(self.my_info['revision']) > int(merged_info['revision']):
            lg.info('"family-refresh" request will overwrite DHT record with my info because my revision is higher than record in DHT')
            return self.my_info.copy()

        try:
            my_position = self.my_info['suppliers'].index(my_id.getIDURL().to_bin())
        except:
            my_position = -1
        if my_position < 0:
            lg.warn('"family-refresh" request failed because my info not exist or not valid, my own position in the family is unknown')
            return None

        my_expected_suppliers_count = None
        if self.my_info['ecc_map']:
            my_expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(self.my_info['ecc_map'])
        if my_expected_suppliers_count and my_position >= my_expected_suppliers_count:
            lg.warn('"family-refresh" request failed because my info is not valid, supplier position greater than expected suppliers count')
            return None

        if my_expected_suppliers_count and len(merged_info['suppliers']) != my_expected_suppliers_count:
            lg.warn('number of suppliers not expected during processing of "family-refresh" request')
            if len(merged_info['suppliers']) < my_expected_suppliers_count:
                merged_info['suppliers'] += [
                    b'',
                ]*(my_expected_suppliers_count - len(merged_info['suppliers']))
            else:
                merged_info['suppliers'] = merged_info['suppliers'][:my_expected_suppliers_count]

        try:
            existing_position = merged_info['suppliers'].index(my_id.getIDURL().to_bin())
        except ValueError:
            existing_position = -1
        if existing_position < 0:
            if merged_info['suppliers'][my_position]:
                # TODO: SECURITY need to implement a signature verification and
                # also build solution to validate that change was approved by customer
                lg.warn('overwriting another supplier %s with my IDURL at position %d in family of customer %s' % (merged_info['suppliers'][my_position], my_position, self.customer_idurl))
            merged_info['suppliers'][my_position] = my_id.getIDURL().to_bin()
            if _Debug:
                lg.out(_DebugLevel, '    placed supplier %s at known position %d in the family of customer %s' % (my_id.getIDURL(), my_position, self.customer_idurl))
            existing_position = my_position

        if existing_position != my_position:
            merged_info['suppliers'][existing_position] = b''
            merged_info['suppliers'][my_position] = my_id.getIDURL().to_bin()
            if _Debug:
                lg.out(_DebugLevel, '    found my IDURL on %d position and will move it on %d position in the family of customer %s' % (existing_position, my_position, self.customer_idurl))
        return merged_info

    def _do_process_request(self, merged_info, current_request):
        if current_request['command'] == 'family-join':
            return self._do_process_family_join_request(merged_info, current_request)
        if current_request['command'] == 'family-leave':
            return self._do_process_family_leave_request(merged_info, current_request)
        if current_request['command'] == 'family-refresh':
            return self._do_process_family_refresh_request(merged_info)
        lg.err('invalid request command')
        return None

    def _do_write_transaction(self, retries):
        if _Debug:
            lg.out(_DebugLevel, 'family_member._do_write_transaction  suppliers=%d  retries=%d' % (len(self.transaction['suppliers']), retries))
        d = dht_relations.write_customer_suppliers(
            customer_idurl=self.customer_idurl,
            suppliers_list=self.transaction['suppliers'],
            ecc_map=self.transaction['ecc_map'],
            revision=self.transaction['revision'],
            publisher_idurl=self.transaction['publisher_idurl'],
        )
        d.addCallback(self._on_dht_write_success)
        d.addErrback(self._on_dht_write_failed, retries)

    def _on_family_refresh_task(self):
        if self.state == 'CONNECTED':
            self.automat('family-refresh')

    def _on_dht_read_success(self, dht_result):
        if dht_result and isinstance(dht_result, dict) and len(dht_result.get('suppliers', [])) > 0:
            if _Debug:
                lg.out(_DebugLevel, 'family_member._on_dht_read_success  result with %d suppliers' % len(dht_result.get('suppliers', [])))
            self.dht_info = dht_result
            self.dht_value_exists = True
            self.automat('dht-value-exist', dht_result)
        else:
            if _Debug:
                lg.out(_DebugLevel, 'family_member._on_dht_read_success  result with %s' % type(dht_result))
            self.dht_info = None
            self.dht_value_exists = False
            self.automat('dht-value-not-exist', None)

    def _on_dht_read_failed(self, err):
        self.dht_info = None
        self.dht_value_exists = False
        if _Debug:
            lg.out(_DebugLevel, 'family_member._on_dht_read_failed : %r' % err)
        self.automat('dht-read-fail')

    def _on_dht_write_success(self, dht_result):
        if _Debug:
            lg.out(_DebugLevel, 'family_member._on_dht_write_success  result: %r' % type(dht_result))
        self.my_info = self.transaction.copy()
        self.dht_info = None
        self.transaction = None
        self.dht_read_use_cache = False
        self.automat('dht-write-ok', dht_result)

    def _on_dht_write_failed(self, err, retries):
        if _Debug:
            lg.out(_DebugLevel, 'family_member._on_dht_write_failed  err: %r' % err)
        self.dht_read_use_cache = False
        try:
            errmsg = err.value.subFailure.getErrorMessage()
        except:
            try:
                errmsg = err.getErrorMessage()
            except:
                try:
                    errmsg = err.value
                except:
                    errmsg = str(err)
        err_msg = strng.to_text(errmsg)
        lg.err('failed to write family info for %s : %s' % (self.customer_idurl, err_msg))
        if err_msg.count('current revision is') and retries < 3:
            try:
                current_revision = re.search('current revision is (\d+)', err_msg).group(1)
                current_revision = int(current_revision)
            except:
                lg.exc()
                current_revision = self.transaction['revision']
            current_revision += 1
            self.transaction['revision'] = current_revision
            if _Debug:
                lg.warn('recognized "DHT write operation failed" because of late revision, increase revision to %d and retry' % current_revision)
            self._do_write_transaction(retries + 1)
            return
        self.transaction = None
        self.dht_info = None
        self.automat('dht-write-fail')

    def _on_incoming_suppliers_list(self, inp):
        incoming_packet = inp['packet']
        if _Debug:
            lg.out(_DebugLevel, 'family_member._on_incoming_suppliers_list with %s' % incoming_packet)
        if not self.my_info:
            if _Debug:
                lg.out(_DebugLevel, '    current DHT info is not yet known, skip')
            return p2p_service.SendAck(incoming_packet)
        try:
            another_ecc_map = inp['customer_ecc_map']
            another_suppliers_list = id_url.to_bin_list(inp['suppliers_list'])
            another_revision = int(inp['transaction_revision'])
        except:
            lg.exc()
            return p2p_service.SendFail(incoming_packet, response=serialization.DictToBytes(self.my_info))
        if _Debug:
            lg.args(_DebugLevel, another_revision=another_revision, another_ecc_map=another_ecc_map, another_suppliers_list=another_suppliers_list)
        if another_revision >= int(self.my_info['revision']):
            self.my_info = self._do_create_revision_from_another_supplier(another_revision, another_suppliers_list, another_ecc_map)
            lg.info('another supplier have more fresh revision, update my info and raise "family-refresh" event')
            self.automat('family-refresh')
            return p2p_service.SendAck(incoming_packet)
        if my_id.getIDURL().to_bin() not in another_suppliers_list:
            if _Debug:
                lg.args(_DebugLevel, another_suppliers_list=another_suppliers_list, customer_idurl=self.customer_idurl)
            lg.warn('another supplier is trying to remove my IDURL from the family of customer %s' % self.customer_idurl)
            return p2p_service.SendFail(incoming_packet, response=serialization.DictToBytes(self.my_info))
        my_position_in_transaction = another_suppliers_list.index(my_id.getIDURL().to_bin())
        try:
            my_known_position = self.my_info['suppliers'].index(my_id.getIDURL().to_bin())
        except:
            my_known_position = -1
        if my_known_position < 0:
            if _Debug:
                lg.args(_DebugLevel, my_known_position=my_known_position, another_suppliers_list=another_suppliers_list, customer_idurl=self.customer_idurl)
            lg.warn('another supplier is trying to remove me from the family of customer %s' % self.customer_idurl)
            return p2p_service.SendFail(incoming_packet, response=serialization.DictToBytes(self.my_info))
        if my_position_in_transaction != my_known_position:
            lg.warn('another supplier is trying to put my IDURL on another position in the family of customer %s' % self.customer_idurl)
            return p2p_service.SendFail(incoming_packet, response=serialization.DictToBytes(self.my_info))
        if _Debug:
            lg.out(_DebugLevel, '    all correct, refresh customer family for %r' % self.customer_idurl)
        self.automat('family-refresh')
        return p2p_service.SendAck(incoming_packet)

    def _on_incoming_supplier_position(self, inp):
        # this packet came from the customer, a godfather of the family ;)))
        # he told me which position in the family I should take
        incoming_packet = inp['packet']
        try:
            ecc_map = inp['customer_ecc_map']
            supplier_idurl = strng.to_bin(inp['supplier_idurl'])
            supplier_position = int(inp['supplier_position'])
            family_snapshot = id_url.to_bin_list(inp.get('family_snapshot') or [])
        except:
            lg.exc()
            return None
        if supplier_idurl != my_id.getIDURL().to_bin():
            return p2p_service.SendFail(incoming_packet, 'contacts packet with supplier position not addressed to me')
        try:
            _existing_position = self.my_info['suppliers'].index(supplier_idurl)
        except:
            _existing_position = -1
        contactsdb.add_customer_meta_info(self.customer_idurl, {
            'ecc_map': ecc_map,
            'position': supplier_position,
            'family_snapshot': id_url.to_bin_list(family_snapshot),
        })
        if _Debug:
            lg.out(_DebugLevel, 'family_member._on_incoming_supplier_position stored new meta info for customer %s:\n' % self.customer_idurl)
            lg.out(_DebugLevel, '    ecc_map=%s position=%s family_snapshot=%s' % (ecc_map, supplier_position, family_snapshot))
        return p2p_service.SendAck(incoming_packet)

    def _on_incoming_contacts_packet(self, inp):
        try:
            contacts_type = inp['type']
            incoming_packet = inp['packet']
        except:
            lg.exc()
            return None
        if contacts_type == 'suppliers_list':
            # this packet came from another supplier who belongs to the same customer family
            # he notified me about changes in the family he is trying to do
            return self._on_incoming_suppliers_list(inp)
        elif contacts_type == 'supplier_position':
            # this packet came from the customer, a godfather of the family ;)))
            # he told me which position in the family I should take
            return self._on_incoming_supplier_position(inp)
        return p2p_service.SendFail(incoming_packet, 'invalid contacts type')

    def _on_supplier_ack(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'family_member._on_supplier_ack with %r' % response)
        if response.PacketID in self.suppliers_requests:
            self.suppliers_requests.remove(response.PacketID)
        if not self.suppliers_requests:
            self.automat('all-suppliers-agree')

    def _on_supplier_fail(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'family_member._on_supplier_fail with %r' % response)
        if response.PacketID in self.suppliers_requests:
            self.suppliers_requests.remove(response.PacketID)
        try:
            json_payload = serialization.BytesToDict(response.Payload, keys_to_text=True)
            ecc_map = strng.to_text(json_payload['ecc_map'])
            suppliers_list = id_url.to_bin_list(json_payload['suppliers'])
        except:
            lg.exc()
            if not self.suppliers_requests:
                self.automat('all-suppliers-agree')
            return None
        if _Debug:
            lg.args(_DebugLevel, ecc_map=ecc_map, suppliers_list=suppliers_list, supplier_idurl=response.OwnerID.to_bin())
        self.automat('one-supplier-not-agree', ecc_map=ecc_map, suppliers_list=suppliers_list, supplier_idurl=response.OwnerID.to_bin())
