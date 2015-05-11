from django.conf.urls import patterns, url

#------------------------------------------------------------------------------ 

from web.auth import login_required

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'(?P<pk>\d+)$', 
        login_required(views.CustomerView.as_view())),
    url(r'$', 
        login_required(views.CustomersView.as_view())),
)


