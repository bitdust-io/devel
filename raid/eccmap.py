#!/usr/bin/python
# eccmap.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (eccmap.py) is part of BitDust Software.
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

"""
.. module:: eccmap.

This object holds one error correcting code map.
When creating an object we give a filename to load from or a map name to load from memory.

The spec says for each datablock which parity blocks XOR it.
As we read in each datablock we XOR all the parity blocks for it.
Probably best to read in all the datablocks at once, and do all
the parities one time.  If we did one datablock after another
the parity blocks would need to be active all the time.

If we XOR integers, we have a byte order issue probably, though
maybe not since they all stay the same order, whatever that is.

Some machines are 64-bit. Would be fun to make use of that if we have it.

    >>> 2^1  # ^ is XOR operator
    3

Parity packets have to be a little longer so they can hold
parities on signatures of datapackets.
So we can reconstruct those signatures.

Numbering is from 0 to 63 for range of 64.
"""

from __future__ import absolute_import
from __future__ import print_function
from six.moves import range
from io import open

import os
import re
import traceback

#------------------------------------------------------------------------------

_Debug = False

#------------------------------------------------------------------------------

__suppliers2eccmap = {
    2: 'ecc/2x2',
    4: 'ecc/4x4',
    7: 'ecc/7x7',
    13: 'ecc/13x13',
    18: 'ecc/18x18',
    26: 'ecc/26x26',
    64: 'ecc/64x64',
}

__suppliers_numbers = sorted(__suppliers2eccmap.keys())

__eccmap2suppliers = {
    'ecc/2x2': 2,
    'ecc/4x4': 4,
    'ecc/7x7': 7,
    'ecc/13x13': 13,
    'ecc/18x18': 18,
    'ecc/26x26': 26,
    'ecc/64x64': 64,
}

__eccmap_names = list(__eccmap2suppliers.keys())
__eccmap_names.sort()

