#!/usr/bin/env python
# urls.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (urls.py) is part of BitDust Software.
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
# -*- coding: utf-8 -*-

from django.conf.urls import patterns, url

#------------------------------------------------------------------------------

from web.auth import login_required

import views

#------------------------------------------------------------------------------

urlpatterns = patterns(
    '',
    url(r'open/?$', login_required(views.open_room)),
    url(r'room/(?P<id>\d+)/ajax/?$', views.BasicAjaxHandler, name="jqchat_ajax"),
    url(r'room/(?P<id>\d+)/?$', login_required(views.room_by_id), name="jqchat_test_window"),
    # url(r"room_with_description/(?P<id>\d+)$", login_required(views.room_with_description), name="jqchat_test_window_with_description"),
    # url(r"room_with_description/(?P<id>\d+)/ajax$", views.WindowWithDescriptionAjaxHandler, name="jqchat_test_window_with_description_ajax"),
    url(r'room/(?P<idurl>[a-zA-Z0-9_.-]+)/?$', login_required(views.room_by_idurl), name="jqchat_test_window"),
    url(r'$', login_required(views.first_page)),
)
