#!/usr/bin/python
# service_backup_db.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_backup_db.py) is part of BitDust Software.
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

module:: service_backup_db
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return BackupDBService()


class BackupDBService(LocalService):

    service_name = 'service_backup_db'
    config_path = 'services/backup-db/enabled'

    def dependent_on(self):
        return [
            'service_list_files',
            'service_data_motion',
        ]

    def start(self):
        from storage import index_synchronizer
        index_synchronizer.A('init')
        return True

    def stop(self):
        from storage import index_synchronizer
        index_synchronizer.A('shutdown')
        return True

    def health_check(self):
        from storage import index_synchronizer
        return index_synchronizer.A().state in ['IN_SYNC!', 'SENDING', 'REQUEST?', ]
