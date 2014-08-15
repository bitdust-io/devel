#checksum.py

import os
import sys

sys.path.append(os.path.join('..','..'))
from lib import misc


def mkinfo(dirpath):
    r = ''
    for root, dirs, files in os.walk(dirpath):
        for fname in files:
            abspath = os.path.abspath(os.path.join(root,fname))
            relpath = os.path.join(root,fname)
            relpath = relpath.split(os.sep, 1)[1]
            txt = misc.file_hash(abspath)+' '+relpath+'\n'
            r += txt
    return r


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print 'checksum.py [source folder path] [output file]'
    else:
        src = mkinfo(sys.argv[1])
        fout = open(sys.argv[2], 'w')
        fout.write(src)
        fout.close()
        sys.stdout.write(misc.get_hash(src))

