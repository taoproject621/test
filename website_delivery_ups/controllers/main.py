from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale_delivery.controllers.main import WebsiteSaleDelivery
from datetime import datetime


class WebsiteSaleDeliveryUPS(WebsiteSaleDelivery):

    @http.route(['/shop/carrier_rate_shipment'], type='json', auth='public', methods=['POST'], website=True)
    def cart_carrier_rate_shipment(self, carrier_id, **kw):
        order = request.website.sale_get_order(force_create=True)
        assert int(carrier_id) in order._get_delivery_methods(
        ).ids, "unallowed carrier"
        Monetary = request.env['ir.qweb.field.monetary']

        res = {'carrier_id': carrier_id}
        carrier = request.env['delivery.carrier'].sudo().browse(
            int(carrier_id))
        rate = carrier.rate_shipment(order)
        if rate.get('success'):
            res['status'] = True
            res['new_amount_delivery'] = Monetary.value_to_html(
                rate['price'], {'display_currency': order.currency_id})
            res['is_free_delivery'] = not bool(rate['price'])
            if rate.get("arrival_date", None):
                res['arrival_date'] = datetime.strptime(
                    rate['arrival_date'], '%Y%m%d').strftime('%Y%m%d')
            res['error_message'] = rate['warning_message']
        else:
            res['status'] = False
            res['new_amount_delivery'] = Monetary.value_to_html(
                0.0, {'display_currency': order.currency_id})
            res['error_message'] = rate['error_message']
        return res

    @http.route(['/shop/update_carrier'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def update_eshop_carrier(self, **post):
        order = request.website.sale_get_order()
        carrier_id = int(post['carrier_id'])
        if order:
            order._check_carrier_quotation(force_carrier_id=carrier_id)
        return self._update_website_sale_delivery_return(order, **post)

    def _update_website_sale_delivery_return(self, order, **post):
        Monetary = request.env['ir.qweb.field.monetary']
        carrier_id = int(post['carrier_id'])
        currency = order.currency_id
        if order:
            return {
                'status': order.delivery_rating_success,
                'error_message': order.delivery_message,
                'carrier_id': carrier_id,
                'is_free_delivery': not bool(order.amount_delivery),
                # 'arrival_date': datetime.strftime(order.arrival_date, '%Y%m%d'),
                'arrival_date': datetime.strftime(order.arrival_date,
                                                  '%Y%m%d') if order.arrival_date else order.arrival_date,
                'new_amount_delivery': Monetary.value_to_html(order.amount_delivery, {'display_currency': currency}),
                'new_amount_untaxed': Monetary.value_to_html(order.amount_untaxed, {'display_currency': currency}),
                'new_amount_tax': Monetary.value_to_html(order.amount_tax, {'display_currency': currency}),
                'new_amount_total': Monetary.value_to_html(order.amount_total, {'display_currency': currency}),
            }
        return {}
