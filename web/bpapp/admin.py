from django.contrib import admin

from bpapp.models import Supplier
from bpapp.models import Customer
from bpapp.models import BackupFSItem

admin.site.register(Supplier)
admin.site.register(Customer)
admin.site.register(BackupFSItem)