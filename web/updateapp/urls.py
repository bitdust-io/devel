from django.conf.urls import patterns, url

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'flag/$', views.UpdateFlagView.as_view()), 
)


