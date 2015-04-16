from django.contrib import admin

from models import Supplier
from models import Customer
from models import BackupFSItem
from models import Friend

admin.site.register(Supplier)
admin.site.register(Customer)
admin.site.register(BackupFSItem)
admin.site.register(Friend)