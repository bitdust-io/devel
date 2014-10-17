#!/usr/bin/python
#raidmake.py
#
# <<<COPYRIGHT>>>
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
import os
import sys
import struct
import time
import cStringIO
import platform

if __name__ == '__main__':
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))

import raid.eccmap

#------------------------------------------------------------------------------ 

_ECCMAP = {}
def geteccmap(name):
    global _ECCMAP
    if not _ECCMAP.has_key(name):
        _ECCMAP[name] = raid.eccmap.eccmap(name) 
    return _ECCMAP[name]

#------------------------------------------------------------------------------ 

def shutdown():
    global _ECCMAP
    _ECCMAP.clear()

#------------------------------------------------------------------------------ 

def RoundupFile(filename, stepsize):
    """
    For some things we need to have files which are round sizes, 
    for example some encryption needs files that are multiples of 8 bytes.
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
        file = open(filename, 'a')         
        file.write(' ' * increase)
        file.close()

def ReadBinaryFile(filename):
    """
    """
    if not os.path.isfile(filename):
        return ''
    if not os.access(filename, os.R_OK):
        return ''
    try:
        file = open(filename, "rb")
        data = file.read()
        file.close()
        return data
    except:
        return ''

def WriteFile(filename, data):
    """
    """
    f = open(filename, "wb")
    f.write(data)
    f.close()
#    
#    try:
#        tmpfilename = filename + ".new"
#        f = open(tmpfilename, "wb")
#        f.write(data)
#        f.flush()
#        #from http://docs.python.org/library/os.html on os.fsync
#        os.fsync(f.fileno())
#        f.close()
#        #in Unix the rename will overwrite an existing file,
#        #but in Windows it fails, so have to remove existing
#        if platform.uname()[0] == "Windows" and os.path.exists(filename):
#            os.remove(filename)
#        os.rename(tmpfilename, filename)
#    except:
#        try:
#            f.close() # make sure file gets closed
#        except:
#            pass
#        return False
#    return True

#------------------------------------------------------------------------------ 

def raidmake(filename, eccmapname, backupId, blockNumber, targetDir=None, in_memory=True):
    # lg.out(12, "raidmake.raidmake BEGIN %s %s %s %d" % (
    #     os.path.basename(filename), eccmapname, backupId, blockNumber))
    t = time.time()
    if in_memory:
        dataNum, parityNum = do_in_memory(filename, eccmapname, backupId, blockNumber, targetDir)
    else:
        dataNum, parityNum = do_with_files(filename, eccmapname, backupId, blockNumber, targetDir)
    # lg.out(12, "raidmake.raidmake time=%.3f data=%d parity=%d" % (time.time()-t, dataNum, parityNum))
    return dataNum, parityNum


def do_in_memory(filename, eccmapname, backupId, blockNumber, targetDir):
    myeccmap = raid.eccmap.eccmap(eccmapname)
    INTSIZE = 4 # settings.IntSize()
    # any padding at end and block.Length fixes
    RoundupFile(filename, myeccmap.datasegments*INTSIZE)     
    wholefile = ReadBinaryFile(filename)
    length = len(wholefile)
    seglength = (length + myeccmap.datasegments - 1) / myeccmap.datasegments                 

    for DSegNum in xrange(myeccmap.datasegments):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(DSegNum) + '-Data'
        f = open(FileName, "wb")
        segoffset = DSegNum * seglength
        for i in xrange(seglength):
            offset = segoffset + i;
            if offset < length:
                f.write(wholefile[offset])
            else:
                # any padding should go at the end of last seg 
                # and block.Length fixes
                f.write(" ")               
        f.close()
        
    dfds = {}
    for DSegNum in xrange(myeccmap.datasegments):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(DSegNum) + '-Data'
        # instead of reading data from opened file 
        # we'l put it in memory 
        # and store current position in the data
        # so start from zero 
        #dfds[DSegNum] = [0, bpio.ReadBinaryFile(FileName)]
        dfds[DSegNum] = cStringIO.StringIO(ReadBinaryFile(FileName))

    pfds = {}
    for PSegNum in xrange(myeccmap.paritysegments):
        # we will keep parirty data in the momory
        # after doing all calculations
        # will write all parts on the disk
        pfds[PSegNum] = cStringIO.StringIO()

    #Parities = range(myeccmap.paritysegments)
    Parities = {}
    for i in xrange(seglength/INTSIZE):
        for PSegNum in xrange(myeccmap.paritysegments):
            Parities[PSegNum] = 0
        for DSegNum in xrange(myeccmap.datasegments):
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
                #TODO
                #out(2, 'raidmake.raidmake WARNING strange read under INTSIZE bytes')
                #out(2, 'raidmake.raidmake len(bstr)=%s DSegNum=%s' % (str(len(bstr)), str(DSegNum)))

        for PSegNum in xrange(myeccmap.paritysegments):
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


def do_with_files(filename, eccmapname, backupId, blockNumber, targetDir):
    myeccmap = raid.eccmap.eccmap(eccmapname)
    INTSIZE = 4 # settings.IntSize()
    RoundupFile(filename,myeccmap.datasegments*INTSIZE)      # any padding at end and block.Length fixes
    wholefile = ReadBinaryFile(filename)
    length = len(wholefile)
    seglength = (length + myeccmap.datasegments - 1)/myeccmap.datasegments                 # PREPRO -

    for DSegNum in range(myeccmap.datasegments):
        FileName = targetDir + '/' + str(blockNumber) + '-' + str(DSegNum) + '-Data'
        f = open(FileName, "wb")
        segoffset = DSegNum * seglength
        for i in range(seglength):
            offset = segoffset + i;
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
        FileName = targetDir + '/' +  str(blockNumber) + '-' + str(PSegNum) + '-Parity'
        pfds[PSegNum] = open(FileName, "wb")

    #Parities = range(myeccmap.paritysegments)
    Parities = {}
    for i in range(seglength/INTSIZE):
        for PSegNum in range(myeccmap.paritysegments):
            Parities[PSegNum] = 0
        for DSegNum in range(myeccmap.datasegments):
            bstr = dfds[DSegNum].read(INTSIZE)
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
                #TODO
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
    raidmake(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6]=='1')
    

if __name__ == "__main__":
    main()



