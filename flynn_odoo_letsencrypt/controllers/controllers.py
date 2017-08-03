# -*- coding: utf-8 -*-
from odoo import http
import os.path
from ..models.models import Challenge

class FlynnOdooLetsencrypt(http.Controller):
    @http.route('/.well-known/acme-challenge/<path>', auth='public', website=True)
    def index(self, path, **kw):
        c = Challenge()
        return c.validate(path)
