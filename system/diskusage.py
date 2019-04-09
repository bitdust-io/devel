#!/usr/bin/python
# diskusage.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (diskusage.py) is part of BitDust Software.
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

"""
.. module:: diskusage.

This is OS specific methods to read and check the local disks usage.
Need to be sure user have enough free space on the disk and able to
donate previously specified amount of space.
"""

from __future__ import absolute_import
from __future__ import print_function
import os
import time
import glob

#------------------------------------------------------------------------------

from lib import diskspace

from main import settings

from . import bpio

#------------------------------------------------------------------------------

if bpio.Windows():
    import win32api
    import win32file

#------------------------------------------------------------------------------


def GetWinDriveSpace(drive):
    """
    For Windows.

    Return a tuple (<free space in bytes>, <total space in bytes>) or
    (None, None). Call system method ``win32file.GetDiskFreeSpace``.
    """
    try:
        sectorsPerCluster, bytesPerSector, numFreeClusters, totalNumClusters = win32file.GetDiskFreeSpace(drive + ":\\")
        sectorsPerCluster = int(sectorsPerCluster)
        bytesPerSector = int(bytesPerSector)
        numFreeClusters = int(numFreeClusters)
        totalNumClusters = int(totalNumClusters)
    except:
        return None, None
    return float(numFreeClusters * sectorsPerCluster * bytesPerSector), float(totalNumClusters * sectorsPerCluster * bytesPerSector)


def GetLinuxDriveSpace(path):
    """
    For Linux.

    Return a tuple (<free space in bytes>, <total space in bytes>) or
    (None, None). Call system method ``os.statvfs``.
    """
    try:
        s = os.statvfs(str(path))
        # free, total = s.f_bsize*(s.f_blocks-s.f_bavail), s.f_bsize * s.f_bavail
        # free, total = float(s.f_bsize * s.f_bavail), float(s.f_bsize * s.f_blocks)
        # free, total = float(s.f_frsize * s.f_bavail), float(s.f_bsize * s.f_blocks)
        free, total = float(s.f_frsize * s.f_bavail), float(s.f_frsize * s.f_blocks)
        return free, total
    except:
        return None, None
#    if free > total:
#        return total, free
#    else:
#        return free, total


def GetDriveSpace(path):
    """
    So this a sort of portable way to get the free HDD space in the system.
    """
    if bpio.Windows():
        drive = os.path.abspath(path)[0]
        if os.path.isdir(drive + ':'):
            # the drive the data directory is on, ie C
            return GetWinDriveSpace(drive)
        else:
            return None, None
    else:
        # on linux the mount points can make a directory be off a different disk than root
        return GetLinuxDriveSpace(path)


def SumFileSizes(fileList):
    """
    Just iterate the input list and call ``os.path.getsize`` for every item,
    also calculate and return the total size.
    """
    fileSizeTotal = 0
    for filename in fileList:
        try:
            fileSizeTotal += os.path.getsize(filename)
        except:
            pass
    return fileSizeTotal


def GetOurTempFileSizeTotal(tempDirectory, masks=['*', ]):
    """
    Not used right now.

    Tried here to calculate our temporary files size. Temp files was
    reorganized and so this must be rewritten. TODO.
    """
    ourFileSizes = 0
    for mask in masks:
        ourFileSizes += SumFileSizes(glob.glob(os.path.join(tempDirectory, mask)))
    return ourFileSizes


def OkToShareSpace(desiredSharedSpaceMB):
    """
    Make sure a user really has the space they claim they want to share.
    """
    dataDir = settings.getCustomersFilesDir()
    dataDriveFreeSpace, dataDriveTotalSpace = GetDriveSpace(dataDir)
    if not dataDriveFreeSpace or not dataDriveTotalSpace:
        return False
    try:
        # TODO: say if less than 10% free storage left of your HDD do not share
        testFree = (dataDriveFreeSpace / dataDriveTotalSpace) > 0.1
    except:
        testFree = False
    if not testFree:
        return False
    currentlySharedSpace = GetDirectorySize(dataDir)
    if (currentlySharedSpace + dataDriveFreeSpace / (1024 * 1024)) < desiredSharedSpaceMB:
        return False
    return True


def GetDirectorySize(directoryPath):
    """
    Calculates the folder size in megabytes using ``bpio.getDirectorySize``.
    """
    return bpio.getDirectorySize(directoryPath) / (1024 * 1024)

#------------------------------------------------------------------------------


def main():
    """
    This method is for tests.

    Need to move all things here to unit tests. TODO.
    """
    dataDir = settings.getCustomersFilesDir()
    tempDir = settings.TempDir()
    dataDriveFreeSpace = 0
    dataDriveTotalSpace = 0
    tempDriveFreeSpace = 0
    tempDriveTotalSpace = 0

    dataDriveFreeSpace, dataDriveTotalSpace = GetDriveSpace(dataDir)
    tempDriveFreeSpace, tempDriveTotalSpace = GetDriveSpace(tempDir)

    print("data dir =", dataDir)
    print("tep dir =", tempDir)
    print("data dir: " + str(dataDriveFreeSpace / (1024 * 1024)) + "MB free/" + str(dataDriveTotalSpace / (1024 * 1024)) + "MB total")
    print("temp dir: " + str(tempDriveFreeSpace / (1024 * 1024)) + "MB free/" + str(tempDriveTotalSpace / (1024 * 1024)) + "MB total")

    print(time.time())
    print("our temp files: " + str(GetOurTempFileSizeTotal(tempDir) / (1024 * 1024)) + "MB")
    print(time.time())

    GetDirectorySize(dataDir)

    ds = diskspace.DiskSpace()
    print(ds.getValueBest(dataDriveFreeSpace))

    print("at OkToShareSpace ...")
    print("ok to share 100MB - should be true")
    print(OkToShareSpace(100))
    print("ok to share 12345678MB - should be false")
    print(OkToShareSpace(12345678))


if __name__ == '__main__':
    main()
