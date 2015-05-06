from django.http import HttpResponse
from django.views import generic
from django.template.response import TemplateResponse
from django.utils.http import urlquote
from django.contrib.admin.utils import quote
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator 
                                        
from models import Identity
from models import Supplier
from models import Customer
from models import BackupFSItem
from models import Friend
 
from lib import nameurl

#------------------------------------------------------------------------------ 

class IndexView(generic.TemplateView):
    template_name = 'index.html'

    # @method_decorator(login_required)    
    # @method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True))    
    # def dispatch(self, request, *args, **kwargs):
    #     return generic.View.dispatch(self, request, *args, **kwargs)

#------------------------------------------------------------------------------ 

class IdentityView(generic.DetailView):
    template_name = 'identity.html'
    model = Identity
    
    def get_context_data(self, **kwargs):
        Iden = super(IdentityView, self).get_object()
        context = super(IdentityView, self).get_context_data(**kwargs)
        context['identity_id'] = Iden.id
        return context


class IdentitiesView(generic.ListView):
    template_name = 'identities.html'
    context_object_name = 'identities_list'
    def get_queryset(self):
        return Identity.objects.order_by('id')

#------------------------------------------------------------------------------ 

class SupplierView(generic.DetailView):
    template_name = 'supplier.html'
    model = Supplier

    def get_context_data(self, **kwargs):
        Sup = super(SupplierView, self).get_object()
        # Ident = Identity.objects.get(idurl=Sup.idurl)
        context = super(SupplierView, self).get_context_data(**kwargs)
        # context['identity_id'] = Ident.id
        context['identity_id'] = nameurl.DjangoQuote(Sup.idurl) # nameurl.Quote(Sup.idurl)
        return context

class SuppliersView(generic.ListView):
    template_name = 'suppliers.html'
    context_object_name = 'suppliers_list'
    def get_queryset(self):
        return Supplier.objects.order_by('id')

#------------------------------------------------------------------------------ 

class CustomerView(generic.DetailView):
    template_name = 'customer.html'
    model = Customer

    def get_context_data(self, **kwargs):
        Cus = super(CustomerView, self).get_object()
        # Ident = Identity.objects.get(idurl=Cus.idurl)
        context = super(CustomerView, self).get_context_data(**kwargs)
        # context['identity_id'] = Ident.id
        context['identity_id'] = nameurl.DjangoQuote(Cus.idurl)
        return context

class CustomersView(generic.ListView):
    template_name = 'customers.html'
    context_object_name = 'customers_list'
    def get_queryset(self):
        return Customer.objects.order_by('id')

#------------------------------------------------------------------------------ 

class FriendView(generic.DetailView):
    template_name = 'friend.html'
    model = Friend

    def get_context_data(self, **kwargs):
        Fri = super(FriendView, self).get_object()
        # Ident = Identity.objects.get(idurl=Fri.idurl)
        context = super(FriendView, self).get_context_data(**kwargs)
        # context['identity_id'] = Ident.id
        context['identity_id'] = nameurl.DjangoQuote(Fri.idurl)
        return context

class FriendsView(generic.ListView):
    template_name = 'friends.html'
    context_object_name = 'friends_list'
    def get_queryset(self):
        return Friend.objects.order_by('id')

#------------------------------------------------------------------------------ 

class BackupFSItemView(generic.DetailView):
    template_name = 'backupfsitem.html'
    model = BackupFSItem

class BackupFSView(generic.ListView):
    template_name = 'backupfs.html'
    context_object_name = 'backup_fs_items_list'
    def get_queryset(self):
        return BackupFSItem.objects.order_by('backupid')