__eccmaps = {
    'ecc/2x2': [[1], [0]],
    'ecc/4x4': [[1, 2, 3], [0, 2], [0, 3], [0, 1]],
    'ecc/7x7': [[3, 4, 6], [0, 4, 5], [1, 5, 6], [0, 2, 6], [0, 1, 3], [1, 2, 4], [2, 3, 5]],
    'ecc/13x13': [[1, 4, 8, 12], [5, 8, 9, 11], [3, 7, 10, 11], [0, 4, 6, 9], [2, 3, 6, 12],
                  [0, 1, 6, 10], [1, 3, 7, 9], [2, 5, 8, 12], [2, 4, 7, 11], [0, 1, 3, 5, 12], [6, 7, 8], [2, 5, 9, 10], [0, 4, 10, 11]],
    'ecc/18x18': [[5, 7, 11, 16, 17], [2, 9, 11, 13, 17], [5, 8, 9, 13, 15], [0, 1, 4, 6, 10], [2, 3, 12, 13, 14],
                  [6, 8, 13, 17], [2, 5, 10, 12], [3, 10, 11, 14], [0, 1, 3, 4, 5, 6, 7, 9, 10, 11, 13, 14, 15, 16, 17],
                  [0, 1, 12, 14], [5, 6, 8, 14, 16], [0, 4, 7, 9], [2, 4, 7, 8], [3, 4, 6, 11, 15],
                  [0, 10, 15, 16], [1, 2, 17], [3, 8, 12, 15], [1, 7, 9, 12, 16]],
    'ecc/26x26': [[1, 8, 11, 16, 19, 21], [3, 6, 8, 17, 23], [6, 7, 11, 17, 21, 25],
                  [0, 10, 13, 14, 21], [5, 9, 10, 18, 22], [12, 13, 17, 20, 21, 22], [1, 2, 9, 13],
                  [2, 3, 5, 9, 20, 22], [0, 6, 9, 12, 15, 25], [2, 7, 14, 15, 16, 24], [2, 5, 6, 11, 15, 16, 18, 19, 23],
                  [2, 10, 12, 13, 14, 20, 23], [0, 3, 4, 11, 19], [0, 1, 4, 18, 19, 20, 23, 25], [1, 5, 7, 11, 20, 21, 25],
                  [1, 4, 16, 17, 18], [2, 4, 11, 22, 24], [5, 12, 13, 14, 16, 24], [3, 7, 10, 20, 22, 24, 25],
                  [0, 8, 10, 12, 17], [0, 8, 9, 17, 19, 22, 25], [4, 5, 15, 16, 22], [6, 8, 12, 14, 15, 18, 23],
                  [1, 3, 7, 13, 19, 24], [0, 3, 4, 7, 14, 15, 21, 23], [6, 8, 9, 10, 18, 24]],
    'ecc/64x64': [[5, 17, 18, 31, 39, 47, 55, 58], [0, 3, 4, 25, 27, 32, 34, 48, 53, 56, 63],
                  [10, 11, 17, 18, 25, 32, 36, 40, 45, 51], [1, 21, 23, 27, 30, 35, 43, 47, 62],
                  [2, 19, 20, 21, 28, 29, 37, 38, 40, 55, 56, 62], [15, 17, 19, 20, 31, 45, 46, 54, 57, 63],
                  [19, 20, 30, 36, 46, 47, 52, 62], [2, 5, 16, 18, 19, 37, 48, 55],
                  [1, 2, 7, 12, 13, 20, 26, 28, 48, 55], [0, 1, 15, 21, 24, 33, 36, 41, 56, 62],
                  [19, 20, 28, 30, 43, 45, 52, 57, 59], [2, 6, 12, 20, 34, 58, 61, 63],
                  [5, 6, 13, 15, 25, 34, 36, 40, 42, 43, 50, 51, 55, 61, 62], [21, 22, 23, 34, 39, 41, 43, 45, 49, 52, 53, 58],
                  [0, 12, 17, 19, 28, 57, 58, 63], [8, 18, 25, 29, 34, 49, 52, 53, 56, 62],
                  [3, 6, 19, 23, 35, 39, 40, 43, 49, 54, 57], [2, 3, 8, 9, 30, 31, 47, 54, 58, 62],
                  [0, 8, 14, 24, 28, 33, 36, 47, 52, 58], [8, 10, 13, 22, 25, 27, 32, 35, 40, 51, 56],
                  [2, 14, 16, 17, 26, 27, 29, 31, 43, 46, 54, 56], [22, 25, 37, 41, 45, 52, 61], [5, 9, 13, 32, 46, 50, 54, 62],
                  [0, 4, 5, 10, 15, 16, 26, 36, 37, 48, 50], [13, 14, 20, 21, 40, 42, 55, 60], [1, 2, 13, 15, 16, 19, 26, 30, 37, 42, 48, 50, 59],
                  [4, 10, 11, 18, 28, 30, 44, 45, 46, 60, 63], [2, 6, 16, 22, 24, 38, 41, 53, 59],
                  [6, 15, 21, 23, 26, 29, 32, 34, 35, 36, 38, 43, 51, 54, 60], [13, 24, 32, 33, 34, 41, 46, 52, 58, 61],
                  [1, 10, 23, 24, 27, 29, 40, 41, 61], [4, 5, 6, 10, 14, 42, 44, 48, 51, 53, 61],
                  [0, 5, 7, 15, 49, 50], [8, 29, 35, 36, 43, 47, 51, 60, 62], [7, 12, 15, 21, 22, 27, 31, 33, 57, 60],
                  [5, 16, 18, 24, 26, 33, 38, 44, 46, 53, 56, 57, 61], [1, 3, 4, 9, 24, 27, 31, 39, 50, 51, 54, 58],
                  [12, 18, 22, 23, 27, 35, 36, 44, 60, 63], [0, 12, 17, 20, 32, 35, 37, 50, 53, 59],
                  [8, 11, 14, 16, 22, 24, 35, 36, 41, 42, 44, 46, 57], [14, 23, 30, 33, 34, 38, 42, 44, 46, 48, 54],
                  [9, 14, 27, 31, 33, 35, 49, 51, 52, 54], [3, 8, 11, 12, 14, 30, 32, 34, 48, 56, 62], [7, 9, 29, 44, 46, 58],
                  [6, 18, 21, 26, 28, 39, 40, 45, 47, 55, 58, 63], [4, 17, 21, 26, 30, 34, 54, 61], [0, 5, 6, 10, 23, 29, 39, 55, 60],
                  [7, 9, 10, 11, 12, 18, 25, 26, 29, 37, 38, 39, 42, 45, 49], [6, 7, 17, 27, 33, 56, 59, 60],
                  [1, 3, 9, 14, 20, 28, 42, 47, 57, 63], [11, 17, 23, 25, 39, 41, 45, 53, 56, 57, 60, 61, 63],
                  [4, 8, 12, 16, 19, 28, 31, 32, 47], [2, 4, 22, 23, 26, 39, 41, 42, 51, 59],
                  [0, 3, 9, 13, 25, 40, 43], [0, 9, 10, 16, 22, 47, 53, 55],
                  [1, 3, 4, 7, 13, 20, 21, 25, 49, 50], [6, 12, 15, 16, 17, 29, 33, 38, 48, 50, 55, 57, 59],
                  [1, 15, 24, 28, 37, 40, 42, 52], [1, 4, 7, 13, 14, 30, 38, 59],
                  [11, 31, 33, 37, 44, 49, 51, 52], [8, 11, 24, 31, 32, 35, 50, 53, 59, 63],
                  [3, 8, 11, 18, 22, 38, 44, 49], [7, 9, 10, 19, 37, 41, 44, 45, 49, 60, 61], [2, 3, 5, 7, 11, 38, 39, 43, 48, 59]],
}

