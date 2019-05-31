
# -*- coding: utf-8 -*-
"""
This module is meant to run JupyterLab in a headless browser, making sure
the application launches and starts up without errors.
"""
from concurrent.futures import ThreadPoolExecutor
import logging
from os import path as osp
import os
import shutil
import sys
import subprocess

from tornado.ioloop import IOLoop
from notebook.notebookapp import flags, aliases
from traitlets import Bool

from .labapp import LabApp, get_app_dir


here = osp.abspath(osp.dirname(__file__))
test_flags = dict(flags)
test_flags['core-mode'] = (
    {'BrowserApp': {'core_mode': True}},
    "Start the app in core mode."
)
test_flags['dev-mode'] = (
    {'BrowserApp': {'dev_mode': True}},
    "Start the app in dev mode."
)


test_aliases = dict(aliases)
test_aliases['app-dir'] = 'BrowserApp.app_dir'


class LogErrorHandler(logging.Handler):
    """A handler that exits with 1 on a logged error."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.errored = False

    def filter(self, record):
        # known startup error message
        if 'paste' in record.msg:
            return
        return super().filter(record)

    def emit(self, record):
        print(record.msg, file=sys.stderr)
        self.errored = True


def run_test(app, func):
    """Run a test against the application.

    func is a function that accepts an app url as a parameter and returns a result.
    """
    handler = LogErrorHandler()

    def finished(future):
        try:
            result = future.result()
        except Exception as e:
            app.log.error(str(e))
        app.log.info('Stopping server...')
        app.stop()
        if handler.errored:
            app.log.critical('Exiting with 1 due to errors')
            sys.exit(1)
        elif result != 0:
            app.log.critical('Exiting with %s due to errors' % result)
            sys.exit(result)
        else:
            sys.exit()

    app.log.addHandler(handler)
    pool = ThreadPoolExecutor()
    future = pool.submit(func, app.display_url)
    IOLoop.current().add_future(future, finished)


class BrowserApp(LabApp):
    """An app the launches JupyterLab and waits for it to start up, checking for
    JS console errors, JS errors, and Python logged errors.
    """
    open_browser = Bool(False)
    base_url = '/foo/'
    ip = '127.0.0.1'
    flags = test_flags
    aliases = test_aliases

    def start(self):
        web_app = self.web_app
        web_app.settings.setdefault('page_config_data', dict())
        web_app.settings['page_config_data']['browserTest'] = True
        web_app.settings['page_config_data']['buildAvailable'] = False
        run_test(self, run_browser)
        super().start()


def run_browser(url):
    """Run the browser test and return an exit code.
    """
    target = osp.join(get_app_dir(), 'browser_test')
    if not osp.exists(osp.join(target, 'node_modules')):
        os.makedirs(target)
        subprocess.call(["jlpm"], cwd=target)
        subprocess.call(["jlpm", "add", "puppeteer"], cwd=target)
    shutil.copy(osp.join(here, 'chrome-test.js'), osp.join(target, 'chrome-test.js'))
    return subprocess.check_call(["node", "chrome-test.js", url], cwd=target)


if __name__ == '__main__':
    BrowserApp.launch_instance()
