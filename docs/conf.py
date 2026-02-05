# Sphinx configuration for Termin documentation

project = "Termin"
copyright = "2026, mirmik"
author = "mirmik"

extensions = [
    "myst_parser",           # Markdown support
    "sphinx.ext.autodoc",    # Python autodoc
    "sphinx.ext.viewcode",   # Links to source code
    "breathe",               # C/C++ via Doxygen
]

# MyST settings
myst_enable_extensions = [
    "colon_fence",    # ::: for directives
    "fieldlist",      # :param: style
]

# Source files
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Theme (uncomment one)
# html_theme = "furo"                    # Современная, контрастная (может резать глаза)
# html_theme = "sphinx_rtd_theme"        # Read the Docs классика, тёмный sidebar
# html_theme = "pydata_sphinx_theme"     # Научный стиль (NumPy, Pandas), есть dark mode
# html_theme = "sphinx_book_theme"       # Книжный стиль, акцент на читаемость
# html_theme = "alabaster"               # Минимализм, встроена в Sphinx
# html_theme = "sphinx_material"         # Material Design
# html_theme = "piccolo_theme"           # Современная, чистая

html_theme = "sphinx_book_theme"  # <-- активная тема
html_title = "Termin"

# Theme options for pydata_sphinx_theme
html_theme_options = {
    "navbar_align": "left",
    # Переключатель light/dark в navbar
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
}

# Language
language = "ru"

# Breathe config (C/C++ docs from Doxygen)
breathe_projects = {"termin": "./doxygen_xml"}
breathe_default_project = "termin"
breathe_default_members = ("members", "undoc-members")
