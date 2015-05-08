from django.views import generic

#----------------------------------------------------------------------------- 4
                                        
from models import Supplier
 
from lib import nameurl

#------------------------------------------------------------------------------ 

class SupplierView(generic.DetailView):
    template_name = 'supplier.html'
    model = Supplier

    def get_context_data(self, **kwargs):
        Sup = super(SupplierView, self).get_object()
        context = super(SupplierView, self).get_context_data(**kwargs)
        context['identity_id'] = nameurl.DjangoQuote(Sup.idurl) # nameurl.Quote(Sup.idurl)
        return context

class SuppliersView(generic.ListView):
    template_name = 'suppliers.html'
    context_object_name = 'suppliers_list'
    
    def get_queryset(self):
        return Supplier.objects.order_by('id')

