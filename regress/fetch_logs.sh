#!/bin/bash

test_name="$1"

rm -rf logs/$test_name
mkdir logs/$test_name

allnodesfile="allnodes"
rm -rf $allnodesfile

echo "$test_name" | python3 -c "import json,sys; tst=sys.stdin.read().strip(); containers=json.loads(open('tests/%s/conf.json' % tst).read())['containers'].keys(); open('allnodes', 'w').write(' '.join(containers));"

nodes=`cat $allnodesfile`

fetch_one(){
    # echo "reading logs [$1/$2]";
    mkdir -p logs/$1/
    rm -rf logs/$1/$2/
    rm -rf logs/$1/$2.tar
    mkdir -p logs/$1/$2/
    docker-compose --file tests/$1/docker-compose.yml exec -T $2 sh -c "cd /root/.bitdust/logs/; tar -cf logs.tar *; cat /root/.bitdust/logs/logs.tar;" 1> logs/$1/$2.tar 2>/dev/null;
    tar -xf logs/$1/$2.tar -C logs/$1/$2/
    rm -rf logs/$1/$2.tar
    # echo "success [$1/$2]"
}

for node in $nodes; do
	fetch_one $test_name $node &
done

wait

rm -rf $allnodesfile
