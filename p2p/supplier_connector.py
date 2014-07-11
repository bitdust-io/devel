

"""
.. module:: supplier
.. role:: red

BitPie.NET supplier_connector() Automat

.. raw:: html

    <a href="supplier.png" target="_blank">
    <img src="supplier.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`ack`
    * :red:`close`
    * :red:`connect`
    * :red:`disconnect`
    * :red:`fail`
    * :red:`shutdown`
    * :red:`timer-10sec`
    * :red:`timer-20sec`
"""

import os
import time 

import lib.dhnio as dhnio
import lib.automat as automat
import lib.nameurl as nameurl
import lib.contacts as contacts
import lib.commands as commands
import lib.diskspace as diskspace
import lib.settings as settings
import lib.misc as misc

import transport.callback as callback

import p2p_service
import fire_hire 

#------------------------------------------------------------------------------ 

_SuppliersConnectors = {}

#------------------------------------------------------------------------------ 

def connectors():
    """
    """
    global _SuppliersConnectors
    return _SuppliersConnectors


def create(supplier_idurl):
    """
    """
    assert supplier_idurl not in connectors()
    connectors()[supplier_idurl] = SupplierConnector(supplier_idurl)
    return connectors()[supplier_idurl]


def by_idurl(idurl):
    return connectors().get(idurl, None)
    
#------------------------------------------------------------------------------ 

class SupplierConnector(automat.Automat):
    """
    This class implements all the functionality of the ``supplier_connector()`` state machine.

    """

    timers = {
        'timer-10sec': (10.0, ['REFUSE']),
        'timer-20sec': (20.0, ['REQUEST']),
        }
    
    def __init__(self, idurl):
        self.idurl = idurl
        self.name = nameurl.GetName(self.idurl)
        self.request_packet_id = None
        self.callbacks = {}
        try:
            st = dhnio.ReadTextFile(settings.SupplierServiceFilename(self.idurl)).strip() 
        except:
            st = 'DISCONNECTED'
        if st == 'CONNECTED':
            automat.Automat.__init__(self, 'supplier_%s' % self.name, 'CONNECTED', 8)
        elif st == 'NO_SERVICE':
            automat.Automat.__init__(self, 'supplier_%s' % self.name, 'NO_SERVICE', 8)
        else:
            automat.Automat.__init__(self, 'supplier_%s' % self.name, 'DISCONNECTED', 8)
        for cb in self.callbacks.values():
            cb(self.idurl, self.state, self.state)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """

    def state_changed(self, oldstate, newstate):
        """
        Method to to catch the moment when automat's state were changed.
        """
        if newstate in ['CONNECTED', 'DISCONNECTED', 'NO_SERVICE']:
            supplierPath = settings.SupplierPath(self.idurl)
            if not os.path.isdir(supplierPath):
                try:
                    os.makedirs(supplierPath)
                except:
                    dhnio.DprintException()
                    return
            dhnio.WriteFile(settings.SupplierServiceFilename(self.idurl), newstate)
        for cb in self.callbacks.values():
            cb(self.idurl, oldstate, newstate)
            
    def set_callback(self, name, cb):
        self.callbacks[name] = cb
        
    def remove_callback(self, name):
        if name in self.callbacks.keys():
            self.callbacks.pop(name)

    def A(self, event, arg):
        #---NO_SERVICE---
        if self.state == 'NO_SERVICE':
            if event == 'connect' :
                self.state = 'REQUEST'
                self.doRequestService(arg)
                self.GoDisconnect=False
            elif event == 'ack' and self.isServiceAccepted(arg) :
                self.state = 'CONNECTED'
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'disconnect' :
                fire_hire.A('supplier-disconnected', self.idurl)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'close' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'disconnect' :
                self.state = 'REFUSE'
                self.doCancelService(arg)
            elif event == 'fail' :
                self.state = 'REQUEST'
                self.doRequestService(arg)
                self.GoDisconnect=False
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'ack' and self.isServiceAccepted(arg) :
                self.state = 'CONNECTED'
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'disconnect' :
                self.state = 'REFUSE'
                self.doCancelService(arg)
            elif event == 'connect' :
                self.state = 'REQUEST'
                self.doRequestService(arg)
                self.GoDisconnect=False
            elif event == 'fail' :
                self.state = 'NO_SERVICE'
                fire_hire.A('supplier-disconnected', self.idurl)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'disconnect' :
                self.GoDisconnect=True
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif not self.GoDisconnect and event == 'ack' and self.isServiceAccepted(arg) :
                self.state = 'CONNECTED'
            elif self.GoDisconnect and event == 'ack' and self.isServiceAccepted(arg) :
                self.state = 'REFUSE'
                self.doCancelService(arg)
            elif event == 'timer-20sec' :
                self.state = 'DISCONNECTED'
                self.doCleanRequest(arg)
            elif event == 'fail' or ( event == 'ack' and not self.isServiceAccepted(arg) and not self.GoDisconnect ) :
                self.state = 'NO_SERVICE'
                fire_hire.A('supplier-disconnected', self.idurl)
        #---REFUSE---
        elif self.state == 'REFUSE':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doCleanRequest(arg)
                self.doDestroyMe(arg)
            elif event == 'timer-10sec' or event == 'fail' or ( event == 'ack' and self.isServiceCancelled(arg) ) :
                self.state = 'NO_SERVICE'
                self.doCleanRequest(arg)
                fire_hire.A('supplier-disconnected', self.idurl)

    def isServiceAccepted(self, arg):
        """
        Condition method.
        """
        newpacket = arg
        if newpacket.Command == commands.Ack():
            if newpacket.Payload.startswith('accepted'):
                dhnio.Dprint(6, 'supplier_connector.isServiceAccepted !!!! supplier %s connected' % self.idurl)
                return True
        return False

    def isServiceCancelled(self, arg):
        """
        Condition method.
        """
        newpacket = arg
        if newpacket.Command == commands.Ack():
            if newpacket.Payload.startswith('accepted'):
                dhnio.Dprint(6, 'supplier_connector.isServiceCancelled !!!! supplier %s disconnected' % self.idurl)
                return True
        return False

    def doRequestService(self, arg):
        """
        Action method.
        """
        bytes_needed = diskspace.GetBytesFromString(settings.getCentralMegabytesNeeded(), 0)
        num_suppliers = settings.getCentralNumSuppliers()
        if num_suppliers > 0:
            mb_per_supplier = round((2.0*bytes_needed/num_suppliers)/(1024.0*1024.0), 2)
        else:
            mb_per_supplier = 1.0 
        service_info = 'storage %d' % mb_per_supplier
        request = p2p_service.SendRequestService(self.idurl, service_info, self._supplier_acked)
        self.request_packet_id = request.PacketID

    def doCancelService(self, arg):
        """
        Action method.
        """
        request = p2p_service.SendCancelService(self.idurl, 'storage', self._supplier_acked)
        self.request_packet_id = request.PacketID

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        connectors().pop(self.idurl)
        automat.objects().pop(self.index)
        
    def doCleanRequest(self, arg):
        """
        Action method.
        """
        # callback.remove_interest(misc.getLocalID(), self.request_packet_id)

    def _supplier_acked(self, response, info):
        dhnio.Dprint(16, 'supplier_connector._supplier_acked %r %r' % (response, info))
        self.automat(response.Command.lower(), response)


