#!/usr/bin/env python
# list_files.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import zlib

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.system import bpio

from bitdust.lib import strng
from bitdust.lib import packetid
from bitdust.lib import misc

from bitdust.main import settings

from bitdust.crypt import encrypted
from bitdust.crypt import key
from bitdust.crypt import my_keys

from bitdust.p2p import commands
from bitdust.p2p import p2p_service
from bitdust.contacts import identitycache

from bitdust.userid import my_id
from bitdust.userid import global_id

#------------------------------------------------------------------------------


def send(customer_idurl, packet_id, format_type, key_id, remote_idurl, query_items=[]):
    if not query_items:
        query_items = ['*']
    key_id = my_keys.latest_key_id(key_id)
    parts = global_id.NormalizeGlobalID(key_id)
    if parts['key_alias'] == 'master' and parts['idurl'] != my_id.getIDURL():
        # lg.warn('incoming ListFiles() request with customer "master" key: %r' % key_id)
        if not my_keys.is_key_registered(key_id) and identitycache.HasKey(parts['idurl']):
            lg.info('customer public key %r to be registered locally for the first time' % key_id)
            known_ident = identitycache.FromCache(parts['idurl'])
            if not my_keys.register_key(key_id, known_ident.getPublicKey()):
                lg.err('failed to register known public key of the customer: %r' % key_id)
    if not my_keys.is_key_registered(key_id):
        lg.warn('not able to return Files() for customer %s, key %s not registered' % (customer_idurl, key_id))
        return p2p_service.SendFailNoRequest(customer_idurl, packet_id, response='key not registered')
    if _Debug:
        lg.out(_DebugLevel, 'list_files.send to %s, customer_idurl=%s, key_id=%s, query_items=%r' % (remote_idurl, customer_idurl, key_id, query_items))
    ownerdir = settings.getCustomerFilesDir(customer_idurl)
    plaintext = ''
    if os.path.isdir(ownerdir):
        try:
            for query_path in query_items:
                plaintext += process_query_item(query_path, parts['key_alias'], ownerdir)
        except:
            lg.exc()
            return p2p_service.SendFailNoRequest(customer_idurl, packet_id, response='list files query processing error')
    else:
        lg.warn('did not found customer folder: %s' % ownerdir)
    if _Debug:
        lg.out(_DebugLevel, '\n%s' % plaintext)
    raw_list_files = PackListFiles(plaintext, format_type)
    block = encrypted.Block(
        CreatorID=my_id.getIDURL(),
        BackupID=key_id,
        Data=raw_list_files,
        SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
        SessionKeyType=key.SessionKeyType(),
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


def process_query_item(query_path, key_alias, ownerdir):
    ret = ''
    ret += 'Q%s\n' % query_path
    if query_path == '*':
        if key_alias == 'master':
            key_alias_dir = os.path.join(ownerdir, key_alias)
            ret += TreeSummary(key_alias_dir, key_alias)
        for one_key_alias in os.listdir(ownerdir):
            if one_key_alias == 'master':
                continue
            if key_alias and key_alias != 'master' and one_key_alias != key_alias:
                continue
            if not misc.ValidKeyAlias(strng.to_text(one_key_alias)):
                continue
            key_alias_dir = os.path.join(ownerdir, one_key_alias)
            ret += TreeSummary(key_alias_dir, one_key_alias)
        if _Debug:
            lg.args(_DebugLevel, o=ownerdir, q=query_path, k=key_alias, result_bytes=len(ret))
        return ret
    # TODO: more validations to be added
    clean_path = query_path.replace('.', '').replace('~', '').replace(':', '').replace('\\', '/').lstrip('/')
    path_items = clean_path.split('/')
    path_items.insert(0, ownerdir)
    local_path = os.path.join(*path_items)
    if not os.path.exists(local_path):
        lg.warn('local file or folder not exist: %r' % local_path)
        return ''
    ret += TreeSummary(local_path, key_alias)
    if _Debug:
        lg.args(_DebugLevel, o=ownerdir, q=query_path, k=key_alias, p=local_path, result_bytes=len(ret))
    return ret


#------------------------------------------------------------------------------


def on_acked(response, info):
    if _Debug:
        lg.out(_DebugLevel, 'list_files.on_acked with %s in %s' % (response, info))


def on_failed(response, error):
    lg.warn('send files %s failed with %s' % (response, error))


def on_timeout(pkt_out):
    lg.warn('send files with %s was timed out' % pkt_out)


#------------------------------------------------------------------------------


def PackListFiles(plaintext, method):
    if method == 'Text':
        return plaintext
    elif method == 'Compressed':
        return zlib.compress(strng.to_bin(plaintext))
    return ''


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
            found_some_versions = False
            for sub_path in os.listdir(realpath):
                if packetid.IsCanonicalVersion(sub_path):
                    found_some_versions = True
                    break
            if found_some_versions:
                result.write('F%s -1\n' % subpath)
            else:
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
            if os.path.isdir(pth):
                result.write('D%s\n' % packetID)
                continue
            try:
                filesz = os.path.getsize(pth)
            except:
                filesz = -1
            if not packetid.Valid(packetID):
                result.write('F%s %d\n' % (packetID, filesz))
                continue
            _, pathID, versionName, blockNum, supplierNum, dataORparity = packetid.SplitFull(packetID)
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
            versionString = '%s %d 0-%d %d' % (subpath, supplierNum, maxBlock, versionSize[supplierNum])
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
