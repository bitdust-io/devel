#!/usr/bin/env python
# config.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (config.py) is part of BitDust Software.
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
from django.apps import AppConfig
from django.contrib.auth import models as auth_models
from django.contrib.auth.management.commands import createsuperuser
from django.db.models import signals


USERNAME = "local_admin"
PASSWORD = "password"


def create_testuser(**kwargs):
    try:
        auth_models.User.objects.get(username=USERNAME)
    except auth_models.User.DoesNotExist:
        auth_models.User.objects.create_superuser(USERNAME, 'local_admin@localhost', PASSWORD)


class ASiteAppConfig(AppConfig):
    name = __package__

    def ready(self):
        # if not settings.DEBUG:
        #     return
        # Prevent interactive question about wanting a superuser created
        signals.post_syncdb.disconnect(createsuperuser, sender=auth_models,
                                       dispatch_uid='django.contrib.auth.management.create_superuser')
        signals.post_syncdb.connect(create_testuser, sender=auth_models,
                                    dispatch_uid='common.models.create_testuser')
