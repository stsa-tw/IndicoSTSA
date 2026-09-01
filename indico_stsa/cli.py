"""The plugin's `indico stsa` commands."""

import click

from indico.cli.core import cli_group
from indico.core.db import db


@cli_group(name='stsa')
def cli():
    """Manage the STSA plugin."""


@cli.command('install-ticket')
@click.option('--category-id', type=int, default=None,
              help='Install into this category instead of the root one.')
@click.option('--default/--no-default', 'set_as_default', default=True,
              help="Also make it the category's default ticket. On by default.")
@click.option('--dry-run', is_flag=True, help='Say what would change, then roll back.')
def install_ticket(category_id, set_as_default, dry_run):
    """Install or refresh the STSA ticket template.

    Safe to re-run: the template is found by title and updated in place, so
    events already pointing at it keep pointing at it. That is also how a
    plugin upgrade's design changes get applied.
    """
    from indico.modules.categories import Category

    from indico_stsa.install_ticket import install

    category = Category.get(category_id) if category_id is not None else Category.get_root()
    if category is None:
        raise click.ClickException(f'no category with id {category_id}')

    previous = category.default_ticket_template
    template, created = install(category, set_as_default=set_as_default)

    click.secho(f'{"Created" if created else "Updated"} "{template.title}" '
                f'in category {category.id} ({category.title})', fg='green')
    if set_as_default:
        if previous is not None and previous.id != template.id:
            click.secho(f'Default ticket was "{previous.title}", now "{template.title}"', fg='yellow')
        else:
            click.secho(f'Default ticket for the category is "{template.title}"', fg='green')

    if dry_run:
        db.session.rollback()
        click.secho('Dry run: rolled back, nothing was saved.', fg='yellow')
    else:
        db.session.commit()
