#!/usr/bin/python
# ftp_server.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (ftp_server.py) is part of BitDust Software.
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

"""
..

module:: ftp_server
"""

import os
import time
import pprint
import traceback
import fnmatch

from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet.defer import Deferred, succeed

from twisted.cred.portal import Portal
from twisted.cred.checkers import AllowAnonymousAccess, FilePasswordDB

from twisted.python import filepath

from twisted.protocols.ftp import (
    # classes
    FTPFactory,
    FTPRealm,
    FTP,
    ASCIIConsumerWrapper,
    _FileReader,
    _FileWriter,
    # methods
    toSegments,
    errnoToFailure,
    # exceptions
    FTPCmdError,
    BadCmdSequenceError,
    InvalidPath,
    FileNotFoundError,
    FileExistsError,
    PermissionDeniedError,
    IsADirectoryError,
    # FTP codes constants
    DATA_CNX_ALREADY_OPEN_START_XFR,
    TXFR_COMPLETE_OK,
    REQ_FILE_ACTN_COMPLETED_OK,
    CNX_CLOSED_TXFR_ABORTED,
    FILE_NOT_FOUND,
    FILE_STATUS_OK_OPEN_DATA_CNX,
    FILE_STATUS,
    MKD_REPLY,
)

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from main import settings

from lib import packetid
from lib import nameurl

from system import tmpfile
from system import bpio

from storage import backup_fs
from storage import backup_control
from storage import restore_monitor
from storage import backup_monitor

from userid import my_id

#------------------------------------------------------------------------------

_FTPServer = None

#------------------------------------------------------------------------------

def init(ftp_port=None):
    global _FTPServer
    lg.out(4, 'ftp_server.init')
    if _FTPServer:
        lg.warn('already started')
        return
    if not ftp_port:
        ftp_port = settings.getFTPServerPort()
    if not os.path.isfile(settings.FTPServerCredentialsFile()):
        bpio.AtomicWriteFile(settings.FTPServerCredentialsFile(), 'bitdust:bitdust')
    # TODO: add protection: accept connections only from local host: 127.0.0.1
    _FTPServer = reactor.listenTCP(
        ftp_port,
        BitDustFTPFactory(
            Portal(
                FTPRealm('./'), [
                    AllowAnonymousAccess(),
                    FilePasswordDB(settings.FTPServerCredentialsFile()),
                ]
            ),
        )
    )
    lg.out(4, '    started on port %d' % ftp_port)


def shutdown():
    global _FTPServer
    lg.out(4, 'ftp_server.shutdown')
    if not _FTPServer:
        return succeed(None)
    result = Deferred()
    lg.out(4, '    calling stopListening()')
    _FTPServer.stopListening().addBoth(lambda *args: result.callback(*args))
    _FTPServer = None
    return result

#------------------------------------------------------------------------------

class BitDustFileReader(_FileReader):
    """
    """

    def __init__(self, fObj, filepath):
        super(BitDustFileReader, self).__init__(fObj)
        self.filepath = filepath

    def _close(self, passthrough):
        passthrough = super(BitDustFileReader, self)._close(passthrough)
        # tmpfile.throw_out(os.path.dirname(self.filepath), 'file read')
        return passthrough

#------------------------------------------------------------------------------

