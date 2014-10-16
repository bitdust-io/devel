
import gate

#------------------------------------------------------------------------------ 

_PeersProtos = {}
_MyProtos = {}
_CountersIn =  {'total_bytes': 0, 
                'unknown_bytes': 0, 
                'total_packets':0,
                'unknown_packets': 0,
                'failed_packets': 0, }
_CountersOut = {'total_bytes': 0, 
                'unknown_bytes': 0, 
                'total_packets':0,
                'unknown_packets': 0,
                'failed_packets': 0, }

#------------------------------------------------------------------------------ 

def my_protos():
    global _MyProtos
    return _MyProtos


def peers_protos():
    global _PeersProtos
    return _PeersProtos


def counters_in():
    global _CountersIn
    return _CountersIn


def counters_out():
    global _CountersOut
    return _CountersOut

#------------------------------------------------------------------------------ 

def ErasePeerProtosStates(idurl):
    global _PeersProtos
    _PeersProtos.pop(idurl, None)
    
def EraseAllMyProtosStates():
    my_protos().clear()
    
def EraseMyProtosStates(idurl):
    my_protos().pop(idurl, None)

#------------------------------------------------------------------------------

def count_outbox(remote_idurl, proto, status, size):
    """
    """
    if not peers_protos().has_key(remote_idurl):
        peers_protos()[remote_idurl] = set()
    if status == 'finished':
        peers_protos()[remote_idurl].add(proto)
        
    counters_out()['total_bytes'] += size
    if remote_idurl and remote_idurl.startswith('http://') and remote_idurl.endswith('.xml'): 
        if not counters_out().has_key(remote_idurl):
            counters_out()[remote_idurl] = 0
        counters_out()[remote_idurl] += size
        if status == 'finished':
            counters_out()['total_packets'] += 1
        else:
            counters_out()['failed_packets'] += 1
    else:
        counters_out()['unknown_bytes'] += size
        counters_out()['unknown_packets'] += 1

        
def count_inbox(remote_idurl, proto, status, bytes_received):
    """
    """
    if not my_protos().has_key(remote_idurl):
        my_protos()[remote_idurl] = set()
    if status == 'finished':
        my_protos()[remote_idurl].add(proto)

    counters_in()['total_bytes'] += bytes_received
    if remote_idurl and remote_idurl.startswith('http://') and remote_idurl.endswith('.xml'): 
        if status == 'finished':
            counters_in()['total_packets'] += 1
        else:
            counters_in()['failed_packets'] += 1
        if not counters_in().has_key(remote_idurl):
            counters_in()[remote_idurl] = 0
        counters_in()[remote_idurl] += bytes_received
    else:
        counters_in()['unknown_packets'] += 1
        counters_in()['unknown_bytes'] += bytes_received
        
 
