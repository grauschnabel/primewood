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

import json
import time

from acme import client
from acme import messages
from acme import jose
from acme import challenges

import requests

# DIRECTORY_URL = 'https://acme-staging.api.letsencrypt.org/directory' # staging
DIRECTORY_URL = 'https://acme-v01.api.letsencrypt.org/directory' # production
KEY_LENGTH = 4096
_logger = logging.getLogger(__name__)

def get_challenge_dir():
    p = os.path.join(config.options.get('data_dir'), 'letsencrypt', 'acme-challenge')
    if not os.path.exists(p):
        os.makedirs(p)
    return p

class Challenge(object):

    _path = ""
    _validation = ""

    def __new__(cls, *args, **kwds):
        self = "__self__"
        if not hasattr(cls, self):
            instance = object.__new__(cls)
            instance.init(*args, **kwds)
            setattr(cls, self, instance)
        return getattr(cls, self)

    def init(self, *args, **kwds):
        pass

    def set_challenge(self, p, v):
        self._path = p
        self._validation = v

    def validate(self, p):
        if self._path == p:
            return self._validation
        return False

class flynn_odoo_letsencrypt(models.Model):
    """Flynn odoo model.  This holds the private key and certificate for different domains."""
    _name = 'flynn_odoo_letsencrypt.flynn_odoo_letsencrypt'

    def _compute_domain_name(self):
        return urlparse.urlparse(self.env['ir.config_parameter'].get_param('web.base.url')).netloc

    name = fields.Char(string="Domain", default=_compute_domain_name, required=True, index=True, help="The domain you are hosting your odoo installation.")
    key = fields.Text(string="TLS private key", copy=False)
    cert = fields.Text(string="TLS public certificate", copy=False)
    tos = fields.Boolean(string="Accept Terms of Service", default=False, readonly=True, copy=False)
    tos_text = fields.Text(string="Let's encrypt's terms of service", readonly=True, default="Will be requested by registration.", copy=False)

    dom_verified = fields.Boolean(string="Domain verified", default=False, readonly=True, copy=False)
    dom_key = fields.Text(string="Domain private key", copy=False)
    dom_csr = fields.Text(string="Certificate signing request", copy=False)
    expires = fields.Date(string="Expire date", readonly=True, copy=False)

    flynn_controller_url = fields.Char(string="Flynn controller url", help="Like https://controller.$CLUSTER_DOMAIN, see `flynn cluster`")
    flynn_auth_key = fields.Char(string="Flynn auth key", help="The value of `flynn -a controller env get AUTH_KEY`")
    flynn_app = fields.Char(string="Flynn application", help="The name of the app you want to install the certificate.")
    flynn_route_id = fields.Char(string="Flynn route ID", help="The ID of the route to add the certificate.  See `flynn -a yourapp route`, use the full string like 'http/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX'")
    flynn_cert = fields.Text(string="Flynn ca-cert", help="May be found in ~/.flynn/ca-certs/. Paste content here.")

    challenge_path = fields.Char("Challenge Path", index=True, copy=False)
    challenge_validation = fields.Char("Challenge Validation", copy=False)

    state = fields.Selection([
        ('priv_key', "Generate Key"),
        ('register', "Register (accept TOS)"),
        ('cert', "Get Certificate"),
        ('flynn', "Install to Flynn"),
        ('update', "Update")
    ], default="priv_key", copy=False)

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
        key = self._deserialize_key(self.key)

        acme = client.Client(DIRECTORY_URL, key)
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

        if self._update():
            self.state = 'flynn'

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

    @api.model
    def cron_update(self): # method of this model
        #        self.search(['expires', '<', ''])
        records = self.search([('expires', '!=', None)])
        for r in records:
            try:
                r._update()
                r._update_flynn()
                _logger.info("Updated letsencrypt certificate for %s"% r.name)
            except Exception as e:
                _logger.warning(_("Cron update failed, try manually."))
                _logger.warning(e)
                # Send message to group:
                self._send_cron_message(e)

                return False
        return True

    def _send_cron_message(self, e):
        users = self.env.ref('base.group_erp_manager').users
        for u in users:
            _logger.warning("message_post to %s" % u)
            u.message_post(subject="Flynn Cronjob failed",
                           body="Flynn cronjob failed with %s"% e)

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

        challb = self._supported_challb(authzr)
        if not challb:
            _logger.warning(_("Didn't find any http01 challenge. Just try again."))
            _logger.warning(authzr)
            raise exceptions.Warning(_("Didn't find any http01 challenge. Just try again."))
        response, self.challenge_validation = challb.response_and_validation(k)
        self.challenge_path = challb.path.split('/')[-1]

        challenge = Challenge()
        challenge.set_challenge(self.challenge_path, self.challenge_validation)

        _logger.info("Need to response %s on url %s", self.challenge_validation, self.challenge_path)

        # write data to file, because it seems that the data is not written to the database bevor
        # the controller requests it.  So the controller loads it from the file:
        #challenge_file = os.path.join(get_challenge_dir(), self.challenge_path)
        #f = open(challenge_file, 'w')
        #f.write(self.challenge_validation)
        #_logger.info("saved %s to '%s'", self.challenge_validation, challenge_file)

        #self.dom_verified = response.simple_verify(
        #    challb.chall, self.name, acme.key.public_key())
        #f.close()

        #if not self.dom_verified:
        #    _logger.warning('%s was not successfully self-verified. '
        #                   'CA is likely to fail as well!', self.name)
        #            raise exceptions.Warning(_("%s was not successfully self-verified. CA is likely to fail as well!"% self.name))
        #else:
        #    _logger.info('%s was successfully self-verified', self.name)

        # os.unlink(challenge_file)
        # _logger.info("unlinked %s", challenge_file)

        #        authzr, authzr_response = acme.poll(authzr)

        acme.answer_challenge(challb, response)

        csr = OpenSSL.crypto.load_certificate_request(OpenSSL.crypto.FILETYPE_PEM, self.dom_csr)

        certr, authzr = acme.poll_and_request_issuance(jose.util.ComparableX509(csr), (authzr,))

        self.cert = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, certr.body)
        if self.cert:
            expire_time = time.strptime(certr.body.get_notAfter(), "%Y%m%d%H%M%SZ")
            self.expires = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT, expire_time)

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
            _logger.warning("No certificate found.")
            self.state = 'cert'
            raise exceptions.Warning(_('No certificate found.'))
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
