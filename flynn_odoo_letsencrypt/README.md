# flynn_odoo_letsencrypt

This implements the letsencrypt ssl to odoo if odoo is installed on a flynn
instance (maybe using flynn-odoo).

## Features
- Request and install a certificate from letsencrypt on the flynn application.
- Auto renew of certificates about one month before it gets outdated.

## Planed features:
- Redirect all requests to odoo from http to https.

## Install

This covers the installation on a flynn-odoo instance, see
[flynn-odoo](https://github.com/grauschnabel/flynn-odoo) for details.

Put flynn_odoo_letsencrypt into the `addons` directory of flynn-odoo.

You need to insert

`acme==0.13.0`

in your `requirements.txt`

Push your repo to your flynn app.  Install letsencrypt from the Apps.

## Usage

You find a menu called Let's Encrypt in the settings.

Just go through the process and come back for issues if it doen't work. :)

