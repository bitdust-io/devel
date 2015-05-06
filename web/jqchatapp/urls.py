# -*- coding: utf-8 -*-

from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required

import views

urlpatterns = patterns('',
    
    # url(r"$", login_required(views.ChatView), name="jqchat_new_room"),

    url(r"room/(?P<id>\d+)/$", views.room_by_id, name="jqchat_test_window"),
    url(r"room/(?P<id>\d+)/ajax/$", views.BasicAjaxHandler, name="jqchat_ajax"),

    url(r"room_with_description/(?P<id>[\w\%\.\#\(\)]+)/$", views.room_with_description, name="jqchat_test_window_with_description"),
    url(r"room_with_description/(?P<id>[\w\%\.\#\(\)]+)/ajax/$", views.WindowWithDescriptionAjaxHandler, name="jqchat_test_window_with_description_ajax"),

    url(r"room/(?P<idurl>[a-zA-Z0-9_.-]+)/$", views.room_by_idurl, name="jqchat_test_window"),
)

