# -*- coding: utf-8 -*-

import logging
import os
from tempfile import NamedTemporaryFile
import urlparse
from odoo import models, fields, api, exceptions, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import config

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import OpenSSL
import time

from acme import client
from acme import messages
from acme import jose
from acme import challenges

import requests
import json

# DIRECTORY_URL = 'https://acme-staging.api.letsencrypt.org/directory' # staging
DIRECTORY_URL = 'https://acme-v01.api.letsencrypt.org/directory' # production
KEY_LENGTH = 4096
_logger = logging.getLogger(__name__)

def get_challenge_dir():
    p = os.path.join(config.options.get('data_dir'), 'letsencrypt', 'acme-challenge')
    if not os.path.exists(p):
        os.makedirs(p)
    return p

class flynn_odoo_letsencrypt(models.Model):
    """Flynn odoo model.  This holds the private key and certificate for different domains."""
    _name = 'flynn_odoo_letsencrypt.flynn_odoo_letsencrypt'

    def _compute_domain_name(self):
        return urlparse.urlparse(self.env['ir.config_parameter'].get_param('web.base.url')).netloc

    name = fields.Char(string="Domain", default=_compute_domain_name, required=True, index=True, help="The domain you are hosting your odoo installation.")
    key = fields.Text(string="TLS private key")
    cert = fields.Text(string="TLS public certificate")
    tos = fields.Boolean(string="Accept Terms of Service", default=False, readonly=True)
    tos_text = fields.Text(string="Let's encrypt's terms of service", readonly=True, default="Will be requested by registration.")

    dom_verified = fields.Boolean(string="Domain verified", default=False, readonly=True)
    dom_key = fields.Text(string="Domain private key")
    dom_csr = fields.Text(string="Certificate signing request")
    expires = fields.Date(string="Expire date", readonly=True)

    flynn_controller_url = fields.Char(string="Flynn controller url", help="Like https://controller.$CLUSTER_DOMAIN, see `flynn cluster`")
    flynn_auth_key = fields.Char(string="Flynn auth key", help="The value of `flynn -a controller env get AUTH_KEY`")
    flynn_app = fields.Char(string="Flynn application", help="The name of the app you want to install the certificate.")
    flynn_route_id = fields.Char(string="Flynn route ID", help="The ID of the route to add the certificate.  See `flynn -a yourapp route`, use the full string like 'http/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX'")
    flynn_cert = fields.Text(string="Flynn ca-cert", help="May be found in ~/.flynn/ca-certs/. Paste content here.")

    challenge_path = fields.Char("Challenge Path", index=True)
    challenge_validation = fields.Char("Challenge Validation")

    state = fields.Selection([
        ('priv_key', "Generate Key"),
        ('register', "Register (accept TOS)"),
        ('cert', "Get Certificate"),
        ('flynn', "Install to Flynn"),
        ('update', "Update")
    ], default="priv_key")

    @api.one
    def action_generate_key(self):
        """Generates the private account key."""
        if self.key:
            self.state = 'register'
            return self.key
        _logger.info('generating rsa account key')
        self._generate_key()

        if self.key:
            self.state = 'register'

        return self.key

    def _generate_key(self):
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=KEY_LENGTH,
            backend=default_backend())
        self.key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        return self.key

    @api.one
    def action_register(self):
        if not self.key:
            self._generate_key
        k = self._deserialize_key(self.key)

        acme = client.Client(DIRECTORY_URL, k)
        regr = acme.register()
        self.tos_text = regr.terms_of_service
        acme.agree_to_tos(regr)
        self.tos = True

        self.state = "cert"
        return self.tos

    @api.one
    def action_install(self):
        if not self.dom_key:
            pkey = OpenSSL.crypto.PKey()
            pkey.generate_key(OpenSSL.crypto.TYPE_RSA, 4096)
            self.dom_key = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, pkey)
        if not self.dom_csr:
            csr = self._gen_csr()
            self.dom_csr = OpenSSL.crypto.dump_certificate_request(OpenSSL.crypto.FILETYPE_PEM, csr)

        return self._update()

    @api.one
    def action_flynn(self):
        ret = self._update_flynn()

        if ret:
            self.state = 'update'
        else:
            self.state = 'flynn'

    @api.one
    def action_update(self):
        self._update()
        self._update_flynn()

    def _update(self):
        if not self.dom_key or not self.dom_csr:
            self.state = 'cert'
            return
        if not self.key:
            self.state = 'priv_key'
            return

        k = self._deserialize_key(self.key)
        acme = client.Client(DIRECTORY_URL, k)

        authzr = acme.request_challenges(
            identifier=messages.Identifier(typ=messages.IDENTIFIER_FQDN, value=self.name))
        authzr, authzr_response = acme.poll(authzr)

        challb = self._supported_challb(authzr)
        if not challb:
            _logger.warning(_("Didn't find any http01 challenge. Just try again."))
            _logger.warning(authzr)
            _logger.warning(authzr_response)
            raise exceptions.Warning(_("Didn't find any http01 challenge. Just try again."))
        response, self.challenge_validation = challb.response_and_validation(k)
        self.challenge_path = challb.path.split('/')[-1]

        _logger.info("Need to response %s on url %s", self.challenge_validation, self.challenge_path)

        # write data to file, because it seems that the data is not written to the database bevor
        # the controller requests it.  So the controller loads it from the file:
        challenge_file = os.path.join(get_challenge_dir(), self.challenge_path)
        f = open(challenge_file, 'w')
        f.write(self.challenge_validation)
        _logger.info("saved %s to '%s'", self.challenge_validation, challenge_file)

        self.dom_verified = response.simple_verify(
            challb.chall, self.name, acme.key.public_key())
        f.close()

        if not self.dom_verified:
            _logger.warning('%s was not successfully self-verified. '
                           'CA is likely to fail as well!', self.name)
            return -1
        else:
            _logger.info('%s was successfully self-verified', self.name)

        # os.unlink(challenge_file)
        # _logger.info("unlinked %s", challenge_file)

        acme.answer_challenge(challb, response)

        csr = OpenSSL.crypto.load_certificate_request(OpenSSL.crypto.FILETYPE_PEM, self.dom_csr)

        certr = acme.request_issuance(jose.util.ComparableX509(csr), (authzr,))

        self.cert = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, certr.body)
        if self.cert:
            expire_time = time.strptime(certr.body.get_notAfter(), "%Y%m%d%H%M%SZ")
            self.expires = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT, expire_time)
            self.state = 'flynn'

        return self.cert

    def _gen_csr(self, sig_hash='sha256'):
        pkey = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, self.dom_key)
        req = OpenSSL.crypto.X509Req()
        req.add_extensions([
            OpenSSL.crypto.X509Extension(
                b'subjectAltName',
                critical=False,
                value=b'DNS:' + str(self.name))]
            )
        req.set_pubkey(pkey)
        req.set_version(2)
        req.sign(pkey, sig_hash)
        return req

    def _deserialize_key(self, k):
        return jose.JWKRSA(key=serialization.load_pem_private_key(
            str(k),
            password=None,
            backend=default_backend()
        ))

    def _supported_challb(self, authorization):
        """Find supported challenge body.
        This plugin supports only `http-01`, so CA must offer it as a
        single-element combo. If this is not the case this function returns
        `None`self.
        Returns:
        `acme.messages.ChallengeBody` with `http-01` challenge or `None`.

        This was stolen from https://github.com/kuba/simp_le/blob/master/simp_le.py and adjusted to this needs.
        """
        for combo in authorization.body.combinations:
            first_challb = authorization.body.challenges[combo[0]]
            if len(combo) == 1 and isinstance(
                    first_challb.chall, challenges.HTTP01):
                return first_challb
        return None

    def _update_flynn(self):
        if not self.cert:
            _logger.warning("No certificate found")
            self.state = 'cert'
            return None
        if not self.flynn_auth_key or not self.flynn_app or not self.flynn_controller_url or not self.flynn_cert:
            _logger.warning("not all flynn vars set")
            raise exceptions.Warning(_("You need to set all variables first."))

        # cert must be in a file:
        f = NamedTemporaryFile()
        f.write(self.flynn_cert)
        f.seek(0)

        url = self.flynn_controller_url + "/apps/" + self.flynn_app + "/routes/" + self.flynn_route_id
        res = requests.get(url, auth=('', self.flynn_auth_key), verify=f.name)

        if res.status_code != requests.codes.ok:
            _logger.warning(_("Got bad status: %d on GET %s"% (res.status_code, res.url)))
            if res.status_code == 401:
                raise exceptions.Warning(_("Got 401 unauthorized on your flynn cluster."))
            else:
                raise exceptions.Warning(_("Got bad status: %d GET on %s"% (res.status_code, res.url)))

        data = res.json()
        data['certificate'] = {
            'key': self.dom_key,
            'cert': self.cert
        }

        res = requests.put(url, auth=('', self.flynn_auth_key), data=json.dumps(data), verify=f.name)

        # this will also remove the file:
        f.close()

        if res.status_code != requests.codes.ok:
            _logger.warning(_("Got bad status: %d PUT on %s"% (res.status_code, res.url)))
            raise exceptions.Warning(_("Got bad status: %d on PUT %s"% (res.status_code, res.url)))

        return res
