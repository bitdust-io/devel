#!/usr/bin/python
# service_personal_messages.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_personal_messages.py) is part of BitDust Software.
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

module:: service_personal_messages
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return PersonalMessagesService()


class PersonalMessagesService(LocalService):

    service_name = 'service_personal_messages'
    config_path = 'services/personal-messages/enabled'

    personal_group_key_id = None

    def dependent_on(self):
        return [
            'service_private_groups',
        ]

    def installed(self):
        # TODO: needs more work, service_private_groups() must be reliable first
        return False

    def start(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from twisted.internet.defer import Deferred  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.main import settings
        from bitdust.access import groups
        from bitdust.crypt import my_keys
        from bitdust.userid import my_id
        self.starting_deferred = Deferred()
        self.starting_deferred.addErrback(lambda err: lg.warn('service %r was not started: %r' % (self.service_name, err.getErrorMessage() if err else 'unknown reason')))
        self.personal_group_key_id = my_keys.make_key_id(alias='person', creator_glob_id=my_id.getGlobalID())

        # TODO: needs more work, service_private_groups() must be reliable first
        return True

        if not my_keys.is_key_registered(self.personal_group_key_id):
            self.personal_group_key_id = groups.create_new_group(
                label='my personal messages',
                creator_id=my_id.getGlobalID(),
                key_size=settings.getPrivateKeySize(),
                group_alias='person',
                with_group_info=True,
            )
            if self.personal_group_key_id is None:
                lg.err('failed creating "personal" message group, service_personal_messages() can not be started')
                if self.starting_deferred:
                    if not self.starting_deferred.called:
                        self.starting_deferred.errback(Exception('failed creating "personal" message group'))
                return self.starting_deferred
        d = groups.send_group_pub_key_to_suppliers(self.personal_group_key_id)
        d.addCallback(lambda results: self._do_join_my_personal_group())
        d.addErrback(self.starting_deferred.errback)
        d.addTimeout(10, clock=reactor)
        return self.starting_deferred

    def stop(self):
        # from bitdust.interface import api
        # api.group_leave(self.personal_group_key_id, erase_key=False)
        return True

    def _do_join_my_personal_group(self):
        from bitdust.logs import lg
        from bitdust.interface import api
        lg.info('about to join my personal message group: %r' % self.personal_group_key_id)
        api.group_join(self.personal_group_key_id)
        if self.starting_deferred:
            if not self.starting_deferred.called:
                self.starting_deferred.callback(True)
            self.starting_deferred = None
