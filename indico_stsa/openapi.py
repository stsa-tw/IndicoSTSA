"""Writing the endpoints of an Indico instance down as an OpenAPI document.

Split from `indico_stsa.api_docs` the same way `indico_stsa.reminders` is split
from `indico_stsa.payments`: everything here is decided from plain values, so it
is the half that can be tested without Indico running.  Going through the URL
map and the handlers to find those values is the other half's job.

What a document made this way can and cannot say is the whole design:

* the **URL, the methods and the path parameters** are facts of the URL map;
* **who may call it** is only partly known.  A handler that asks for an OAuth
  scope of its own says so, and one that does not is, by core's own rule, open to
  tokens with ``read:everything`` (or ``full:everything`` for anything but a
  ``GET``).  Whether it *also* answers without credentials is decided inside the
  handler, so that is not claimed either way;
* **what it accepts** comes from the marshmallow schemas the handler parses its
  arguments with, where there are any (`indico_stsa.marshmallow_schema`);
* **what it returns** is not written down anywhere in Indico, so a response is
  described only if the handler declares one, and is otherwise just "a
  successful response" -- which is less than a hand-written document would say,
  and not wrong.
"""

import inspect
import re
from dataclasses import dataclass

from indico_stsa.marshmallow_schema import object_schema


METHOD_ORDER = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')
#: The methods whose arguments travel in a body rather than the query string.
BODY_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})

_SCOPE_GET = ('read:everything', 'full:everything')
_SCOPE_OTHER = ('full:everything',)

#: webargs locations, by where an OpenAPI document puts them.
_QUERY_LOCATIONS = frozenset({'query', 'querystring'})
_JSON_LOCATIONS = frozenset({'json'})
_FORM_LOCATIONS = frozenset({'form'})
#: Indico's own default, and the meta-locations that include a query string.
_EITHER_LOCATIONS = frozenset({'json_or_form', 'json_or_form_or_query'})

_RULE_VARIABLE = re.compile(r'<(?:(?P<converter>[a-zA-Z_]\w*)(?:\((?P<args>[^)]*)\))?:)?(?P<name>[a-zA-Z_]\w*)>')
_CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


@dataclass(frozen=True)
class Arguments:
    """One place a handler reads arguments from, and the schema it parses them with."""

    #: webargs' name for where: ``query``, ``json``, ``form``, ``json_or_form``, ...
    location: str
    #: A marshmallow `Schema`, class or instance.
    schema: object
    partial: bool = False
    only: tuple | None = None
    exclude: tuple = ()


@dataclass(frozen=True)
class Operation:
    """One method of one URL rule, with everything that is known about its handler."""

    rule: str
    method: str
    #: Flask's endpoint name, ``blueprint.view``.
    endpoint: str
    #: The handler's class name, for a summary when it has no docstring.
    handler: str
    doc: str = ''
    #: The OAuth scope the handler asks for in particular, if it does.
    scope: str | None = None
    json_errors: bool = False
    #: The handler does its own authentication, so core's is not what applies.
    custom_auth: bool = False
    arguments: tuple = ()
    #: OpenAPI parameter objects for what the handler reads by hand.
    parameters: tuple = ()
    #: A JSON Schema for the body of a successful response, if the handler says.
    response: dict | None = None


def convert_rule(rule):
    """``(path, parameters)`` for a werkzeug rule: ``/e/<int:id>`` -> ``/e/{id}``.

    ``parameters`` are OpenAPI parameter objects.  A ``path`` converter matches
    slashes, which an OpenAPI path parameter cannot; it is described as the
    one thing in the document that does not mean what the spec says it does.
    """
    parameters = []

    def replace(match):
        name = match['name']
        schema, description = _converter_schema(match['converter'], match['args'])
        parameter = {'name': name, 'in': 'path', 'required': True, 'schema': schema}
        if description:
            parameter['description'] = description
        parameters.append(parameter)
        return '{' + name + '}'

    return _RULE_VARIABLE.sub(replace, rule), parameters


def _converter_schema(converter, args):
    if converter == 'int':
        return {'type': 'integer'}, None
    if converter == 'float':
        return {'type': 'number'}, None
    if converter == 'uuid':
        return {'type': 'string', 'format': 'uuid'}, None
    if converter == 'any':
        choices = [choice.strip() for choice in (args or '').split(',') if choice.strip()]
        return {'type': 'string', 'enum': choices}, None
    if converter == 'path':
        return {'type': 'string'}, 'May contain slashes.'
    return {'type': 'string'}, None


