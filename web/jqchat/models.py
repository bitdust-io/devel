# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.safestring import mark_safe
from django.conf import settings

import datetime
import time

class Room(models.Model):
    """Conversations can take place in one of many rooms.

    >>> l = Room(name='Test room')
    >>> l.save()
    >>> l
    <Room: Test room>

    Note that updating 'description' auto-updates 'description_modified' when saving:

    >>> l.description_modified

    >>> l.description = 'A description'

    Note that we need to always set the 'user' attribute as a system message is generated for each change.
    >>> l.user = User.objects.get(id=1)
    >>> l.save()

    # description_modified is a unix timestamp.
    >>> m = l.description_modified
    >>> m > 0
    True

    """
    name = models.CharField(max_length=20, null=True, blank=True, help_text='Name of the room.')
    created = models.DateTimeField(editable=False)
    description = models.CharField(max_length=100, null=True, blank=True, help_text='The description of this room.')
    description_modified = models.IntegerField(null=True, editable=False, help_text='Unix timestamp when the description was created or last modified.')
    last_activity = models.IntegerField(editable=False,
                                        help_text='Last activity in the room. Stored as a Unix timestamp.')
    # Define generic relation to target object. This is optional.
    content_type = models.ForeignKey(ContentType, blank=True, null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = generic.GenericForeignKey()

    def __unicode__(self):
        return u'%s' % (self.name)

    class Meta:
        ordering = ['created']

    def __init__(self, *args, **kw):
        super(Room, self).__init__(*args, **kw)
        self._init_description = self.description

    def save(self, **kw):
        # If description modified, update the timestamp field.
        if self._init_description != self.description:
            self.description_modified = time.time()
        # if last_activity is null (i.e. we are creating the room) set it to now.
        if not self.last_activity:
            self.last_activity = time.time()
        if not self.created:
            self.created = datetime.datetime.now()
        super(Room, self).save(**kw)

    @property
    def last_activity_formatted(self):
        """Return Unix timestamp, then express it as a time."""
        return display_timestamp(self.last_activity)

    @property
    def last_activity_datetime(self):
        """Convert last_activity into a datetime object (used to feed into timesince
        filter tag, ideally I should send a patch to Django to accept Unix times)"""
        return datetime.datetime.fromtimestamp(self.last_activity)

# The list of events can be customised for each project.
try:
    EVENT_CHOICES = settings.JQCHAT_EVENT_CHOICES
except:
    # Use default event list.
    EVENT_CHOICES = (
                  (1, "has changed the room's description."),
                  (2, "has joined the room."),
                  (3, "has left the room."),
                 )
class messageManager(models.Manager):
    
    def create_message(self, user, room, msg):
        """Create a message for the given user."""
        m = Message.objects.create(user=user,
                                   room=room,
                                   text='<strong>%s</strong> %s<br />' % (user, msg))
        return m

    def create_event(self, user, room, event_id):
        """Create an event for the given user."""
        m = Message(user=user,
                    room=room,
                    event=event_id)
        m.text = "<strong>%s</strong> <em>%s</em><br />" % (user, m.get_event_display())
        m.save()
        return m

class Message(models.Model):
    """Messages displayed in the chat client.

    Note that we have 2 categories of messages:
    - a text typed in by the user.
    - an event carried out in the room ("user X has left the room.").

    New messages should be created through the supplied manager methods, as all 
    messages get preformatted (added markup) for display in the chat window.
    For example:
    
    Messages:
    >>> user = User.objects.create_user('john', 'lennon@thebeatles.com', 'johnpassword')
    >>> room = Room.objects.create(name='Test room')
    >>> m = Message.objects.create_message(user, room, 'hello there')
    >>> m.text
    '<strong>john</strong> hello there<br />'

    Events:
    >>> m1 = Message.objects.create_event(user, room, 1)
    >>> u'<strong>john</strong> <em>has changed' in m1.text
    True

    Note that there are 2 timestamp fields:
    - a unix timestamp.
    - a datetime timestamp.
    The reason: the unix timestamp is higher performance when sending data to the browser (easier
    and faster to handle numbers instead of datetimes. The 'created' is used for displaying the date
    of messages; I could calculate it from the unix timestamp, but I'm guessing that I will get
    higher performance by storing it in the database.

    """

    user = models.ForeignKey(User, related_name='jchat_messages')
    room = models.ForeignKey(Room, help_text='This message was posted in a given chat room.')
    event = models.IntegerField(null=True, blank=True, choices=EVENT_CHOICES, help_text='An action performed in the room, either by a user or by the system (e.g. XYZ leaves room.')
    text = models.TextField(null=True, blank=True, help_text='A message, either typed in by a user or generated by the system.')
    unix_timestamp = models.FloatField(editable=False, help_text='Unix timestamp when this message was inserted into the database.')
    created = models.DateTimeField(editable=False)

    def __unicode__(self):
        return u'%s, %s' % (self.user, self.unix_timestamp)

    def save(self, **kw):
        if not self.unix_timestamp:
            self.unix_timestamp = time.time()
            self.created = datetime.datetime.fromtimestamp(self.unix_timestamp)
        super(Message, self).save(**kw)
        self.room.last_activity = int(time.time())
        self.room.save()

    class Meta:
        ordering = ['unix_timestamp']

    objects = messageManager()

class memberManager(models.Manager):
    
    def remove_member(self, user, room):
        """Remove a room user association"""
        usr_prev_rooms = RoomMember.objects.filter(user=user)
        for prev_room in usr_prev_rooms:
            if prev_room.room == room:
                continue
            Message.objects.create_event(user, prev_room.room, 3)
        usr_prev_rooms.delete()

    def create_member(self, user, room):
        """Create a room user association"""
        self.remove_member(user, room)        
        Message.objects.create_event(user, room, 2)
        m = RoomMember.objects.create(user=user, room=room)

        return m

class RoomMember(models.Model):
    """A room member"""
    room = models.ForeignKey(Room, null=True)
    user = models.ForeignKey(User)
    
    def save(self, **kw):
        super(RoomMember, self).save(**kw)
    class Meta:
        ordering = ['user']

    objects = memberManager()

def display_timestamp(t):
        """Takes a Unix timestamp as a an arg, returns a text string with
        '<unix timestamp> (<equivalent time>)'."""
        return '%s (%s)' % (t, time.strftime('%d/%m/%Y %H:%M', time.gmtime(t)))


