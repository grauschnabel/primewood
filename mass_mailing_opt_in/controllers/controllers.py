# -*- coding: utf-8 -*-
from odoo import http

class MassMailingOptIn(http.Controller):
    @http.route('/mail/mailing/subscribe/<string:validation_key>', website=True, auth='public')
    def index(self, validation_key, **kw):
        contact = http.request.env['mail.mass_mailing.contact'].sudo().search([('validation_key', '=', validation_key)])
        #contact = http.request.env['mail.mass_mailing.contact'].sudo().browse(contact_ids[0])
        if not contact:
            return http.request.render('mass_mailing_opt_in.contact_not_found')
        contact.opt_out = False
        return http.request.render('mass_mailing_opt_in.validated',
                                   {'contact': contact})
