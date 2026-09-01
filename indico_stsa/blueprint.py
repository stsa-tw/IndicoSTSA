from indico.core.plugins import IndicoPluginBlueprint

from indico_stsa.controllers import management


blueprint = IndicoPluginBlueprint('stsa', __name__, url_prefix='/event/<int:event_id>')

blueprint.add_url_rule('/manage/stsa/', 'manage_overview',
                       management.RHSTSAOverview)
blueprint.add_url_rule('/manage/registration/<int:reg_form_id>/stsa/', 'manage_settings',
                       management.RHSTSASettings, methods=('GET', 'POST'))
blueprint.add_url_rule('/manage/registration/<int:reg_form_id>/stsa/recalculate', 'recalculate',
                       management.RHRecalculateDiscounts, methods=('POST',))
