#!/usr/bin/env python
"""Vendor Scalar's API reference into the plugin, pinned and checked.

    python scripts/update-scalar.py 1.76.0

The API reference page serves one JavaScript file, and it is the plugin's own
copy rather than a CDN's: the page is for administrators, it should keep
working on a server that cannot reach the internet, and a script loaded from
somebody else's domain into a page that is signed in as an administrator is the
wrong thing to depend on.  The file is `dist/browser/standalone.js` of the
`@scalar/api-reference` package on npm -- the build made for a ``<script>`` tag.

What this checks: the npm registry says what the tarball's SHA-512 is, and the
tarball is refused if it is anything else.  What it records, in
`indico_stsa/vendor/scalar/scalar.json`, is that integrity string and the
SHA-256 of the file taken out of it, which `tests/test_vendor.py` compares the
committed file against -- so a file that was edited, or mangled by a line-ending
conversion, fails a test rather than shipping.

Nothing is unpacked but the one file; the tarball is read member by member and
never extracted to disk.
"""

import base64
import hashlib
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path


PACKAGE = '@scalar/api-reference'
REGISTRY = 'https://registry.npmjs.org'
LICENSE_URL = 'https://raw.githubusercontent.com/scalar/scalar/main/LICENSE'
MEMBER = 'package/dist/browser/standalone.js'
TARGET = Path(__file__).resolve().parent.parent / 'indico_stsa' / 'vendor' / 'scalar'


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:  # ruff: ignore[suspicious-url-open-usage]
        return response.read()


def main(version):
    metadata = json.loads(fetch(f'{REGISTRY}/{PACKAGE}/{version}'))
    tarball_url, integrity = metadata['dist']['tarball'], metadata['dist']['integrity']
    if not tarball_url.startswith(f'{REGISTRY}/'):
        sys.exit(f'the registry points at {tarball_url}, which is not the registry')
    algorithm, expected = integrity.split('-', 1)
    if algorithm != 'sha512':
        sys.exit(f'expected a sha512 integrity, got {integrity}')

    tarball = fetch(tarball_url)
    actual = base64.b64encode(hashlib.sha512(tarball).digest()).decode()
    if actual != expected:
        sys.exit(f'the tarball does not match the registry: {actual} != {expected}')

    with tarfile.open(fileobj=io.BytesIO(tarball), mode='r:gz') as archive:
        member = archive.extractfile(MEMBER)
        if member is None:
            sys.exit(f'{MEMBER} is not in the package any more')
        script = member.read()
    if b'\r' in script:
        sys.exit('the file has carriage returns in it, which a text checkout would rewrite')

    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / 'standalone.js').write_bytes(script)
    (TARGET / 'LICENSE').write_bytes(fetch(LICENSE_URL))
    manifest = {
        'package': PACKAGE,
        'version': version,
        'integrity': integrity,
        'file': 'standalone.js',
        'sha256': hashlib.sha256(script).hexdigest(),
    }
    (TARGET / 'scalar.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'{PACKAGE}@{version}: {len(script):,} bytes, sha256 {manifest["sha256"]}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
