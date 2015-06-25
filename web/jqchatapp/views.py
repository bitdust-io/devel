import time

#------------------------------------------------------------------------------ 

from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.http import Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.conf import settings
from django.utils.html import escape

#------------------------------------------------------------------------------ 

from web import auth

from models import Room, RoomMember, Message

from logs import lg

from lib import nameurl

from main import settings

from chat import message

from contacts import contactsdb

from userid import my_id

#------------------------------------------------------------------------------ 

try:
    DATE_FORMAT = settings.JQCHAT_DATE_FORMAT
except:
    DATE_FORMAT = "H:i:s"

# How many messages to retrieve at most.
JQCHAT_DISPLAY_COUNT = getattr(settings, 'JQCHAT_DISPLAY_COUNT', 100) 

#------------------------------------------------------------------------------ 

def open_room(request):
    roomid = request.REQUEST.get('id', '')
    idurl = request.REQUEST.get('idurl', '')
    name = request.REQUEST.get('name', contactsdb.get_correspondent_nickname(idurl))

    if roomid:
        try:
            roomid = int(roomid)
        except:
            lg.exc()
            return Http404('incorrect Room ID')
        try:
            ThisRoom = get_object_or_404(Room, id=roomid)
        except:
            ThisRoom = Room(id=roomid,
                            idurl=idurl, 
                            name=name)
            ThisRoom.save() 
            # myname = settings.getNickName() or my_id.getIDName() 
            RoomMember.objects.create_member(idurl=my_id.getLocalID(),
                                             # idurl=idurl,
                                             room=ThisRoom)
        return HttpResponseRedirect('/chat/room/%d' % ThisRoom.id)

    if idurl:
        try:
            ThisRoom = get_object_or_404(Room, idurl=idurl)
        except:
            ThisRoom = Room(idurl=idurl, 
                            name=name)
            ThisRoom.save() 
            RoomMember.objects.create_member(idurl=my_id.getLocalID(),
                                             # idurl=idurl,
                                             room=ThisRoom)
        return HttpResponseRedirect('/chat/room/%d' % ThisRoom.id)

    return Http404('need to provide a room info')

#------------------------------------------------------------------------------ 

def room_by_id(request, id):
    try:
        ThisRoom = get_object_or_404(Room, id=id)
    except:
        raise Http404
    return render_to_response('jqchat/chat_test.html', 
                              {'room': ThisRoom},
                              context_instance=RequestContext(request))

#------------------------------------------------------------------------------

def room_by_idurl(request, idurl):
    idurl = nameurl.DjangoUnQuote(idurl)
    try:
        ThisRoom = get_object_or_404(Room, idurl=idurl)
    except:
        raise Http404
    return render_to_response('jqchat/chat_test.html', 
                              {'room': ThisRoom},
                              context_instance=RequestContext(request))

#------------------------------------------------------------------------------

class Ajax(object):
    def __call__(self, request, id):
        try:
            if not (auth.is_session_authenticated(request.user) and auth.is_identity_authenticated()):
                return HttpResponseBadRequest('You need to be logged in to access the chat system.')
        
            StatusCode = 0 # Default status code is 0 i.e. no new data.

            self.request = request
            try:
                self.request_time = float(self.request.REQUEST['time'])
            except:
                return HttpResponseBadRequest("What's the time?")
            try:
                self.ThisRoom = get_object_or_404(Room, id=id)
            except:
                lg.exc('id=%s' % str(id))
                return HttpResponseBadRequest("Not found Room with id=%s" % str(id))

            NewDescription = None
    
            if self.request.method == "POST":
                # User has sent new data.
                action = self.request.POST['action']
                msg_text = ''
        
                if action == 'postmsg':
                    msg_text = self.request.POST['message']
                if action == 'room_join':
                    RoomMember.objects.create_member(idurl=id, room=self.ThisRoom)
                if action == 'room_leave':
                    RoomMember.objects.remove_member(idurl=id, room=self.ThisRoom)
                if len(msg_text.strip()) > 0: # Ignore empty strings.
                    Message.objects.create_message(
                        my_id.getLocalID(), 
                        self.ThisRoom, 
                        escape(msg_text))
                    message.SendMessage(
                        str(self.ThisRoom.idurl), 
                        str(msg_text))
            else:
                # If a GET, make sure that no action was specified.
                if self.request.GET.get('action', None):
                    return HttpResponseBadRequest('Need to POST if you want to send data.')
    
            NewMessages = self.ThisRoom.message_set.filter(unix_timestamp__gt=self.request_time)
            if NewMessages:
                StatusCode = 1
    
            NewMembers = RoomMember.objects.filter(room=self.ThisRoom)
    
            l = len(NewMessages)
            if l > JQCHAT_DISPLAY_COUNT:
                NewMessages = NewMessages[l-JQCHAT_DISPLAY_COUNT:]
                
            response = render_to_response('jqchat/chat_payload.json',
                {'current_unix_timestamp': time.time(),
                 'NewMessages': NewMessages,
                 'StatusCode': StatusCode,
                 'NewDescription': NewDescription,
                 'NewMembers': NewMembers,
                 'CustomPayload': '',
                 'TimeDisplayFormat': DATE_FORMAT
                },
                context_instance=RequestContext(self.request))
            
            response['Content-Type'] = 'text/plain; charset=utf-8'
            response['Cache-Control'] = 'no-cache'
            return response
        
        except:
            e = lg.exc()
            return HttpResponseBadRequest('EXCEPTION:' + e)


BasicAjaxHandler = Ajax()