__correctable_errors = {
    64: 10,
    26: 6,
    18: 5,
    13: 4,
    7: 3,
    4: 2,
    2: 1,
}

__fire_hire_errors = {
    64: 5,
    26: 3,
    18: 2,
    13: 2,
    7: 2,
    4: 1,
    2: 1,
}

#------------------------------------------------------------------------------

CurrentMap = None

#------------------------------------------------------------------------------


def init():
    """
    Firstly need to call that method, it will set the current map - always keep only one map in memory.
    This module can be imported inside a thread - another map will be created in memory.
    Should have no conflicts with main ecc map. Once the thread is closed - the new map will be destroyed.
    """
    global CurrentMap
    if CurrentMap is not None:
        del CurrentMap
        CurrentMap = None
    CurrentMap = eccmap(CurrentName())


def shutdown():
    """
    This clear the current map from memory.
    """
    global CurrentMap
    del CurrentMap
    CurrentMap = None

#------------------------------------------------------------------------------


def DefaultName():
    """
    This is a wrapper for ``settings.DefaultEccMapName``.
    """
    from main import settings
    return settings.DefaultEccMapName()


def CurrentName():
    """
    Should return a ecc map name from current suppliers number - taken from user settings.
    """
    from main import settings
    return GetEccMapName(settings.getSuppliersNumberDesired())


def Current():
    """
    Return current map stored in memory, if not yet created - call ``init`` method above.
    """
    global CurrentMap
    if CurrentMap is None:
        init()
    return CurrentMap


def Update():
    """
    Regenerate current map stored in memory from scratch - based on getSuppliersNumberDesired()
    """
    global CurrentMap
    if CurrentMap is not None:
        del CurrentMap
        CurrentMap = None
    CurrentMap = eccmap(CurrentName())


def SuppliersNumbers():
    """
    Return a list of valid suppliers numbers.

    This is: [2, 4, 7, 13, 18, 26, 64]
    """
    global __suppliers_numbers
    return __suppliers_numbers


def EccMapNames():
    """
    Return a list of valid ecc names.
    """
    global __eccmap_names
    return __eccmap_names


def GetEccMapName(suppliers_number):
    """
    Return a ecc map name for given suppliers number or ``DefaultName()``.
    """
    global __suppliers2eccmap
    return __suppliers2eccmap[suppliers_number]


def GetPossibleSuppliersCount():
    global __suppliers2eccmap
    return __suppliers2eccmap.keys()


def GetEccMapSuppliersNumber(eccmapname):
    """
    Reverse method, return a suppliers number for that map.
    """
    global __eccmap2suppliers
    return int(__eccmap2suppliers[eccmapname])


