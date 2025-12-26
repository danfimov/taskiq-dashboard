import pathlib

from fastapi.templating import Jinja2Templates


jinja_templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / 'templates')
