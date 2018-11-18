import subprocess
import json


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


def run_ssh_curl_and_wait(host, url, body=None, method='GET', *args, **kwargs):
    curl = 'curl -s -X %s ' % method
    if body:
        curl += "-d '%s' " % body
    curl += "'%s'" % url
    cmd_args = ['ssh', '-o', 'StrictHostKeyChecking=no', '-p', '22', 'root@%s' % host, curl, ]
    ssh_proc = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, shell=False)
    output, err = ssh_proc.communicate()
    if err:
        print('CURL ERR: %r' % err)
    assert not err
    json_data = json.loads(output.decode())
    return json_data
