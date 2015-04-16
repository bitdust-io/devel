from django.conf.urls import patterns, include, url
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin

# import sys
# print 'asite.urls', '\n'.join(sys.path) 

admin.autodiscover()

import web.jqchat

urlpatterns = patterns('',
    url(r'', include('web.bpapp.urls', namespace='bpapp')),
    url(r'^admin/', include(admin.site.urls)),
    # url(r'^chat/', include('jqchat.urls', namespace='jqchat')),
    url(r'^chat/', include('web.jqchat.urls')),  
    # url(r'^accounts/', include('django.contrib.auth.urls')),
    # url(r"^accounts/", include("account.urls")),
    # url(r'^accounts/', include('registration.backends.default.urls')), 
) 

urlpatterns += static(
    settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# print 'asite urls:', '\n'.join(urlpatterns)