class BitDustFTP(FTP):
    """
    """

    def _accessGrantedResponse(self, result, segments):
        self.workingDirectory = segments
        return (REQ_FILE_ACTN_COMPLETED_OK,)

    def _dirListingResponse(self, results):
        self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        for (name, attrs) in results:
            name = self._encodeName(name)
            self.dtpInstance.sendListResponse(name, attrs)
        self.dtpInstance.transport.loseConnection()
        return (TXFR_COMPLETE_OK,)

    def _enableTimeoutLater(self, result, newsegs=None):
        self.setTimeout(self.factory.timeOut)
        return result

    def _cbFileSent(self, result):
        return (TXFR_COMPLETE_OK,)

    def _ebFileSent(self, err):
        lg.warn("Unexpected error attempting to transmit file to client: " + str(err))
        if err.check(FTPCmdError):
            return err
        return (CNX_CLOSED_TXFR_ABORTED,)

    def _cbReadOpened(self, file_obj, consumer):
        if self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        d = file_obj.send(consumer)
        d.addCallbacks(self._cbFileSent, self._ebFileSent)
        return d

    def _ebReadOpened(self, err, newsegs):
        if not err:
            return (FILE_NOT_FOUND, '/'.join(newsegs))
        if not err.check(PermissionDeniedError, FileNotFoundError, IsADirectoryError):
            lg.warn("Unexpected error attempting to open file for transmission: " + str(err))
        if err.check(FTPCmdError):
            return (err.value.errorCode, '/'.join(newsegs))
        return (FILE_NOT_FOUND, '/'.join(newsegs))

    def _cbFileRecevied(self, consumer, upload_filename, newsegs):
        #         receive_defer.addCallback(self._startFileBackup, upload_filename, newsegs, d)
#         consumer.fObj.flush()
#         os.fsync(consumer.fObj.fileno())
#         consumer.fObj.close()
#         consumer.close()
        full_path = '/' + ('/'.join(newsegs))
        path_id = backup_fs.ToID(full_path)
        if not path_id:
            path_id, _, _ = backup_fs.AddFile(full_path, read_stats=False)
        item = backup_fs.GetByID(path_id)
        item.read_stats(upload_filename)
        backup_control.StartSingle(path_id, upload_filename)
        # upload_task.result_defer.addCallback(self._cbFileBackup, result_defer, newsegs)
        backup_fs.Calculate()
        backup_control.Save()
        # result_defer.callback(None)
        # return consumer
        return (TXFR_COMPLETE_OK,)

    def _ebFileReceived(self, err):
        lg.warn("Unexpected error received during transfer: " + str(err))
        if err.check(FTPCmdError):
            return err
        return (CNX_CLOSED_TXFR_ABORTED,)

    def _cbWriteOpened(self, consumer, upload_filename, newsegs):
        d = consumer.receive()
        d.addCallback(self._startConsumer)
        d.addCallback(self._stopConsumer, consumer)
        # d.addCallback(lambda ignored: file_writer.close())
        d.addCallback(self._cbFileRecevied, upload_filename, newsegs)
        d.addErrback(self._ebFileReceived)
        return d

    def _ebWriteOpened(self, err, newsegs):
        if isinstance(err.value, FTPCmdError):
            return (err.value.errorCode, '/'.join(newsegs))
        lg.warn("Unexpected error received while opening file: %s" % str(err))
        return (FILE_NOT_FOUND, '/'.join(newsegs))

    def _startConsumer(self, consumer):
        if not self.binary:
            consumer = ASCIIConsumerWrapper(consumer)
        d = self.dtpInstance.registerConsumer(consumer)
        if self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        return d

    def _stopConsumer(self, d, consumer):
        # consumer.fObj.flush()
        # os.fsync(consumer.fObj.fileno())
        # consumer.fObj.close()
        consumer.close()
        return d

    def _cbRestoreDone(self, backupID, result, restore_path, path_segments, result_defer):
        if result != 'restore done':
            return result_defer.errback(None, path_segments)
        fp = filepath.FilePath(restore_path)
        try:
            fobj = fp.open('r')
        except:
            return result_defer.errback(None, path_segments)
        fr = _FileReader(fobj)
        return result_defer.callback(fr)

