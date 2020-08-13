# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from datetime import datetime


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_ups_service_types(self):
        return self.env['delivery.carrier']._get_ups_service_types()

    ups_carrier_account = fields.Char(string='Carrier Account', copy=False)
    ups_service_type = fields.Selection(
        _get_ups_service_types, string="UPS Service Type")
    ups_bill_my_account = fields.Boolean(
        related='carrier_id.ups_bill_my_account', readonly=True)
    arrival_date = fields.Date("Arrival Date")

    @api.onchange('carrier_id')
    def _onchange_carrier_id(self):
        self.ups_service_type = self.carrier_id.ups_default_service_type

    def _check_carrier_quotation(self, force_carrier_id=None):
        self.ensure_one()
        DeliveryCarrier = self.env['delivery.carrier']

        if self.only_services:
            self.write({'carrier_id': None})
            self._remove_delivery_line()
            return True
        else:
            # attempt to use partner's preferred carrier
            if not force_carrier_id and self.partner_shipping_id.property_delivery_carrier_id:
                force_carrier_id = self.partner_shipping_id.property_delivery_carrier_id.id

            carrier = force_carrier_id and DeliveryCarrier.browse(
                force_carrier_id) or self.carrier_id
            available_carriers = self._get_delivery_methods()
            if carrier:
                if carrier not in available_carriers:
                    carrier = DeliveryCarrier
                else:
                    # set the forced carrier at the beginning of the list to be verfied first below
                    available_carriers -= carrier
                    available_carriers = carrier + available_carriers
            if force_carrier_id or not carrier or carrier not in available_carriers:
                for delivery in available_carriers:
                    verified_carrier = delivery._match_address(
                        self.partner_shipping_id)
                    if verified_carrier:
                        carrier = delivery
                        break
                self.write({'carrier_id': carrier.id})
            self._remove_delivery_line()
            if carrier:
                res = carrier.rate_shipment(self)
                if res.get('success'):
                    self.set_delivery_line(carrier, res['price'])
                    self.delivery_rating_success = True
                    self.delivery_message = res['warning_message']
                    if res.get("arrival_date"):
                        self.arrival_date = datetime.strptime(
                            res['arrival_date'], '%Y%m%d')
                else:
                    self.set_delivery_line(carrier, 0.0)
                    self.delivery_rating_success = False
                    self.delivery_message = res['error_message']

        return bool(carrier)
