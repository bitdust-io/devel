from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import REDIRECT_FIELD_NAME

#------------------------------------------------------------------------------ 

from logs import lg 

from userid import my_id

from crypt import key

#------------------------------------------------------------------------------ 

def is_session_authenticated(user):
    ok = user.is_authenticated()
    lg.out(8, 'django.is_session_authenticated session=%s' % (ok))
    return ok  

def is_identity_authenticated():
    ok = my_id.isLocalIdentityReady() and key.isMyKeyReady()
    lg.out(8, 'django.is_identity_authenticated node=%s' % (ok))
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


