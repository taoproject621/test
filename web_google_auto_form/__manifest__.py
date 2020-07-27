# -*- coding: utf-8 -*-
{
    'name': "Web Google Map Form",

    'summary': """""",

    'description': """
        
    """,

    'author': "",
    'website': "",
    'category': 'website',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['website_sale'],

    # always loaded
    'data': [
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
