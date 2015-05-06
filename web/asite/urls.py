from django.conf.urls import patterns, include, url
# from django.conf import settings
# from django.conf.urls.static import static
from django.contrib import admin
# from django.contrib.staticfiles.views import serve as serve_static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

import views

#------------------------------------------------------------------------------ 

admin.autodiscover()

urlpatterns = patterns('',
    # url(r'^static/(?P<path>.*)$', serve_static),
    url(r'^accounts/login/$', views.login_point), 
    url(r'^accounts/logout/$', views.logout_point), 
    url(r'^admin/', include(admin.site.urls)),
    url(r'^chat/', include('web.jqchatapp.urls')),  
    url(r'^setup/', include('web.setupapp.urls')), 
    url(r'^update/', include('web.updateapp.urls')),
    url(r'', include('web.mainapp.urls')),

    # url(r'^accounts/login/$','django.contrib.auth.views.login', {'template_name': 'admin/login.html'}),
    # url(r'^accounts/logout/$', 'django.contrib.auth.views.logout'),     
    # url(r'^chat/', include('jqchat.urls', namespace='jqchat')),
    # url(r'^accounts/', include('django.contrib.auth.urls')),
    # url(r"^accounts/", include("account.urls")),
    # url(r'^accounts/', include('registration.backends.default.urls')),
) 

# urlpatterns += static(
#     settings.STATIC_URL,
#     document_root=settings.STATIC_ROOT)


urlpatterns += staticfiles_urlpatterns()
