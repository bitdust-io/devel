#!/bin/bash

PYTHON2=`which python`
PYTHON3=`which python3`


if [ -z "$PYTHON2" ] then
    PYTHON="$PYTHON2"
else
    PYTHON="$PYTHON3"
fi

$PYTHON --version

exit 0


test_name="$1"

rm -rf logs/$test_name
mkdir logs/$test_name

allnodesfile="allnodes"
rm -rf $allnodesfile

echo "$test_name" | $PYTHON -c "import json,sys; tst=sys.stdin.read().strip(); containers=json.loads(open('tests/%s/conf.json' % tst).read())['containers'].keys(); open('allnodes', 'w').write(' '.join(containers));"

nodes=`cat $allnodesfile`

for node in $nodes; do
    echo "[$node]";
    docker-compose --file tests/$test_name/docker-compose.yml exec -T $node sh -c "cat /root/.bitdust/logs/automats.log" > logs/$test_name/state.$node.log;
    docker-compose --file tests/$test_name/docker-compose.yml exec -T $node sh -c "cat /root/.bitdust/logs/event.log" > logs/$test_name/event.$node.log;
    docker-compose --file tests/$test_name/docker-compose.yml exec -T $node sh -c "cat /root/.bitdust/logs/packet.log" > logs/$test_name/packet.$node.log;
    docker-compose --file tests/$test_name/docker-compose.yml exec -T $node sh -c "cat /root/.bitdust/logs/stdout.log" > logs/$test_name/stdout.$node.log;
done

rm -rf $allnodesfile
