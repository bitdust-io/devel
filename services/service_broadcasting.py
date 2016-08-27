#!/usr/bin/python
#service_broadcasting.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_broadcasting

"""

from services.local_service import LocalService

def create_service():
    return BroadcastingService()
    
class BroadcastingService(LocalService):
    
    service_name = 'service_broadcasting'
    config_path = 'services/broadcasting/enabled'
    
    def dependent_on(self):
        return ['service_p2p_hookups', 
                'service_entangled_dht',
                ]
    
    def start(self):
        from broadcast import broadcaster_node
        from broadcast import broadcasters_finder
        broadcasters_finder.A('init')
        broadcaster_node.A('init')
        return True
    
    def stop(self):
        from broadcast import broadcaster_node
        from broadcast import broadcasters_finder
        broadcaster_node.A('shutdown')
        broadcasters_finder.A('shutdown')
        return True
    
    def request(self, request, info):
        from logs import lg
        from p2p import p2p_service
        words = request.Payload.split(' ')
        try:
            mode = words[1][:20]
        except:
            lg.exc()
            return p2p_service.SendFail(request, 'wrong mode provided')
        if mode != 'route' and mode != 'listen':
            lg.out(8, "service_broadcasting.request DENIED, wrong mode provided : %s" % mode)
            return p2p_service.SendFail(request, 'wrong mode provided')
        if mode == 'listen':
            lg.out(8, "service_broadcasting.request DENIED, wrong mode provided : %s" % mode)
            return p2p_service.SendFail(request, 'listening is not supported yet')
        if mode == 'route' and False: # and not settings.getBroadcastRoutingEnabled():
            # TODO check if this is enabled in settings
            # so broadcaster_node should be existing
            lg.out(8, "service_broadcasting.request DENIED, broadcast routing disabled")
            return p2p_service.SendFail(request, 'broadcast routing disabled')
        from broadcast import broadcaster_node
        if broadcaster_node.A().state not in ['BROADCASTING', 'OFFLINE', 'BROADCASTERS?',]:
            lg.out(8, "service_broadcasting.request DENIED, current state is : %s" % broadcaster_node.A().state)
            return p2p_service.SendFail(request, 'currently not broadcasting')
        broadcaster_node.A('new-broadcaster-connected', request)
        return p2p_service.SendAck(request, 'accepted')
    
#     def cancel(self, request, info):
#         from logs import lg
#         from p2p import p2p_service
#         words = request.Payload.split(' ')
#         try:
#             mode = words[1][:20]
#         except:
#             lg.exc()
#             return p2p_service.SendFail(request, 'wrong mode provided')
#         if mode == 'route' and False: # and not settings.getBroadcastRoutingEnabled():      
#             # TODO check if this is enabled in settings
#             # so broadcaster_node should be existing already
#             lg.out(8, "service_broadcasting.request DENIED, broadcast routing disabled")
#             return p2p_service.SendFail(request, 'broadcast routing disabled')
#         from broadcast import broadcaster_node
#         if broadcaster_node.A().state not in ['BROADCASTING', ]:
#             lg.out(8, "service_broadcasting.request DENIED, current state is : %s" % broadcaster_node.A().state)
#             return p2p_service.SendFail(request, 'currently not broadcasting')        
#         broadcaster_node.A('broadcaster-disconnected', request)
#         return p2p_service.SendAck(request, 'accepted')
