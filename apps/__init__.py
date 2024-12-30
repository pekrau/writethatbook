"Collect all apps into a routes list."

from fasthtml.common import Mount

import apps.book
import apps.edit
import apps.mod
import apps.move
import apps.copy
import apps.delete
import apps.refs
import apps.meta
import apps.state
import apps.search
import apps.user
import apps.diff


routes = [
    Mount("/book", apps.book.app),
    Mount("/edit", apps.edit.app),
    Mount("/mod", apps.mod.app),
    Mount("/move", apps.move.app),
    Mount("/copy", apps.copy.app),
    Mount("/delete", apps.delete.app),
    Mount("/refs", apps.refs.app),
    Mount("/meta", apps.meta.app),
    Mount("/state", apps.state.app),
    Mount("/search", apps.search.app),
    Mount("/user", apps.user.app),
    Mount("/diff", apps.diff.app),
]
