#!/usr/bin/env python
"""Build a real, signed `.pkpass` so the design can be opened in Wallet.

`preview-wallet-pass.py` draws a picture of the pass; this makes the pass.  It
builds the same `EventTicket` Indico builds, paints it with `wallet_pass.styled`
exactly as the plugin does, signs it, and writes a file you can open.

That is the only way to see what Wallet will really render: iOS refuses an
unsigned pass, in the Simulator as much as on a phone, so no drawing can stand
in for one.  Deploying the plugin is *not* required -- the certificate is.

    pip install wallet-py3k cryptography
    python scripts/sign-preview-pass.py \\
        --certificate ~/pass-cert.pem --key ~/pass-key.pem --password secret

Then open the file it writes:

* **iPhone** -- AirDrop it to yourself. The surest route, and the real thing.
* **Simulator** -- drag the file onto a booted simulator window.
* **Mac** -- open it, if this machine's Wallet accepts passes.

**The key never leaves your machine and is never written anywhere.** Both are
read straight from the paths you give and handed to the signer. Where to find
them: the same PEM blocks configured on the Indico category, under Apple Wallet,
or the Pass Type ID certificate from your Apple Developer account.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7
from wallet.models import Barcode, BarcodeFormat, EventTicket, Pass


sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap

ROOT = _bootstrap.ROOT

from indico_stsa.wallet_pass import refined, styled

#: Apple's intermediate.  Indico ships a copy; this uses that one rather than
#: asking for a second, so the signature matches what the server would produce.
#: Pinned to a release rather than `master` so the same command fetches the
#: same bytes next year.  A wrong or tampered certificate here cannot produce a
#: pass Wallet accepts, so the failure mode is a refused preview, not a bad one.
WWDR_URL = ('https://raw.githubusercontent.com/indico/indico/v3.3.13/'
            'indico/modules/events/registration/wallets/apple-wwdr.pem')


class PreviewPass(Pass):
    """`wallet.models.Pass`, signed the way Indico signs.

    The library shells out to `openssl smime` and wants the certificate and key
    as *file paths*; `IndicoPass` replaces that with `cryptography`, taking a
    loaded certificate and the key as PEM text.  This repeats that override
    verbatim, for the reason the whole script exists: a preview signed
    differently from production is a preview of something else.
    """

    def _createSignature(self, manifest, certificate, key, wwdr_certificate, password):
        private_key = serialization.load_pem_private_key(key.encode(), password=(password.encode() or None))
        wwdr_cert = x509.load_pem_x509_certificate(Path(wwdr_certificate).read_bytes())
        return (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(manifest)
            .add_signer(certificate, private_key, hashes.SHA256())
            .add_certificate(wwdr_cert)
            .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])
        )


def build(title, date, venue, name, email, *, cert_details):
    """The front fields core writes, in its order, plus the back fields the
    refinement reads from -- enough for the pass to be the one a member gets."""
    ticket = EventTicket()
    ticket.addPrimaryField('event-title', title, 'Event')
    ticket.addSecondaryField('event-date', date, 'Date')
    ticket.addSecondaryField('event-venue', venue, 'Venue')
    ticket.addAuxiliaryField('registration-name', name, 'Name')
    ticket.addAuxiliaryField('registration-email', email, 'Email')
    ticket.addBackField('back-registration-email', email, 'Email')
    ticket.addBackField('back-ticket-number', '#1042', 'Ticket number')

    # The same pair the plugin applies, in the same order, so this previews the
    # pass a member gets rather than a near relative of it.
    refined(ticket)

    passfile = PreviewPass(ticket,
                           passTypeIdentifier=cert_details['UID'],
                           organizationName=cert_details['O'],
                           teamIdentifier=cert_details['OU'])
    passfile.serialNumber = 'stsa-design-preview'
    passfile.description = f'{title} — design preview'
    # Not a real check-in code: this pass is for looking at, and one that
    # scanned would eventually be scanned at a door.
    passfile.barcode = Barcode(message='stsa-design-preview', format=BarcodeFormat.QR)

    return styled(passfile)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--certificate', type=Path, required=True, help='Pass Type ID certificate, PEM')
    parser.add_argument('--key', type=Path, required=True, help='its private key, PEM')
    parser.add_argument('--password', default='', help='the key password, if it has one')
    parser.add_argument('--wwdr', type=Path, help="Apple's WWDR intermediate, PEM (downloaded if omitted)")
    parser.add_argument('--out', type=Path, default=ROOT / 'preview' / 'wallet-pass.pkpass')
    parser.add_argument('--title', default='2026 STSA Boba Chat')
    parser.add_argument('--date', default='30 Aug 2026, 13:00')
    parser.add_argument('--venue', default='Wushiland Boba')
    parser.add_argument('--name', default='楊晨諺')
    parser.add_argument('--email', default='member@u.nus.edu')
    # For trying a palette before committing one to `constants.py`. Omitted,
    # the pass is exactly what the plugin would issue.
    parser.add_argument('--background')
    parser.add_argument('--foreground')
    parser.add_argument('--label')
    args = parser.parse_args()

    certificate = x509.load_pem_x509_certificate(args.certificate.read_bytes())
    details = dict(part.split('=', 1) for part in certificate.subject.rfc4514_string().split(','))

    wwdr = args.wwdr
    if wwdr is None:
        wwdr = ROOT / 'preview' / 'apple-wwdr.pem'
        wwdr.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(WWDR_URL, wwdr)

    passfile = build(args.title, args.date, args.venue, args.name, args.email, cert_details=details)

    for attribute, override in (('backgroundColor', args.background),
                                ('foregroundColor', args.foreground),
                                ('labelColor', args.label)):
        if override:
            setattr(passfile, attribute, override)

    # `create` hands back the stream it wrote into, positioned at the end --
    # reading without rewinding yields an empty file, which unzip reports as a
    # corrupt archive rather than an empty one. Indico seeks it too.
    archive = passfile.create(certificate, args.key.read_text(), str(wwdr), args.password)
    archive.seek(0)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(archive.read())

    print(f'Wrote {args.out}')
    print('AirDrop it to your phone, or drag it onto a booted simulator, to see it in Wallet.')


if __name__ == '__main__':
    main()
