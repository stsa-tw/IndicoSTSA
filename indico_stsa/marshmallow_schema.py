"""Describing a marshmallow schema as JSON Schema, as far as an OpenAPI document needs it.

Indico declares what an endpoint accepts as a marshmallow schema and has no way
to say so to anybody else, so this walks one and writes down what it finds.
It is best effort and says so by being generous: a field it does not recognise
-- Indico has plenty of its own, such as `ModelField`, which takes an ID and
looks the row up -- is described as *anything*, which is true, rather than
guessed at, which would not be.

Needs marshmallow and nothing else, so it is tested without Indico.
"""

from marshmallow import fields, missing, validate


#: How deep a `Nested` is followed.  Indico's schemas are not recursive, but a
#: handler's own may be, and a document that never ends is worse than one that
#: stops describing at some depth.
MAX_DEPTH = 4

#: What each marshmallow field is, most specific first -- `Integer` is a
#: `Number` and a `UUID` is a `String`, so the order is the whole of the logic.
_SCALARS = (
    (fields.Boolean, {'type': 'boolean'}),
    (fields.Integer, {'type': 'integer'}),
    (fields.Number, {'type': 'number'}),
    (fields.UUID, {'type': 'string', 'format': 'uuid'}),
    (fields.Email, {'type': 'string', 'format': 'email'}),
    (fields.URL, {'type': 'string', 'format': 'uri'}),
    # `Date` and `Time` are `DateTime`s in marshmallow, so they come first.
    (fields.Date, {'type': 'string', 'format': 'date'}),
    (fields.Time, {'type': 'string', 'format': 'time'}),
    (fields.DateTime, {'type': 'string', 'format': 'date-time'}),
    (fields.TimeDelta, {'type': 'integer', 'description': 'A number of seconds.'}),
    (fields.String, {'type': 'string'}),
)


def object_schema(schema, *, partial=False, only=None, exclude=(), depth=0):
    """The JSON Schema of what `schema` accepts, as an object.

    :param schema: a marshmallow `Schema`, class or instance
    :param partial: whether nothing in it is required, as for a ``PATCH``
    :param only: the names that are kept, if it is not all of them
    :param exclude: the names that are left out
    """
    properties = {}
    required = []
    for name, field in _declared_fields(schema).items():
        if field.dump_only:
            continue
        key = field.data_key or name
        if (only is not None and name not in only and key not in only) or name in exclude or key in exclude:
            continue
        properties[key] = field_schema(field, depth=depth)
        if field.required and not partial:
            required.append(key)
    result = {'type': 'object', 'properties': properties}
    if required:
        result['required'] = required
    return result


def field_schema(field, *, depth=0):
    """The JSON Schema of one marshmallow field."""
    result = _base_schema(field, depth)
    _apply_validators(field, result)
    if description := field.metadata.get('description'):
        result['description'] = str(description)
    if field.load_default is not missing and not callable(field.load_default):
        default = _json_safe(field.load_default)
        if default is not _UNSAFE:
            result['default'] = default
    if field.allow_none and (kind := result.get('type')):
        result['type'] = [*kind, 'null'] if isinstance(kind, list) else [kind, 'null']
    return result


def _declared_fields(schema):
    return getattr(schema, '_declared_fields', None) or getattr(type(schema), '_declared_fields', {})


def _base_schema(field, depth):
    if isinstance(field, fields.Nested):
        return _nested_schema(field, depth)
    if isinstance(field, fields.List):
        inner = getattr(field, 'inner', None)
        return {'type': 'array', 'items': field_schema(inner, depth=depth) if inner is not None else {}}
    if isinstance(field, fields.Dict):
        value = getattr(field, 'value_field', None)
        result = {'type': 'object'}
        if value is not None:
            result['additionalProperties'] = field_schema(value, depth=depth)
        return result
    if isinstance(field, fields.Enum):
        return _enum_schema(field)
    for kind, schema in _SCALARS:
        if isinstance(field, kind):
            return dict(schema)
    # `Raw`, `Field` and everything Indico made up: anything at all.
    return {}


def _nested_schema(field, depth):
    if depth >= MAX_DEPTH:
        result = {'type': 'object'}
    else:
        try:
            nested = field.schema
        except Exception:
            # A forward reference, or a schema that needs a context to be built.
            result = {'type': 'object'}
        else:
            result = object_schema(nested, depth=depth + 1)
    if field.many:
        return {'type': 'array', 'items': result}
    return result


def _enum_schema(field):
    try:
        members = [member.value for member in field.enum] if field.by_value else [member.name for member in field.enum]
    except Exception:
        return {}
    kind = 'integer' if members and all(isinstance(m, int) and not isinstance(m, bool) for m in members) else 'string'
    return {'type': kind, 'enum': members}


def _apply_validators(field, result):
    for validator in field.validators:
        if isinstance(validator, validate.OneOf):
            result['enum'] = [choice for choice in validator.choices if _json_safe(choice) is not _UNSAFE]
        elif isinstance(validator, validate.Range):
            if validator.min is not None:
                result['minimum' if validator.min_inclusive else 'exclusiveMinimum'] = validator.min
            if validator.max is not None:
                result['maximum' if validator.max_inclusive else 'exclusiveMaximum'] = validator.max
        elif isinstance(validator, validate.Length):
            prefix = 'Items' if result.get('type') == 'array' else 'Length'
            if validator.equal is not None:
                result['min' + prefix] = result['max' + prefix] = validator.equal
            else:
                if validator.min is not None:
                    result['min' + prefix] = validator.min
                if validator.max is not None:
                    result['max' + prefix] = validator.max


_UNSAFE = object()


def _json_safe(value):
    """`value` if JSON can say it, else `_UNSAFE`: a default may be any Python object."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        items = [_json_safe(item) for item in value]
        return _UNSAFE if _UNSAFE in items else items
    if isinstance(value, dict):
        items = {k: _json_safe(v) for k, v in value.items()}
        return _UNSAFE if not all(isinstance(k, str) for k in items) or _UNSAFE in items.values() else items
    return _UNSAFE
