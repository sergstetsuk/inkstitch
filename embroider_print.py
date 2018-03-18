#!/usr/bin/python
#

import sys
import traceback
import os
from threading import Thread
import socket
import errno
import time

import inkex
import inkstitch
from inkstitch import _, PIXELS_PER_MM, SVG_GROUP_TAG
from inkstitch.extensions import InkstitchExtension
from inkstitch.stitch_plan import patches_to_stitch_plan
from inkstitch.svg import render_stitch_plan

from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import date
import base64

from flask import Flask, request
import webbrowser

def datetimeformat(value, format='%Y/%m/%d'):
    return value.strftime(format)


class PrintPreviewServer(Thread):
    def __init__(self, *args, **kwargs):
        self.html = kwargs.pop('html')
        Thread.__init__(self, *args, **kwargs)
        self.daemon = True

        self.__setup_app()

    def __setup_app(self):
        self.app = Flask(__name__)

        @self.app.route('/')
        def index():
            return self.html

        @self.app.route('/shutdown', methods=['POST', 'GET'])
        def shutdown():
            request.environ.get('werkzeug.server.shutdown')()
            return 'Server shutting down...'

        @self.app.route('/dostuff')
        def dostuff():
            print >> sys.stderr, "dostuff called"
            return "do stuff!"

    def run(self):
        self.host = "127.0.0.1"
        self.port = 5000

        while True:
            try:
                self.app.run(self.host, self.port)
            except socket.error, e:
                if e.errno == errno.EADDRINUSE:
                    self.port += 1
                    continue
                else:
                    raise
            else:
                break



class Print(InkstitchExtension):
    def build_environment(self):
        if getattr( sys, 'frozen', False ) :
            template_dir = os.path.join(sys._MEIPASS, "templates")
        else:
            template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates")

        env = Environment(
            loader = FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            # extensions=['jinja2.ext.i18n']
        )

        env.filters['datetimeformat'] = datetimeformat

        return env

    def strip_namespaces(self):
        # namespace prefixes seem to trip up HTML, so get rid of them
        for element in self.document.iter():
            if element.tag[0]=='{':
                element.tag = element.tag[element.tag.index('}',1) + 1:]

    def effect(self):
        if not self.get_elements():
            return

        self.hide_all_layers()

        patches = self.elements_to_patches(self.elements)
        stitch_plan = patches_to_stitch_plan(patches)
        render_stitch_plan(self.document.getroot(), stitch_plan)

        self.strip_namespaces()

        # Now the stitch plan layer will contain a set of groups, each
        # corresponding to a color block.  We'll create a set of SVG files
        # corresponding to each individual color block and a final one
        # for all color blocks together.

        svg = self.document.getroot()
        layers = svg.findall("./g[@{http://www.inkscape.org/namespaces/inkscape}groupmode='layer']")
        stitch_plan_layer = svg.find(".//*[@id='__inkstitch_stitch_plan__']")

        # First, delete all of the other layers.  We don't need them and they'll
        # just bulk up the SVG.
        for layer in layers:
            if layer is not stitch_plan_layer:
                svg.remove(layer)

        overview_svg = inkex.etree.tostring(self.document)

        color_block_groups = stitch_plan_layer.getchildren()

        for i, group in enumerate(color_block_groups):
            # clear the stitch plan layer
            del stitch_plan_layer[:]

            # add in just this group
            stitch_plan_layer.append(group)

            # save an SVG preview
            stitch_plan.color_blocks[i].svg_preview = inkex.etree.tostring(self.document)

        env = self.build_environment()
        template = env.get_template('index.html')

        html = template.render(
            view = {'overview': True, 'detailedview': True},
            logo = {'src' : 'test.png', 'title' : 'LOGO'},
            date = date.today(),
            client = "The name of the long client name thing",
            job = {'title' : 'TITLE OF THE JOB LONG NAME THING', 'totalcolors' : '000', 'totalstops' : '000', 'totaltrims' : '000', 'size' : '0000 x 0000', 'stitchcount' : '000 000 000', 'totalthread' : '000 000 000', 'estimatedtime' : '00h00 @ 000mm/s'},
            svg_complete = overview_svg,
            svg_scale = '1/1',
            color_blocks = stitch_plan.color_blocks,
            num_pages = '2',
        )

        print_preview_server = PrintPreviewServer(html=html)
        print_preview_server.start()

        time.sleep(1)
        webbrowser.open("http://%s:%s/" % (print_preview_server.host, print_preview_server.port))
        print_preview_server.join()

        # don't let inkex print the document out
        sys.exit(0)

    def show_print_preview(self, html):
        cef.Initialize()

        self.browser = cef.CreateBrowserSync(url=html_to_data_uri(html), window_title='Ink/Stitch Print Preview')
        threading.Timer(3.0, self.browser.Print).start()
        cef.MessageLoop()
        cef.Shutdown()

if __name__ == '__main__':
    effect = Print()
    effect.affect()
