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
from django.views import generic

#------------------------------------------------------------------------------

from models import Customer

from lib import nameurl

#------------------------------------------------------------------------------


class CustomerView(generic.DetailView):
    template_name = 'customer.html'
    model = Customer

    def get_context_data(self, **kwargs):
        Cus = super(CustomerView, self).get_object()
        context = super(CustomerView, self).get_context_data(**kwargs)
        context['identity_id'] = nameurl.DjangoQuote(Cus.idurl)
        return context


class CustomersView(generic.ListView):
    template_name = 'customers.html'
    context_object_name = 'customers_list'

    def get_queryset(self):
        return Customer.objects.order_by('id')
