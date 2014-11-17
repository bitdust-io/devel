#!/usr/bin/python
#service_p2p_hookups.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_p2p_hookups

"""

from services.local_service import LocalService

def create_service():
    return P2PHookupsService()
    
class P2PHookupsService(LocalService):
    
    service_name = 'service_p2p_hookups'
    config_path = 'services/p2p-hookups/enabled'
    
    def dependent_on(self):
        from lib import settings
        depends = ['service_gateway',
                   'service_identity_propagate', ]
        if settings.enableTCP():
            depends.append('service_tcp_transport')
        if settings.enableUDP():
            depends.append('service_udp_transport')
        return depends
    
    def start(self):
        from p2p import p2p_service
        from p2p import contact_status
        from p2p import p2p_connector
        from p2p import network_connector
        from twisted.internet.defer import Deferred
        p2p_service.init()
        contact_status.init()
        self._starting_defer = Deferred()
        p2p_connector.A().addStateChangedCallback(
            self._on_p2p_connector_switched)
        network_connector.A().addStateChangedCallback(
            self._on_network_connector_switched)
        p2p_connector.A('init')
        return self._starting_defer
    
    def stop(self):
        from p2p import contact_status
        from p2p import p2p_connector
        from p2p import network_connector
        network_connector.A().removeStateChangedCallback(
            self._on_network_connector_switched)
        p2p_connector.A().removeStateChangedCallback(
            self._on_p2p_connector_switched)
        contact_status.shutdown()
        p2p_connector.Destroy()
        return True
    
    def _on_p2p_connector_switched(self, oldstate, newstate, evt, args ):
        if self._starting_defer is not None:
            if newstate == 'INCOMMING?':
                self._starting_defer.callback(newstate)
                self._starting_defer = None
        from p2p import network_connector
        from p2p import tray_icon
        tray_icon.state_changed(network_connector.A().state, newstate)
        
    def _on_network_connector_switched(self, oldstate, newstate, evt, args): 
        from p2p import p2p_connector
        from p2p import tray_icon 
        if oldstate != newstate:
            if newstate == 'CONNECTED' or newstate == 'DISCONNECTED':
                p2p_connector.A('network_connector.state', newstate)
                tray_icon.state_changed(newstate, p2p_connector.A().state)
        
        
