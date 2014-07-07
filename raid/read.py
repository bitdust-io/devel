#!/usr/bin/python
#raidread.py
#
# <<<COPYRIGHT>>>
#
#
#
#

#
# This is to read some possibly incomplete raid data and recover original data.
#
# Basic idea is to find a parity that is only missing one data, then fix that
#  data, and look at parities again to see if another is now missing only one.
#  This can be called an "iterative algorithm" or "belief propagation".
#  There are algorithms that can recover data when this can not, but
#    they are more complicated.
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
# 2^1 => 3       ^ is XOR operator  - so maybe we can do it in Python
#
# In the production code, when there are multiple errors we really want
# to fix the one we can fix fastest first.  The only danger is that
# we get too many errors at the same time.  We reduce this danger if
# we fix the one we can fix fastest first.


import struct
import os
import sys


import lib.dhnio as dhnio
import lib.eccmap as eccmap
import lib.settings as settings

INTSIZE = 4

#------------------------------------------------------------------------------ 

_ECCMAP = {}
def geteccmap(name):
    global _ECCMAP
    if not _ECCMAP.has_key(name):
        _ECCMAP[name] = eccmap.eccmap(name) 
    return _ECCMAP[name]

#------------------------------------------------------------------------------ 

def shutdown():
    global _ECCMAP
    _ECCMAP.clear()

#------------------------------------------------------------------------------ 

#RebuildOne_new and RebuildOne_orig are just for debugging purposes
def RebuildOne(inlist, listlen, outfilename):
    readsize = 1 # vary from 1 byte to 4 bytes
    raidfiles = [''] * listlen # range(listlen)   # just need a list of this size
    raidreads = [''] * listlen # range(listlen)
    for filenum in xrange(listlen):
        try:
            raidfiles[filenum] = open(inlist[filenum], "rb")
        except:
            dhnio.DprintException()
            for f in raidfiles:
                try:
                    f.close()
                except:
                    pass 
            return 
    rebuildfile = open(outfilename, "wb")
    while True:
        for k in xrange(listlen):
            raidreads[k] = raidfiles[k].read(2048)
        if not raidreads[0]:
            break
        i = 0
        while i < len(raidreads[0]):
            xor = 0
            for j in xrange(listlen):
                b1 = ord(raidreads[j][i])
                xor = xor ^ b1
            rebuildfile.write(chr(xor))
            i += readsize
    for filenum in xrange(listlen):
        raidfiles[filenum].close()
    rebuildfile.close()


def RebuildOne_new(inlist, listlen, outfilename):
    # INTSIZE = settings.IntSize()
    fds = range(0,listlen)   # just need a list of this size
    wholefile = dhnio.ReadBinaryFile(inlist[0])
    seglength = len(wholefile)   # just needed length of file
    for filenum in xrange(listlen):
        fds[filenum]=open(inlist[filenum],"r")
    fout = open(outfilename,"w")
    for i in xrange(seglength):
        xor = 0
        for j in xrange(listlen):
            b1 = ord(fds[j].read(1))
            xor = xor ^ b1
        fout.write(chr(xor))
    for filenum in xrange(listlen):
        fds[filenum].close

# We XOR list of listlen input files and write result to a file named outfilename
def RebuildOne_orig(inlist, listlen, outfilename):
        # INTSIZE = settings.IntSize()
        fds = range(0,listlen)   # just need a list of this size
        wholefile = dhnio.ReadBinaryFile(inlist[0])
        seglength=len(wholefile)   # just needed length of file
        for filenum in range(0, listlen):
                fds[filenum]=open(inlist[filenum],"rb")
        fout=open(outfilename,"w")
        for i in range(0,seglength/INTSIZE):
                xor=0
                for j in range(0, listlen):
                        bstr1 = fds[j].read(INTSIZE)
                        b1, = struct.unpack(">l", bstr1)
                        xor = xor ^ b1
                outstr = struct.pack(">l", xor)
                fout.write(outstr)
        for filenum in range(0, listlen):
                fds[filenum].close

# If segment is good, there is a file for it, if not then no file exists.
# We only rebuild data segments.
# Could only make parity segments from existing data segments, so no help toward getting data.
# As long as we could rebuild one more data segment in a pass,
#  we do another pass to see if we are then able to do another.
#  When we can't do anything more we could how many good data segments there
#    are, and if we have all we win, if not we fail.

def raidread(OutputFileName, eccmapname, backupId, blockNumber, data_parity_dir=None):
    if data_parity_dir is None:
        data_parity_dir = settings.getLocalBackupsDir()

    # INTSIZE = settings.IntSize()
    # myeccmap = eccmap.eccmap(eccmapname)
    myeccmap = geteccmap(eccmapname)
    GoodFiles = range(0, 200)
    MakingProgress = 1
    while MakingProgress == 1:
        MakingProgress = 0
        for PSegNum in xrange(myeccmap.paritysegments):
                PFileName = os.path.join(data_parity_dir, backupId,  str(blockNumber) + '-' + str(PSegNum) + '-Parity')
                if os.path.exists(PFileName):
                        Map = myeccmap.ParityToData[PSegNum]
                        TotalDSegs = 0
                        GoodDSegs = 0
                        for DSegNum in Map:
                                TotalDSegs+=1
                                FileName = os.path.join(data_parity_dir, backupId, str(blockNumber) + '-' + str(DSegNum) + '-Data')
                                if os.path.exists(FileName):
                                        GoodFiles[GoodDSegs]=FileName
                                        GoodDSegs+=1
                                else:
                                        BadName=FileName
                        if GoodDSegs == TotalDSegs - 1:
                                MakingProgress = 1
                                GoodFiles[GoodDSegs]=PFileName
                                GoodDSegs += 1
                                RebuildOne(GoodFiles,GoodDSegs,BadName)

    #  Count up the good segments and combine
    GoodDSegs = 0
    output = open(OutputFileName, "wb")
    for DSegNum in xrange(myeccmap.datasegments):
        FileName = os.path.join(data_parity_dir, backupId, str(blockNumber) + '-' + str(DSegNum) + '-Data')
        if os.path.exists(FileName):
            GoodDSegs += 1
            moredata = open(FileName,"rb").read()
            output.write(moredata)
    output.close()
    return GoodDSegs


def main():
    if (len(sys.argv) < 3):
        print "raidread needs an output filename and eccmap name"
        sys.exit(2)

    OutputFileName = sys.argv[1]
    eccmapname = sys.argv[2]

    print "raidread is starting with"
    print OutputFileName
    print eccmapname
    raidread(OutputFileName, eccmapname)


if __name__ == "__main__":
    main()


