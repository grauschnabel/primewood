# -*- coding: utf-8 -*-

from odoo import models, fields
from odoo.tools.translate import html_translate

class PrimewoodBlogPost(models.Model):
    _inherit = "blog.post"

    # switch to html on teaser_manual
    teaser_manual = fields.Html('Teaser Content', default='<p><b>Teaser</b> is Mandatory here.', translate=html_translate, sanitize=True)

    
