from django.conf.urls import patterns, url

#------------------------------------------------------------------------------ 

from web.auth import login_required

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'(?P<pk>\d+)$', 
        login_required(views.BackupFSItemView.as_view()), name='backupfsitem'),
    url(r'$', 
        login_required(views.BackupFSView.as_view()), name='backupfsitems'),
)


