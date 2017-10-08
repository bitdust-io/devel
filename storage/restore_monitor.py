#!/usr/bin/python
# restore_monitor.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
#
#
#
#
# manage currently restoring backups

import os
import sys
import time

from twisted.internet import reactor, threads

from logs import lg

from system import bpio
from system import tmpfile

import restore
import backup_tar
import backup_matrix

#------------------------------------------------------------------------------

_WorkingBackupIDs = {}
_WorkingRestoreProgress = {}
OnRestorePacketFunc = None
OnRestoreDoneFunc = None
OnRestoreBlockFunc = None

#------------------------------------------------------------------------------


def init():
    lg.out(4, 'restore_monitor.init')


def shutdown():
    lg.out(4, 'restore_monitor.shutdown')


def block_restored_callback(backupID, block):
    global OnRestoreBlockFunc
    if OnRestoreBlockFunc is not None:
        OnRestoreBlockFunc(backupID, block)


def packet_in_callback(backupID, newpacket):
    # lg.out(8, 'restore_monitor.packet_in_callback ' + backupID)
    global _WorkingRestoreProgress
    global OnRestorePacketFunc
    SupplierNumber = newpacket.SupplierNumber()

    # want to count the data we restoring
    if SupplierNumber not in _WorkingRestoreProgress[backupID].keys():
        _WorkingRestoreProgress[backupID][SupplierNumber] = 0
    _WorkingRestoreProgress[backupID][SupplierNumber] += len(newpacket.Payload)

    backup_matrix.LocalFileReport(newpacket.PacketID)

    if OnRestorePacketFunc is not None:
        OnRestorePacketFunc(backupID, SupplierNumber, newpacket)


def extract_done(retcode, backupID, tarfilename, callback_method):
    lg.out(4, 'restore_monitor.extract_done %s result: %s' % (backupID, str(retcode)))
    global OnRestoreDoneFunc

    _WorkingBackupIDs.pop(backupID, None)
    _WorkingRestoreProgress.pop(backupID, None)

    # tmpfile.throw_out(tarfilename, 'file extracted')

    if OnRestoreDoneFunc is not None:
        OnRestoreDoneFunc(backupID, 'restore done')

    if callback_method:
        callback_method(backupID, 'restore done')

    return retcode


def extract_failed(err, backupID, callback_method):
    lg.warn(str(err))
    if callback_method:
        callback_method(backupID, 'extract failed')
    return err


def restore_done(result, backupID, tarfilename, outputlocation, callback_method):
    lg.out(4, '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    lg.out(4, 'restore_monitor.restore_done for %s with result=%s' % (backupID, result))
    global _WorkingBackupIDs
    global _WorkingRestoreProgress
    global OnRestoreDoneFunc
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
        callback_method(backupID, result)
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
#         elif isinstance(x, str):
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


def Start(backupID, outputLocation, callback=None, keyID=None):
    lg.out(8, 'restore_monitor.Start %s to %s' % (backupID, outputLocation))
    global _WorkingBackupIDs
    global _WorkingRestoreProgress
    if backupID in _WorkingBackupIDs.keys():
        return None
    outfd, outfilename = tmpfile.make(
        'restore', '.tar.gz',
        backupID.replace('@', '_').replace('.', '_').replace('/', '_').replace(':', '_') + '_')
    r = restore.restore(backupID, outfd, KeyID=keyID)
    r.MyDeferred.addCallback(restore_done, backupID, outfilename, outputLocation, callback)
    # r.MyDeferred.addErrback(restore_failed, outfilename, callback)
    r.set_block_restored_callback(block_restored_callback)
    r.set_packet_in_callback(packet_in_callback)
    _WorkingBackupIDs[backupID] = r
    _WorkingRestoreProgress[backupID] = {}
    r.automat('init')
    return r


def Abort(backupID):
    lg.out(8, 'restore_monitor.Abort %s' % backupID)
    global _WorkingBackupIDs
    global _WorkingRestoreProgress
    if backupID not in _WorkingBackupIDs.keys():
        return False
    r = _WorkingBackupIDs[backupID]
    r.abort()
    return True


def GetWorkingIDs():
    global _WorkingBackupIDs
    return _WorkingBackupIDs.keys()


def GetWorkingObjects():
    global _WorkingBackupIDs
    return _WorkingBackupIDs.values()


def IsWorking(backupID):
    global _WorkingBackupIDs
    return backupID in _WorkingBackupIDs.keys()


def GetProgress(backupID):
    global _WorkingRestoreProgress
    return _WorkingRestoreProgress.get(backupID, {})


def GetWorkingRestoreObject(backupID):
    global _WorkingBackupIDs
    return _WorkingBackupIDs.get(backupID, None)
