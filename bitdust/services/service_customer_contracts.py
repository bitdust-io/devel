#!/usr/bin/python
# service_customer_contracts.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_customer_contracts.py) is part of BitDust Software.
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
#
#
#
#
"""
..

module:: service_customer_contracts
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return CustomerContractsService()


class CustomerContractsService(LocalService):

    service_name = 'service_customer_contracts'
    config_path = 'services/customer-contracts/enabled'

    def dependent_on(self):
        return [
            'service_customer',
            'service_blockchain_id',
        ]

    def start(self):
        from twisted.internet import task  # @UnresolvedImport
        self.payment_loop = task.LoopingCall(self.on_payment_task)
        self.payment_loop.start(60*60, now=True)
        return True

    def stop(self):
        if self.payment_loop and self.payment_loop.running:
            self.payment_loop.stop()
        self.payment_loop = None
        return True

    def on_payment_task(self):
        from bitdust.customer import payment
        payment.pay_for_storage()
