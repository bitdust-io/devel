#!/usr/bin/env python
# list_files.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (list_files.py) is part of BitDust Software.
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

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import zlib
import cStringIO

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from lib import nameurl
from lib import packetid

from main import settings

from p2p import commands

from contacts import contactsdb

from userid import my_id

from crypt import signed

from transport import gateway

#------------------------------------------------------------------------------

def send(customer_idurl, packet_id, format_type):
    customer_name = nameurl.GetName(customer_idurl)
    MyID = my_id.getLocalID()
    RemoteID = customer_idurl
    PacketID = packet_id
    if _Debug:
        lg.out(_DebugLevel, "list_files.send to %s, format is '%s'" % (customer_name, format_type))
    custdir = settings.getCustomersFilesDir()
    ownerdir = os.path.join(custdir, nameurl.UrlFilename(customer_idurl))
    if not os.path.isdir(ownerdir):
        if _Debug:
            lg.out(_DebugLevel, "list_files.send did not found customer dir: " + ownerdir)
        src = PackListFiles('', format_type)
        result = signed.Packet(commands.Files(), MyID, MyID, PacketID, src, RemoteID)
        gateway.outbox(result)
        return result
    plaintext = TreeSummary(ownerdir)
    if _Debug:
        lg.out(_DebugLevel + 8, '\n%s' % (plaintext))
    src = PackListFiles(plaintext, format_type)
    result = signed.Packet(commands.Files(), MyID, MyID, PacketID, src, RemoteID)
    gateway.outbox(result)
    return result

#------------------------------------------------------------------------------

def PackListFiles(plaintext, method):
    if method == "Text":
        return plaintext
    elif method == "Compressed":
        return zlib.compress(plaintext)
    return ''


def UnpackListFiles(payload, method):
    if method == "Text":
        return payload
    elif method == "Compressed":
        return zlib.decompress(payload)
    return payload


def ListCustomerFiles(customer_idurl):
    filename = nameurl.UrlFilename(customer_idurl)
    customer_dir = os.path.join(settings.getCustomersFilesDir(), filename)
    result = cStringIO.StringIO()

    def cb(realpath, subpath, name):
        if os.path.isdir(realpath):
            result.write('D%s\n' % subpath)
        else:
            result.write('F%s\n' % subpath)
        return True
    bpio.traverse_dir_recursive(cb, customer_dir)
    src = result.getvalue()
    result.close()
    return src


def ListCustomerFiles1(customerNumber):
    """
    On the status form when clicking on a customer, find out what files we're
    holding for that customer.
    """
    idurl = contactsdb.customer(customerNumber)
    filename = nameurl.UrlFilename(idurl)
    customerDir = os.path.join(settings.getCustomersFilesDir(), filename)
    if os.path.exists(customerDir) and os.path.isdir(customerDir):
        backupFilesList = os.listdir(customerDir)
        if len(backupFilesList) > 0:
            return ListSummary(backupFilesList)
    return "No files stored for this customer"


def ListSummary(dirlist):
    """
    Take directory listing and make summary of format:: BackupID-1-Data 1-1873
    missing for 773,883, BackupID-1-Parity 1-1873 missing for 777,982,
    """
    BackupMax = {}
    BackupAll = {}
    result = ""
    for filename in dirlist:
        if not packetid.Valid(filename):       # if not type we can summarize
            result += filename + "\n"  # then just include filename
        else:
            BackupID, BlockNum, SupNum, DataOrParity = packetid.BidBnSnDp(filename)
            LocalID = BackupID + "-" + str(SupNum) + "-" + DataOrParity
            blocknum = int(BlockNum)
            BackupAll[(LocalID, blocknum)] = True
            if LocalID in BackupMax:
                if BackupMax[LocalID] < blocknum:
                    BackupMax[LocalID] = blocknum
            else:
                BackupMax[LocalID] = blocknum
    for BackupName in sorted(BackupMax.keys()):
        missing = []
        thismax = BackupMax[BackupName]
        for blocknum in range(0, thismax):
            if not (BackupName, blocknum) in BackupAll:
                missing.append(str(blocknum))
        result += BackupName + " from 0-" + str(thismax)
        if len(missing) > 0:
            result += ' missing '
            result += ','.join(missing)
