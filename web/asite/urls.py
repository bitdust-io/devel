from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

#------------------------------------------------------------------------------ 

from web.auth import login_required
import views

#------------------------------------------------------------------------------ 

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^accounts/login/$', views.LoginPoint), 
    url(r'^accounts/logout/$', views.LogoutPoint), 
    url(r'^repaintflag/$', views.RepaintFlagView.as_view()),     
    url(r'^admin/', include(admin.site.urls)),
    url(r'^chat/', include('web.jqchatapp.urls')),  
    url(r'^setup/', include('web.setupapp.urls')), 
    url(r'^identity/', include('web.identityapp.urls')),
    url(r'^supplier/', include('web.supplierapp.urls')),
    url(r'^customer/', include('web.customerapp.urls')),
    url(r'^friend/', include('web.friendapp.urls')),
    url(r'^myfiles/', include('web.myfilesapp.urls')),
    url(r'^$', login_required(views.IndexView.as_view()), name='index'),
) 

urlpatterns += staticfiles_urlpatterns()

