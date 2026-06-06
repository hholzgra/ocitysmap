# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from . import Stylesheet
from coords import BoundingBox

import os
import tempfile
from string import Template
import gpxpy
import gpxpy.gpx
import codecs
import logging
from shapely.geometry import LineString

LOG = logging.getLogger('ocitysmap')

class GpxProcessor:
    def __init__(self, gpx_file):
        gpx_fp = codecs.open(gpx_file, 'r', 'utf-8-sig')
        self.gpx = gpxpy.parse(gpx_fp)
        gpx_fp.close()
            
    def getBoundingBox(self):
        b = self.gpx.get_bounds()
        return BoundingBox(b.min_latitude, b.min_longitude, b.max_latitude, b.max_longitude)

    def getTitle(self):
        return self.gpx.name.strip()

    def getAnnotation(self):
        return None

class GpxStylesheet(Stylesheet):
    def __init__(self, gpx_file, tmpdir, track_color = '#7f7f7f'):
        super().__init__()

        self.linestrings = []

        gpx_fp = codecs.open(gpx_file, 'r', 'utf-8-sig')
        gpx = gpxpy.parse(gpx_fp)
        gpx_fp.close()

        if gpx.copyright_year or gpx.copyright_author or gpx.copyright_license:
            self.annotation = "GPX track © %s %s %s" % (gpx.copyright_year, gpx.copyright_author, gpx.copyright_license)

        template_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__),
                '../../templates/gpx'))

        style_template_file = os.path.join(template_dir, 'style-template.xml')
        layer_template_file = os.path.join(template_dir, 'layer-template.xml')

        GPX_filename = tempfile.mktemp(suffix='.xml', dir=tmpdir)
        tmpfile = open(GPX_filename, 'w')

        layer_text = ""

        with open(layer_template_file, 'r') as layer_template:
            tmplayer = Template(layer_template.read())

        if  len(gpx.tracks):
            nonempty_tracks = 0
            for track in gpx.tracks:
                for segment in track.segments:
                    if len(segment.points) > 0:
                        nonempty_tracks = nonempty_tracks + 1
                        l = LineString([(x.longitude, x.latitude) for x in segment.points])
                        self.linestrings.append(l)
            if nonempty_tracks > 0:
                layer_text += tmplayer.substitute(
                    gpxfile = gpx_file,
                    layername = "tracks"
                )

        if  len(gpx.routes):
            nonempty_routes = 0
            for route in gpx.routes:
                if len(route.points) > 0:
                    nonempty_routes = nonempty_routes + 1
                    l = LineString([(x.longitude, x.latitude) for x in route.points])
                    self.linestrings.append(l)
            if nonempty_routes > 0:
                layer_text += tmplayer.substitute(
                    gpxfile = gpx_file,
                    layername = "routes"
                )

        if  len(gpx.waypoints):
            layer_text += tmplayer.substitute(
                gpxfile = gpx_file,
                layername = "waypoints"
            )

        with open(style_template_file, 'r') as style_template:
            tmpstyle = Template(style_template.read())
            tmpfile.write(
                tmpstyle.substitute(
                    gpxfile = gpx_file,
                    svgdir = template_dir,
                    color  = track_color,
                    layers = layer_text
                ))

        tmpfile.close()

        self.name = "GPX overlay"
        self.path = GPX_filename
