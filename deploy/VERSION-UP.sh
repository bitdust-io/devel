#!/bin/bash
# cd ~/bitdust/release/
echo "[ update revision number ]"
git rev-list --count HEAD >revnum
REVNUM=`cat revnum`
echo "revision number is ${REVNUM}"
echo "[ update version number ]"
echo "current version number is: "
cat version
python -c "v=list(open('version').read().strip().split('.'));v[-2]=str(int(v[-2])+1);v[-1]=open('revnum').read().strip();open('version','w').write(('.'.join(v)).strip())"
rm revnum
echo "new version is: "
cat version
VER=`cat version`
echo "[ version UPDATED ]"
