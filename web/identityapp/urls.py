from django.conf.urls import patterns, url

#------------------------------------------------------------------------------ 

from web.auth import login_required

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'(?P<pk>\d+)$', 
        login_required(views.IdentityView.as_view())),
    url(r'(?P<idurl>[a-zA-Z0-9_.-]+)$', 
        login_required(views.IdentityByIDURLView.as_view())),
    url(r'$', 
        login_required(views.IdentitiesView.as_view())),
)


