# -*- coding: utf-8 -*-
# License AGPL-3
from odoo import http
from odoo.http import request
from odoo.tools.safe_eval import safe_eval


class WebsiteGoogleAddressForm(http.Controller):

    @http.route('/my/account/get_country', type='json', auth='public')
    def get_country(self, country):
        country_id = request.env['res.country'].sudo().search([
            '|', ('code', '=', country), ('name', '=', country)])
        return country_id and country_id.id or False

    @http.route('/my/account/get_country_state', type='json', auth='public')
    def get_country_state(self, country, state):
        country_id = request.env['res.country'].sudo().search([
            '|', ('code', '=', country), ('name', '=', country)])
        state_id = request.env['res.country.state'].sudo().search([
            '&', '|', ('code', '=', state), ('name', '=', state),
            ('country_id', '=', country_id.id)])
        return state_id and state_id.id or False

