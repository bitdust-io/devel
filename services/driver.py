
import os
import sys
import importlib

if __name__ == '__main__':
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

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
        'network',
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

def init(callback=None):
    """
    """
    lg.out(2, 'driver.init')
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


def shutdown(callback=None):
    """
    """
    lg.out(2, 'driver.shutdown')
    for svc in services().values():
        lg.out(2, '    closing %r' % svc)
        automat.clear_object(svc.index)
    services().clear()
    if callback:
        callback()


def build_order():
    """
    """
    order = []
    for svc in services().values():
        if svc.service_name not in order:
            for depend_name in svc.dependent_on():
                if depend_name not in order:
                    order.append(depend_name)
            order.append(svc.service_name)
        else:
            index = order.index(svc.service_name)
            for depend_name in svc.dependent_on():
                if depend_name not in order:
                    order.insert(index+1, depend_name)
                else:
                    depend_index = order.index(depend_name)
                    if index < depend_index:
                        order.insert(depend_index+1, svc.service_name)
                        del order[index]
    for svc_name in services().keys():
        for depend_name in svc.dependent_on():
            if order.index(svc_name) < order.index(depend_name):
                lg.warn('dependency not satisfied: #%d:%s depend on #d:%s' % (
                    order.index(svc_name), svc.service_name, order.index(depend_name), depend_name,))
    return order


def start():
    """
    """
    lg.out(2, 'driver.start')
    order = build_order()
    for name in order:
        svc = services().get(name, None)
        if not svc:
            raise ServiceNotFound(name)
        svc.automat('start')
        
        
def stop():
    """
    """
    lg.out(2, 'driver.stop')
    order = build_order()
    for name in order.reverse():
        svc = services().get(name, None)
        if not svc:
            raise ServiceNotFound(name)
        svc.automat('stop')

#------------------------------------------------------------------------------ 

class ServiceAlreadyExist(Exception):
    pass

class RequireSubclass(Exception):
    pass

class ServiceNotFound(Exception):
    pass

#------------------------------------------------------------------------------ 

def main():
    lg.set_debug_level(20)
    init()
    print '\n'.join(build_order())
    shutdown()


if __name__ == '__main__':
    main()
    