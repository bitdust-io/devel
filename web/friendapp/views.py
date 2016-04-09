from django.views.generic import TemplateView, DetailView, ListView
from django.template.response import TemplateResponse
from django.http import JsonResponse
from django.http import HttpResponseRedirect

#------------------------------------------------------------------------------ 

from models import Friend
from web.identityapp.models import Identity 

from logs import lg

from lib import nameurl

from contacts import contactsdb

from chat import nickname_observer

from p2p import commands
from p2p import propagate
from p2p import contact_status

from web import control 

#------------------------------------------------------------------------------ 

_SearchLookups = {}

#------------------------------------------------------------------------------ 

class FriendView(DetailView):
    template_name = 'friend.html'
    model = Friend

    def get_context_data(self, **kwargs):
        Fri = super(FriendView, self).get_object()
        context = super(FriendView, self).get_context_data(**kwargs)
        try:
            CachedIdentity = Identity.objects.get(idurl=Fri.idurl)
            context['identity_id'] = CachedIdentity.id
        except:
            pass
        return context


class FriendsView(ListView, control.DebugMixin):
    template_name = 'friends.html'
    context_object_name = 'friends_list'
    
    def get(self, request):
        action = request.GET.get('action', None)
        if action == 'add':
            idurl = request.GET.get('idurl', '')
            username = request.GET.get('username', '')
            if idurl:
                if not contactsdb.is_correspondent(idurl):
                    contactsdb.add_correspondent(idurl, username)
                    contactsdb.save_correspondents()
                    return HttpResponseRedirect(request.path)
        return ListView.get(self, request)
    
    def get_queryset(self):
        return Friend.objects.order_by('id')


class FriendSearchView(TemplateView):
    template = 'friendsearch.html'
    
    def get(self, request):
        global _SearchLookups
        target_username = request.GET.get('target_username', '')
        sessionkey = request.session.session_key
        context = {'target_username': target_username,}
        # lg.out(8, 'django.FriendSearchView.get %s' % target_username) 
        if target_username: 
            try: 
                result = _SearchLookups[sessionkey][target_username]
            except:
                result = []
            return JsonResponse({'result': result})
        return TemplateResponse(request, self.template, context) 
    
    def post(self, request):
        global _SearchLookups
        target_username = request.REQUEST.get('target_username', '')
        sessionkey = request.session.session_key
        context = {'target_username': target_username, }
        # lg.out(8, 'django.FriendSearchView.post %s' % target_username) 
        if target_username:
            if sessionkey not in _SearchLookups.keys():
                _SearchLookups[sessionkey] = {}
            if target_username in _SearchLookups[sessionkey].keys():
                return JsonResponse({'result': 'lookup'})
            _SearchLookups[sessionkey].clear()
            _SearchLookups[sessionkey][target_username] = []
            nickname_observer.stop_all()
            nickname_observer.observe_many(target_username, 
                results_callback=lambda result, nik, pos, idurl:
                    nickname_observer_result(sessionkey, target_username, result, nik, pos, idurl))
            return JsonResponse({'result': 'started'})
        return TemplateResponse(request, self.template, context)
            
        
def nickname_observer_result(sessionkey, target_username, result, nik, pos, idurl):
    lg.out(6, 'django.nickname_observer_result: %s' % str((sessionkey, target_username, result, nik, idurl)))
    global _SearchLookups
    try:
        status = ''
        if result == 'exist':
            if contact_status.isKnown(idurl):
                status = contact_status.getStatusLabel(idurl)
            else: 
                propagate.single(idurl, 
                    ack_handler=lambda ackpacket, info: 
                        contact_acked(sessionkey, target_username, ackpacket, info),
                    fail_handler=lambda failpacket, info:
                        contact_failed(sessionkey, target_username, failpacket, info),
                    wide=True)
                status = 'checking'
            _SearchLookups[sessionkey][target_username].append({
                'nickname': nik,
                'position': pos,
                'idurl': idurl,
                'status': status, })
    except:
        lg.exc()
        return
    # control.request_update()
    
    
def contact_acked(sessionkey, target_username, ackpacket, info):
    lg.out(6, 'django.contact_acked: %s' % str((sessionkey, target_username, ackpacket, info)))
    global _SearchLookups
    try:
        results = _SearchLookups[sessionkey][target_username]
        for i in xrange(len(results)):
            result = results[i]
            if result['idurl'] == ackpacket.OwnerID:
                if ackpacket.Command == commands.Ack():
                    new_status = contact_status.getStatusLabel(ackpacket.OwnerID)
                    _SearchLookups[sessionkey][target_username][i]['status'] = new_status 
                    break 
    except:
        lg.exc()
            
def contact_failed(sessionkey, target_username, ackpacket, info):
    """
    TODO:
    """
