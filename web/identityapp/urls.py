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


