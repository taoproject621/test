from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    google_maps_view_api_key = fields.Char(
        string='Google Maps View Api Key',
        config_parameter='web_google_auto_form.api_key_geocode')
