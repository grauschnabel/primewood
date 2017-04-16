# -*- coding: utf-8 -*-
{
    'name': "Let's encrypt for odoo as a flynn app",

    'summary': """
       Adds a letsencrypt ssl certificate to odoo.
    """,

    'description': """
      This will create a letsencrypt ssl certificate for the odoo installation.
      http will then be redirected to https requets.
      The certificate will be upgraded once a week.
    """,
    'license': "AGPL-3",

    'author': "Martin Kaffanke @ primewood.at",
    'website': "http://www.primewood.at/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Website',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],
    'installable': True,
    'auto_install': False,

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
