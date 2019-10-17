#!/bin/bash

test_name="$1"

rm -rf logs/$test_name
mkdir logs/$test_name

echo "$test_name" | python3 -c "import json,sys; tst=sys.stdin.read().strip(); containers=json.loads(open(f'tests/{tst}/conf.json').read())['containers'].keys(); open('allnodes', 'w').write(' '.join(containers));"

allnodesfile="allnodes"
nodes=`cat $allnodesfile`

for node in $nodes; do
    echo "[$node]";
    docker-compose --file tests/$test_name/docker-compose.yml exec $node sh -c "cat /root/.bitdust/logs/automats.log" > logs/$test_name/state.$node.log;
    docker-compose --file tests/$test_name/docker-compose.yml exec $node sh -c "cat /root/.bitdust/logs/event.log" > logs/$test_name/event.$node.log;
    docker-compose --file tests/$test_name/docker-compose.yml exec $node sh -c "cat /root/.bitdust/logs/packet.log" > logs/$test_name/packet.$node.log;
    docker-compose --file tests/$test_name/docker-compose.yml exec $node sh -c "cat /root/.bitdust/logs/stdout.log" > logs/$test_name/stdout.$node.log;
done

rm -rf $allnodesfile
