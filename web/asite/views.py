from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.http import is_safe_url
from django.shortcuts import resolve_url
from django.views.decorators.cache import never_cache
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth import authenticate
from django.contrib.auth import REDIRECT_FIELD_NAME

#------------------------------------------------------------------------------ 

from logs import lg
 
from userid import my_id

from crypt import key

from main import installer

#------------------------------------------------------------------------------ 

SETUP_PATH = '/setup/'

#------------------------------------------------------------------------------ 

@never_cache
def login_point(request, 
                redirect_field_name=REDIRECT_FIELD_NAME,
                current_app=None,
                extra_context=None,
                ):

    identity_ready = my_id.isLocalIdentityReady()
    private_key_ready = key.isMyKeyReady() 

    lg.out(4, 'django.login_point identity_ready=%s private_key_ready=%s' % (
        identity_ready, private_key_ready))
     
    if not identity_ready or not private_key_ready:
        return HttpResponseRedirect(SETUP_PATH)
    
    if installer.IsExist() and installer.A().state == 'DONE':
        return HttpResponseRedirect(SETUP_PATH)
        
    user = authenticate(username=my_id.getIDName(), password='password')
    
    lg.out(4, '    authenticate user is %s' % user)

    if user is not None:
        if not user.is_active:
            lg.out(4, '    user not active')
            logout(request)
            return HttpResponseRedirect(SETUP_PATH)
    else:
        newuser = User.objects.create_user(my_id.getIDName(), password='password')
        newuser.save()
        user = authenticate(username=my_id.getIDName(), password='password')
        if user is None:
            lg.out(4, '    authenticate after creating a new user failed')
            logout(request)
            return HttpResponseRedirect(SETUP_PATH)
        lg.out(4, '    created new user %s %s' % (newuser, user))        

    login(request, user)
        
    redirect_to = request.POST.get(redirect_field_name,
                                   request.GET.get(redirect_field_name, ''))
    if not is_safe_url(url=redirect_to, host=request.get_host()):
        redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)
        
    lg.out(4, '    redirecting to %s' % redirect_to)
        
    return HttpResponseRedirect(redirect_to)

@never_cache
def logout_point(request, 
                redirect_field_name=REDIRECT_FIELD_NAME,
                current_app=None,
                extra_context=None,
                ):

    lg.out(4, 'django.logout_point')

    logout(request)

    redirect_to = request.POST.get(redirect_field_name,
                                   request.GET.get(redirect_field_name, ''))
    if not is_safe_url(url=redirect_to, host=request.get_host()):
        redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)
        
    return HttpResponseRedirect(redirect_to)