def GetEccMapData(name):
    """
    This return a matrix of that ecc map.

    You can see this is in the top of the file.
    """
    global __eccmaps
    return __eccmaps.get(name, None)


def GetCorrectableErrors(suppliers_number):
    """
    For every map we have different amount of "fixable" errors.
    """
    global __correctable_errors
    return __correctable_errors[suppliers_number]


def GetFireHireErrors(suppliers_number):
    """
    For every map we have different critical amount of dead suppliers.
    """
    global __fire_hire_errors
    return __fire_hire_errors[suppliers_number]

#------------------------------------------------------------------------------


def ReadTextFile(filename):
    """
    Read text file and return its content.

    Also replace line endings: \r\n with \n - convert to Linux file format.
    """
    if not os.path.isfile(filename):
        return ''
    if not os.access(filename, os.R_OK):
        return ''
    try:
        fil = open(filename, "r")
        data = fil.read()
        fil.close()
        # Windows/Linux trouble with text files
        return data.replace('\r\n', '\n')
    except:
        # lg.exc()
        traceback.print_exc()
    return ''

#------------------------------------------------------------------------------


class eccmap:
    """
    A class to do many operations with ecc map.
    """

    def __init__(self, filename='', suppliers_number=2):
        if filename != '':
            self.name = filename      # sometimes we will just want the name
            self.suppliers_number = GetEccMapSuppliersNumber(self.name)
        else:
            self.suppliers_number = suppliers_number
            self.name = GetEccMapName(self.suppliers_number)
        self.CorrectableErrors = self.CalcCorrectableErrors(self.name)
        self.ParityToData = []    # index with Parity number and output is Data numbers for that parity
        self.DataToParity = []    # index with Data number and output is Parities that use that Data number
        self.datasegments = 0     #
        self.paritysegments = 0   #
        self.type = 0             # 0 is data+parity on same nodes, 1 is different
        self.from_memory(self.name)
        self.convert()
        # lg.out(8, 'eccmap.init %s id=%d thread=%s' % (self.name, id(self), threading.currentThread().getName()))

    # def __del__(self):
    #     try:
    #         # lg.out(8, 'eccmap.del %s id=%d thread=%s' % (self.name, id(self), threading.currentThread().getName()))
    #     except:
    #         pass

    def __repr__(self):
        return '%s' % self.name

    def NumSuppliers(self):
        """
        Return a number of suppliers for the map.
        """
        return self.suppliers_number

    def DataNeeded(self):
        """
        How many good segments ensures we can fix all.
        """
        return self.datasegments - self.CorrectableErrors

    def CalcCorrectableErrors(self, filename):
        """
        We can fix at least this many errors (probably more for big nums).

        All our codes can handle at least one error.
        """
        basename = os.path.basename(filename)
        CE = 1
        if basename == "64x64":
            CE = 10
        if basename == "26x26":
            CE = 6
        if basename == "18x18":
            CE = 5
        if basename == "13x13":
            CE = 4
        if basename == "7x7":
            CE = 3
        if basename == "4x4":
            CE = 2
        if basename == "2x2":
            CE = 1
        return CE

    def from_memory(self, name):
        """
        Read the constants from memory and take needed matrix on hands.
        """
        # lg.out(6, "eccmap.from_memory with " + name)
        maxdata = 0
        maxparity = 0
        data = GetEccMapData(name)
        self.ParityToData = []
        for PS in data:
            oneset = []
            for datanum in PS:
                try:
                    oneset.append(datanum)
                    if datanum > maxdata:
                        maxdata = datanum
                except (TypeError, ValueError):
                    # lg.out(1, 'eccmap.from_memory ERROR')
                    # lg.exc()
                    traceback.print_exc()
            if oneset:
                self.ParityToData.append(oneset)
                maxparity += 1
        self.paritysegments = maxparity
        self.datasegments = maxdata + 1
        # we only do this type at the moment
        self.type = 0
        # lg.out(6, "   %s with parity=%s data=%s " % (name, self.paritysegments, self.datasegments))

    def loadfromfile(self, fname):
        """
        This is old method, I decide to move all constants into the Python
        code.
        """
        # lg.out(10, "eccmap.loadfromfile with " + fname)
        if os.path.exists(fname):
            filename = fname
        else:
            filename = os.path.join("..", fname)
        maxdata = 0
        maxparity = 0
        s = ReadTextFile(filename)
        for PS in re.split("\]", s):
            good = PS.lstrip("\[\,")
            oneset = []
            for datastring in good.split(","):
                try:
                    datanum = int(datastring)
                    oneset.append(datanum)
                    if datanum > maxdata:
                        maxdata = datanum
                except (TypeError, ValueError):
                    # lg.exc()
                    traceback.print_exc()
            if oneset:
                self.ParityToData.append(oneset)
                maxparity += 1
        self.paritysegments = maxparity
        self.datasegments = maxdata + 1
        self.type = 0                    # we only do this type at the moment
        # lg.out(10, "eccmap.loadfromfile  %s  with parity=%s  data=%s " % (filename, self.paritysegments, self.datasegments))

    def convert(self):
        """
        This creates a backward matrix and remember it.
        """
        for datanum in range(self.datasegments):
            self.DataToParity.append([])
        paritynum = 0
        for parity in self.ParityToData:
            for datanum in parity:
                self.DataToParity[datanum].append(paritynum)
            paritynum += 1

    def nodes(self):
        """
        Number of nodes/hosts/sites used for this map.
        """
        if self.type == 0:            # 0 is data+parity on same nodes, 1 is different
            return self.datasegments
        else:
            return self.datasegments + self.paritysegments

    def check(self):
        """
        This is just to test I suppose.
        """
        for emap in self.DataToParity:
            for parity in emap:
                if parity > self.paritysegments:
                    return False
        for emap in self.ParityToData:
            for data in emap:
                if data > self.datasegments:
                    return False
        return True

    def FixableNode(self, NodeMap):
        """
        Case where each node has one parity and one data so same missing.
        """
        DataSegs = [0] * self.datasegments
        ParitySegs = [0] * self.datasegments
        if len(NodeMap) != self.datasegments:
            raise Exception("eccmap.FixableNode not given NodeMap of correct length")
        if self.datasegments != self.paritysegments:
            raise Exception("eccmap.FixableNode only usable if same number of data and parity ")
        for i in range(0, self.datasegments):
            DataSegs[i] = NodeMap[i]
            ParitySegs[i] = NodeMap[i]
        return (self.Fixable(DataSegs, ParitySegs))

    def Fixable(self, DataSegs, ParitySegs):
        """
        Check is reconstruction is possible.

        Lists are 1 for Data and Parity, lists are [0,1,1,1,0...] 0 is
        don't have 1 is have.
        """
        stillMissing = 0
        for i in range(self.datasegments):
            if DataSegs[i] != 1:
                stillMissing += 1

        MakingProgress = 1
        # now we test to see if this is fixable
        while MakingProgress == 1 and stillMissing > 0:
            MakingProgress = 0
            for paritynum in range(self.paritysegments):
                if ParitySegs[paritynum] == 1:      # foreach parity
                    Parity = self.ParityToData[paritynum]  # If parity is not missing (so we can use it)
                    missing = 0                     # We will see how many of the datas are missing
                    for DataNum in Parity:          # look at all datas that went into this parity
                        if DataSegs[DataNum] == 0:  # if this data is missing
                            missing += 1  # increase count of those missing in this parity
                            lastMissing = DataNum  # keep track of the last missing in case only one is missing
                    if missing == 1:                # if missing exactly 1 of datas in parity
                        MakingProgress = 1  # then we are making progress
                        DataSegs[lastMissing] = 1  # as we could fix lastMissing with current Parity
                        stillMissing -= 1  # so one less stillMissing

        AllFixed = stillMissing == 0                # If nothing else missing we are good
        return AllFixed

    def CanMakeProgress(self, DataSegs, ParitySegs):
        """
        Another method to check if we can do some data reconstruction.

        Lists are 1 for Data and Parity, lists are [0,1,1,1,0...] 0 is
        don't have 1 is have.
        """
        for paritynum in range(self.paritysegments):  # foreach parity
            if ParitySegs[paritynum] == 1:      # If parity is not missing (so we can use it)
                Parity = self.ParityToData[paritynum]
                missing = 0                     # We will see how many of the datas are missing
                for DataNum in Parity:          # look at all datas that went into this parity
                    try:
                        if DataSegs[DataNum] != 1:  # if this data is missing
                            missing += 1  # increase count of those missing in this parity
                    except:
                        # lg.exc()
                        traceback.print_exc()
                        return False
                        #     keep track of the last missing in case only one is missing
                if missing == 1:                # if missing exactly 1 of datas in parity, we can fix the data, have work to do
                    return True
            else:                               # we're missing this parity, can we rebuild it
                Parity = self.ParityToData[paritynum]
                missing = 0                     # We will see how many of the datas are missing
                for DataNum in Parity:          # look at all datas that went into this parity
                    try:
                        if DataSegs[DataNum] != 1:  # if this data is missing
                            missing += 1  # increase count of those missing in this parity
                    except:
                        # lg.exc()
                        traceback.print_exc()
                        return False
                        #     keep track of the last missing in case only one is missing
                if missing == 0:                # if missing none of the data for this parity, we have work to do
                    return True
        return False

    def GetDataFixPath(self, DataSegs, ParitySegs, DataSegNum):
        """
        Given a missing segment number (DataSegNum) and a list of available
        Data Segments and Parity Segments.

        Identify which Parity to use to rebuild the missing Data
        Segment, return the parity segment number and the map of data
        segments in that parity.
        """
        #out(14, 'eccmap.GetDataFixPath %s %s %s' % (str(DataSegNum), str(DataSegs), str(ParitySegs)))
        bestParityNum = -1
        bestParityMap = []
        if DataSegs[DataSegNum] == 1:
            # we have the data segment nothing to fix, unclear why this was called, don't expect this to happen
            #out(12, "eccmap.GetDataFixPath we already have the data segment requested to fix?")
            return bestParityNum, bestParityMap
        for paritynum in range(0, self.paritysegments):
            # If parity is not missing (so we can use it) and contains the missing DataSegNum
            if ParitySegs[paritynum] and (DataSegNum in self.ParityToData[paritynum]):
                Parity = self.ParityToData[paritynum]
                missing = 0                       # We will see how many of the datas are missing
                for DataNum in Parity:          # look at all datas that went into this parity
                    if DataSegs[DataNum] == 0:  # if this data is missing
                        missing += 1  # increase count of those missing in this parity
                if missing == 1:              # if missing exactly 1 of datas in parity
                    if (len(bestParityMap) == 0) or (len(Parity) < len(bestParityMap)):
                        bestParityNum = paritynum
                        bestParityMap = Parity
        if _Debug:
            open('/tmp/raid.log', 'a').write(u'GetDataFixPath bestParityNum=%d\n' % bestParityNum)
        return bestParityNum, bestParityMap

