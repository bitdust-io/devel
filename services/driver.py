
import os
import sys
import importlib

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from logs import lg

from lib import automat
from lib import bpio

#------------------------------------------------------------------------------ 

_ServicesDict = {}

#------------------------------------------------------------------------------ 

def services():
    """
    """
    global _ServicesDict
    return _ServicesDict

def registered_services():
    return [
        'distributed_hash_table',
        'udp_datagrams',
        'tcp_connections',
        'network_connector',
        'tcp_transport',
        'udp_transport',
        'gateway',
        'identity_server',
        'identity_propagate',
        'supplier',
        'customer',
        'list_files',
        'backup_db',
        'stun_server',
        'stun_client',
        'backup_monitor',
        'rebuilding',
        'customers_rejector',
        'data_sender',
        'fire_hire',
        'private_messages',
        'restore_monitor',
        ]

def is_started(name):
    svc = services().get(name, None)
    if svc is None:
        return False
    return svc.state == 'ON'

def is_exist(name):
    return services().has_key(name)

#------------------------------------------------------------------------------ 

def init_all(callback=None):
    """
    """
    lg.out(2, 'local_service.init_all')
    available_services_dir = os.path.join(bpio.getExecutableDir(), 'services', 'available')
    for filename in os.listdir(available_services_dir):
        if not filename.endswith('.py'):
            continue
        if filename == '__init__.py':
            continue
        # filepath = os.path.join(available_services_dir, filename)
        name = filename[:-3]
        try:
            py_mod = importlib.import_module('services.available.'+name)
        except:
            lg.exc()
            continue
        try:
            services()[name] = py_mod.create_service()
        except:
            lg.exc()
    if callback:
        callback()


def shutdown_all(callback=None):
    """
    """
    for svc in services().values():
        lg.out(2, 'local_service.shutdown_all closing %r' % svc)
        automat.clear_object(svc.index)
    services().clear()
    if callback:
        callback()


def order_all():
    order = []
    for svc in services().values():
        if svc.name not in order:
            for depend_name in svc.dependent_on():
                if depend_name not in order:
                    order.append(depend_name)
                    print 'append', depend_name
            order.append(svc.name)
            print 'append parent', svc.name
        else:
            index = order.index(svc.name)
            for depend_name in svc.dependent_on():
                if depend_name not in order:
                    order.insert(index, depend_name)
                    print 'insert', svc.name, depend_name 
                else:
                    if order.index(depend_name) > index:
                        lg.warn('dependency not satisfied: %s depend on %s' % (
                            svc.name, depend_name))
                    else:
                        print 'ok', svc.name, depend_name 
    return order

#------------------------------------------------------------------------------ 

class ServiceAlreadyExist(Exception):
    pass

class RequireSubclass(Exception):
    pass

#------------------------------------------------------------------------------ 

def main():
    lg.set_debug_level(20)
    init_all()
    print '\n    '.join(order_all())


if __name__ == '__main__':
    main()
    