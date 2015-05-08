from django.views import generic

#------------------------------------------------------------------------------ 

from models import Identity
 
from lib import nameurl

#------------------------------------------------------------------------------ 

class IdentityView(generic.DetailView):
    template_name = 'identity.html'
    model = Identity
    
    def get_context_data(self, **kwargs):
        Iden = super(IdentityView, self).get_object()
        context = super(IdentityView, self).get_context_data(**kwargs)
        context['identity_id'] = Iden.id
        return context


class IdentityByIDURLView(generic.DetailView):
    template_name = 'identity.html'
    model = Identity

    def get_context_data(self, **kwargs):
        Iden = super(IdentityByIDURLView, self).get_object()
        context = super(IdentityView, self).get_context_data(**kwargs)
        context['identity_id'] = Iden.id
        return context


class IdentitiesView(generic.ListView):
    template_name = 'identities.html'
    context_object_name = 'identities_list'
    
    def get_queryset(self):
        return Identity.objects.order_by('id')

