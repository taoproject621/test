# -*- coding: utf-8 -*-
{
    'name': "Website UPS Shipping",
    'description': "UPS services",
    'category': 'Operations/Inventory/Delivery',
    'version': '1.0',
    'depends': ['delivery'],
    'data': [
        'data/delivery_ups_data.xml',
        'views/delivery_ups_view.xml',
        'views/res_config_settings_views.xml',
    ],
    'uninstall_hook': 'uninstall_hook',
}
