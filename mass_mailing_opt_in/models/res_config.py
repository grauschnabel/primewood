# -*- coding: utf-8 -*-

from odoo import fields, models

class MassMailingConfiguration(models.TransientModel):
    _inherit = 'mass.mailing.config.settings'
    group_mass_mailing_opt_in = fields.Selection([
        (0, 'New contacts are default opted in when created.'),
        (1, 'New contacts have to click a link in an \'Welcome Email\' to opt in to the list.  (This covers european laws.)')
    ], string="Opt-In or Opt-Out",
        implied_group="mass_mailing_opt_in.group_mass_mailing_opt_in")
