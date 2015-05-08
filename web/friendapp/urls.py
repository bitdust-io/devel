from django.conf.urls import patterns, url

#------------------------------------------------------------------------------ 

from web.auth import login_required

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'(?P<pk>\d+)/$', 
        login_required(views.FriendView.as_view())),
    url(r'search/$', 
        login_required(views.FriendSearchView.as_view())),
    url(r'$', 
        login_required(views.FriendsView.as_view())),
)


