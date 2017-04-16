# -*- coding: utf-8 -*-
from odoo import http
import os.path
from ..models.models import get_challenge_dir

class FlynnOdooLetsencrypt(http.Controller):
    @http.route('/.well-known/acme-challenge/<path>', auth='public', website=True)
    def index(self, path, **kw):
        p = os.path.join(get_challenge_dir(), path)
        if not os.path.exists(p):
            return "file not found: %s"% p
        f = open(p)
        s = f.read()
        f.close()
        if s:
            return s
        else:
            return "not found"
#        o = http.request.env['flynn_odoo_letsencrypt.flynn_odoo_letsencrypt'].search([['challenge_path', '=', path]])
#        if len(o) < 1:
#            return "not found"
#        return o[0].challenge_validation