#     def _cbStat(self, result):
#         (size,) = result
#         return (FILE_STATUS, str(size))

    #------------------------------------------------------------------------------

    def ftp_LIST(self, path=''):
        # Uh, for now, do this retarded thing.
        if self.dtpInstance is None or not self.dtpInstance.isConnected:
            return defer.fail(BadCmdSequenceError('must send PORT or PASV before RETR'))
        # Various clients send flags like -L or -al etc.  We just ignore them.
        if path.lower() in ['-a', '-l', '-la', '-al']:
            path = ''
        try:
            segments = toSegments(self.workingDirectory, path)
        except InvalidPath:
            return defer.fail(FileNotFoundError(path))
        d = Deferred()
        d.addCallback(self._dirListingResponse)
        pth = '/' + ('/'.join(segments))
        lst = backup_fs.ListByPathAdvanced(pth)
        result = []
        for itm in lst:
            if itm[1] == 'index':
                continue
            # known_size = max(itm[7].size, 0)
            if itm[7].any_version():
                known_size = itm[7].versions[itm[7].get_latest_version()][1]
            else:
                known_size = 0
            result.append((itm[7].filename(), [  # name
                known_size,  # size
                True if itm[0] == 'dir' else False,  # folder or file ?
                filepath.Permissions(07777),  # permissions
                0,  # hardlinks
                time.mktime(time.strptime(itm[4], '%Y-%m-%d %H:%M:%S')) if itm[4] else None,  # time
                my_id.getIDName(),  # owner
                my_id.getIDName(),    # group   TODO: implement groups and populate here
            ], ))
        d.callback(result)
        return d

    def ftp_CWD(self, path):
        try:
            segments = toSegments(self.workingDirectory, path)
        except InvalidPath:
            # XXX Eh, what to fail with here?
            return defer.fail(FileNotFoundError(path))
        pth = '/' + ('/'.join(segments))
        d = Deferred()
        d.addCallback(lambda r: self._accessGrantedResponse(r, segments))
        if backup_fs.IsDir(pth):
            d.callback(None)
        else:
            d.errback(FileNotFoundError(path))
        return d

    def ftp_RETR(self, path):
        if self.dtpInstance is None:
            raise BadCmdSequenceError('PORT or PASV required before RETR')
        try:
            newsegs = toSegments(self.workingDirectory, path)
        except InvalidPath:
            return defer.fail(FileNotFoundError(path))
        # XXX For now, just disable the timeout.  Later we'll want to
        # leave it active and have the DTP connection reset it
        # periodically.
        self.setTimeout(None)
        # Put it back later
        # And away she goes
        if not self.binary:
            consumer = ASCIIConsumerWrapper(self.dtpInstance)
        else:
            consumer = self.dtpInstance
        pth = '/' + ('/'.join(newsegs))
        path_id = backup_fs.ToID(pth)
        if not path_id:
            return defer.fail(FileNotFoundError(path))
        item = backup_fs.GetByID(path_id)
        if not item:
            return defer.fail(FileNotFoundError(path))
        version = item.get_latest_version()
        if version is None:
            return defer.fail(FileNotFoundError(path))
        backupID = path_id + '/' + version
        if backup_control.IsBackupInProcess(backupID):
            # TODO: try older version, or return another error
            return defer.fail(FileNotFoundError(path))
        path_id, version = packetid.SplitBackupID(backupID)
        if restore_monitor.IsWorking(backupID):
            # TODO: wrap and consume existing restore process
            return defer.fail(FileNotFoundError(path))
        restore_filename = newsegs[-1]
        restore_dir = tmpfile.make_dir('restore', prefix=(backupID.replace('/', '_') + '_'))
        restore_path = os.path.join(restore_dir, restore_filename)

        d = Deferred()
        d.addCallback(self._cbReadOpened, consumer)
        d.addErrback(self._ebReadOpened, newsegs)
        d.addBoth(self._enableTimeoutLater)
        restore_monitor.Start(
            backupID,
            restore_dir,
            callback=lambda backup_id, result: self._cbRestoreDone(
                backup_id, result, restore_path, newsegs, d,
            ),
        )
        return d

    def ftp_STOR(self, path):
        if self.dtpInstance is None:
            raise BadCmdSequenceError('PORT or PASV required before STOR')
        try:
            newsegs = toSegments(self.workingDirectory, path)
        except InvalidPath:
            return defer.fail(FileNotFoundError(path))

