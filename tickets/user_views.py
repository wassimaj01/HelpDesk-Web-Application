"""
This module has been removed and its implementation moved to the `users`
app: use `from users import views as user_views` or import specific
symbols from `users.views`.

For safety this file now raises ImportError so any stale imports are
clearly visible during development. Remove this file entirely once all
references have been updated.
"""

raise ImportError(
    "tickets.user_views has been removed. Use users.views instead. "
    "Update imports to use the users app (e.g. from users import views)."
)
