from django.conf.urls import patterns, url

import views

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'', views.SetupView.as_view()),
    
#    url(r'^select/$', views.SelectActionView.as_view()),
#    url(r'^inputname/$', views.InputNameView.as_view()),
#    url(r'^newidentity/$', views.NewIdentityView.as_view()),
#    url(r'^loadkey/$', views.LoadKeyView.as_view()),
#    url(r'^recover/$', views.RecoverView.as_view()),
#    url(r'^success/$', views.SuccessView.as_view()),
#    url(r'^failed/$', views.FailedView.as_view()),
    
#    url(r'^wizard/$', views.WizardSelectRoleView.as_view()),
#    url(r'^wizard/tryit/$', views.WizardTryItView.as_view()),
#    url(r'^wizard/beta/$', views.WizardBetaView.as_view()),
#    url(r'^wizard/donator/$', views.WizardDonatorView.as_view()),
#    url(r'^wizard/freespace/$', views.WizardFreeSpaceView.as_view()),
#    url(r'^wizard/tryit/$', views.WizardTryItView.as_view()),

)


