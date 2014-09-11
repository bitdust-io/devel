from django.views import generic

from bpapp.models import Supplier
from bpapp.models import Customer
from bpapp.models import BackupFSItem
 

class IndexView(generic.TemplateView):
    template_name = 'bpapp/index.html'

class SuppliersView(generic.ListView):
    template_name = 'bpapp/suppliers.html'
    context_object_name = 'suppliers_list'
    def get_queryset(self):
        return Supplier.objects.order_by('id')

class SupplierView(generic.DetailView):
    template_name = 'bpapp/supplier.html'
    model = Supplier

class CustomersView(generic.ListView):
    template_name = 'bpapp/customers.html'
    context_object_name = 'customers_list'
    def get_queryset(self):
        return Customer.objects.order_by('id')

class CustomerView(generic.DetailView):
    template_name = 'bpapp/customer.html'
    model = Customer

class BackupFSView(generic.ListView):
    template_name = 'bpapp/backupfs.html'
    context_object_name = 'backup_fs_items_list'
    def get_queryset(self):
        return BackupFSItem.objects.order_by('backupid')

class BackupFSItemView(generic.DetailView):
    template_name = 'bpapp/backupfsitem.html'
    model = BackupFSItem
