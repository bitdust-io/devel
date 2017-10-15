#!/usr/bin/env python
# views.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (views.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
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

def first_page(request):
    return render_to_response('jqchat/first_page.html',
                              {'known_ids': [], },
                              context_instance=RequestContext(request))

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
            raise Http404('incorrect Room ID')
        try:
            ThisRoom = get_object_or_404(Room, id=roomid)
        except:
            ThisRoom = Room(id=roomid,
                            idurl=idurl,
                            name=name)
            ThisRoom.save()
            # myname = settings.getNickName() or my_id.getIDName()
            RoomMember.objects.create_member(idurl=my_id.getLocalID(),
                                             # name=nameurl.GetName(my_id.getLocalID()),
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
                                             # name=nameurl.GetName(my_id.getLocalID()),
                                             room=ThisRoom)
        return HttpResponseRedirect('/chat/room/%d' % ThisRoom.id)

    raise Http404('need to provide a room info')

#------------------------------------------------------------------------------


def room_by_id(request, id):
    try:
        ThisRoom = get_object_or_404(Room, id=id)
    except Exception as e:
        raise e
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

            StatusCode = 0  # Default status code is 0 i.e. no new data.

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
                    RoomMember.objects.create_member(idurl=id,
                                                     # name=nameurl.GetName(id),
                                                     room=self.ThisRoom)
                if action == 'room_leave':
                    RoomMember.objects.remove_member(idurl=id,
                                                     # name=nameurl.GetName(id),
                                                     room=self.ThisRoom)
                if len(msg_text.strip()) > 0:  # Ignore empty strings.
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
            NewMembersNames = map(lambda mem: nameurl.GetName(mem.idurl), NewMembers)

            l = len(NewMessages)
            if l > JQCHAT_DISPLAY_COUNT:
                NewMessages = NewMessages[l - JQCHAT_DISPLAY_COUNT:]

            response = render_to_response('jqchat/chat_payload.json',
                                          {'current_unix_timestamp': time.time(),
                                           'NewMessages': NewMessages,
                                           'StatusCode': StatusCode,
                                           'NewDescription': NewDescription,
                                           'NewMembers': NewMembers,
                                           'NewMembersNames': NewMembersNames,
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
