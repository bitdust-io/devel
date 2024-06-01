#!/usr/bin/python
# restore_monitor.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (restore_monitor.py) is part of BitDust Software.
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
"""
.. module:: restore_monitor.

Manages currently restoring backups.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 8

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.main import events

from bitdust.lib import misc

from bitdust.system import tmpfile

from bitdust.storage import backup_tar
from bitdust.storage import backup_matrix
from bitdust.storage import backup_control

from bitdust.userid import global_id

#------------------------------------------------------------------------------

_WorkingBackupIDs = {}
_WorkingRestoreProgress = {}

#------------------------------------------------------------------------------

OnRestorePacketFunc = None
OnRestoreDoneFunc = None
OnRestoreBlockFunc = None

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'restore_monitor.init')


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'restore_monitor.shutdown')


#------------------------------------------------------------------------------


def block_restored_callback(backupID, block):
    global OnRestoreBlockFunc
    if OnRestoreBlockFunc is not None:
        OnRestoreBlockFunc(backupID, block)


def packet_in_callback(backupID, newpacket):
    global _WorkingRestoreProgress
    global OnRestorePacketFunc
    SupplierNumber = newpacket.SupplierNumber()
    if _Debug:
        lg.out(_DebugLevel, 'restore_monitor.packet_in_callback %s from supplier %s' % (backupID, SupplierNumber))
    # want to count the data we restoring
    if SupplierNumber not in list(_WorkingRestoreProgress[backupID].keys()):
        _WorkingRestoreProgress[backupID][SupplierNumber] = 0
    _WorkingRestoreProgress[backupID][SupplierNumber] += len(newpacket.Payload)
    packetID = global_id.CanonicalID(newpacket.PacketID)
    backup_matrix.LocalFileReport(packetID)
    if OnRestorePacketFunc is not None:
        OnRestorePacketFunc(backupID, SupplierNumber, newpacket)


def extract_done(retcode, backupID, source_filename, output_location, callback_method):
    lg.info('extract success of %s with result : %s' % (backupID, str(retcode)))
    global OnRestoreDoneFunc
    _WorkingBackupIDs.pop(backupID, None)
    _WorkingRestoreProgress.pop(backupID, None)
    tmpfile.throw_out(source_filename, 'file extracted')
    if OnRestoreDoneFunc is not None:
        OnRestoreDoneFunc(backupID, 'restore done')
    if callback_method:
        try:
            callback_method(backupID, 'restore done')
        except:
            lg.exc()
    events.send('restore-done', data=dict(
        backup_id=backupID,
        output_location=output_location,
    ))
    return retcode


def extract_failed(err, backupID, source_filename, output_location, callback_method):
    lg.err('extract failed of %s with: %s' % (backupID, str(err)))
    global OnRestoreDoneFunc
    _WorkingBackupIDs.pop(backupID, None)
    _WorkingRestoreProgress.pop(backupID, None)
    tmpfile.throw_out(source_filename, 'file extract failed')
    if OnRestoreDoneFunc is not None:
        OnRestoreDoneFunc(backupID, 'extract failed')
    if callback_method:
        try:
            callback_method(backupID, 'extract failed')
        except:
            lg.exc()
    events.send('restore-failed', data=dict(
        backup_id=backupID,
        output_location=output_location,
        reason='extracting file failed',
        error=str(err),
    ))
    return err


def restore_done(result, backupID, outfd, tarfilename, outputlocation, callback_method):
    global _WorkingBackupIDs
    global _WorkingRestoreProgress
    global OnRestoreDoneFunc
    if _Debug:
        lg.args(_DebugLevel, result=result, bid=backupID, tar=tarfilename, out=outputlocation)
    if result == 'done':
        lg.info('restore success of %s with result=%s' % (backupID, result))
    else:
        lg.err('restore failed of %s with result=%s' % (backupID, result))
    try:
        os.close(outfd)
    except:
        lg.exc()
    if result == 'done':
        d = backup_tar.extracttar_thread(tarfilename, outputlocation)
        d.addCallback(extract_done, backupID, tarfilename, outputlocation, callback_method)
        d.addErrback(extract_failed, backupID, tarfilename, outputlocation, callback_method)
        return d
    _WorkingBackupIDs.pop(backupID, None)
    _WorkingRestoreProgress.pop(backupID, None)
    tmpfile.throw_out(tarfilename, 'restore ' + result)
    if OnRestoreDoneFunc is not None:
        OnRestoreDoneFunc(backupID, result)
    if callback_method:
        try:
            callback_method(backupID, result)
        except:
            lg.exc()
    return result


#------------------------------------------------------------------------------


def Start(backupID, outputLocation, callback=None, keyID=None):
    if _Debug:
        lg.out(_DebugLevel, 'restore_monitor.Start %s to %s' % (backupID, outputLocation))
    global _WorkingBackupIDs
    global _WorkingRestoreProgress
    if backupID in list(_WorkingBackupIDs.keys()):
        return _WorkingBackupIDs[backupID]
    alias = backupID.split('$')[0]
    outfd, outfilename = tmpfile.make(
        'restore',
        extension='.tar.gz',
        prefix=alias + '_',
    )
    from bitdust.storage import restore_worker
    r = restore_worker.RestoreWorker(backupID, outfd, KeyID=keyID)
    r.MyDeferred.addCallback(restore_done, backupID, outfd, outfilename, outputLocation, callback)
    r.set_block_restored_callback(block_restored_callback)
    r.set_packet_in_callback(packet_in_callback)
    _WorkingBackupIDs[backupID] = r
    _WorkingRestoreProgress[backupID] = {}
    r.automat('init')
    return r


def Abort(backupID):
    global _WorkingBackupIDs
    global _WorkingRestoreProgress
    if backupID not in list(_WorkingBackupIDs.keys()):
        lg.warn('%s not found in working list' % backupID)
        return False
    r = _WorkingBackupIDs[backupID]
    r.automat('abort', 'abort')
    if _Debug:
        lg.out(_DebugLevel, 'restore_monitor.Abort %s' % backupID)
    return True


#------------------------------------------------------------------------------


def GetWorkingIDs():
    global _WorkingBackupIDs
    return list(_WorkingBackupIDs.keys())


def GetWorkingObjects():
    global _WorkingBackupIDs
    return list(_WorkingBackupIDs.values())


def IsWorking(backupID):
    global _WorkingBackupIDs
    return backupID in list(_WorkingBackupIDs.keys())


def GetProgress(backupID):
    global _WorkingRestoreProgress
    return _WorkingRestoreProgress.get(backupID, {})


def GetWorkingRestoreObject(backupID):
    global _WorkingBackupIDs
    return _WorkingBackupIDs.get(backupID, None)


def FindWorking(pathID=None, customer=None):
    global _WorkingBackupIDs
    if pathID:
        pathID = global_id.CanonicalID(pathID)
    result = set()
    for backupID in _WorkingBackupIDs:
        if pathID:
            if backupID.count(pathID):
                result.add(backupID)
        if customer:
            if backupID.count(customer + ':'):
                result.add(backupID)
    return list(result)


def GetBackupStatusInfo(backupID, item_info, item_name, parent_path_existed=None):
    _, percent, weakBlock, weakPercent = backup_matrix.GetBackupRemoteStats(backupID)
    totalNumberOfFiles, maxBlockNum, statsArray = backup_matrix.GetBackupStats(backupID)
    ret = {
        'state': 'ready',
        'delivered': misc.percent2string(percent),
        'reliable': misc.percent2string(weakPercent),
        'fragments': totalNumberOfFiles,
        'weak_block': weakBlock,
        'max_block': maxBlockNum,
        'suppliers': [{
            'stored': misc.percent2string(i[0]),
            'fragments': i[1],
        } for i in statsArray],
    }
    backupObj = backup_control.GetRunningBackupObject(backupID)
    if backupObj:
        ret['state'] = 'uploading'
        ret['progress'] = misc.percent2string(backupObj.progress())
        return ret
    elif IsWorking(backupID):
        restoreObj = GetWorkingRestoreObject(backupID)
        if restoreObj:
            maxBlockNum = backup_matrix.GetKnownMaxBlockNum(backupID)
            currentBlock = max(0, restoreObj.block_number)
            percent = 0.0
            if maxBlockNum > 0:
                percent = 100.0*currentBlock/maxBlockNum
            ret['state'] = 'downloading'
            ret['progress'] = misc.percent2string(percent)
            return ret
    return ret
