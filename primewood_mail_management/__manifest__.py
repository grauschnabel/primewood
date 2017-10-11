# -*- coding: utf-8 -*-
{
    'name': "Primewood Mail Management",

    'summary': """
    Extends standard mail things for primewood.""",

    'description': """
        - Extends account.invoice to handle incoming email.
        - Rewrites some templates.
    """,

    'author': "Martin Kaffanke m.kaffanke@primewood.at",
    'website': "https://www.primewood.at/",
    'category': 'Administration',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'mail',
        'account',
        'email_template_qweb',
    ],

    # always loaded
    'data': [
        'views/email_templates_qweb.xml',
        'data/account_email_templates.xml',
        'data/mail_email_templates.xml',
    ],
}
