from django.views.generic import View
from django.http import HttpResponse

#------------------------------------------------------------------------------ 

from web import control

#------------------------------------------------------------------------------ 

class UpdateFlagView(View):
    def get(self, request):
        result = str(control.get_update_flag())
        control.set_updated()
        return HttpResponse('%s' % result)