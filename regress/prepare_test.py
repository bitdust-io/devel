import os
import sys
import json


test_name = sys.argv[1]

conf = json.loads(open(os.path.join('tests', test_name, 'conf.json')).read())

default_image = conf.get('default_image', 'bitdust-baseimage')
ports_offset = int(conf.get('ports_offset', 0))

tester_links_src = ''
for link in conf['tester_links']:
    tester_links_src +=  f'      - {link}\n'

tester_volumes_src = ''
for volume in conf.get('tester_volumes', []):
    tester_volumes_src +=  f'      - {volume}\n'

containers_volumes_src = ''
for volume in conf.get('containers_volumes', []):
    containers_volumes_src +=  f'  {volume}\n'

all_containers_src = ''  
for container_name, container_info in conf['containers'].items():
    container_image = container_info.get('image', default_image)
    container_ports = container_info['ports'].split(':')
    container_ports = "%s:%s" % ((int(container_ports[0]) + ports_offset), container_ports[1])
    container_links = container_info.get('links')
    container_volumes = container_info.get('volumes')
    container_src = f'''
  {container_name}:
    image: {container_image}
    ports:
      - "{container_ports}"'''
    if container_volumes:
        container_volumes_src = ''
        for volume in container_volumes:
            container_volumes_src +=  f'\n      - {volume}'
        container_src += f'''
    volumes:{container_volumes_src}'''
    if container_links:
        container_links_src = ''
        for link in container_links:
            container_links_src +=  f'\n      - {link}'
        container_src += f'''
    links:{container_links_src}'''
    all_containers_src += (container_src + '\n')

docker_compose_template = open('docker-compose.template').read()
docker_compose_src = docker_compose_template.format(
    test_name=test_name,
    containers=all_containers_src,
    tester_links=tester_links_src,
    tester_volumes=tester_volumes_src,
    containers_volumes=containers_volumes_src,
)

open(os.path.join('tests', test_name, 'docker-compose.yml'), 'wt').write(docker_compose_src)