#            for m in missing:
#                result += str(m) + ","
        result += "\n"
    return result


def TreeSummary(ownerdir):
    out = cStringIO.StringIO()

    def cb(result, realpath, subpath, name):
        if not os.access(realpath, os.R_OK):
            return False
        if os.path.isfile(realpath):
            try:
                filesz = os.path.getsize(realpath)
            except:
                filesz = -1
            result.write('F%s %d\n' % (subpath, filesz))
            return False
        if not packetid.IsCanonicalVersion(name):
            result.write('D%s\n' % subpath)
            return True
        maxBlock = -1
        versionSize = {}
        dataBlocks = {}
        parityBlocks = {}
        dataMissing = {}
        parityMissing = {}
        for filename in os.listdir(realpath):
            packetID = subpath + '/' + filename
            pth = os.path.join(realpath, filename)
            try:
                filesz = os.path.getsize(pth)
            except:
                filesz = -1
            if os.path.isdir(pth):
                result.write('D%s\n' % packetID)
                continue
            if not packetid.Valid(packetID):
                result.write('F%s %d\n' % (packetID, filesz))
                continue
            customer, pathID, versionName, blockNum, supplierNum, dataORparity = packetid.SplitFull(packetID)
            if None in [pathID, versionName, blockNum, supplierNum, dataORparity]:
                result.write('F%s %d\n' % (packetID, filesz))
                continue
            if dataORparity != 'Data' and dataORparity != 'Parity':
                result.write('F%s %d\n' % (packetID, filesz))
                continue
            if maxBlock < blockNum:
                maxBlock = blockNum
            if supplierNum not in versionSize:
                versionSize[supplierNum] = 0
            if supplierNum not in dataBlocks:
                dataBlocks[supplierNum] = {}
            if supplierNum not in parityBlocks:
                parityBlocks[supplierNum] = {}
            if dataORparity == 'Data':
                dataBlocks[supplierNum][blockNum] = filesz
            elif dataORparity == 'Parity':
                parityBlocks[supplierNum][blockNum] = filesz
        for supplierNum in versionSize.keys():
            dataMissing[supplierNum] = set(range(maxBlock + 1))
            parityMissing[supplierNum] = set(range(maxBlock + 1))
            for blockNum in range(maxBlock + 1):
                if blockNum in dataBlocks[supplierNum].keys():
                    versionSize[supplierNum] += dataBlocks[supplierNum][blockNum]
                    dataMissing[supplierNum].discard(blockNum)
                if blockNum in parityBlocks[supplierNum].keys():
                    versionSize[supplierNum] += parityBlocks[supplierNum][blockNum]
                    parityMissing[supplierNum].discard(blockNum)
        suppliers = set(dataBlocks.keys() + parityBlocks.keys())
        for supplierNum in suppliers:
            versionString = '%s %d 0-%d %d' % (
                subpath, supplierNum, maxBlock, versionSize[supplierNum])
            if len(dataMissing[supplierNum]) > 0 or len(parityMissing[supplierNum]) > 0:
                versionString += ' missing'
                if len(dataMissing[supplierNum]) > 0:
                    versionString += ' Data:' + (','.join(map(str, dataMissing[supplierNum])))
                if len(parityMissing[supplierNum]) > 0:
                    versionString += ' Parity:' + (','.join(map(str, parityMissing[supplierNum])))
            result.write('V%s\n' % versionString)
        del dataBlocks
        del parityBlocks
        del dataMissing
        del parityMissing
        return False
    bpio.traverse_dir_recursive(lambda realpath, subpath, name: cb(out, realpath, subpath, name), ownerdir)
    src = out.getvalue()
    out.close()
    return src
