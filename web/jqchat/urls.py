# -*- coding: utf-8 -*-

from django.conf.urls import patterns, url

import views

# print 'jqchat.urls' 

urlpatterns = patterns('',
    # Example chat room.
    url(r"room/(?P<id>\d+)/$", views.window, name="jqchat_test_window"),
    url(r"room/(?P<id>\d+)/ajax/$", views.BasicAjaxHandler, name="jqchat_ajax"),
    # Second example room - adds room descriptions.
    url(r"room_with_description/(?P<id>\d+)/$", views.WindowWithDescription, name="jqchat_test_window_with_description"),
    url(r"room_with_description/(?P<id>\d+)/ajax/$", views.WindowWithDescriptionAjaxHandler, name="jqchat_test_window_with_description_ajax"),
)

# print 'urlpatterns', urlpatterns



