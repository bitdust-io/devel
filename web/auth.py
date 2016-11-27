#!/usr/bin/env python
# auth.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (auth.py) is part of BitDust Software.
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
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import REDIRECT_FIELD_NAME

#------------------------------------------------------------------------------

from logs import lg

from userid import my_id

from crypt import key

#------------------------------------------------------------------------------


def is_session_authenticated(user):
    ok = user.is_authenticated()
    # lg.out(8, 'django.is_session_authenticated session=%s' % (ok))
    return ok


def is_identity_authenticated():
    ok = my_id.isLocalIdentityReady() and key.isMyKeyReady()
    # lg.out(8, 'django.is_identity_authenticated node=%s' % (ok))
    return ok


def username():
    return my_id.getIDName()


def password():
    return "password"


def login_required(function=None,
                   redirect_field_name=REDIRECT_FIELD_NAME,
                   login_url=None):
    actual_decorator = user_passes_test(
        # lambda u: u.is_authenticated(),
        lambda u: (is_session_authenticated(u) and is_identity_authenticated()),
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        return actual_decorator(function)
    return actual_decorator
