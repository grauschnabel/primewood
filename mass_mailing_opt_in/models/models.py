# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

import random, string, urlparse

from res_config import MassMailingConfiguration

_logger = logging.getLogger(__name__)

class MassMailingContact(models.Model):
    """We want the user to subscribe to the mailing list.  So he/she should get an
    Email, with a link to opt in rather than to opt out only.  This is a better way
    to cover the european laws.
    """
    _inherit = 'mail.mass_mailing.contact'

    def _default_opt_out(self):
        return (self.env['mass.mailing.config.settings'].default_get('')['group_mass_mailing_opt_in'] == 1) and True or False
    opt_out = fields.Boolean(string='Opt Out', help='The contact has chosen not to receive mails anymore from this list',
                             default=_default_opt_out)
    subscription_date = fields.Datetime(string='Subscription Date')
    def _compute_validation_key(self):
        return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(48))
    validation_key = fields.Char(string='Validation string for the email to validate.', default=_compute_validation_key)
    subscribe_to_newsletter_url = fields.Char(compute='_compute_subscribe_to_newsletter_url', string="Subscription URL")
    company_id = fields.Many2one(comodel_name='res.company', string='Get the current company to set email from', compute="_get_company")

    @api.model
    def send_validation_email(self):
        active_ids = self._context.get('active_ids')
        self._send_greeting_emails(active_ids)
        return True
            

    @api.depends('validation_key')
    def _compute_subscribe_to_newsletter_url(self):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        for record in self:
            record.subscribe_to_newsletter_url = urlparse.urljoin(
                base_url, 'mail/mailing/subscribe/%(validation_key)s' % {
                    'validation_key': record.validation_key
                }
            )

    @api.multi
    def write(self, vals):
        if 'opt_out' in vals:
            if not vals['opt_out']:
                vals['subscription_date'] = fields.Datetime.now()
        return super(MassMailingContact, self).write(vals)

    def _get_company(self):
        for record in self:
            record.company_id = self.env['res.company']._company_default_get()
            
    @api.multi
    def _send_greeting_emails(self, ids):
        template = self.env.ref('mass_mailing_opt_in.mass_mailing_opt_in_welcome_email_template')
        for i in ids:
            record = self.browse(i)
            if template and record.opt_out:
                template.send_mail(record.id, force_send=True)
            else:
                _logger.warning("No email template found to send email for newsletter subscription.")
        return True
