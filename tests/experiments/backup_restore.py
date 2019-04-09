#!/usr/bin/env python
# backup_restore.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (backup_restore.py) is part of BitDust Software.
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
from __future__ import absolute_import
from __future__ import print_function
import os
import sys

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

if __name__ == "__main__":
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

#------------------------------------------------------------------------------

from logs import lg

from userid import my_id

from main import settings

from system import bpio
from system import tmpfile

from storage import backup_tar
from storage import backup_fs
from storage import backup
from storage import restore_worker

from raid import raid_worker

#------------------------------------------------------------------------------


def backup_done(bid, result):
    from crypt import signed
    try:
        os.mkdir(os.path.join(settings.getLocalBackupsDir(), bid + '.out'))
    except:
        pass
    for filename in os.listdir(os.path.join(settings.getLocalBackupsDir(), bid)):
        filepath = os.path.join(settings.getLocalBackupsDir(), bid, filename)
        payld = str(bpio.ReadBinaryFile(filepath))
        outpacket = signed.Packet(
            'Data',
            my_id.getLocalID(),
            my_id.getLocalID(),
            filename,
            payld,
            'http://megafaq.ru/cvps1010.xml')
        newfilepath = os.path.join(settings.getLocalBackupsDir(),
                                   bid + '.out', filename)
        bpio.WriteBinaryFile(newfilepath, outpacket.Serialize())
    # Assume we delivered all pieces from ".out" to suppliers and lost original data
    # Then we requested the data back and got it into ".inp"
    try:
        os.mkdir(os.path.join(settings.getLocalBackupsDir(), bid + '.inp'))
    except:
        pass
    for filename in os.listdir(os.path.join(settings.getLocalBackupsDir(), bid + '.out')):
        filepath = os.path.join(settings.getLocalBackupsDir(), bid + '.out', filename)
        data = bpio.ReadBinaryFile(filepath)
        inppacket = signed.Unserialize(data)
        assert inppacket
        assert inppacket.Valid()
        newfilepath = os.path.join(settings.getLocalBackupsDir(),
                                   bid + '.inp', filename)
        bpio.WriteBinaryFile(newfilepath, inppacket.Payload)
    # Now do restore from input data
    backupID = bid + '.inp'
    outfd, tarfilename = tmpfile.make(
        'restore',
        extension='.tar.gz',
        prefix=backupID.replace('/', '_') + '_',
    )
    r = restore_worker.RestoreWorker(backupID, outfd)
    r.MyDeferred.addBoth(restore_done, tarfilename)
    reactor.callLater(1, r.automat, 'init')


def restore_done(x, tarfilename):
    backupID, result = x.split(' ')
    print(backupID, result)
    print(tarfilename)
    reactor.stop()


def main():
    sourcePath = sys.argv[1]
    backupID = sys.argv[2]
    lg.set_debug_level(24)
    compress_mode = 'none'  # 'gz'
    raid_worker.A('init')
    backupPath = backup_fs.MakeLocalDir(settings.getLocalBackupsDir(), backupID)
    if bpio.pathIsDir(sourcePath):
        backupPipe = backup_tar.backuptardir(sourcePath, compress=compress_mode)
    else:
        backupPipe = backup_tar.backuptarfile(sourcePath, compress=compress_mode)
    backupPipe.make_nonblocking()

    job = backup.backup(backupID, backupPipe, backup_done)
    reactor.callLater(1, job.automat, 'start')
    reactor.run()


if __name__ == "__main__":
    main()