def split_doc(doc, handler):
    """``(summary, description)`` from a handler's docstring, or from its name if it has none.

    The summary is the first sentence.  The description is the rest of the
    docstring -- all of it, when that sentence has more after it in the same
    paragraph, so that nothing is cut in half -- which is Markdown-compatible
    enough as it is.  A viewer prints both, and a description that begins by
    repeating the title is a worse page.
    """
    # The docstrings are reStructuredText and the viewer reads Markdown, which differ
    # most visibly in how much backtick a piece of code gets.
    doc = inspect.cleandoc(doc or '').replace('``', '`')
    if not doc:
        return humanize_handler(handler), ''
    paragraph = ' '.join(doc.split('\n\n', 1)[0].split())
    summary = re.split(r'(?<=[.!?])\s', paragraph, maxsplit=1)[0].rstrip('.')
    if len(summary) > 120:
        summary = summary[:117].rstrip() + '...'
    if paragraph.rstrip('.') == summary:
        # The paragraph was the summary and nothing else.
        return summary, doc.partition('\n\n')[2].strip()
    return summary, doc


def humanize_handler(name):
    """``RHCheckinAPIEventDetails`` -> ``Checkin API Event Details``."""
    name = name.removeprefix('RH')
    return ' '.join(_CAMEL_BOUNDARY.split(name)) or name


#: The blueprints whose names are not what anybody would call them.
_TAG_NAMES = {'rb': 'Room booking'}


def tag_for(endpoint):
    """The tag an endpoint is listed under: its blueprint, which is its module."""
    blueprint = endpoint.partition('.')[0]
    if blueprint.startswith('plugin_'):
        return f'{blueprint.removeprefix("plugin_")} (plugin)'
    return _TAG_NAMES.get(blueprint) or blueprint.replace('_', ' ').capitalize()


def security_for(operation):
    """The OpenAPI security requirements for an operation, or ``None`` for "not core's to say".

    Alternatives, not a combination: a token with *any* of the scopes is let in,
    as is a signed-in session.
    """
    if operation.custom_auth:
        return None
    scopes = [operation.scope] if operation.scope else []
    scopes.extend(_SCOPE_GET if operation.method == 'GET' else _SCOPE_OTHER)
    return [{'oauth2': [scope]} for scope in dict.fromkeys(scopes)] + [{'cookieAuth': []}]


def build_spec(operations, *, title, version, description, server_url, scopes, authorization_url, token_url,
               cookie_name):
    """The OpenAPI document for `operations`.

    Deterministic -- paths, methods and tags are sorted -- so that the document
    of one instance can be compared with another's, or with itself last week.

    :param scopes: ``{scope: description}`` for every OAuth scope there is
    """
    paths = {}
    seen_ids = {}
    for operation in sorted(operations, key=lambda op: (op.rule, method_rank(op.method))):
        path, path_parameters = convert_rule(operation.rule)
        item = paths.setdefault(path, {})
        item[operation.method.lower()] = _build_operation(operation, path_parameters, seen_ids)

    tags = _tags(operations)
    return {
        'openapi': '3.1.0',
        'info': {'title': title, 'version': version, 'description': description},
        'servers': [{'url': server_url}],
        'tags': tags,
        'x-tagGroups': _tag_groups(operations),
        'paths': dict(sorted(paths.items())),
        'components': {
            'securitySchemes': {
                'oauth2': {
                    'type': 'oauth2',
                    'description': 'An OAuth application, or a personal access token, which is sent the same '
                                   'way: `Authorization: Bearer <token>`.',
                    'flows': {'authorizationCode': {'authorizationUrl': authorization_url, 'tokenUrl': token_url,
                                                    'scopes': dict(sorted(scopes.items()))}},
                },
                'cookieAuth': {'type': 'apiKey', 'in': 'cookie', 'name': cookie_name,
                               'description': 'The signed-in browser session. Anything but a `GET` also needs the '
                                              "session's CSRF token in an `X-CSRF-Token` header."},
            },
            'schemas': {'Error': _ERROR_SCHEMA},
        },
    }


_ERROR_SCHEMA = {
    'type': 'object',
    'description': 'What an endpoint that answers errors as JSON says when something is wrong.',
    'properties': {'error': {'type': 'object', 'properties': {
        'message': {'type': 'string'},
        'title': {'type': 'string'},
        'error_uuid': {'type': ['string', 'null']},
    }}},
}


def method_rank(method):
    return METHOD_ORDER.index(method) if method in METHOD_ORDER else len(METHOD_ORDER)


