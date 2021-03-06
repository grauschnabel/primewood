# -*- coding: utf-8 -*-
{
    'name': "Mass Mailing OPT-IN",

    'summary': """
        Default opt out and email validation for newsletter.""",

    'description': """
    This rewrites the mass_mailing module to make it default to opt out, and opt
    in when the users klick on a link in the email to validate their email.

    This is specially for websites where user can put theirself on the list.

    **NOTE**
    
    To get the correct url in the email templates, you need to make sure set up
    'web.base.url' in your config paremters correctly. (start with https://)
    """,

    'author': "Mag. Martin Kaffanke - Primewood",
    'website': "http://www.primewood.at",

    'category': 'Marketing',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base_action_rule', 'mass_mailing', 'website'],

    # always loaded
    'data': [
        'security/mass_mailing_opt_in_security.xml',
        'data/action_rules.xml',
        'views/inherit_views.xml',
        'views/res_config_view.xml',
        'views/mail_templates.xml',
        'views/website_templates.xml',
    ],
}
