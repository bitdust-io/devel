from django.views.generic import DetailView, ListView
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.template.response import TemplateResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

#------------------------------------------------------------------------------ 

from logs import lg

from lib import nameurl

from web.auth import login_required

from models import Identity

#------------------------------------------------------------------------------ 

class IdentitiesView(ListView):
    template_name = 'identities.html'
    context_object_name = 'identities_list'
    
    def get_queryset(self):
        return Identity.objects.order_by('id')
    
#------------------------------------------------------------------------------ 

def open_by_idurl1(request, idurl_id):
    template_name = 'identity.html'
    idurl = nameurl.DjangoUnQuote(idurl_id)
    try:
        Ident = get_object_or_404(Identity, idurl=str(idurl))
    except:
        lg.exc()
        context = { 'identity.idurl': idurl, }
        return TemplateResponse(request, template_name, context)
    context = { 'identity': Ident, } 
    return render_to_response(template_name,
                              context, 
                              context_instance=RequestContext(request))


def open_by_id(request, id):
    try:
        ThisIdentity = get_object_or_404(Identity, id=id)
    except:
        context = { 'idurl': '', }
        return TemplateResponse(request, 'identity.html', context)
    context = {
        'identity': ThisIdentity, 
        'idurl': ThisIdentity.idurl, }
    return render_to_response('identity.html', context, 
                              context_instance=RequestContext(request))


def open_by_idurl(request, idurl_id):
    idurl = nameurl.DjangoUnQuote(idurl_id)
    try:
        ThisIdentity = get_object_or_404(Identity, idurl=idurl)
    except:
        context = { 'idurl': idurl, }
        return TemplateResponse(request, 'identity.html', context)
    context = {
        'identity': ThisIdentity, 
        'idurl': idurl, }
    return render_to_response('identity.html', context, 
                              context_instance=RequestContext(request))
    
#------------------------------------------------------------------------------ 

def ping(request):
    idurl = request.REQUEST.get('idurl', '')
    if not idurl:
        return HttpResponseBadRequest('need to provide idurl parameter') 
    from p2p import propagate
    propagate.single(str(idurl), wide=True)
    next_url = request.REQUEST.get('next', '/identity/%s' % nameurl.DjangoQuote(idurl))
    return HttpResponseRedirect(next_url) 
    
        


