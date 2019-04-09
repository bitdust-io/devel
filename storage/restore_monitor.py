#!/usr/bin/python
# restore_monitor.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
import os
import sys
import time

from twisted.internet import threads

#------------------------------------------------------------------------------

from logs import lg

from system import tmpfile

from storage import backup_tar
from storage import backup_matrix

from userid import global_id

#------------------------------------------------------------------------------

_WorkingBackupIDs = {}
_WorkingRestoreProgress = {}

#------------------------------------------------------------------------------

OnRestorePacketFunc = None
OnRestoreDoneFunc = None
OnRestoreBlockFunc = None

#------------------------------------------------------------------------------


def init():
    lg.out(4, 'restore_monitor.init')


def shutdown():
    lg.out(4, 'restore_monitor.shutdown')

#------------------------------------------------------------------------------

def block_restored_callback(backupID, block):
    global OnRestoreBlockFunc
    if OnRestoreBlockFunc is not None:
        OnRestoreBlockFunc(backupID, block)


def packet_in_callback(backupID, newpacket):
    global _WorkingRestoreProgress
    global OnRestorePacketFunc
    SupplierNumber = newpacket.SupplierNumber()
    lg.out(12, 'restore_monitor.packet_in_callback %s from suppier %s' % (backupID, SupplierNumber))

    # want to count the data we restoring
    if SupplierNumber not in list(_WorkingRestoreProgress[backupID].keys()):
        _WorkingRestoreProgress[backupID][SupplierNumber] = 0
    _WorkingRestoreProgress[backupID][SupplierNumber] += len(newpacket.Payload)

    packetID = global_id.CanonicalID(newpacket.PacketID)
    backup_matrix.LocalFileReport(packetID)

    if OnRestorePacketFunc is not None:
        OnRestorePacketFunc(backupID, SupplierNumber, newpacket)


def extract_done(retcode, backupID, tarfilename, callback_method):
    lg.info('EXTRACT SUCCESS of %s  tarfile=%s, result=%s' % (backupID, tarfilename, str(retcode)))
    global OnRestoreDoneFunc

    _WorkingBackupIDs.pop(backupID, None)
    _WorkingRestoreProgress.pop(backupID, None)

    # tmpfile.throw_out(tarfilename, 'file extracted')

    if OnRestoreDoneFunc is not None:
        OnRestoreDoneFunc(backupID, 'restore done')

    if callback_method:
        try:
            callback_method(backupID, 'restore done')
        except:
            lg.exc()

    return retcode


def extract_failed(err, backupID, callback_method):
    lg.err('EXTRACT FAILED of %s with: %s' % (backupID, str(err)))
    if callback_method:
        try:
            callback_method(backupID, 'extract failed')
        except:
            lg.exc()
    return err


def restore_done(result, backupID, outfd, tarfilename, outputlocation, callback_method):
    global _WorkingBackupIDs
    global _WorkingRestoreProgress
    global OnRestoreDoneFunc
    if result == 'done':
        lg.info('RESTORE SUCCESS of %s with result=%s' % (backupID, result))
    else:
        lg.err('RESTORE FAILED of %s with result=%s' % (backupID, result))
    try:
        os.close(outfd)
    except:
        lg.exc()
    if result == 'done':
        p = backup_tar.extracttar(tarfilename, outputlocation)
        if p:
            d = threads.deferToThread(p.wait)
            d.addCallback(extract_done, backupID, tarfilename, callback_method)
            d.addErrback(extract_failed, backupID, callback_method)
            return d
        result = 'extract failed'
    _WorkingBackupIDs.pop(backupID, None)
    _WorkingRestoreProgress.pop(backupID, None)
    # tmpfile.throw_out(tarfilename, 'restore ' + result)
    if OnRestoreDoneFunc is not None:
        OnRestoreDoneFunc(backupID, result)
    if callback_method:
        try:
            callback_method(backupID, result)
        except:
            lg.exc()
    return result


# def restore_failed(x, tarfilename, callback):
#     lg.out(4, 'restore_monitor.restore_failed ' + str(x))
#     global _WorkingBackupIDs
#     global _WorkingRestoreProgress
#     global OnRestoreDoneFunc
#     backupID = result = None
#     try:
#         if isinstance(x, Exception):
#             backupID, result = x.getErrorMessage().split(' ')
#         elif isinstance(x, six.text_type):
#             backupID, result = x.split(' ')
#     except:
#         lg.exc()
#     if not backupID:
#         lg.warn('Unknown backupID: %s' % str(x))
#         return
#     _WorkingBackupIDs.pop(backupID, None)
#     _WorkingRestoreProgress.pop(backupID, None)
#     tmpfile.throw_out(tarfilename, 'restore ' + result)
#     if OnRestoreDoneFunc is not None:
#         OnRestoreDoneFunc(backupID, result)
#     if callback:
#         callback(backupID, result)

#------------------------------------------------------------------------------

def Start(backupID, outputLocation, callback=None, keyID=None):
    lg.out(8, 'restore_monitor.Start %s to %s' % (backupID, outputLocation))
    global _WorkingBackupIDs
    global _WorkingRestoreProgress
    if backupID in list(_WorkingBackupIDs.keys()):
        return _WorkingBackupIDs[backupID]
    outfd, outfilename = tmpfile.make(
        'restore',
        extension='.tar.gz',
        prefix=backupID.replace('@', '_').replace('.', '_').replace('/', '_').replace(':', '_') + '_',
    )
    from storage import restore_worker
    r = restore_worker.RestoreWorker(backupID, outfd, KeyID=keyID)
    r.MyDeferred.addCallback(restore_done, backupID, outfd, outfilename, outputLocation, callback)
    # r.MyDeferred.addErrback(restore_failed, outfilename, callback)
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
    lg.out(8, 'restore_monitor.Abort %s' % backupID)
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
