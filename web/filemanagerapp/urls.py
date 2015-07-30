from django.conf.urls import patterns, url

#------------------------------------------------------------------------------ 

from web.auth import login_required

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'bridge$', login_required(views.filemanager_api_view)),
    url(r'$', login_required(views.FileManagerView.as_view())),
)


