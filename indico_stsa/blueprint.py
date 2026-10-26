from indico.core.plugins import IndicoPluginBlueprint

from indico_stsa.controllers import api, docs, management


# No `url_prefix` on the blueprint: the participant-facing API is not about any
# one event, so it cannot live under `/event/<id>`, and a plugin gets one
# blueprint only.
blueprint = IndicoPluginBlueprint('stsa', __name__)

EVENT = '/event/<int:event_id>'

blueprint.add_url_rule(f'{EVENT}/manage/stsa/', 'manage_overview',
                       management.RHSTSAOverview)
blueprint.add_url_rule(f'{EVENT}/manage/registration/<int:reg_form_id>/stsa/', 'manage_settings',
                       management.RHSTSASettings, methods=('GET', 'POST'))
blueprint.add_url_rule(f'{EVENT}/manage/registration/<int:reg_form_id>/stsa/recalculate', 'recalculate',
                       management.RHRecalculateDiscounts, methods=('POST',))
blueprint.add_url_rule(f'{EVENT}/manage/registration/<int:reg_form_id>/stsa/payment-reminders', 'payment_reminders',
                       management.RHSTSAPaymentReminders, methods=('GET', 'POST'))
blueprint.add_url_rule(f'{EVENT}/manage/registration/<int:reg_form_id>/stsa/payment-reminders/preview',
                       'payment_reminders_preview', management.RHSTSAPaymentReminderPreview, methods=('POST',))

blueprint.add_url_rule('/api/stsa/registered-events', 'registered_events', api.RHSTSARegisteredEvents)

# Administrators only, all of them.  The URLs are under /admin/ for that reason as
# much as any other: nothing here is for anybody who is not signed in as one.
blueprint.add_url_rule('/admin/stsa/api-docs/', 'api_docs', docs.RHSTSAAPIDocs)
blueprint.add_url_rule('/admin/stsa/api-docs/openapi.json', 'api_docs_spec', docs.RHSTSAOpenAPI)
blueprint.add_url_rule('/admin/stsa/api-docs/scalar.js', 'api_docs_scalar', docs.RHSTSAScalarScript)