def _build_operation(operation, path_parameters, seen_ids):
    summary, description = split_doc(operation.doc, operation.handler)
    parameters = list(path_parameters)
    body_properties, body_required, body_types = {}, [], []
    for arguments in operation.arguments:
        where = _where(arguments.location, operation.method)
        if where is None:
            continue
        schema = object_schema(arguments.schema, partial=arguments.partial, only=arguments.only,
                               exclude=arguments.exclude)
        if where == 'query':
            for name, field_schema in schema['properties'].items():
                parameters.append(_query_parameter(name, field_schema, name in schema.get('required', ())))
        else:
            body_properties.update(schema['properties'])
            body_required.extend(name for name in schema.get('required', ()) if name not in body_required)
            body_types.extend(t for t in _body_types(arguments.location) if t not in body_types)

    declared = {(p['name'], p['in']): p for p in operation.parameters}
    parameters = [p for p in parameters if (p['name'], p['in']) not in declared] + list(declared.values())

    result = {
        'tags': [tag_for(operation.endpoint)],
        'summary': summary,
        'operationId': _operation_id(operation, seen_ids),
        'x-indico-endpoint': operation.endpoint,
        'x-indico-handler': operation.handler,
    }
    if description:
        result['description'] = description
    if re.search(r'\bis deprecated\b', description, re.IGNORECASE):
        result['deprecated'] = True
    if parameters:
        result['parameters'] = parameters
    if body_properties or body_types:
        body_schema = {'type': 'object', 'properties': body_properties}
        if body_required:
            body_schema['required'] = body_required
        result['requestBody'] = {'content': {kind: {'schema': body_schema} for kind in body_types}}
    if (security := security_for(operation)) is not None:
        result['security'] = security
    result['responses'] = _responses(operation, bool(path_parameters), bool(operation.arguments))
    return result


def _where(location, method):
    """``'query'``, ``'body'`` or ``None``: where an OpenAPI document would put these arguments."""
    if location in _QUERY_LOCATIONS:
        return 'query'
    if location in _JSON_LOCATIONS | _FORM_LOCATIONS:
        return 'body' if method in BODY_METHODS else None
    if location in _EITHER_LOCATIONS:
        if method in BODY_METHODS:
            return 'body'
        # Nothing is read from the body of a GET; only the longer name looks at the query string.
        return 'query' if location == 'json_or_form_or_query' else None
    return None


def _body_types(location):
    kinds = []
    if location in _JSON_LOCATIONS | _EITHER_LOCATIONS:
        kinds.append('application/json')
    if location in _FORM_LOCATIONS | _EITHER_LOCATIONS:
        kinds.append('application/x-www-form-urlencoded')
    return kinds


def _query_parameter(name, schema, required):
    parameter = {'name': name, 'in': 'query', 'required': required, 'schema': schema}
    if description := schema.get('description'):
        parameter['description'] = description
    return parameter


def _operation_id(operation, seen):
    """Unique, because the same handler is often mounted twice, under and without a user ID."""
    base = f'{operation.endpoint}.{operation.method.lower()}'
    seen[base] = seen.get(base, 0) + 1
    return base if seen[base] == 1 else f'{base}__{seen[base]}'


def _responses(operation, has_path_parameters, has_arguments):
    ok = {'description': 'Successful response.'}
    if operation.response:
        ok['content'] = {'application/json': {'schema': operation.response}}
    responses = {'200': ok}
    if operation.scope:
        responses['403'] = _error('Not signed in, or not allowed to do this.', operation)
    if has_path_parameters:
        responses['404'] = _error('Nothing there with this ID.', operation)
    if has_arguments:
        responses['422'] = {'description': 'An argument was missing or not valid.'}
    return responses


def _error(description, operation):
    response = {'description': description}
    if operation.json_errors:
        response['content'] = {'application/json': {'schema': {'$ref': '#/components/schemas/Error'}}}
    return response


def _tags(operations):
    names = sorted({tag_for(op.endpoint) for op in operations})
    return [{'name': name} for name in names]


def _tag_groups(operations):
    """The tags, in three groups: the plugins', the ones with a scope of their own, and the rest."""
    plugins, integration, internal = set(), set(), set()
    for operation in operations:
        tag = tag_for(operation.endpoint)
        if operation.endpoint.startswith('plugin_'):
            plugins.add(tag)
        elif operation.scope:
            integration.add(tag)
    for operation in operations:
        tag = tag_for(operation.endpoint)
        if tag not in plugins and tag not in integration:
            internal.add(tag)
    groups = [('Plugins', plugins), ('Integration APIs', integration), ('Everything else', internal)]
    return [{'name': name, 'tags': sorted(tags)} for name, tags in groups if tags]
