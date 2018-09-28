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


def do_in_memory(filename, eccmapname, version, blockNumber, targetDir):
    INTSIZE = 4
    myeccmap = raid.eccmap.eccmap(eccmapname)
    # any padding at end and block.Length fixes
    RoundupFile(filename, myeccmap.datasegments * INTSIZE)
    wholefile = ReadBinaryFile(filename)
    length = len(wholefile)
    seglength = (length + myeccmap.datasegments - 1) / myeccmap.datasegments

    for DSegNum in range(myeccmap.datasegments):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(DSegNum) + '-Data'
        f = open(FileName, "wb")
        segoffset = DSegNum * seglength
        for i in range(seglength):
            offset = segoffset + i
            if offset < length:
                f.write(wholefile[offset])
            else:
                # any padding should go at the end of last seg
                # and block.Length fixes
                f.write(" ")
        f.close()

    dfds = {}
    for DSegNum in range(myeccmap.datasegments):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(DSegNum) + '-Data'
        # instead of reading data from opened file
        # we'l put it in memory
        # and store current position in the data
        # so start from zero
        #dfds[DSegNum] = [0, bpio.ReadBinaryFile(FileName)]
        dfds[DSegNum] = cStringIO.StringIO(ReadBinaryFile(FileName))

    pfds = {}
    for PSegNum in range(myeccmap.paritysegments):
        # we will keep parirty data in the momory
        # after doing all calculations
        # will write all parts on the disk
        pfds[PSegNum] = cStringIO.StringIO()

    #Parities = range(myeccmap.paritysegments)
    Parities = {}
    for i in range(seglength / INTSIZE):
        for PSegNum in range(myeccmap.paritysegments):
            Parities[PSegNum] = 0
        for DSegNum in range(myeccmap.datasegments):
            bstr = dfds[DSegNum].read(INTSIZE)
            #pos = dfds[DSegNum][0]
            #dfds[DSegNum][0] += INTSIZE
            #bstr = dfds[DSegNum][1][pos:pos+INTSIZE]
            if len(bstr) == INTSIZE:
                b, = struct.unpack(">l", bstr)
                Map = myeccmap.DataToParity[DSegNum]
                for PSegNum in Map:
                    if PSegNum > myeccmap.paritysegments:
                        # lg.out(2, "raidmake.raidmake PSegNum out of range " + str(PSegNum))
                        # lg.out(2, "raidmake.raidmake limit is " + str(myeccmap.paritysegments))
                        myeccmap.check()
                        raise Exception("eccmap error")
                    Parities[PSegNum] = Parities[PSegNum] ^ b
            else:
                raise Exception('strange read under INTSIZE bytes, len(bstr)=%d DSegNum=%d' % (len(bstr), DSegNum))
                # TODO
                #out(2, 'raidmake.raidmake WARNING strange read under INTSIZE bytes')
                #out(2, 'raidmake.raidmake len(bstr)=%s DSegNum=%s' % (str(len(bstr)), str(DSegNum)))

        for PSegNum in range(myeccmap.paritysegments):
            bstr = struct.pack(">l", Parities[PSegNum])
            #pfds[PSegNum] += bstr
            pfds[PSegNum].write(bstr)

    dataNum = len(dfds)
    parityNum = len(pfds)

    for PSegNum, data in pfds.items():
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(PSegNum) + '-Parity'
        WriteFile(FileName, pfds[PSegNum].getvalue())

    for f in dfds.values():
        f.close()
        #dataNum += 1

    for f in pfds.values():
        f.close()
        #parityNum += 1

    del myeccmap
    del dfds
    del pfds
    del Parities
    return dataNum, parityNum

    # except:
    #     return None


def do_with_files(filename, eccmapname, version, blockNumber, targetDir):
    INTSIZE = 4
    myeccmap = raid.eccmap.eccmap(eccmapname)
    RoundupFile(filename, myeccmap.datasegments * INTSIZE)      # any padding at end and block.Length fixes
    wholefile = ReadBinaryFile(filename)
    length = len(wholefile)
    seglength = (length + myeccmap.datasegments - 1) / myeccmap.datasegments                 # PREPRO -

    for DSegNum in range(myeccmap.datasegments):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(DSegNum) + '-Data'
        f = open(FileName, "wb")
        segoffset = DSegNum * seglength
        for i in range(seglength):
            offset = segoffset + i
            if (offset < length):
                f.write(wholefile[offset])
            else:
                # any padding should go at the end of last seg
                # and block.Length fixes
                f.write(" ")
        f.close()
    del wholefile

    #dfds = range(myeccmap.datasegments)
    dfds = {}
    for DSegNum in range(myeccmap.datasegments):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(DSegNum) + '-Data'
        dfds[DSegNum] = open(FileName, "rb")

    #pfds = range(myeccmap.paritysegments)
    pfds = {}
    for PSegNum in range(myeccmap.paritysegments):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(PSegNum) + '-Parity'
        pfds[PSegNum] = open(FileName, "wb")

    #Parities = range(myeccmap.paritysegments)
    Parities = {}
    for i in range(seglength / INTSIZE):
        for PSegNum in range(myeccmap.paritysegments):
            Parities[PSegNum] = 0
        for DSegNum in range(myeccmap.datasegments):
            bstr = dfds[DSegNum].read(INTSIZE).decode('utf-8')
            if len(bstr) == INTSIZE:
                b, = struct.unpack(">l", bstr)
                Map = myeccmap.DataToParity[DSegNum]
                for PSegNum in Map:
                    if PSegNum > myeccmap.paritysegments:
                        # lg.out(2, "raidmake.raidmake PSegNum out of range " + str(PSegNum))
                        # lg.out(2, "raidmake.raidmake limit is " + str(myeccmap.paritysegments))
                        myeccmap.check()
                        raise Exception("eccmap error")
                    Parities[PSegNum] = Parities[PSegNum] ^ b
            # else :
                # TODO
                # lg.warn('strange read under INTSIZE bytes')
                # lg.out(2, 'raidmake.raidmake len(bstr)=%s DSegNum=%s' % (str(len(bstr)), str(DSegNum)))

        for PSegNum in range(myeccmap.paritysegments):
            bstr = struct.pack(">l", Parities[PSegNum])
            pfds[PSegNum].write(bstr)

    dataNum = 0
    parityNum = 0

    for f in dfds.values():
        f.close()
        dataNum += 1

    for f in pfds.values():
        f.close()
        parityNum += 1

    del dfds
    del pfds
    del Parities

    return dataNum, parityNum


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
