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

#     @http.route('/mass_mailing_opt_in/mass_mailing_opt_in/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('mass_mailing_opt_in.listing', {
#             'root': '/mass_mailing_opt_in/mass_mailing_opt_in',
#             'objects': http.request.env['mass_mailing_opt_in.mass_mailing_opt_in'].search([]),
#         })

#     @http.route('/mass_mailing_opt_in/mass_mailing_opt_in/objects/<model("mass_mailing_opt_in.mass_mailing_opt_in"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mass_mailing_opt_in.object', {
#             'object': obj
#         })
