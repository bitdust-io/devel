#!/usr/bin/env python
#urls.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
from django.conf.urls import patterns, url

#------------------------------------------------------------------------------ 

from web.auth import login_required

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'ping$',
        login_required(views.ping)),
    url(r'(?P<id>\d+)$',
        login_required(views.open_by_id)),
    url(r'(?P<idurl_id>[a-zA-Z0-9_.-]+)$', 
        login_required(views.open_by_idurl)),
    url(r'$', 
        login_required(views.IdentitiesView.as_view())),
)


