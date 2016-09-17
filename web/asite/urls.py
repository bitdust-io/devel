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
from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

#------------------------------------------------------------------------------ 

from web.auth import login_required
import views

#------------------------------------------------------------------------------ 

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^api/(?P<method>stop)', views.call_api_method),
    url(r'^api/(?P<method>restart)', views.call_api_method),
    url(r'^api/(?P<method>[a-zA-Z0-9_.-]+)$', login_required(views.call_api_method)),
    url(r'^accounts/login/$', views.LoginPoint), 
    url(r'^accounts/logout/$', views.LogoutPoint), 
    url(r'^repaintstate$', views.RepaintState),     
    url(r'^admin/', include(admin.site.urls)),
    url(r'^chat/', include('web.jqchatapp.urls')),  
    url(r'^setup/', include('web.setupapp.urls')), 
    url(r'^identity/', include('web.identityapp.urls')),
    url(r'^supplier/', include('web.supplierapp.urls')),
    url(r'^customer/', include('web.customerapp.urls')),
    url(r'^friend/', include('web.friendapp.urls')),
    # url(r'^myfiles/', include('web.myfilesapp.urls')),
    url(r'^filemanager/', include('web.filemanagerapp.urls')),
    url(r'^$', include('web.filemanagerapp.urls')),
    # url(r'^$', login_required(views.IndexView.as_view())),
) 

# urlpatterns += staticfiles_urlpatterns()

