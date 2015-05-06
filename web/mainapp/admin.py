from django.contrib import admin

from models import Identity
from models import Supplier
from models import Customer
from models import Friend
from models import BackupFSItem

admin.site.register(Identity)
admin.site.register(Supplier)
admin.site.register(Customer)
admin.site.register(Friend)
admin.site.register(BackupFSItem)
