import os
from uuid import uuid4

from aiohttp.web import Application, AppRunner, TCPSite
from aiohttp_wsgi import WSGIHandler
from flask import Flask
from flask_admin import Admin, AdminIndexView
from flask_basicauth import BasicAuth


class IndexView(AdminIndexView):
    pass


class WebServer(Flask):
    def __init__(self, index_view=None, title="Temp Monitor", username=None, password=None):
        super(WebServer, self).__init__(__name__)

        self.template_folder = os.path.normpath(os.getcwd() + "/templates")
        self.secret_key = str(uuid4())

        if username is not None:
            self.config['BASIC_AUTH_USERNAME'] = username
            self.config['BASIC_AUTH_PASSWORD'] = password
            self.config['BASIC_AUTH_FORCE'] = True
            self.config['BASIC_AUTH_REALM'] = title
            BasicAuth(self)

        admin_params = {"name": title, "template_mode": 'bootstrap3'}
        if index_view is not None:
            admin_params.update({"index_view": index_view})
        self.admin = Admin(self, **admin_params)

    async def run_async(self, host=None, port=None, loop=None):
        wsgi = WSGIHandler(application=self, loop=loop)
        app = Application(loop=loop)
        app.router.add_route("*", "/{path_info:.*}", wsgi)
        runner = AppRunner(app)
        await runner.setup()
        site = TCPSite(runner, host, port)
        await site.start()