#         parent_path = '/' + ('/'.join(newsegs[:-1]))
#         parent_item = backup_fs.GetByPath(parent_path)
#         if not parent_item:
#             return defer.fail(FileNotFoundError(parent_path))

        # XXX For now, just disable the timeout.  Later we'll want to
        # leave it active and have the DTP connection reset it
        # periodically.
        self.setTimeout(None)
        # Put it back later

        # , prefix=(newsegs[-1] + '_')
        upload_dir = tmpfile.make_dir('backup', extension='.ftp')
        if not upload_dir:
            return defer.fail(FileNotFoundError(path))
        upload_filename = os.path.join(upload_dir, newsegs[-1])
        fp = filepath.FilePath(upload_filename)
        try:
            fObj = fp.open('w')
        except (IOError, OSError) as e:
            return errnoToFailure(e.errno, path)
        except:
            return defer.fail(FileNotFoundError(path))
        # TODO: remove file after all
        # d.addCallback(lambda ignored: file.close(); and remove file)
        # d = Deferred()
        d = Deferred()
        d.addCallback(self._cbWriteOpened, upload_filename, newsegs)
        d.addErrback(self._ebWriteOpened, newsegs)
        d.addBoth(self._enableTimeoutLater)
        d.callback(_FileWriter(fObj))

#         d.addCallbacks(self._cbFileRecevied, self._ebFileReceived)
#         fw = _FileWriter(fObj)
#         receive_defer = fw.receive()
#         receive_defer.addBoth(self._enableTimeoutLater)
#         receive_defer.addCallback(self._prepareConsumer)
#         receive_defer.addCallback(self._startFileBackup, upload_filename, newsegs, d)
#         receive_defer.addErrback(lambda err: d.errback(FileNotFoundError(path)))

        return d

    def ftp_SIZE(self, path):
        try:
            newsegs = toSegments(self.workingDirectory, path)
        except InvalidPath:
            return defer.fail(FileNotFoundError(path))
        full_path = '/' + ('/'.join(newsegs))
        path_id = backup_fs.ToID(full_path)
        if path_id is None:
            return defer.fail(FileNotFoundError(path))
        item = backup_fs.GetByID(path_id)
        if item is None:
            return defer.fail(FileNotFoundError(path))
        return succeed((FILE_STATUS, str(item.size), ))
        # return self.shell.stat(newsegs, ('size',)).addCallback(self._cbStat)

    def ftp_MKD(self, path):
        try:
            newsegs = toSegments(self.workingDirectory, path)
        except InvalidPath:
            return defer.fail(FileNotFoundError(path))
        full_path = '/' + ('/'.join(newsegs))
        if backup_fs.Exists(full_path):
            return defer.fail(FileExistsError(path))
        path_id, _, _ = backup_fs.AddDir(path)
        backup_control.Save()
        return succeed((MKD_REPLY, path))

    def ftp_RMD(self, path):
        try:
            newsegs = toSegments(self.workingDirectory, path)
        except InvalidPath:
            return defer.fail(FileNotFoundError(path))
        full_path = '/' + ('/'.join(newsegs))
        path_id = backup_fs.ToID(full_path)
        if path_id is None:
            return defer.fail(FileNotFoundError(path))
        item = backup_fs.GetByID(path_id)
        if item is None:
            return defer.fail(FileNotFoundError(path))
        backup_control.DeletePathBackups(path_id, saveDB=False, calculate=False)
        backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), path_id)
        backup_fs.DeleteByID(path_id)
        backup_fs.Scan()
        backup_fs.Calculate()
        backup_control.Save()
        backup_monitor.A('restart')
        return succeed((REQ_FILE_ACTN_COMPLETED_OK,))

    def ftp_DELE(self, path):
        try:
            newsegs = toSegments(self.workingDirectory, path)
        except InvalidPath:
            return defer.fail(FileNotFoundError(path))
        full_path = '/' + ('/'.join(newsegs))
        path_id = backup_fs.ToID(full_path)
        if path_id is None:
            return defer.fail(FileNotFoundError(path))
        item = backup_fs.GetByID(path_id)
        if item is None:
            return defer.fail(FileNotFoundError(path))
        backup_control.DeletePathBackups(path_id, saveDB=False, calculate=False)
        backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), path_id)
        backup_fs.DeleteByID(path_id)
        backup_fs.Scan()
        backup_fs.Calculate()
        backup_control.Save()
        backup_monitor.A('restart')
        return succeed((REQ_FILE_ACTN_COMPLETED_OK,))

    def ftp_RNTO(self, toName):
        fromName = self._fromName
        del self._fromName
        self.state = self.AUTHED
        try:
            fromsegs = toSegments(self.workingDirectory, fromName)
            tosegs = toSegments(self.workingDirectory, toName)
        except InvalidPath:
            return defer.fail(FileNotFoundError(fromName))
        # TODO:
        return succeed((REQ_FILE_ACTN_COMPLETED_OK,))

