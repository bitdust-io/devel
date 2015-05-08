# -*- coding: utf-8 -*-

from django.conf.urls import patterns, url

#------------------------------------------------------------------------------ 

from web.auth import login_required

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r"room/(?P<id>\d+)/$", login_required(views.room_by_id), name="jqchat_test_window"),
    url(r"room/(?P<id>\d+)/ajax/$", views.BasicAjaxHandler, name="jqchat_ajax"),
    url(r"room_with_description/(?P<id>\d+)/$", login_required(views.room_with_description), name="jqchat_test_window_with_description"),
    url(r"room_with_description/(?P<id>\d+)/ajax/$", views.WindowWithDescriptionAjaxHandler, name="jqchat_test_window_with_description_ajax"),
    url(r"room/(?P<idurl>[a-zA-Z0-9_.-]+)/$", login_required(views.room_by_idurl), name="jqchat_test_window"),
)

