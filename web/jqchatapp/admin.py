# -*- coding: utf-8 -*-

from models import Message, Room, RoomMember
from django.contrib import admin

#------------------------------------------------------------------------------ 

class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'created', 'last_activity_formatted', 'description')
    readonly_fields = ('created', 'content_type', 'object_id')
    # As we've set some fields to be read-only, they will automatically appear at the end 
    # of the list. Manually order the fields to be as they are defined in the model.
    fieldsets = (
        (None, {
            'fields': ('idurl', 
                       'name', 
                       'created', 
                       'description', 
                       'content_type', 
                       'object_id')
        }),
    )

    # When changing a description, we need to know the request.user as an attribute
    # of the room instance. This snippet below adds it.
    # def save_model(self, request, obj, form, change):
    #     obj.user = request.user
    #     obj.save()

admin.site.register(Room, RoomAdmin)

#------------------------------------------------------------------------------ 

class RoomMemberAdmin(admin.ModelAdmin):
    list_display = ('room', 'idurl', )
    list_filter = ['room', 'idurl', ]

admin.site.register(RoomMember, RoomMemberAdmin)

#------------------------------------------------------------------------------ 

class MessageAdmin(admin.ModelAdmin):
    list_display = ('room', 'created', 'unix_timestamp', 'idurl', 'text', 'event',)
    list_filter = ['room', 'idurl',]

admin.site.register(Message, MessageAdmin)


