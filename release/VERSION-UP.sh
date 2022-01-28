#!/bin/bash

echo "[ update revision number ]"

echo "core version is:"
cat core_version
echo ""

git rev-list --count HEAD >revnum
REVNUM=`cat revnum`
echo "revision number based on total amount of commits in the Git repository is"
cat revnum

echo "current version number in the local file is:"
cat version
echo ""

echo "[ updateing version number ]"
python -c "cv=open('core_version').read().strip().split('.');v=list(open('version').read().strip().split('.'));v[0]=cv[0];v[1]=cv[1];v[-2]=str(int(v[-2])+1);v[-1]=open('revnum').read().strip();open('version','w').write(('.'.join(v)).strip())"
rm -rf revnum

echo "new version is: "
cat version
echo ""

VER=`cat version`

echo "[ local version file updated ]"
