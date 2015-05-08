from django.views import generic

#------------------------------------------------------------------------------ 

from models import Customer
 
from lib import nameurl

#------------------------------------------------------------------------------ 

class CustomerView(generic.DetailView):
    template_name = 'customer.html'
    model = Customer

    def get_context_data(self, **kwargs):
        Cus = super(CustomerView, self).get_object()
        context = super(CustomerView, self).get_context_data(**kwargs)
        context['identity_id'] = nameurl.DjangoQuote(Cus.idurl)
        return context


class CustomersView(generic.ListView):
    template_name = 'customers.html'
    context_object_name = 'customers_list'
    
    def get_queryset(self):
        return Customer.objects.order_by('id')

