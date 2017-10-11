# -*- coding: utf-8 -*-

from odoo import models, fields, api
import re

class PrimewoodAccountInvoice(models.Model):
    _inherit = "account.invoice"

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """ Overrides mail_thread message_new that is called by the mailgateway
            through message_process.
            This override updates the document according to the email.
        """
        # remove default author when going through the mail gateway. Indeed we
        # do not want to explicitly set user_id to False; however we do not
        # want the gateway user to be responsible if no other responsible is
        # found.
        self = self.with_context({'default_user_id': False, 'default_type': 'in_invoice', 'type': 'in_invoice', 'journal_type': 'purchase'})
        
        if custom_values is None:
            custom_values = {}
        defaults = {
            'name':  msg_dict.get('subject') or _("No Subject"),
            'date_invoice': msg_dict.get('date') or False,
            #'email_from': msg_dict.get('from'),
            #'email_cc': msg_dict.get('cc'),
            'partner_id': msg_dict.get('author_id', False),
            # 'company_id': env['res.company']._company_default_get('account.invoice'),
            # 'account_id': self._default_account(),
            # 'currency_id': self._default_currency(),
            # 'journal_id': self._default_journal(),
        }

        if not defaults['partner_id']:
            # create partner
            expression = re.compile(r"<?(\S+@[\w.]+)>?")
            email_address = expression.findall(msg_dict.get('from'))[0]
            defaults['partner_id'] = self.env['res.partner'].with_context({'type': 'contact'}).create({'name': msg_dict.get('from'), 'email': email_address}).id

        defaults.update(custom_values)
        return super(PrimewoodAccountInvoice, self).message_new(msg_dict, custom_values=defaults)

