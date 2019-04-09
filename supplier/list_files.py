#!/usr/bin/env python
# list_files.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import
from six.moves import map
from six.moves import range
from io import StringIO

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import zlib

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from lib import strng
from lib import packetid
from lib import misc

from main import settings

from crypt import encrypted
from crypt import key
from crypt import my_keys

from p2p import commands
from p2p import p2p_service

from userid import my_id

#------------------------------------------------------------------------------

def send(customer_idurl, packet_id, format_type, key_id, remote_idurl):
    if not my_keys.is_key_registered(key_id):
        lg.warn('not able to return Files() for customer %s, key %s not registered' % (
            customer_idurl, key_id, ))
        return p2p_service.SendFailNoRequest(customer_idurl, packet_id)
    if _Debug:
        lg.out(_DebugLevel, "list_files.send to %s, customer_idurl=%s, key_id=%s" % (
            remote_idurl, customer_idurl, key_id, ))
    ownerdir = settings.getCustomerFilesDir(customer_idurl)
    plaintext = ''
    if os.path.isdir(ownerdir):
        for key_alias in os.listdir(ownerdir):
            if not misc.ValidKeyAlias(str(key_alias)):
                continue
            key_alias_dir = os.path.join(ownerdir, key_alias)
            plaintext += TreeSummary(key_alias_dir, key_alias)
    else:
        lg.warn('did not found customer dir: %s' % ownerdir)
    if _Debug:
        lg.out(_DebugLevel + 8, '\n%s' % plaintext)
    raw_list_files = PackListFiles(plaintext, format_type)
    block = encrypted.Block(
        CreatorID=my_id.getLocalID(),
        BackupID=key_id,
        Data=raw_list_files,
        SessionKey=key.NewSessionKey(),
        EncryptKey=key_id,
    )
    encrypted_list_files = block.Serialize()
    newpacket = p2p_service.SendFiles(
        idurl=remote_idurl,
        raw_list_files_info=encrypted_list_files,
        packet_id=packet_id,
        callbacks={
            commands.Ack(): on_acked,
            commands.Fail(): on_failed,
            None: on_timeout,
        },
    )
    return newpacket

#------------------------------------------------------------------------------

def on_acked(response, info):
    if _Debug:
        lg.out(_DebugLevel, 'list_files.on_acked with %s in %s' % (response, info, ))


def on_failed(response, error):
    lg.warn('send files %s failed with %s' % (response, error, ))


def on_timeout(pkt_out):
    lg.warn('send files with %s was timed out' % pkt_out)

#------------------------------------------------------------------------------

def PackListFiles(plaintext, method):
    if method == "Text":
        return plaintext
    elif method == "Compressed":
        return zlib.compress(strng.to_bin(plaintext))
    return ''


def UnpackListFiles(payload, method):
    if method == "Text":
        return payload
    elif method == "Compressed":
        return strng.to_text(zlib.decompress(strng.to_bin(payload)))
    return payload

#------------------------------------------------------------------------------

def TreeSummary(ownerdir, key_alias):
    out = StringIO()
    out.write('K%s\n' % key_alias)

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
                if blockNum in list(dataBlocks[supplierNum].keys()):
                    versionSize[supplierNum] += dataBlocks[supplierNum][blockNum]
                    dataMissing[supplierNum].discard(blockNum)
                if blockNum in list(parityBlocks[supplierNum].keys()):
                    versionSize[supplierNum] += parityBlocks[supplierNum][blockNum]
                    parityMissing[supplierNum].discard(blockNum)
        suppliers = set(list(dataBlocks.keys()) + list(parityBlocks.keys()))
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

#------------------------------------------------------------------------------
