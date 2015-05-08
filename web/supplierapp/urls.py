from django.conf.urls import patterns, url

#------------------------------------------------------------------------------ 

from web.auth import login_required

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'(?P<pk>[0-9]+)/$', 
        login_required(views.SupplierView.as_view())),
    url(r'$', 
        login_required(views.SuppliersView.as_view())),
)


