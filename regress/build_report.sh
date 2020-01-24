#!/bin/bash

test_name="$1"

mkdir -p logs/$test_name

echo "$test_name" | python3 -c "import json,sys; tst=sys.stdin.read().strip(); containers=json.loads(open(f'tests/{tst}/conf.json').read())['containers'].keys(); open('allnodes', 'w').write(' '.join(containers));"

allnodesfile="allnodes"
nodes=`cat $allnodesfile`

for node in $nodes; do
    echo "[$node]";
    docker-compose --file tests/$test_name/docker-compose.yml exec $node sh -c "curl localhost:8180/network/info/v1" > logs/$test_name/report.$node.log;
done

rm -rf $allnodesfile
