"""Make `indico_stsa` importable from a script, with or without Indico.

The three scripts beside this one read the plugin's own constants rather than
keeping a copy of the palette in step by hand.  That means importing the
package, and `indico_stsa/__init__.py` binds a gettext from Indico -- which is
present on a server and absent on the laptop where somebody is trying to see
what a colour looks like.

Gettext is the only thing the pure modules need from Indico, so when Indico is
missing it is stubbed with the identity function.  Where Indico *is* installed
nothing is stubbed and the real one is used.

    import _bootstrap  # noqa -- must precede any indico_stsa import
"""

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if importlib.util.find_spec('indico') is None:
    i18n = types.ModuleType('indico.util.i18n')
    i18n.make_bound_gettext = lambda domain: (lambda text, *args, **kwargs: text)

    util = types.ModuleType('indico.util')
    util.i18n = i18n

    indico = types.ModuleType('indico')
    indico.util = util

    sys.modules.setdefault('indico', indico)
    sys.modules.setdefault('indico.util', util)
    sys.modules.setdefault('indico.util.i18n', i18n)
