#!/usr/bin/python
# raidmake.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (make.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#

#
# Input is a file and a RAID spec.
# The spec says for each datablock which parity blocks XOR it.
# As we read in each datablock we XOR all the parity blocks for it.
# Probably best to read in all the datablocks at once, and do all
# the parities one time.  If we did one datablock after another
# the parity blocks would need to be active all the time.
#
# If we XOR integers, we have a byte order issue probably, though
# maybe not since they all stay the same order, whatever that is.
#
# Some machines are 64-bit.  Would be fun to make use of that if
# we have it.
#
# 2^1 => 3       ^ is XOR operator
#
# Parity packets have to be a little longer so they can hold
# parities on signatures of datapackets.  So we can reconstruct
# those signatures.
#
#

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import open

#------------------------------------------------------------------------------

import os
import sys
import struct
import cStringIO
import array

unpack = struct.Struct('>l').unpack
pack = struct.Struct('>l').pack

#------------------------------------------------------------------------------

if __name__ == '__main__':
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))

#------------------------------------------------------------------------------

import raid.eccmap

#------------------------------------------------------------------------------

_ECCMAP = {}

#------------------------------------------------------------------------------

def geteccmap(name):
    global _ECCMAP
    if name not in _ECCMAP:
        _ECCMAP[name] = raid.eccmap.eccmap(name)
    return _ECCMAP[name]

#------------------------------------------------------------------------------

def shutdown():
    global _ECCMAP
    _ECCMAP.clear()

#------------------------------------------------------------------------------


def RoundupFile(filename, stepsize):
    """
    For some things we need to have files which are round sizes, for example
    some encryption needs files that are multiples of 8 bytes.

    This function rounds file up to the next multiple of step size.
    """
    try:
        size = os.path.getsize(filename)
    except:
        return
    mod = size % stepsize
    increase = 0
    if mod > 0:
        increase = stepsize - mod
        f = open(filename, 'ab')
        f.write(' ' * increase)
        f.close()


def ReadBinaryFile(filename):
    """
    """
    if not os.path.isfile(filename):
        return ''
    if not os.access(filename, os.R_OK):
        return ''
    f = open(filename, "rb")
    data = f.read()
    f.close()
    return data


def WriteFile(filename, data):
    """
    """
    if sys.version_info[0] == 3:
        binary_type = bytes
    else:
        binary_type = str
    s = data
    if not isinstance(s, binary_type):
        s = s.encode('utf-8')
    f = open(filename, "wb")
    f.write(s)
    f.close()

#------------------------------------------------------------------------------

# def raidmake(filename, eccmapname, backupId, blockNumber, targetDir=None, in_memory=True):
#    # lg.out(12, "raidmake.raidmake BEGIN %s %s %s %d" % (
#    #     os.path.basename(filename), eccmapname, backupId, blockNumber))
#    # t = time.time()
#    if in_memory:
#        dataNum, parityNum = do_in_memory(filename, eccmapname, backupId, blockNumber, targetDir)
#    else:
#        dataNum, parityNum = do_with_files(filename, eccmapname, backupId, blockNumber, targetDir)
#        # lg.out(12, "raidmake.raidmake time=%.3f data=%d parity=%d" % (time.time()-t, dataNum, parityNum))
#    return dataNum, parityNum


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i + n]


def ReadBinaryFile2(filename):
    """
    """
    if not os.path.isfile(filename):
        return ''
    if not os.access(filename, os.R_OK):
        return ''
    length = os.stat(filename).st_size

    with open(filename, "rb") as f:
        values = array.array('i', f.read())

    values.byteswap()
    return values


def do_in_memory(filename, eccmapname, version, blockNumber, targetDir):
    import copy
    INTSIZE = 4
    myeccmap = raid.eccmap.eccmap(eccmapname)
    # any padding at end and block.Length fixes
    RoundupFile(filename, myeccmap.datasegments * INTSIZE)
    wholefile = ReadBinaryFile2(filename)
    length = len(wholefile)
    length = length * 4
    seglength = (length + myeccmap.datasegments - 1) / myeccmap.datasegments
    iters = seglength / INTSIZE

    #: dict of data segments
    sds = {}
    sds_ = {}
    dfds = {}
    pfds = {}
    for seg_num, chunk in enumerate(chunks(wholefile, seglength / 4)):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(seg_num) + '-Data'
        with open(FileName, "wb") as f:
            chunk_to_write = copy.copy(chunk)
            sds[seg_num] = iter(chunk)

            pfds[seg_num] = cStringIO.StringIO()

            chunk_to_write.byteswap()
            f.write(chunk_to_write)

    Parities = {}

    for i in range(iters):
        for PSegNum in range(myeccmap.paritysegments):
            Parities[PSegNum] = 0
        for seg_num in range(myeccmap.datasegments):
            bstr = next(sds[seg_num])

            # assert len(bstr) == INTSIZE, 'strange read under INTSIZE bytes, len(bstr)=%d seg_num=%d' % (len(bstr), seg_num)

            b = bstr
            # b, = unpack(bstr)
            Map = myeccmap.DataToParity[seg_num]
            for PSegNum in Map:
                if PSegNum > myeccmap.paritysegments:
                    myeccmap.check()
                    raise Exception("eccmap error")
                Parities[PSegNum] = Parities[PSegNum] ^ b

        for PSegNum in range(myeccmap.paritysegments):
            bstr = pack(Parities[PSegNum])
            pfds[PSegNum].write(bstr)

    dataNum = len(dfds)
    parityNum = len(pfds)

    for PSegNum, data in pfds.items():
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(PSegNum) + '-Parity'
        WriteFile(FileName, pfds[PSegNum].getvalue())

    return dataNum, parityNum

    # except:
    #     return None


def main():
    from logs import lg
    lg.set_debug_level(18)
    do_in_memory(
        filename=sys.argv[1],
        eccmapname=sys.argv[2],
        version=sys.argv[3],
        blockNumber=int(sys.argv[4]),
        targetDir=sys.argv[5]
    )


if __name__ == "__main__":
    main()
