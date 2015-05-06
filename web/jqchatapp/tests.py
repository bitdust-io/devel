
"""
Unit tests for jqchat application.

"""

from django.test import TestCase
from django.test.client import Client
from django.contrib.auth.models import User
#from django.conf import settings

import simplejson
from models import Room, Message

# During testing we want to use default settings.
import views
views.DATE_FORMAT = "H:i:s"

class ChatPageTest(TestCase):
    """Test the chat test page."""

    # This includes a sample room.
    fixtures = ['test_jqchat.json']

    def setUp(self):
        self.client = Client()
        self.client.login(username='mickey', password='test')

    def test_chat_page(self):
        """We have a basic test page for the chat client."""

        # Get the room defined in the fixture.
        response = self.client.get('/jqchat/room/1/')
        self.assert_(response.status_code == 200, response.status_code)

        # Basic checks on the content of this page.
        self.assert_('<div id="chatwindow">' in response.content)
        self.assert_(response.context[0]['room'].name == 'The first room', response.context[0]['room'])

    def test_login(self):
        """Must be logged in to access the chat page."""

        self.client.logout()
        response = self.client.get('/jqchat/room/1/')
        # Should redirect to login page.
        self.assert_(response.status_code == 302, response.status_code)


class AJAXGetTest(TestCase):
    """Retrieving messages from the server."""

    fixtures = ['test_jqchat.json']

    def setUp(self):
        self.client = Client()
        self.client.login(username='mickey', password='test')
        
    def test_get_messages(self):
        """Get the latest messages."""

        response = self.client.get('/jqchat/room/1/ajax/', {'time': 0})

        # Basic sanity checks
        self.assert_(response.status_code == 200, response.status_code)
        self.assert_(response['Content-Type'] == 'text/plain; charset=utf-8', response['Content-Type'])
        self.assert_(response['Cache-Control'] == 'no-cache', response['Cache-Control'])

        # Check payload contents
        payload = simplejson.loads(response.content)

        # Should have a status of 1 (there are new messages).
        self.assert_(payload['status'] == 1, payload)

        # The server returns the Unix time, this will be a number > 0.
        t = payload['time']
        try:
            t = float(t)
        except:
            self.assert_(False, 'Time (%s) should be a number.' % t)

        messages = payload['messages']

        # Check the contents of the first message.
        # Note that messages should always be ordered oldest message first.
        self.assert_(len(messages) == 4)
        self.assert_(messages[0]['text'] == '15:04:29 <strong>mickey</strong>: hello<br />', '#%s#' % messages[0]['text'])

    def test_not_logged_in(self):
        """If the user is not logged in, they cannot access this method."""

        self.client.logout()
        response = self.client.get('/jqchat/room/1/ajax/', {'time': 0})

        self.assert_(response.status_code == 400, response.status_code)

    def test_get_last_message(self):
        """Set the time sent to the server so as to only retrieve the last message for room 1."""

        response = self.client.get('/jqchat/room/1/ajax/', {'time': 1227629906})

        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)

        # Should have a status of 1 (there are new messages).
        self.assert_(payload['status'] == 1, payload)

        messages = payload['messages']

        self.assert_(len(messages) == 1)
        self.assert_(messages[0]['text'] == "16:18:27 <strong>mickey</strong>: Yes, let's play!<br />", messages[0]['text'])

    def test_no_messages(self):
        """Set the time sent to the server to after the time of the most recent message."""

        response = self.client.get('/jqchat/room/1/ajax/', {'time': 1227629910})

        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)

        # Should have a status of 0 (no messages)
        self.assert_(payload['status'] == 0, payload)
        messages = payload['messages']
        self.assert_(len(messages) == 0)

    def test_no_time(self):
        """All requests should include the time."""

        response = self.client.get('/jqchat/room/1/ajax/')
        self.assert_(response.status_code == 400, response.status_code)

    def test_room_2(self):
        """Retrieve messages for room 2 - should be a different list to room 1.
        Additionally, set the time so as to retrieve only the latest 2 messages in that room -
        the first message gets ignored."""

        response = self.client.get('/jqchat/room/2/ajax/', {'time': 1227629877})

        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)

        # Should have a status of 1 (there are new messages).
        self.assert_(payload['status'] == 1, payload)

        messages = payload['messages']

        self.assert_(len(messages) == 2)
        self.assert_(messages[0]['text'].startswith('16:17:58'), messages)
        self.assert_(messages[1]['text'].startswith('16:18:02'), messages)


