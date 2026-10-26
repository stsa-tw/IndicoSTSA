"""The API reference: Scalar, drawing this instance's OpenAPI document.

Everything on this page is for administrators and nobody else -- the document
is an inventory of every endpoint this installation has, which is not for the
public, and the page can be used to send requests as whoever is looking at it.
So there are three handlers and all of them are `RHAdminBase`: the page, the
document, and Scalar's own script.  The script is public software and no secret,
but it is served from here and not from the plugin's static folder, because
that folder is public by design and "all of it behind the administrator login"
should mean all of it.
"""

import json
from pathlib import Path

from flask import Response, send_file

from indico.core.plugins import render_plugin_template, url_for_plugin
from indico.modules.admin.controllers.base import RHAdminBase
from indico.web.rh import json_errors

from indico_stsa.api_docs import generate_spec


#: Where `scripts/update-scalar.py` puts it.  Not under `static/`: see above.
SCALAR_SCRIPT = Path(__file__).resolve().parent.parent / 'vendor' / 'scalar' / 'standalone.js'

#: What the page is allowed to do, which is run its own script and talk to this
#: server.  Indico sends no content security policy by default, and a page that
#: holds an administrator's session is a good place to have one -- and to keep
#: Scalar honest about reaching out to anybody else, which it can.
CONTENT_SECURITY_POLICY = '; '.join((
    "default-src 'none'",
    "script-src 'self'",
    # Scalar sets a great many inline styles.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
))

#: Scalar's own settings, handed over in the page.  The ones that matter are what
#: is switched *off*: it reports usage to Scalar by default, offers an AI agent
#: that talks to Scalar's servers, and loads its fonts from them.  None of that
#: belongs in an administrator's browser tab, and the policy above would block it
#: anyway -- this stops it asking.
SCALAR_CONFIGURATION = {
    'telemetry': False,
    'withDefaultFonts': False,
    'agent': {'disabled': True},
    'mcp': {'disabled': True},
    'showDeveloperTools': 'never',
    'persistAuth': False,
}


class RHSTSAAPIDocs(RHAdminBase):
    """The page itself."""

    def _process(self):
        html = render_plugin_template('api_docs.html', title='API reference',
                                      spec_url=url_for_plugin('stsa.api_docs_spec'),
                                      script_url=url_for_plugin('stsa.api_docs_scalar'),
                                      configuration=json.dumps(SCALAR_CONFIGURATION))
        response = Response(html, mimetype='text/html')
        response.headers['Content-Security-Policy'] = CONTENT_SECURITY_POLICY
        response.headers['Cache-Control'] = 'no-store'
        return response


@json_errors
class RHSTSAOpenAPI(RHAdminBase):
    """The OpenAPI document, generated for this instance as it is now."""

    def _process(self):
        # Generated on every request, as it should be: it follows the plugins
        # that are loaded, and asking for it is rare.
        response = Response(json.dumps(generate_spec(), ensure_ascii=False, separators=(',', ':')),
                            mimetype='application/json')
        response.headers['Cache-Control'] = 'no-store'
        return response


class RHSTSAScalarScript(RHAdminBase):
    """Scalar's browser bundle."""

    def _process(self):
        # Revalidated, never stored for somebody else to find: the file is the
        # same for everybody, but a shared cache holding anything this handler
        # served would defeat the point of guarding it.
        response = send_file(SCALAR_SCRIPT, mimetype='text/javascript', conditional=True, max_age=0)
        response.headers['Cache-Control'] = 'private, no-cache'
        return response
