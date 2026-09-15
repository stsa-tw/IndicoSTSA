#!/usr/bin/env python
"""Build a real, signed `.pkpass` so the design can be opened in Wallet.

It builds the pass `wallet_pass.styled` would hand back for a registration --
the same call the plugin makes, from the same Pass Designer template -- signs it
the way Indico signs, and writes a file you can open.

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
from wallet.models import EventTicket, Pass


sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap

ROOT = _bootstrap.ROOT

from indico_stsa.wallet_pass import PassTicket, styled

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


def build(ticket, *, cert_details):
    """The pass the plugin would issue for `ticket`.

    Core's own `EventTicket` fields are not constructed here, deliberately: the
    template supersedes every one of them, so building them would prove only
    that they are discarded.  What core really contributes is the identity, read
    off the certificate exactly as `AppleWalletManager` reads it -- and Wallet
    checks those three against the signature, so a preview that invented them
    would be refused for a reason that has nothing to do with the design.
    """
    passfile = PreviewPass(EventTicket(),
                           passTypeIdentifier=cert_details['UID'],
                           organizationName=cert_details['O'],
                           teamIdentifier=cert_details['OU'])
    passfile.serialNumber = 'stsa-design-preview'
    return styled(passfile, ticket)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--certificate', type=Path, required=True, help='Pass Type ID certificate, PEM')
    parser.add_argument('--key', type=Path, required=True, help='its private key, PEM')
    parser.add_argument('--password', default='', help='the key password, if it has one')
    parser.add_argument('--wwdr', type=Path, help="Apple's WWDR intermediate, PEM (downloaded if omitted)")
    parser.add_argument('--out', type=Path, default=ROOT / 'preview' / 'wallet-pass.pkpass')
    parser.add_argument('--title', default='2026 STSA Boba Chat')
    # Real dates rather than pre-formatted text: the template's fields carry
    # `dateStyle`, so Wallet formats them for the reader's locale and a
    # already-formatted string would render as literal characters.
    parser.add_argument('--start', default='2026-08-30T13:00:00+08:00')
    parser.add_argument('--end', default='2026-08-30T15:00:00+08:00')
    parser.add_argument('--venue', default='Wushiland Boba')
    parser.add_argument('--room', default='')
    parser.add_argument('--address', default='')
    parser.add_argument('--url', default='https://event.stsa.tw/')
    parser.add_argument('--name', default='楊晨諺')
    parser.add_argument('--number', default='1042', help='registration friendly id')
    # No colour overrides: the colours are in the template now, and `styled`
    # replaces the whole of pass.json, so an attribute set afterwards would be
    # silently ignored rather than previewed.
    args = parser.parse_args()

    certificate = x509.load_pem_x509_certificate(args.certificate.read_bytes())
    details = dict(part.split('=', 1) for part in certificate.subject.rfc4514_string().split(','))

    wwdr = args.wwdr
    if wwdr is None:
        wwdr = ROOT / 'preview' / 'apple-wwdr.pem'
        wwdr.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(WWDR_URL, wwdr)

    ticket = PassTicket(
        title=args.title,
        start=args.start,
        end=args.end,
        venue=' · '.join(p for p in (args.venue, args.room) if p) or None,
        venue_name=args.venue or None,
        room_name=args.room or None,
        address=args.address or None,
        event_url=args.url,
        holder=args.name,
        friendly_id=args.number,
        # Not a real check-in code: this pass is for looking at, and one that
        # scanned would eventually be scanned at a door.
        qr_message='stsa-design-preview',
    )
    passfile = build(ticket, cert_details=details)

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
