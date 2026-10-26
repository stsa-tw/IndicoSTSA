"""The OpenAPI document built from what is known about an instance's endpoints.

`indico_stsa.api_docs` goes through the URL map and hands over plain
`Operation`s; these tests start from those, so they run without Indico and
cover everything that decides what the document says.  The structural checks at
the bottom are what a validator would insist on, written out by hand: a document
that the viewer cannot make sense of fails there rather than in somebody's
browser.
"""

import json
import re

from marshmallow import Schema, fields

from indico_stsa.openapi import (Arguments, Operation, build_spec, convert_rule, humanize_handler, security_for,
                                 split_doc, tag_for)


class TestConvertRule:
    def test_a_rule_without_variables(self):
        assert convert_rule('/api/user/') == ('/api/user/', [])

    def test_an_integer(self):
        path, params = convert_rule('/event/<int:event_id>/api/note')
        assert path == '/event/{event_id}/api/note'
        assert params == [{'name': 'event_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}]

    def test_a_uuid(self):
        params = convert_rule('/api/checkin/ticket/<uuid:ticket_uuid>')[1]
        assert params[0]['schema'] == {'type': 'string', 'format': 'uuid'}

    def test_a_choice_of_words(self):
        path, params = convert_rule('/editing/api/<any(paper,slides,poster):type>/list')
        assert path == '/editing/api/{type}/list'
        assert params[0]['schema'] == {'type': 'string', 'enum': ['paper', 'slides', 'poster']}

    def test_a_path_may_have_slashes_and_says_so(self):
        params = convert_rule('/rooms/api/<path:path>')[1]
        assert params[0]['schema'] == {'type': 'string'}
        assert 'slashes' in params[0]['description']

    def test_a_variable_with_no_converter_is_a_string(self):
        path, params = convert_rule('/api/favorites/users/<identifier>')
        assert path == '/api/favorites/users/{identifier}'
        assert params[0]['schema'] == {'type': 'string'}

    def test_several_in_order(self):
        path, params = convert_rule('/event/<int:event_id>/api/<int:contrib_id>/revision/<int:revision_id>')
        assert path == '/event/{event_id}/api/{contrib_id}/revision/{revision_id}'
        assert [p['name'] for p in params] == ['event_id', 'contrib_id', 'revision_id']


class TestSplitDoc:
    def test_the_first_sentence_is_the_summary_and_the_rest_the_description(self):
        summary, description = split_doc('Get details about an event.\n\nMore of it.', 'RHEvent')
        assert summary == 'Get details about an event'
        assert description == 'More of it.'

    def test_a_docstring_that_is_only_a_summary_has_no_description(self):
        assert split_doc('Get details about an event.', 'RHEvent') == ('Get details about an event', '')

    def test_a_paragraph_with_more_than_the_summary_is_kept_whole(self):
        summary, description = split_doc('Get details. Carefully.\n\nMore of it.', 'RHEvent')
        assert summary == 'Get details'
        assert description == 'Get details. Carefully.\n\nMore of it.'

    def test_an_indented_docstring_is_cleaned_up(self):
        assert split_doc('\n    One thing.\n\n    Another.\n    ', 'RHX') == ('One thing', 'Another.')

    def test_a_paragraph_on_several_lines_is_one_summary(self):
        assert split_doc('Get the\nthing. Then more.', 'RHX')[0] == 'Get the thing'

    def test_a_long_first_sentence_is_cut(self):
        summary = split_doc('word ' * 100, 'RHX')[0]
        assert len(summary) <= 120
        assert summary.endswith('...')

    def test_no_docstring_falls_back_on_the_class_name(self):
        assert split_doc(None, 'RHCheckinAPIEventDetails') == ('Checkin API Event Details', '')
        assert split_doc('', 'RHAPISearch')[0] == 'API Search'

    def test_restructuredtext_code_is_markdown_code(self):
        assert split_doc('Needs ``read:user``.', 'RHX') == ('Needs `read:user`', '')
        assert split_doc('Hi.\n\nNeeds ``read:user``.', 'RHX')[1] == 'Needs `read:user`.'

    def test_humanize(self):
        assert humanize_handler('RHRoomBlockings') == 'Room Blockings'
        assert humanize_handler('RHUserAPI') == 'User API'


class TestTags:
    def test_a_blueprint_is_a_tag(self):
        assert tag_for('event_registration.api_checkin_regforms') == 'Event registration'

    def test_a_cryptic_blueprint_is_renamed(self):
        assert tag_for('rb.rooms') == 'Room booking'

    def test_a_plugin_says_so(self):
        assert tag_for('plugin_stsa.registered_events') == 'stsa (plugin)'


class TestSecurity:
    @staticmethod
    def op(method='GET', scope=None, custom_auth=False):
        return Operation(rule='/x', method=method, endpoint='a.b', handler='RHX', scope=scope,
                         custom_auth=custom_auth)

    def test_a_get_is_open_to_the_wildcard_scopes_and_the_session(self):
        assert security_for(self.op()) == [{'oauth2': ['read:everything']}, {'oauth2': ['full:everything']},
                                           {'cookieAuth': []}]

    def test_anything_else_needs_the_full_one(self):
        assert security_for(self.op('POST')) == [{'oauth2': ['full:everything']}, {'cookieAuth': []}]

    def test_its_own_scope_comes_first_and_is_one_alternative_among_them(self):
        assert security_for(self.op(scope='registrants'))[0] == {'oauth2': ['registrants']}
        assert len(security_for(self.op(scope='registrants'))) == 4

    def test_a_handler_with_its_own_authentication_is_not_described(self):
        assert security_for(self.op(custom_auth=True)) is None


def operation(rule='/api/thing/', method='GET', endpoint='things.thing', **kwargs):
    return Operation(rule=rule, method=method, endpoint=endpoint, handler='RHThing', **kwargs)


def spec_of(*operations):
    return build_spec(list(operations), title='T', version='1', description='D', server_url='https://example.org',
                      scopes={'read:user': 'Read the user'}, authorization_url='https://example.org/authorize',
                      token_url='https://example.org/token', cookie_name='indico_session')


class TestBuildSpec:
    def test_the_envelope(self):
        spec = spec_of(operation())
        assert spec['openapi'].startswith('3.1')
        assert spec['info'] == {'title': 'T', 'version': '1', 'description': 'D'}
        assert spec['servers'] == [{'url': 'https://example.org'}]
        flow = spec['components']['securitySchemes']['oauth2']['flows']['authorizationCode']
        assert flow['scopes'] == {'read:user': 'Read the user'}
        assert spec['components']['securitySchemes']['cookieAuth']['name'] == 'indico_session'

    def test_a_path_with_two_methods(self):
        spec = spec_of(operation(method='PATCH'), operation(method='GET'), operation(method='DELETE'))
        assert list(spec['paths']['/api/thing/']) == ['get', 'patch', 'delete']

    def test_path_parameters_are_declared(self):
        spec = spec_of(operation(rule='/event/<int:event_id>/api/thing'))
        op = spec['paths']['/event/{event_id}/api/thing']['get']
        assert [p['name'] for p in op['parameters']] == ['event_id']
        assert '404' in op['responses']

    def test_summary_and_description_come_from_the_docstring(self):
        op = spec_of(operation(doc='Do the thing. Carefully.'))['paths']['/api/thing/']['get']
        assert op['summary'] == 'Do the thing'
        assert op['description'] == 'Do the thing. Carefully.'
        assert 'description' not in spec_of(operation(doc='Do the thing.'))['paths']['/api/thing/']['get']

    def test_a_deprecated_handler_says_so(self):
        op = spec_of(operation(doc='RESTful thing.\n\nThis API is deprecated.'))['paths']['/api/thing/']['get']
        assert op['deprecated'] is True
        assert 'deprecated' not in spec_of(operation(doc='Fine.'))['paths']['/api/thing/']['get']

    def test_the_same_handler_mounted_twice_has_two_operation_ids(self):
        spec = spec_of(operation(rule='/user/api/thing'), operation(rule='/user/<int:user_id>/api/thing'))
        ids = [op['operationId'] for item in spec['paths'].values() for op in item.values()]
        assert len(ids) == len(set(ids)) == 2

    def test_a_scoped_handler_can_be_forbidden(self):
        op = spec_of(operation(scope='registrants', json_errors=True))['paths']['/api/thing/']['get']
        assert op['responses']['403']['content']['application/json']['schema'] == {'$ref': '#/components/schemas/Error'}
        plain = spec_of(operation(scope='registrants'))['paths']['/api/thing/']['get']
        assert 'content' not in plain['responses']['403']

    def test_what_the_handler_declares_is_used(self):
        parameter = {'name': 'from', 'in': 'query', 'required': False, 'schema': {'type': 'string'}}
        response = {'type': 'object', 'properties': {'a': {'type': 'integer'}}}
        op = spec_of(operation(parameters=(parameter,), response=response))['paths']['/api/thing/']['get']
        assert op['parameters'] == [parameter]
        assert op['responses']['200']['content']['application/json']['schema'] == response

    def test_a_declared_parameter_replaces_one_found_in_a_schema(self):
        found = Arguments('query', Schema.from_dict({'from': fields.String()}))
        declared = {'name': 'from', 'in': 'query', 'description': 'Declared.', 'schema': {'type': 'string'}}
        op = spec_of(operation(arguments=(found,), parameters=(declared,)))['paths']['/api/thing/']['get']
        assert op['parameters'] == [declared]

    def test_sorted_and_so_comparable(self):
        operations = [operation(rule=f'/api/{name}/', endpoint=f'{name}.view', method=method)
                      for name in ('c', 'a', 'b') for method in ('GET', 'POST')]
        shuffled = [*operations[3:], *reversed(operations[:3])]
        assert json.dumps(spec_of(*operations)) == json.dumps(spec_of(*shuffled))


class TestArguments:
    schema = Schema.from_dict({'name': fields.String(required=True), 'count': fields.Integer()})

    def test_a_query_string_becomes_parameters(self):
        op = spec_of(operation(arguments=(Arguments('query', self.schema),)))['paths']['/api/thing/']['get']
        by_name = {p['name']: p for p in op['parameters']}
        assert by_name['name'] == {'name': 'name', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}
        assert by_name['count']['required'] is False
        assert 'requestBody' not in op
        assert '422' in op['responses']

    def test_json_in_a_post_becomes_a_body(self):
        op = spec_of(operation(method='POST', arguments=(Arguments('json', self.schema),)))['paths']['/api/thing/']
        body = op['post']['requestBody']['content']
        assert list(body) == ['application/json']
        assert body['application/json']['schema']['required'] == ['name']
        assert 'parameters' not in op['post']

    def test_indicos_default_is_json_or_a_form(self):
        op = spec_of(operation(method='POST', arguments=(Arguments('json_or_form', self.schema),)))
        assert list(op['paths']['/api/thing/']['post']['requestBody']['content']) == [
            'application/json', 'application/x-www-form-urlencoded']

    def test_a_form_is_only_a_form(self):
        op = spec_of(operation(method='PUT', arguments=(Arguments('form', self.schema),)))
        assert list(op['paths']['/api/thing/']['put']['requestBody']['content']) == [
            'application/x-www-form-urlencoded']

    def test_nothing_is_read_from_the_body_of_a_get(self):
        for location in ('json', 'form', 'json_or_form'):
            op = spec_of(operation(arguments=(Arguments(location, self.schema),)))['paths']['/api/thing/']['get']
            assert 'parameters' not in op
            assert 'requestBody' not in op

    def test_the_longest_location_includes_the_query_string(self):
        op = spec_of(operation(arguments=(Arguments('json_or_form_or_query', self.schema),)))
        assert [p['name'] for p in op['paths']['/api/thing/']['get']['parameters']] == ['name', 'count']

    def test_a_partial_update_requires_nothing(self):
        arguments = Arguments('json', self.schema, partial=True)
        body = spec_of(operation(method='PATCH', arguments=(arguments,)))['paths']['/api/thing/']['patch']
        assert 'required' not in body['requestBody']['content']['application/json']['schema']

    def test_arguments_from_two_places_are_one_body(self):
        other = Schema.from_dict({'extra': fields.Boolean()})
        op = spec_of(operation(method='POST', arguments=(Arguments('json', self.schema), Arguments('json', other))))
        schema = op['paths']['/api/thing/']['post']['requestBody']['content']['application/json']['schema']
        assert set(schema['properties']) == {'name', 'count', 'extra'}

    def test_arguments_that_are_not_ours_to_describe_are_ignored(self):
        for location in ('headers', 'cookies', 'view_args', 'files'):
            op = spec_of(operation(method='POST', arguments=(Arguments(location, self.schema),)))
            assert 'requestBody' not in op['paths']['/api/thing/']['post']


class TestTagGroups:
    def test_plugins_scoped_and_the_rest(self):
        spec = spec_of(operation(endpoint='plugin_stsa.view'),
                       operation(rule='/api/a', endpoint='users.me', scope='read:user'),
                       operation(rule='/api/b', endpoint='core.config'))
        assert spec['x-tagGroups'] == [
            {'name': 'Plugins', 'tags': ['stsa (plugin)']},
            {'name': 'Integration APIs', 'tags': ['Users']},
            {'name': 'Everything else', 'tags': ['Core']},
        ]

    def test_an_empty_group_is_left_out(self):
        assert [g['name'] for g in spec_of(operation(endpoint='core.config'))['x-tagGroups']] == ['Everything else']

    def test_every_tag_is_in_exactly_one_group(self):
        spec = spec_of(operation(endpoint='plugin_stsa.view'),
                       operation(rule='/api/a', endpoint='users.me', scope='read:user'),
                       operation(rule='/api/a2', endpoint='users.other'),
                       operation(rule='/api/b', endpoint='core.config'))
        grouped = [tag for group in spec['x-tagGroups'] for tag in group['tags']]
        assert sorted(grouped) == sorted(tag['name'] for tag in spec['tags'])


class TestTheDocumentIsSound:
    """What a validator would check, for a document with every feature in it."""

    @staticmethod
    def everything():
        schema = Schema.from_dict({'name': fields.String(required=True), 'n': fields.Integer()})
        return spec_of(
            operation(rule='/api/user/', endpoint='users.me', scope='read:user', doc='Who am I.'),
            operation(rule='/event/<int:event_id>/api/x/<any(a,b):kind>', endpoint='ev.x', method='POST',
                      arguments=(Arguments('json', schema),)),
            operation(rule='/event/<int:event_id>/api/x/<any(a,b):kind>', endpoint='ev.x', method='GET',
                      arguments=(Arguments('query', schema),)),
            operation(rule='/user/api/f', endpoint='u.f'),
            operation(rule='/user/<int:user_id>/api/f', endpoint='u.f'),
            operation(rule='/api/auth', endpoint='plugin_x.auth', custom_auth=True),
        )

    def test_it_is_json(self):
        assert json.loads(json.dumps(self.everything())) == self.everything()

    def test_every_path_variable_is_declared_once_and_nothing_else_is(self):
        for path, item in self.everything()['paths'].items():
            variables = re.findall(r'{(\w+)}', path)
            for op in item.values():
                declared = [p['name'] for p in op.get('parameters', []) if p['in'] == 'path']
                assert sorted(declared) == sorted(variables), path
                assert all(p['required'] for p in op.get('parameters', []) if p['in'] == 'path')

    def test_no_parameter_is_declared_twice(self):
        for item in self.everything()['paths'].values():
            for op in item.values():
                keys = [(p['name'], p['in']) for p in op.get('parameters', [])]
                assert len(keys) == len(set(keys))

    def test_operation_ids_are_unique(self):
        ids = [op['operationId'] for item in self.everything()['paths'].values() for op in item.values()]
        assert len(ids) == len(set(ids))

    def test_every_reference_and_scheme_exists(self):
        spec = self.everything()
        text = json.dumps(spec)
        for ref in set(re.findall(r'"\$ref": "#/components/schemas/(\w+)"', text)):
            assert ref in spec['components']['schemas']
        for item in spec['paths'].values():
            for op in item.values():
                for requirement in op.get('security', []):
                    assert set(requirement) <= set(spec['components']['securitySchemes'])

    def test_every_operation_is_tagged_with_a_declared_tag(self):
        spec = self.everything()
        declared = {tag['name'] for tag in spec['tags']}
        for item in spec['paths'].values():
            for op in item.values():
                assert set(op['tags']) <= declared

    def test_every_operation_has_a_response(self):
        for item in self.everything()['paths'].values():
            for op in item.values():
                assert '200' in op['responses']
