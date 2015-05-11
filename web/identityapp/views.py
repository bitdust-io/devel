from django.views.generic import DetailView, ListView
from django.http import HttpResponseRedirect, Http404

#------------------------------------------------------------------------------ 

from logs import lg

from lib import nameurl

from models import Identity
 
#------------------------------------------------------------------------------ 

class IdentityView(DetailView):
    template_name = 'identity.html'
    model = Identity
    
#    def get_context_data(self, **kwargs):
#        Ident = super(IdentityView, self).get_object()
#        context = super(IdentityView, self).get_context_data(**kwargs)
#        context['identity_id'] = Ident.id
#        return context

class IdentityByIDURLView(DetailView):
    template_name = 'identity.html'
    model = Identity
    
    def get_object(self):
        try:
            return Identity.objects.get(idurl=nameurl.DjangoUnQuote(self.kwargs.get("idurl")))
        except:
            raise Http404

#    def get(self, request):
#        try:
#            return DetailView.get(self, request)
#        except:
#            return HttpResponseRedirect('/identity')


class IdentitiesView(ListView):
    template_name = 'identities.html'
    context_object_name = 'identities_list'
    
    def get_queryset(self):
        return Identity.objects.order_by('id')

