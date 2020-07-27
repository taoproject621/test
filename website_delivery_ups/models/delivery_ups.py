# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import pdf

from .ups_request import UPSRequest, Package


class ProviderUPS(models.Model):
    _inherit = 'delivery.carrier'

    def _get_ups_service_types(self):
        return [
            ('03', 'UPS Ground'),
            ('11', 'UPS Standard'),
            ('01', 'UPS Next Day'),
            ('14', 'UPS Next Day AM'),
            ('13', 'UPS Next Day Air Saver'),
            ('02', 'UPS 2nd Day'),
            ('59', 'UPS 2nd Day AM'),
            ('12', 'UPS 3-day Select'),
            ('65', 'UPS Saver'),
            ('07', 'UPS Worldwide Express'),
            ('08', 'UPS Worldwide Expedited'),
            ('54', 'UPS Worldwide Express Plus'),
            ('96', 'UPS Worldwide Express Freight')
        ]

    delivery_type = fields.Selection(selection_add=[('ups', "UPS")])

    ups_username = fields.Char(string='UPS Username', groups="base.group_system")
    ups_passwd = fields.Char(string='UPS Password', groups="base.group_system")
    ups_shipper_number = fields.Char(string='UPS Shipper Number', groups="base.group_system")
    ups_access_number = fields.Char(string='UPS AccessLicenseNumber', groups="base.group_system")
    ups_default_packaging_id = fields.Many2one('product.packaging', string='UPS Default Packaging Type')
    ups_default_service_type = fields.Selection(_get_ups_service_types, string="UPS Service Type", default='03')
    ups_duty_payment = fields.Selection([('SENDER', 'Sender'), ('RECIPIENT', 'Recipient')], required=True,
                                        default="RECIPIENT")
    ups_package_weight_unit = fields.Selection([('LBS', 'Pounds'), ('KGS', 'Kilograms')], default='LBS')
    ups_package_dimension_unit = fields.Selection([('IN', 'Inches'), ('CM', 'Centimeters')],
                                                  string="Units for UPS Package Size", default='IN')
    ups_label_file_type = fields.Selection([('GIF', 'PDF'),
                                            ('ZPL', 'ZPL'),
                                            ('EPL', 'EPL'),
                                            ('SPL', 'SPL')],
                                           string="UPS Label File Type", default='GIF')
    ups_bill_my_account = fields.Boolean(string='Bill My Account',
                                         help="If checked, ecommerce users will be prompted their UPS account number\n"
                                              "and delivery fees will be charged on it.")
    ups_cod = fields.Boolean(string='Collect on Delivery',
                             help='This value added service enables UPS to collect the payment of the shipment from your customer.')
    ups_saturday_delivery = fields.Boolean(string='UPS Saturday Delivery',
                                           help='This value added service will allow you to ship the package on saturday also.')
    ups_cod_funds_code = fields.Selection(selection=[
        ('0', "Check, Cashier's Check or MoneyOrder"),
        ('8', "Cashier's Check or MoneyOrder"),
    ], string='COD Funding Option', default='0')

    def _compute_can_generate_return(self):
        super(ProviderUPS, self)._compute_can_generate_return()
        for carrier in self:
            if carrier.delivery_type == 'ups':
                carrier.can_generate_return = True

    @api.onchange('ups_default_service_type')
    def on_change_service_type(self):
        self.ups_cod = False
        self.ups_saturday_delivery = False

    def ups_rate_shipment(self, order):
        superself = self.sudo()
        srm = UPSRequest(self.log_xml, superself.ups_username, superself.ups_passwd, superself.ups_shipper_number,
                         superself.ups_access_number, self.prod_environment)
        ResCurrency = self.env['res.currency']
        max_weight = self.ups_default_packaging_id.max_weight
        packages = []
        total_qty = 0
        total_weight = 0
        for line in order.order_line.filtered(lambda line: not line.is_delivery and not line.display_type):
            total_qty += line.product_uom_qty
            total_weight += line.product_id.weight * line.product_qty

        if max_weight and total_weight > max_weight:
            total_package = int(total_weight / max_weight)
            last_package_weight = total_weight % max_weight

            for seq in range(total_package):
                packages.append(Package(self, max_weight))
            if last_package_weight:
                packages.append(Package(self, last_package_weight))
        else:
            packages.append(Package(self, total_weight))

        shipment_info = {
        }

        if self.ups_cod:
            cod_info = {
                'currency': order.partner_id.country_id.currency_id.name,
                'monetary_value': order.amount_total,
                'funds_code': self.ups_cod_funds_code,
            }
        else:
            cod_info = None

        check_value = srm.check_required_value(order.company_id.partner_id, order.warehouse_id.partner_id,
                                               order.partner_shipping_id, order=order)
        if check_value:
            return {'success': False,
                    'price': 0.0,
                    'error_message': check_value,
                    'warning_message': False}

        ups_service_type = order.ups_service_type or self.ups_default_service_type
        result = srm.get_shipping_price(
            shipment_info=shipment_info,
            packages=packages,
            shipper=order.company_id.partner_id,
            ship_from=order.warehouse_id.partner_id,
            ship_to=order.partner_shipping_id,
            packaging_type=self.ups_default_packaging_id.shipper_package_code,
            service_type=ups_service_type,
            saturday_delivery=self.ups_saturday_delivery, cod_info=cod_info)

        if result.get('error_message'):
            return {'success': False,
                    'price': 0.0,
                    'error_message': _('Error:\n%s') % result['error_message'],
                    'warning_message': False}

        if order.currency_id.name == result['currency_code']:
            price = float(result['price'])
        else:
            quote_currency = ResCurrency.search([('name', '=', result['currency_code'])], limit=1)
            price = quote_currency._convert(
                float(result['price']), order.currency_id, order.company_id, order.date_order or fields.Date.today())

        if self.ups_bill_my_account and order.ups_carrier_account:
            # Don't show delivery amount, if ups bill my account option is true
            price = 0.0

        return {'success': True,
                'price': price,
                'error_message': False,
                'warning_message': False}

    def _ups_get_default_custom_package_code(self):
        return '02'

    def _ups_convert_weight(self, weight, unit='KGS'):
        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        if unit == 'KGS':
            return weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_kgm'), round=False)
        elif unit == 'LBS':
            return weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_lb'), round=False)
        else:
            raise ValueError