#------------------------------------------------------------------------------


def main():
    """
    Tests.
    """
    myecc = eccmap("ecc/4x4")
    print(myecc.ParityToData)
    print(myecc.DataToParity)
    myecc.check()

    print("Do some checks for rebuilding a block")
    dataSegments = [1, 0, 1, 1]
    paritySegments = [1, 1, 1, 0]
    parityNum, parityMap = myecc.GetDataFixPath(dataSegments, paritySegments, 1)
    print(parityNum)       # as of the writing, the best parity was 7
    print(parityMap)
    print(myecc.Fixable(dataSegments, paritySegments))


def main2():
    """
    Another tests.
    """
    myecc = eccmap("ecc/64x64")
    print(myecc.ParityToData)
    print(myecc.DataToParity)
    myecc.check()

    print("Do some checks for rebuilding a block")
    dataSegments = [1] * 64
    paritySegments = [1] * 64
    dataSegments[2] = 0   # making it so we're missing data segment 2
    parityNum, parityMap = myecc.GetDataFixPath(dataSegments, paritySegments, 2)
    print(parityNum)       # as of the writing, the best parity was 7
    print(parityMap)
    paritySegments[7] = 0  # remove parity 7 and then try it again.
    parityNum, parityMap = myecc.GetDataFixPath(dataSegments, paritySegments, 2)
    print(parityNum)       # should be 11
    print(parityMap)

#------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
