from django.conf.urls import patterns, url

from bpapp import views

urlpatterns = patterns('',
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^suppliers/$', views.SuppliersView.as_view(), name='suppliers'),
    url(r'^suppliers/(?P<pk>[0-9]+)/$', views.SupplierView.as_view(), name='supplier'),
    url(r'^customers/$', views.CustomersView.as_view(), name='customers'),
    url(r'^customers/(?P<pk>[0-9]+)/$', views.CustomerView.as_view(), name='customer'),
    url(r'^backupfs/$', views.BackupFSView.as_view(), name='backupfsitems'),
    url(r'^backupfs/(?P<pk>[0-9]+)/$', views.BackupFSItemView.as_view(), name='backupfsitem'),
)