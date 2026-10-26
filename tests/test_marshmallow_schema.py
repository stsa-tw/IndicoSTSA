"""What a marshmallow schema looks like once it is written down as JSON Schema.

`indico_stsa.api_docs` finds the schemas Indico's handlers parse their arguments
with and `indico_stsa.marshmallow_schema` describes them for the API reference.
These are the fields Indico actually uses, and the ones it made up -- which have
to come out as "anything" rather than as a guess.
"""

import enum

import pytest
from marshmallow import Schema, fields, validate

from indico_stsa.marshmallow_schema import field_schema, object_schema


def schema_of(**declared):
    return object_schema(Schema.from_dict(declared))


@pytest.mark.parametrize(('field', 'expected'), (
    (fields.String(), {'type': 'string'}),
    (fields.Integer(), {'type': 'integer'}),
    (fields.Float(), {'type': 'number'}),
    (fields.Boolean(), {'type': 'boolean'}),
    (fields.UUID(), {'type': 'string', 'format': 'uuid'}),
    (fields.Email(), {'type': 'string', 'format': 'email'}),
    (fields.URL(), {'type': 'string', 'format': 'uri'}),
    (fields.DateTime(), {'type': 'string', 'format': 'date-time'}),
))
def test_scalars(field, expected):
    assert field_schema(field) == expected


def test_a_date_is_not_a_date_time():
    # `Date` and `Time` are `DateTime`s in marshmallow, so the order they are tried in matters.
    assert field_schema(fields.Date()) == {'type': 'string', 'format': 'date'}
    assert field_schema(fields.Time()) == {'type': 'string', 'format': 'time'}


def test_a_field_nobody_has_heard_of_is_anything():
    class ModelField(fields.Field):
        """Takes an ID and looks the row up: not something a schema can say."""

    assert field_schema(ModelField()) == {}
    assert field_schema(fields.Raw()) == {}


def test_a_custom_subclass_is_what_it_derives_from():
    class LowercaseString(fields.String):
        pass

    assert field_schema(LowercaseString()) == {'type': 'string'}


def test_lists_and_dicts():
    assert field_schema(fields.List(fields.Integer())) == {'type': 'array', 'items': {'type': 'integer'}}
    assert field_schema(fields.Dict(keys=fields.String(), values=fields.Boolean())) == {
        'type': 'object', 'additionalProperties': {'type': 'boolean'}}
    assert field_schema(fields.Dict()) == {'type': 'object'}


def test_nested():
    inner = Schema.from_dict({'name': fields.String(required=True)})
    assert field_schema(fields.Nested(inner)) == {
        'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    assert field_schema(fields.Nested(inner, many=True))['type'] == 'array'


def test_nested_that_cannot_be_built_is_still_an_object():
    assert field_schema(fields.Nested('NoSuchSchema')) == {'type': 'object'}


def test_nested_stops_somewhere():
    class Tree(Schema):
        child = fields.Nested(lambda: Tree())

    schema = object_schema(Tree)
    depth = 0
    while 'child' in schema.get('properties', {}):
        schema = schema['properties']['child']
        depth += 1
    assert 0 < depth < 10


def test_enums():
    class Colour(enum.Enum):
        red = 1
        green = 2

    assert field_schema(fields.Enum(Colour)) == {'type': 'string', 'enum': ['red', 'green']}
    assert field_schema(fields.Enum(Colour, by_value=True)) == {'type': 'integer', 'enum': [1, 2]}


class TestValidators:
    def test_one_of(self):
        assert field_schema(fields.String(validate=validate.OneOf(['a', 'b']))) == {
            'type': 'string', 'enum': ['a', 'b']}

    def test_range(self):
        result = field_schema(fields.Integer(validate=validate.Range(min=1, max=10, max_inclusive=False)))
        assert result == {'type': 'integer', 'minimum': 1, 'exclusiveMaximum': 10}

    def test_length_of_a_string_and_of_a_list(self):
        assert field_schema(fields.String(validate=validate.Length(min=1, max=5))) == {
            'type': 'string', 'minLength': 1, 'maxLength': 5}
        assert field_schema(fields.List(fields.String(), validate=validate.Length(max=3))) == {
            'type': 'array', 'items': {'type': 'string'}, 'maxItems': 3}


class TestObjects:
    def test_required_and_the_name_it_is_sent_under(self):
        result = schema_of(name=fields.String(required=True), kind=fields.String(data_key='type'))
        assert set(result['properties']) == {'name', 'type'}
        assert result['required'] == ['name']

    def test_nothing_is_required_of_a_partial_update(self):
        schema = Schema.from_dict({'name': fields.String(required=True)})
        assert 'required' not in object_schema(schema, partial=True)

    def test_what_is_only_ever_sent_back_is_not_asked_for(self):
        assert schema_of(id=fields.Integer(dump_only=True), name=fields.String()) == {
            'type': 'object', 'properties': {'name': {'type': 'string'}}}

    def test_only_and_exclude(self):
        schema = Schema.from_dict({'a': fields.String(), 'b': fields.String(), 'c': fields.String()})
        assert set(object_schema(schema, only=('a', 'b'))['properties']) == {'a', 'b'}
        assert set(object_schema(schema, exclude=('a',))['properties']) == {'b', 'c'}

    def test_an_instance_is_as_good_as_a_class(self):
        schema = Schema.from_dict({'a': fields.String()})
        assert object_schema(schema()) == object_schema(schema)


class TestMetadata:
    def test_null_is_allowed(self):
        assert field_schema(fields.String(allow_none=True)) == {'type': ['string', 'null']}

    def test_a_default(self):
        assert field_schema(fields.Integer(load_default=5))['default'] == 5

    def test_a_default_json_cannot_say_is_left_out(self):
        assert 'default' not in field_schema(fields.Raw(load_default=object()))
        assert 'default' not in field_schema(fields.Integer(load_default=lambda: 5))

    def test_a_description(self):
        assert field_schema(fields.String(metadata={'description': 'Who.'}))['description'] == 'Who.'
