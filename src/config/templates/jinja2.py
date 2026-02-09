from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config.settings import settings

jinja_env = Environment(
    loader=FileSystemLoader(Path(settings.ROOT_DIR) / 'templates'),
    autoescape=select_autoescape(['html', 'xml']),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    enable_async=True,
)
