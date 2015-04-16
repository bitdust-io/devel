from django.views import generic

from models import Supplier
from models import Customer
from models import BackupFSItem
from models import Friend
 

class IndexView(generic.TemplateView):
    template_name = 'index.html'

class SuppliersView(generic.ListView):
    template_name = 'suppliers.html'
    context_object_name = 'suppliers_list'
    def get_queryset(self):
        return Supplier.objects.order_by('id')

class SupplierView(generic.DetailView):
    template_name = 'supplier.html'
    model = Supplier

class CustomersView(generic.ListView):
    template_name = 'customers.html'
    context_object_name = 'customers_list'
    def get_queryset(self):
        return Customer.objects.order_by('id')

class CustomerView(generic.DetailView):
    template_name = 'customer.html'
    model = Customer

class BackupFSView(generic.ListView):
    template_name = 'backupfs.html'
    context_object_name = 'backup_fs_items_list'
    def get_queryset(self):
        return BackupFSItem.objects.order_by('backupid')

class BackupFSItemView(generic.DetailView):
    template_name = 'backupfsitem.html'
    model = BackupFSItem

class FriendsView(generic.ListView):
    template_name = 'friends.html'
    context_object_name = 'friends_list'
    def get_queryset(self):
        return Friend.objects.order_by('id')

class FriendView(generic.DetailView):
    template_name = 'friend.html'
    model = Friend

class ChatView(generic.DetailView):
    template_name = 'chat.html'
    model = Friend
    
