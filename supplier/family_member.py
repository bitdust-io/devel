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

DHT_RECORD_REFRESH_INTERVAL = 2 * 60

#------------------------------------------------------------------------------

from twisted.internet.task import LoopingCall

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from main import settings

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
        self.my_info = None
        self.transaction = None
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
        self._do_build_family_transaction(args[0])
        self.refresh_period = DHT_RECORD_REFRESH_INTERVAL * settings.DefaultDesiredSuppliers()
        if self.transaction:
            known_ecc_map = self.transaction.get('ecc_map')
            if known_ecc_map:
                expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(known_ecc_map)
                self.refresh_period = DHT_RECORD_REFRESH_INTERVAL * expected_suppliers_count

    def doSendContactsToSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        if not self.transaction:
            return
        for supplier_idurl in self.transaction['suppliers']:
            if not supplier_idurl:
                continue
            outpacket = self._do_send_transaction_to_another_supplier(supplier_idurl)
            # TODO: wait Ack()/Fail() responses from other suppliers and decide to write to DHT or not 
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
            publisher_idurl=self.transaction['publisher_idurl'],
        )
        d.addCallback(self._on_dht_write_success)
        d.addErrback(self._on_dht_write_failed)

    def doNotifyConnected(self, *args, **kwargs):
        """
        Action method.
        """
        self.current_request = None
        if self.refresh_task.running:
            self.refresh_task.stop()
        self.refresh_task.start(self.refresh_period, now=False)

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
        self.transaction = None
        self.refresh_task = None
        delete_family(self.customer_idurl)
        self.destroy()

    #------------------------------------------------------------------------------

    def _do_build_family_transaction(self, dht_info):
        dht_info_valid = self._do_validate_dht_info(dht_info)
        my_info_valid = self._do_validate_my_info(self.my_info)
        latest_revision = self._do_detect_latest_revision(dht_info_valid, my_info_valid)
        merged_info = self._do_merge_info(dht_info_valid, my_info_valid, latest_revision)
        self.transaction = self._do_process_request(merged_info, self.current_request) 
        if self.transaction:
            self._do_increase_next_revision()
        if _Debug:
            lg.out(_DebugLevel, 'family_member._do_build_family_transaction     result transaction is %r' % self.transaction)

    def _do_validate_dht_info(self, inp):
        if not inp or not isinstance(inp, dict):
            return None
        out = inp.copy()
        try:
            dht_revision = int(out['revision'])
            suppliers = out['suppliers']
            ecc_map = out['ecc_map']
            if dht_revision < 1:
                raise Exception('invalid revision')
            if not isinstance(suppliers, list) or len(suppliers) < 1:
                raise Exception('must include some suppliers')
            if ecc_map and ecc_map not in eccmap.EccMapNames():
                raise Exception('invalid ecc_map name')
            out['publisher_idurl']
            # TODO: add publisher_signature and Validate method to check publisher signature
            out['customer_idurl']
            # TODO: add customer_signature and Validate method to check customer signature
        except:
            lg.exc()
            lg.warn('skip invalid DHT info and assume DHT record not exist')
            return None
        return out

    def _do_validate_my_info(self, inp):
        if not inp or not isinstance(inp, dict):
            return self._do_prepare_my_default_info()
        out = inp.copy()
        try:
            my_revision = int(out['revision'])
            if my_revision < 1:
                raise Exception('invalid revision')
        except:
            lg.exc()
            out['revision'] = 1
        default_info = self._do_prepare_my_default_info()
        try:
            suppliers = out['suppliers']
            if not isinstance(suppliers, list) or len(suppliers) < 1:
                raise Exception('must include some suppliers')
        except:
            out['suppliers'] = default_info['suppliers']
        try:
            ecc_map = out['ecc_map']
            if ecc_map and ecc_map not in eccmap.EccMapNames():
                raise Exception('invalid ecc_map name')
        except:
            out['ecc_map'] = default_info['ecc_map']
        try:
            out['publisher_idurl']
            # TODO: if I am a publisher - revision number must be the same as my info
        except:
            out['publisher_idurl'] = default_info['publisher_idurl']
        try:
            customer_idurl = out['customer_idurl']
            if customer_idurl != self.customer_idurl:
                out['customer_idurl'] = default_info['customer_idurl']
        except:
            out['customer_idurl'] = default_info['customer_idurl']
        return out

    def _do_prepare_my_default_info(self):
        return {
            'revision': 1,
            # I will be a publisher
            'publisher_idurl': my_id.getLocalIDURL(),
            # I am the supplier and need to put myself on the first position, but I do know other suppliers yet
            'suppliers': [my_id.getLocalIDURL(), ],
            'ecc_map': contactsdb.get_customer_meta_info(self.customer_idurl).get('ecc_map', None),
            'customer_idurl': self.customer_idurl,
        }

    def _do_detect_latest_revision(self, dht_info, my_info):
        my_revision = int(my_info['revision'])
        if dht_info is None or not isinstance(dht_info, dict):
            lg.warn('DHT info is unknown, assume my info is correct and return revision %d' % my_revision)
            return my_revision
        dht_revision = int(dht_info['revision'])
        if _Debug:
            lg.out(_DebugLevel, 'family_member._do_detect_latest_revision   my_revision=%r dht_revision=%r' % (
                my_revision, dht_revision, ))
        if my_revision == dht_revision:
            return dht_revision
        if my_revision > dht_revision:
            # TODO: SECURITY need to find a solution to prevent cheating here
            # some supplier could publish a record where he is only alone present ...
            # that means he actually brutally dropped all other suppliers from the family 
            lg.info('known DHT info for customer %s is more fresh, will rewrite DHT record' % self.customer_idurl)
            if my_revision > dht_revision + 1:
                lg.warn('switching revision too far, normally always increase by one on every change')
            return my_revision
        return dht_revision

    def _do_merge_info(self, dht_info, my_info, latest_revision):
        if dht_info is None or not isinstance(dht_info, dict):
            merged_info = my_info
        else:
            if latest_revision == dht_info['revision']:
                if latest_revision == my_info['revision']:
                    # I have same revision as info from DHT
                    merged_info = dht_info
                else:
                    # here my revision is lower, I need to take info from DHT 
                    merged_info = dht_info
            else:
                # here my revision is higher, so I have some changes that needs to be published already
                merged_info = my_info
        # make sure list of suppliers have correct length according to ecc_map
        if not merged_info['ecc_map']:
            known_ecc_map = contactsdb.get_customer_meta_info(self.customer_idurl).get('ecc_map', None)
            lg.warn('unknown ecc_map, will populate known value: %s' % known_ecc_map)
            merged_info['ecc_map'] = known_ecc_map
        if merged_info['ecc_map']:
            expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(merged_info['ecc_map'])
            if len(merged_info['suppliers']) < expected_suppliers_count:
                merged_info['suppliers'] += [b'', ] * (expected_suppliers_count - len(merged_info['suppliers']))
            elif len(merged_info['suppliers']) > expected_suppliers_count:
                merged_info['suppliers'] = merged_info['suppliers'][:expected_suppliers_count]
        return merged_info

    def _do_process_request(self, merged_info, current_request):
        expected_suppliers_count = None
        if merged_info['ecc_map']:
            expected_suppliers_count = eccmap.GetEccMapSuppliersNumber(merged_info['ecc_map'])
        if current_request['command'] == 'family-join':
            if merged_info['ecc_map'] and current_request['ecc_map']:
                if current_request['ecc_map'] != merged_info['ecc_map']:
                    lg.info('from "family-join" request, detected ecc_map change %s -> %s for customer %s' % (
                        merged_info['ecc_map'], current_request['ecc_map'], self.customer_idurl))
                    new_suppliers_count = eccmap.GetEccMapSuppliersNumber(current_request['ecc_map'])
                    if len(merged_info['suppliers']) < new_suppliers_count:
                        merged_info['suppliers'] += [b'', ] * (new_suppliers_count - len(merged_info['suppliers']))
                    else:
                        merged_info['suppliers'] = merged_info['suppliers'][:new_suppliers_count]
                    if not expected_suppliers_count:
                        expected_suppliers_count = new_suppliers_count
                    if new_suppliers_count > expected_suppliers_count:
                        expected_suppliers_count = new_suppliers_count
                    else:
                        expected_suppliers_count = new_suppliers_count

            try:
                _existing_position = merged_info['suppliers'].index(current_request['supplier_idurl'])
            except ValueError:
                _existing_position = -1

            if current_request['position'] is not None and current_request['position'] >= 0:
                if expected_suppliers_count and current_request['position'] >= expected_suppliers_count:
                    lg.warn('"family-join" request is not valid, supplier position greater than expected suppliers count')
                    return None
                if len(merged_info['suppliers']) <= current_request['position']:
                    lg.warn('stretching customer family because supplier position is larger than known family size')
                    merged_info['suppliers'] += [b'', ] * (current_request['position'] + 1 - len(merged_info['suppliers']))
                if _existing_position >= 0 and _existing_position != current_request['position']:
                    merged_info['suppliers'][_existing_position] = b''
                    merged_info['suppliers'][current_request['position']] = current_request['supplier_idurl']
                    if _Debug:
                        lg.out(_DebugLevel, '    found my IDURL on %d position and will move it on %d position in the family of customer %s' % (
                        _existing_position, current_request['position'], self.customer_idurl))
                if merged_info['suppliers'][current_request['position']] != current_request['supplier_idurl']:
                    if merged_info['suppliers'][current_request['position']] not in [b'', '', None]:
                        # TODO: SECURITY need to implement a signature verification and
                        # also build solution to validate that change was approved by customer 
                        lg.warn('overwriting another supplier %s with my IDURL at position %d in family of customer %s' % (
                            merged_info['suppliers'][current_request['position']], current_request['position'], self.customer_idurl, ))
                    merged_info['suppliers'][current_request['position']] = current_request['supplier_idurl']
                    if _Debug:
                        lg.out(_DebugLevel, '    placed supplier %s at known position %d in the family of customer %s' % (
                            current_request['supplier_idurl'], current_request['position'], self.customer_idurl))

            else:
                if current_request['supplier_idurl'] not in merged_info['suppliers']:
                    if b'' in merged_info['suppliers']:
                        _empty_position = merged_info['suppliers'].index(b'')
                        merged_info['suppliers'][_empty_position] = current_request['supplier_idurl']
                        if _Debug:
                            lg.out(_DebugLevel, '    placed supplier %s at empty position %d in family of customer %s' % (
                                current_request['supplier_idurl'], _empty_position, self.customer_idurl))
                    else:
                        merged_info['suppliers'].append(current_request['supplier_idurl'])
                        if _Debug:
                            lg.out(_DebugLevel, '    added supplier %s to family of customer %s' % (
                                current_request['supplier_idurl'], self.customer_idurl))

        elif current_request['command'] == 'family-leave':
            try:
                _existing_position = merged_info['suppliers'].index(current_request['supplier_idurl'])
            except ValueError:
                _existing_position = -1
            if _existing_position < 0:
                lg.warn('skip "family-leave" request, did not found supplier %r in customer family %r' % (
                    current_request['supplier_idurl'], self.customer_idurl, ))
                return None
            merged_info['suppliers'][_existing_position] = b''

        elif current_request['command'] == 'family-refresh':
            pass
        
        return merged_info

    def _do_increase_next_revision(self):
        self.transaction['revision'] += 1
        self.transaction['publisher_idurl'] = my_id.getLocalIDURL()

    def _do_send_transaction_to_another_supplier(self, supplier_idurl):
        return p2p_service.SendContacts(
            remote_idurl=supplier_idurl,
            json_payload={
                'space': 'family_member',
                'type': 'suppliers_list',
                'customer_idurl': self.customer_idurl,
                'customer_ecc_map': self.transaction['ecc_map'],
                # 'transaction_revision': self.transaction['revision'],
                'suppliers_list': self.transaction['suppliers'],
            },
        )

    def _on_family_refresh_task(self):
        self.automat('family-refresh')

    def _on_dht_read_success(self, dht_result):
        if dht_result:
            self.automat('dht-value-exist', dht_result)
        else:
            self.automat('dht-value-not-exist', None)

    def _on_dht_read_failed(self, err):
        lg.err('doDHTRead FAILED: %s' % err)
        self.my_info = None
        
    def _on_dht_write_success(self, dht_result):
        self.my_info = self.transaction.copy()
        self.transaction = None
        self.automat('dht-ok', dht_result)

    def _on_dht_write_failed(self, err):
        lg.err('doDHTWrite FAILED: %s' % err)
        self.my_info = None
        self.transaction = None
        self.automat('dht-fail')

    def _on_incoming_contacts_packet(self, inp):
        try:
            contacts_type = inp['type']
            incoming_packet = inp['packet']
        except:
            lg.exc()
            return

        if _Debug:
            lg.out(_DebugLevel, 'family_member._on_incoming_contacts_packet   type=%s')

        if self.state != 'CONNECTED':  # in ['DISCONNECTED', 'DHT_READ', ]:
            # currently this family member is not ready yet, skip
            return p2p_service.SendAck(incoming_packet)

        if not self.my_info:
            # current DHT info is not yet known, skip
            return p2p_service.SendAck(incoming_packet)

        if contacts_type == 'suppliers_list':
            try:
                # TODO: check revision with my_info
                # transaction_revision = int.get('transaction_revision', -1)
                ecc_map = inp['customer_ecc_map']
                suppliers_list = inp['suppliers_list']
            except:
                lg.exc()
                return
            if my_id.getLocalIDURL() not in suppliers_list:
                lg.warn('another supplier is trying to remove my IDURL from the family of customer %s' % self.customer_idurl)
                return p2p_service.SendFail(incoming_packet, 'contacts list from remote user does not include my identity')
            if self.my_info['ecc_map'] and ecc_map and self.my_info['ecc_map'] != ecc_map:
                lg.warn('known ecc_map not matching with contacts list received from remote user')
                # TODO: check this later
                # return p2p_service.SendFail(incoming_packet, 'known ecc_map not matching with contacts list received from remote user')
                return p2p_service.SendAck(incoming_packet)
            if len(suppliers_list) != len(self.my_info['suppliers']):
                lg.warn('known number of suppliers not matching with contacts list received from remote user')
                # TODO: check this later
                # return p2p_service.SendFail(incoming_packet, 'known number of suppliers not matching with contacts list received from remote user')
                return p2p_service.SendAck(incoming_packet)
            return p2p_service.SendAck(incoming_packet)

        elif contacts_type == 'supplier_position':
            try:
                ecc_map = inp['customer_ecc_map']
                supplier_idurl = inp['supplier_idurl']
                supplier_position = inp['supplier_position']
            except:
                lg.exc()
                return
            if supplier_idurl != my_id.getLocalIDURL():
                return p2p_service.SendFail(incoming_packet, 'contacts packet with supplier position not addressed to me')
            try:
                _existing_position = self.my_info['suppliers'].index(supplier_idurl)
            except ValueError:
                _existing_position = -1
            contactsdb.add_customer_meta_info(self.customer_idurl, {
                'ecc_map': ecc_map,
                'position': supplier_position,
            })
            if _existing_position >=0 and _existing_position != supplier_position:
                if _Debug:
                    lg.out(_DebugLevel, '')
                self.automat('family-join', {
                    'supplier_idurl': supplier_idurl,
                    'ecc_map': ecc_map,
                    'position': supplier_position,
                })
            return p2p_service.SendAck(incoming_packet)

        return p2p_service.SendFail(incoming_packet, 'invalid contacts type')