class AJAXPostTest(TestCase):
    """Send new data to the server."""

    fixtures = ['test_jqchat.json']

    def setUp(self):
        self.client = Client()
        self.client.login(username='mickey', password='test')

    def test_post_message(self):
        """Post a new message to the server"""

        response = self.client.post('/jqchat/room/1/ajax/', {'time': 0,
                                                         'action': 'postmsg',
                                                         'message': 'rhubarb'})
        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)
        # Should have a status of 1 (there are new messages).
        self.assert_(payload['status'] == 1, payload)

        messages = payload['messages']

        # Check the contents of the last message - the one that we have just posted.
        # Note that messages should always be ordered oldest message first.
        self.assert_(len(messages) == 5)
        # Remember that we are logged in as Donald Duck.
        self.assert_('mickey' in messages[-1]['text'])
        self.assert_('rhubarb' in messages[-1]['text'])

        # The 'last activity' flag on the room will be updated.
        # (the default value from the test fixture is 0).
        r = Room.objects.get(id=1)
        self.assert_(r.last_activity > 0, r.last_activity)

    def test_not_get(self):
        """If sending new data, we have to use a POST."""

        response = self.client.get('/jqchat/room/1/ajax/', {'time': 0,
                                                         'action': 'postmsg',
                                                         'message': 'rhubarb'})
        self.assert_(response.status_code == 400, response.status_code)

    def test_no_time(self):
        """All requests should include the time."""

        response = self.client.get('/jqchat/room/1/ajax/', {'action': 'postmsg',
                                                         'message': 'rhubarb'})
        self.assert_(response.status_code == 400, response.status_code)

    def test_empty_message(self):
        """Post an empty message to the server - it will be ignored."""

        response = self.client.post('/jqchat/room/1/ajax/', {'time': 0,
                                                         'action': 'postmsg',
                                                         'message': '  '})
        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)
        messages = payload['messages']
        # No messages added to the 4 already defined.
        self.assert_(len(messages) == 4)

    def test_XSS(self):
        """Check that chat is protected against cross-site scripting (by disabling html tags)."""

        response = self.client.post('/jqchat/room/1/ajax/', {'time': 0,
                                                         'action': 'postmsg',
                                                         'message': '<script>alert("boo!");</script>'})
        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)
        messages = payload['messages']
        self.assert_('&lt;script&gt;' in messages[-1]['text'])
        self.assert_('<script>' not in messages[-1]['text'])

class BehaviourTest(TestCase):
    """Check out how the chat window behaves in different scenarios."""

    fixtures = ['test_jqchat.json']

    def setUp(self):
        self.client = Client()
        self.client.login(username='mickey', password='test')

        self.client2 = Client()
        self.client2.login(username='donald', password='test')

    def test_simultaneous_messages(self):
        """Ensure that messages sent by different users at (virtually) the same time are picked up."""

        response = self.client.post('/jqchat/room/1/ajax/', {'time': 0,
                                                         'action': 'postmsg',
                                                         'message': 'rhubarb'})
        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)
        # Should have a status of 1 (there are new messages).
        self.assert_(payload['status'] == 1, payload)

        mickey_time = payload['time']
        messages = payload['messages']

        self.assert_(len(messages) == 5)
        self.assert_('mickey' in messages[-1]['text'])
        self.assert_('rhubarb' in messages[-1]['text'])

        # Donald also sends a message, at virtually the same time.
        response = self.client2.post('/jqchat/room/1/ajax/', {'time': 0,
                                                         'action': 'postmsg',
                                                         'message': 'crumble'})
        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)
        # Should have a status of 1 (there are new messages).
        self.assert_(payload['status'] == 1, payload)

        messages = payload['messages']

        # Will pick up the message by Mickey, as well as the one just posted by Donald.
        self.assert_(len(messages) == 6, messages)
        self.assert_('donald' in messages[-1]['text'])
        self.assert_('crumble' in messages[-1]['text'])

        # And the next to last message is the one by Mickey.
        self.assert_('mickey' in messages[-2]['text'])
        self.assert_('rhubarb' in messages[-2]['text'])

        # Mickey immediately requests the latest messages (it could happen...).
        # Note how the time is no longer 0 - it's whatever time was returned from the 
        # last AJAX query.
        response = self.client.get('/jqchat/room/1/ajax/', {'time': mickey_time})
        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)
        # Should have a status of 1 (there are new messages).
        self.assert_(payload['status'] == 1, payload)

        messages = payload['messages']

        # Since Mickey last checked, there has been one message posted by Donald.
        self.assert_(len(messages) == 1, messages)
        self.assert_('donald' in messages[-1]['text'])
        self.assert_('crumble' in messages[-1]['text'])

