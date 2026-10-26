"""Going through this instance's URL map for the endpoints `indico_stsa.openapi` writes down.

The other half of `indico_stsa.openapi`: everything here needs a running Indico
-- its URL map, its handler classes, its settings -- so none of it is
unit-tested; see the layering note in CLAUDE.md.

There is no registry of Indico's API endpoints to read, so an endpoint is found
by what it looks like: a handler mounted under an ``/api/`` path, or one that
asks for an OAuth scope of its own, which only the endpoints meant to be called
from outside do.  That is a heuristic and it is not perfect: the pages that
manage the classic API's keys live under ``/api/`` too, and are left out by name.
"""

import inspect
from contextlib import suppress

from flask import current_app

from indico import __version__ as indico_version
from indico.core.config import config
from indico.core.logger import Logger
from indico.core.oauth.scopes import SCOPES
from indico.modules.core.settings import core_settings
from indico.web.flask.util import url_for

from indico_stsa.openapi import Arguments, Operation, build_spec, method_rank


logger = Logger.get('plugin.stsa')

#: Blueprints whose ``/api/`` URLs are HTML pages and forms, not an API.
NOT_AN_API = frozenset({'api'})

#: How many wrappers to look through for the handler.  `make_view_func` makes one
#: and `@cors` adds a second; anything deeper is not a handler.
_MAX_UNWRAP = 4

DESCRIPTION = '''\
This document is **generated from the URL map of this Indico instance** by the STSA plugin, so it \
lists exactly the endpoints this installation has -- the plugins' included -- at the version it is \
running.

### Reading it

* **Integration APIs** have an OAuth scope of their own. Those are the endpoints meant to be called \
from outside Indico.
* **Everything else** is what Indico's own pages call. A token can use these too, with the \
`read:everything` scope (`full:everything` for anything but a `GET`), but nothing promises they \
stay as they are from one release to the next.
* Where a handler parses its arguments with a schema, they are described; where it reads them by \
hand and says nothing about it, they are not.

### What it does not say

* **What an endpoint returns.** Indico does not write that down anywhere. A response is described \
only where the handler declares one.
* **Whether an endpoint also answers without credentials.** That is decided inside the handler.
* **The classic HTTP API** -- the `/export/...` URLs -- is not listed. It is built from a different \
mechanism, and has its own documentation: https://docs.getindico.io/en/stable/http-api/
'''


def generate_spec():
    """The OpenAPI document of the running instance."""
    site_title = core_settings.get('site_title')
    return build_spec(
        collect_operations(),
        title=f'{site_title} API',
        version=indico_version,
        description=DESCRIPTION,
        server_url=config.BASE_URL.rstrip('/'),
        scopes={scope: str(description) for scope, description in SCOPES.items()},
        authorization_url=url_for('oauth.oauth_authorize', _external=True),
        token_url=url_for('oauth.oauth_token', _external=True),
        cookie_name=current_app.config['SESSION_COOKIE_NAME'],
    )


def collect_operations(app=None):
    """Every method of every API-looking URL rule, as an `Operation`.

    One handler that cannot be read is logged and leaves out whatever could not
    be found out about it, never the document: nobody should be unable to look at
    the other six hundred endpoints because of the one that is built oddly.
    """
    app = app or current_app
    operations = []
    for rule in app.url_map.iter_rules():
        handler = rh_class(app.view_functions.get(rule.endpoint))
        if not is_api(rule, handler):
            continue
        for method in sorted(rule.methods - {'HEAD', 'OPTIONS'}, key=method_rank):
            try:
                operations.append(_operation(rule, method, handler))
            except Exception:
                logger.exception('Could not describe %s %s', method, rule.rule)
                operations.append(Operation(rule=rule.rule, method=method, endpoint=rule.endpoint,
                                            handler=handler.__name__))
    return operations


def is_api(rule, handler):
    """Whether this URL rule looks like an API endpoint.  See the module docstring."""
    if handler is None or rule.endpoint.partition('.')[0] in NOT_AN_API:
        return False
    return '/api/' in rule.rule or rule.rule.endswith('/api') or bool(getattr(handler, '_OAUTH_SCOPE', None))


def rh_class(view_func):
    """The request handler class that a URL rule was made from, or ``None``.

    ``IndicoBlueprint.add_url_rule`` replaces an RH class with a closure over it
    (`make_view_func`) and keeps nothing else, so the class is found in the
    closure.  A rule that is not a handler -- a catch-all that answers 404, the
    classic API's -- has no such class, and is not an endpoint to document.
    """
    for __ in range(_MAX_UNWRAP):
        if not inspect.isfunction(view_func):
            return None
        handler = _closure(view_func).get('obj')
        if inspect.isclass(handler) and hasattr(handler, 'process'):
            return handler
        view_func = getattr(view_func, '__wrapped__', None)
    return None


def _operation(rule, method, handler):
    process = getattr(handler, f'_process_{method}', None) or getattr(handler, '_process', None)
    return Operation(
        rule=rule.rule,
        method=method,
        endpoint=rule.endpoint,
        handler=handler.__name__,
        doc=(getattr(process, '__doc__', None) or handler.__doc__ or ''),
        scope=getattr(handler, '_OAUTH_SCOPE', None),
        json_errors=bool(getattr(handler, '_JSON_ERRORS', False)),
        custom_auth=bool(getattr(handler, '_DISABLE_CORE_AUTH', False)),
        arguments=_arguments(handler, method),
        parameters=tuple(getattr(handler, '_OPENAPI_PARAMETERS', ())),
        response=getattr(handler, '_OPENAPI_RESPONSE', None),
    )


def _arguments(handler, method):
    """The schemas the handler parses its arguments with, for this method.

    `use_args` and friends wrap the method and keep what they were given in the
    wrapper's closure; the schema is in a second closure, the factory's.  All of
    it is looked up by name, so a webargs that is built differently one day
    finds nothing -- which is an undocumented argument, not a failure.
    """
    names = ['_process_args', f'_process_{method}' if hasattr(handler, f'_process_{method}') else '_process']
    sources = []
    for name in names:
        function = getattr(handler, name, None)
        while function is not None:
            if source := _webargs_source(function):
                sources.append(source)
            function = getattr(function, '__wrapped__', None)
    return tuple(sources)


def _webargs_source(function):
    if not inspect.isfunction(function):
        return None
    closure = _closure(function)
    factory = closure.get('argmap')
    if not callable(factory) or 'location' not in closure or not inspect.isfunction(factory):
        return None
    inner = _closure(factory)
    schema = inner.get('schema_cls')
    if schema is None:
        return None
    kwargs = inner.get('schema_kwargs') or {}
    return Arguments(
        location=closure['location'] or 'json_or_form',
        schema=schema,
        partial=kwargs.get('partial') is True,
        only=tuple(kwargs['only']) if kwargs.get('only') else None,
        exclude=tuple(kwargs.get('exclude') or ()),
    )


def _closure(function):
    """``{name: value}`` of what `function` closes over, leaving out names not bound yet."""
    values = {}
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or (), strict=True):
        with suppress(ValueError):
            values[name] = cell.cell_contents
    return values
