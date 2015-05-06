from django.conf.urls import patterns, url
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import REDIRECT_FIELD_NAME

#------------------------------------------------------------------------------ 

from logs import lg

from userid import my_id

from crypt import key

#------------------------------------------------------------------------------ 

import views

#------------------------------------------------------------------------------ 

def is_authenticated():
    identity_ready = my_id.isLocalIdentityReady()
    private_key_ready = key.isMyKeyReady()
    lg.out(4, 'django.is_authenticated identity_ready=%s private_key_ready=%s' % (
        identity_ready, private_key_ready))
    return identity_ready and private_key_ready 

def login_required(function=None, redirect_field_name=REDIRECT_FIELD_NAME, login_url=None):
    """
    Decorator for views that checks that the user is logged in, redirecting
    to the log-in page if necessary.
    """
    actual_decorator = user_passes_test(
        lambda u: is_authenticated(),
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        return actual_decorator(function)
    return actual_decorator

#------------------------------------------------------------------------------ 

urlpatterns = patterns('',
    url(r'^$', 
        login_required(views.IndexView.as_view()), name='index'),
    url(r'^identity/$', 
        login_required(views.IdentitiesView.as_view()), name='identities'),
    url(r'^identity/(?P<pk>[\w\%\.\#\(\)\_\-]+)/$', 
        login_required(views.IdentityView.as_view()), name='identity'),
    url(r'^suppliers/$', 
        login_required(views.SuppliersView.as_view()), name='suppliers'),
    url(r'^suppliers/(?P<pk>[0-9]+)/$', 
        login_required(views.SupplierView.as_view()), name='supplier'),
    url(r'^customers/$', 
        login_required(views.CustomersView.as_view()), name='customers'),
    url(r'^customers/(?P<pk>[0-9]+)/$', 
        login_required(views.CustomerView.as_view()), name='customer'),
    url(r'^backupfs/$', 
        login_required(views.BackupFSView.as_view()), name='backupfsitems'),
    url(r'^backupfs/(?P<pk>[0-9]+)/$', 
        login_required(views.BackupFSItemView.as_view()), name='backupfsitem'),
    url(r'^friends/$', 
        login_required(views.FriendsView.as_view()), name='friends'),
    url(r'^friends/(?P<pk>[0-9]+)/$', 
        login_required(views.FriendView.as_view()), name='friend'),
)