class EventTest(TestCase):
    """Create new events in the room."""

    fixtures = ['test_jqchat.json']

    def setUp(self):
        self.client = Client()
        self.client.login(username='mickey', password='test')

    def test_event(self):
        """Set the time sent to the server so as to only retrieve the last message for room 1.
        Also create a new event, such that we also pick up the event."""

        # Create a new event.
        u = User.objects.get(username='mickey')
        r = Room.objects.get(id=1)
        Message.objects.create_event(u, r, 3)
        
        response = self.client.get('/jqchat/room/1/ajax/', {'time': 1227629906})

        self.assert_(response.status_code == 200, response.status_code)

        payload = simplejson.loads(response.content)

        # Should have a status of 1 (there are new messages).
        self.assert_(payload['status'] == 1, payload)

        messages = payload['messages']

        self.assert_(len(messages) == 2)
        self.assert_(messages[0]['text'] == "16:18:27 <strong>mickey</strong>: Yes, let's play!<br />", messages)
        self.assert_("<strong>mickey</strong> <em>has left" in messages[1]['text'], messages)

        # The 'last activity' flag on the room will be updated.
        # (the default value from the test fixture is 0).
        r = Room.objects.get(id=1)
        self.assert_(r.last_activity > 0, r.last_activity)

class DescriptionTest(TestCase):
    """Get and update the description field.
    The description is only in the second test chat window, and is a demo of how to extend 
    the chat system.
    """

    fixtures = ['test_jqchat.json']

    def setUp(self):
        self.client = Client()
        self.client.login(username='mickey', password='test')

    def test_get_description(self):
        """For room 1, there is no description."""

        response = self.client.get('/jqchat/room_with_description/1/ajax/', {'time': 0})
        self.assert_(response.status_code == 200, response.status_code)
        payload = simplejson.loads(response.content)
        self.assert_(payload.has_key('description') == False)

    def test_get_description2(self):
        """room 2 has a pre-canned description."""

        response = self.client.get('/jqchat/room_with_description/2/ajax/', {'time': 0})
        self.assert_(response.status_code == 200, response.status_code)
        payload = simplejson.loads(response.content)
        self.assert_(payload['description'] == 'Enter description here!', payload)


    def test_change_description(self):
        """Change the description for room 2."""

        response = self.client.post('/jqchat/room_with_description/2/ajax/', {'time': 0,
                                                                            'action': 'change_description',
                                                                            'description': 'A new description'})
        self.assert_(response.status_code == 200, response.status_code)
        payload = simplejson.loads(response.content)
        self.assert_(payload['description'] == 'A new description', payload)

        # The latest message will be an event.
        messages = payload['messages']
        self.assert_("<strong>mickey</strong>" in messages[-1]['text'], messages)
        self.assert_("description" in messages[-1]['text'], messages)

        # The 'last activity' flag on the room will be updated.
        # (the default value from the test fixture is 0).
        r = Room.objects.get(id=2)
        self.assert_(r.last_activity > 0, r.last_activity)


    def test_XSS(self):
        """Check that chat is protected against cross-site scripting (by disabling html tags)."""

        response = self.client.post('/jqchat/room_with_description/2/ajax/', {'time': 0,
                                                                            'action': 'change_description',
                                                                            'description': '<script>alert("boo!");</script>'})
        self.assert_(response.status_code == 200, response.status_code)
        payload = simplejson.loads(response.content)
        self.assert_(payload['description'] == '&lt;script&gt;alert(&quot;boo!&quot;);&lt;/script&gt;', payload)





