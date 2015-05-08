from django.views import generic
from django.template.response import TemplateResponse

#------------------------------------------------------------------------------ 

from models import Friend

#------------------------------------------------------------------------------ 

from logs import lg

from lib import nameurl

from chat import nickname_observer

#------------------------------------------------------------------------------ 

_SearchLookups = {}

#------------------------------------------------------------------------------ 

class FriendView(generic.DetailView):
    template_name = 'friend.html'
    model = Friend

    def get_context_data(self, **kwargs):
        Fri = super(FriendView, self).get_object()
        context = super(FriendView, self).get_context_data(**kwargs)
        context['identity_id'] = nameurl.DjangoQuote(Fri.idurl)
        return context


class FriendsView(generic.ListView):
    template_name = 'friends.html'
    context_object_name = 'friends_list'
    
    def get_queryset(self):
        return Friend.objects.order_by('id')


class FriendSearchView(generic.TemplateView):
    template = 'friendsearch.html'
    
    def get(self, request):
        global _SearchLookups
        context = {}
        return TemplateResponse(request, self.template, context)
    
    def post(self, request):
        global _SearchLookups
        action = request.POST.get('action', None)
        target_username = request.POST.get('target_username', None)
        if action == 'search' and target_username:
            skey = request.session.session_key
            if skey not in _SearchLookups.keys():
                _SearchLookups[skey] = {}
            if target_username not in _SearchLookups[skey].keys():
                _SearchLookups[skey][target_username] = []
            nickname_observer.observe_many(target_username, 
                results_callback=lambda result, nik, idurl: nickname_observer_result(skey, target_username, result, nik, idurl))
            
        
def nickname_observer_result(sessionkey, target_username, result, nik, idurl):
    global _SearchLookups
    try:
        _SearchLookups[sessionkey][target_username].append((result, nik, idurl))
    except:
        lg.exc()
            