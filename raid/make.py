#!/usr/bin/python
# raidmake.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
import copy
import array

#------------------------------------------------------------------------------

if __name__ == '__main__':
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))

#------------------------------------------------------------------------------

import raid.eccmap
import raid.raidutils

#------------------------------------------------------------------------------

_Debug = False

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
        f.write(b' ' * increase)
        f.close()


def ReadBinaryFile(filename):
    """
    """
    if not os.path.isfile(filename):
        return b''
    if not os.access(filename, os.R_OK):
        return b''
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


def ReadBinaryFileAsArray(filename):
    """
    """
    if not os.path.isfile(filename):
        return b''
    if not os.access(filename, os.R_OK):
        return b''

    with open(filename, "rb") as f:
        values = array.array('i', f.read())

    values.byteswap()
    return values


def do_in_memory(filename, eccmapname, version, blockNumber, targetDir):
    try:
        if _Debug:
            open('/tmp/raid.log', 'a').write(u'do_in_memory filename=%s eccmapname=%s blockNumber=%s\n' % (repr(filename), eccmapname, blockNumber))
        INTSIZE = 4
        myeccmap = raid.eccmap.eccmap(eccmapname)
        # any padding at end and block.Length fixes
        RoundupFile(filename, myeccmap.datasegments * INTSIZE)
        wholefile = ReadBinaryFileAsArray(filename)
        length = len(wholefile)
        length = length * 4
        seglength = (length + myeccmap.datasegments - 1) / myeccmap.datasegments
    
        #: dict of data segments
        sds = {}
        for seg_num, chunk in enumerate(raid.raidutils.chunks(wholefile, int(seglength / 4))):
            FileName = targetDir + '/' + str(blockNumber) + '-' + str(seg_num) + '-Data'
            with open(FileName, "wb") as f:
                chunk_to_write = copy.copy(chunk)
                chunk_to_write.byteswap()
                sds[seg_num] = iter(chunk)
                f.write(chunk_to_write)
    
        psds_list = raid.raidutils.build_parity(
            sds, int(seglength / INTSIZE), myeccmap.datasegments, myeccmap, myeccmap.paritysegments)
    
        dataNum = len(sds)
        parityNum = len(psds_list)
    
        for PSegNum, _ in psds_list.items():
            FileName = targetDir + '/' + str(blockNumber) + '-' + str(PSegNum) + '-Parity'
            with open(FileName, 'wb') as f:
                f.write(psds_list[PSegNum])
    
        return dataNum, parityNum

    except:
        import traceback
        traceback.print_exc()
        return -1, -1


def main():
    do_in_memory(
        filename=sys.argv[1],
        eccmapname=sys.argv[2],
        version=sys.argv[3],
        blockNumber=int(sys.argv[4]),
        targetDir=sys.argv[5]
    )


if __name__ == "__main__":
    main()
