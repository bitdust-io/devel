import subprocess
import json

#------------------------------------------------------------------------------

_SSHTunnels = {}
_NodeTunnelPort = {} 
_NextSSHTunnelPort = 10000

#------------------------------------------------------------------------------

def run_ssh_command_and_wait(host, cmd):
    if host in [None, '', b'', 'localhost', ]:
        cmd_args = cmd
    else:
        cmd_args = ['ssh', '-o', 'StrictHostKeyChecking=no', '-p', '22', 'root@%s' % host, cmd, ]
    ssh_proc = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, shell=False)
    output, err = ssh_proc.communicate()
    if err:
        print('STDERR: %r' % err)
    assert not err
    return output.decode(), err


def run_ssh_curl_and_wait(host, url, body=None, method='GET', max_time=10, *args, **kwargs):
    curl = 'curl -s -X %s ' % method
    if body:
        curl += "-d '%s' " % body
    if max_time:
        curl += "--max-time %d " % max_time
    curl += "'%s'" % url
    cmd_args = ['ssh', '-o', 'StrictHostKeyChecking=no', '-p', '22', 'root@%s' % host, curl, ]
    print('\n[%s] %s' % (host, curl, ))
    ssh_proc = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, shell=False)
    output, err = ssh_proc.communicate()
    if err:
        print('CURL ERR: %r' % err)
    assert not err
    output = output.decode()
    try:
        json_data = json.loads(output)
    except:
        print('    returned : %r' % output)
        return None
    print('    returned %d bytes JSON data' % len(output))
    return json_data


def open_tunnel(node):
    global _SSHTunnels
    global _NodeTunnelPort
    global _NextSSHTunnelPort
    if node == 'is':
        node = 'identity-server'
    local_port = int(str(_NextSSHTunnelPort))
    ssh_proc = open_ssh_port_forwarding(node, port1=local_port, port2=8180)
    _SSHTunnels[node] = ssh_proc
    _NodeTunnelPort[node] = local_port
    _NextSSHTunnelPort += 1
    print('open_tunnel [%s] on port %d with %s\n' % (node, local_port, ssh_proc, ))


def close_tunnel(node):
    global _SSHTunnels
    if node == 'is':
        node = 'identity-server'
    if node not in _SSHTunnels:
        assert False, 'ssh tunnel process for that node was not found'
    close_ssh_port_forwarding(node, _SSHTunnels[node])
    _SSHTunnels.pop(node)
    print('close_tunnel [%s] OK\n' % node)


def open_ssh_port_forwarding(node, port1, port2):
    if node == 'is':
        node = 'identity-server'
    cmd_args = ['ssh', '-4', '-o', 'StrictHostKeyChecking=no', '-p', '22', '-N', '-L', '%d:localhost:%d' % (port1, port2, ), 'root@%s' % node, ]
    print('\n[%s] %s' % (node, ' '.join(cmd_args), ))
    ssh_proc = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, shell=False)
    return ssh_proc


def close_ssh_port_forwarding(node, ssh_proc):
    if node == 'is':
        node = 'identity-server'
    print('\n[%s] closing %s' % (node, ssh_proc))
    ssh_proc.kill()
    return True


def close_all_tunnels():
    global _SSHTunnels
    for node in list(_SSHTunnels.keys()):
        if node == 'is':
            node = 'identity-server'
        close_tunnel(node)


def tunnel_port(node):
    global _NodeTunnelPort
    if node == 'is':
        node = 'identity-server'
    return _NodeTunnelPort[node]

def tunnel_url(node, endpoint):
    return 'http://127.0.0.1:%d/%s' % (tunnel_port(node), endpoint.lstrip('/'))
