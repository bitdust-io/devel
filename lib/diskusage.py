#!/usr/bin/python
#diskusage.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: diskusage

This is OS specific methods to read and check the local disks usage.
Need to be sure user have enough free space on the disk and able to donate previously specified amount of space. 
"""

import os
import time
import glob

import dhnio
import settings
import diskspace

if dhnio.Windows():
    import win32api
    import win32file

#------------------------------------------------------------------------------ 

def GetWinDriveSpace(drive):
    """
    For Windows.
    Return a tuple (<free space in bytes>, <total space in bytes>) or (None, None).
    Call system method ``win32file.GetDiskFreeSpace``.
    """ 
    try:
        sectorsPerCluster, bytesPerSector, numFreeClusters, totalNumClusters = win32file.GetDiskFreeSpace(drive + ":\\")
        sectorsPerCluster = long(sectorsPerCluster)
        bytesPerSector = long(bytesPerSector)
        numFreeClusters = long(numFreeClusters)
        totalNumClusters = long(totalNumClusters)
    except:
        return None, None
    return float(numFreeClusters * sectorsPerCluster * bytesPerSector), float(totalNumClusters * sectorsPerCluster * bytesPerSector)

def GetLinuxDriveSpace(path):
    """
    For Linux.
    Return a tuple (<free space in bytes>, <total space in bytes>) or (None, None).
    Call system method ``os.statvfs``.    
    """ 
    try:
        s = os.statvfs(str(path))
        # free, total = s.f_bsize*(s.f_blocks-s.f_bavail), s.f_bsize * s.f_bavail 
        # free, total = float(s.f_bsize * s.f_bavail), float(s.f_bsize * s.f_blocks)
        free, total = float(s.f_frsize * s.f_bavail), float(s.f_bsize * s.f_blocks) 
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
    if dhnio.Windows():
        drive = os.path.abspath(path)[0]
        if os.path.isdir(drive+':'):
            # the drive the data directory is on, ie C
            return GetWinDriveSpace(drive)
        else:
            return None, None
    else:
        # on linux the mount points can make a directory be off a different disk than root
        return GetLinuxDriveSpace(path)

def SumFileSizes(fileList):
    """
    Just iterate the input list and call ``os.path.getsize`` for every item, also calculate and return the total size.
    """
    fileSizeTotal = 0
    for filename in fileList:
        try:
            fileSizeTotal += os.path.getsize(filename)
        except:
            pass
    return fileSizeTotal

def GetOurTempFileSizeTotal(tempDirectory):
    """
    Not used right now.
    Tried here to calculate our temporary files size.
    Temp files was reorganized and so this must be rewritten. TODO.
    """
    ourFileMasks = ['*-Data', '*-Parity', '*dhn*', '*.controloutbox', 'newblock-*', '*.backup']
    ourFileSizes = 0
    for mask in ourFileMasks:
        ourFileSizes += SumFileSizes(glob.glob(os.path.join(tempDirectory, mask)))
    return ourFileSizes

def OkToShareSpace(desiredSharedSpaceMB):
    """
    Make sure a user really has the space they claim they want to share.
    """
    dataDir = settings.getCustomersFilesDir()
    dataDriveFreeSpace, dataDriveTotalSpace = GetDriveSpace(dataDir)
    if dataDriveFreeSpace is None:
        return False
    currentlySharedSpace = GetDirectorySize(dataDir)
    if (currentlySharedSpace + dataDriveFreeSpace/(1024*1024)) < desiredSharedSpaceMB:
        return False
    else:
        return True
    
def GetDirectorySize(directoryPath):
    """
    Just calculates the folder size in megabytes using ``dhnio.getDirectorySize``.
    """
    return dhnio.getDirectorySize(directoryPath)/(1024*1024)

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

    print "data dir =", dataDir
    print "tep dir =", tempDir
    print "data dir: " + str(dataDriveFreeSpace/(1024*1024)) +"MB free/" + str(dataDriveTotalSpace/(1024*1024)) +"MB total"
    print "temp dir: " + str(tempDriveFreeSpace/(1024*1024)) +"MB free/" + str(tempDriveTotalSpace/(1024*1024)) +"MB total"

    print time.time()
    print "our temp files: " + str(GetOurTempFileSizeTotal(tempDir)/(1024*1024)) + "MB"
    ourFileMasks = ['*-Data', '*-Parity', '*dhn*', '*.controloutbox', 'newblock-*', '*.backup']
    for mask in ourFileMasks:
        print time.time()
        print mask + "=" + str(SumFileSizes(glob.glob(os.path.join(tempDir, mask))))

    print time.time()

    GetDirectorySize(dataDir)

    ds = diskspace.DiskSpace()
    print ds.getValueBest(dataDriveFreeSpace)

    print "at OkToShareSpace ..."
    print "ok to share 100MB - should be true"
    print OkToShareSpace(100)
    print "ok to share 12345678MB - should be false"
    print OkToShareSpace(12345678)


if __name__ == '__main__':
    main()