#------------------------------------------------------------------------------

class BitDustFTPFactory(FTPFactory):
    """
    """
    protocol = BitDustFTP


#------------------------------------------------------------------------------

if __name__ == "__main__":
    lg.set_debug_level(20)
    settings.init()
    backup_fs.init()
    backup_control.init()
    # print backup_fs.IsDir('/Users')
    init()
    reactor.run()








#     def ftp_NLST(self, path):
#         """
#         """
#         print 'ftp_NLST:', path
#         # XXX: why is this check different from ftp_RETR/ftp_STOR? See #4180
#         if self.dtpInstance is None or not self.dtpInstance.isConnected:
#             return defer.fail(
#                 BadCmdSequenceError('must send PORT or PASV before RETR'))
# 
#         try:
#             segments = toSegments(self.workingDirectory, path)
#         except InvalidPath:
#             return defer.fail(FileNotFoundError(path))
# 
#         def cbList(results, glob):
#             """
#             Send, line by line, each matching file in the directory listing, and
#             then close the connection.
# 
#             @type results: A C{list} of C{tuple}. The first element of each
#                 C{tuple} is a C{str} and the second element is a C{list}.
#             @param results: The names of the files in the directory.
# 
#             @param glob: A shell-style glob through which to filter results (see
#                 U{http://docs.python.org/2/library/fnmatch.html}), or L{None}
#                 for no filtering.
#             @type glob: L{str} or L{None}
# 
#             @return: A C{tuple} containing the status code for a successful
#                 transfer.
#             @rtype: C{tuple}
#             """
#             self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
#             for (name, ignored) in results:
#                 if not glob or (glob and fnmatch.fnmatch(name, glob)):
#                     name = self._encodeName(name)
#                     self.dtpInstance.sendLine(name)
#             self.dtpInstance.transport.loseConnection()
#             return (TXFR_COMPLETE_OK,)
# 
#         def listErr(results):
#             """
#             RFC 959 specifies that an NLST request may only return directory
#             listings. Thus, send nothing and just close the connection.
# 
#             @type results: L{Failure}
#             @param results: The L{Failure} wrapping a L{FileNotFoundError} that
#                 occurred while trying to list the contents of a nonexistent
#                 directory.
# 
#             @returns: A C{tuple} containing the status code for a successful
#                 transfer.
#             @rtype: C{tuple}
#             """
#             self.dtpInstance.transport.loseConnection()
#             return (TXFR_COMPLETE_OK,)
# 
#         if _isGlobbingExpression(segments):
#             # Remove globbing expression from path
#             # and keep to be used for filtering.
#             glob = segments.pop()
#         else:
#             glob = None
# 
#         d = Deferred()
#         d.addCallback(cbList, glob)
#         d.addErrback(listErr)
# #         if not driver.is_started('service_restores'):
# #             d.errback(None)
#         result = [(itm['id'], []) for itm in api.backups_list()['result']]
#         d.callback(result)
#         return d