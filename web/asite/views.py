from django.conf import settings
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.utils.http import is_safe_url
from django.shortcuts import resolve_url
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView
from django.views.generic import View
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth import authenticate
from django.contrib.auth import REDIRECT_FIELD_NAME

#------------------------------------------------------------------------------ 

from logs import lg

from interface import api
 
from web import auth
from web import control 

#------------------------------------------------------------------------------ 

SETUP_PATH = '/setup/'

#------------------------------------------------------------------------------ 

class IndexView(TemplateView):
    template_name = 'index.html'

    # @method_decorator(login_required)    
    # @method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True))    
    # def dispatch(self, request, *args, **kwargs):
    #     return generic.View.dispatch(self, request, *args, **kwargs)

#------------------------------------------------------------------------------ 

def call_api_method(request, method):
    lg.out(2, 'views.asite.call_api_method:    %s()' % method)
    pth = request.path
    if method == 'stop':
        pth = '/'
        from twisted.internet import reactor
        reactor.callLater(0.2, api.stop)
    elif method == 'restart':
        api.restart(True)
    return HttpResponseRedirect(pth) 

#------------------------------------------------------------------------------ 

@never_cache
def LoginPoint(request, redirect_field_name=REDIRECT_FIELD_NAME,
                current_app=None, extra_context=None, ):
    ok = auth.is_identity_authenticated()
    lg.out(4, 'django.login_point is_identity_authenticated=%s' % ok)
    if not ok:
        return HttpResponseRedirect(SETUP_PATH)
    # if installer.IsExist() and installer.A().state == 'DONE':
        # return HttpResponseRedirect(SETUP_PATH)
    user = authenticate(
        username=auth.username(), 
        password=auth.password())
    lg.out(4, '    authenticate user is %s' % user)
    if user is not None:
        if not user.is_active:
            lg.out(4, '    user not active')
            logout(request)
            return HttpResponseRedirect(SETUP_PATH)
    else:
        newuser = User.objects.create_user(
            auth.username(),
            password=auth.password())
        newuser.save()
        user = authenticate(
            username=auth.username(), 
            password=auth.password())
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
def LogoutPoint(request, redirect_field_name=REDIRECT_FIELD_NAME,
                current_app=None, extra_context=None, ):
    lg.out(4, 'django.logout_point')
    logout(request)
    redirect_to = request.POST.get(redirect_field_name,
                                   request.GET.get(redirect_field_name, ''))
    if not is_safe_url(url=redirect_to, host=request.get_host()):
        redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)
    return HttpResponseRedirect(redirect_to)

#------------------------------------------------------------------------------ 

class RepaintFlagView(View):
    def get(self, request):
        result = control.get_update_flag()
        if result is True:
            control.set_updated()
        return HttpResponse('%s' % str(result))
    
    