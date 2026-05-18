"""PyQt6 UI layer.

All widgets read translations from :class:`ordertracker.i18n.Translator` and
observe it for language-change events. Domain calls go through
``services.*`` — UI files never touch SQLAlchemy directly.
"""
