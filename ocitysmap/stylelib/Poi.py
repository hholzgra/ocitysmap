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

import os
import shutil
import tempfile
from string import Template

import logging

LOG = logging.getLogger('ocitysmap')

class PoiStylesheet(Stylesheet):
    def __init__(self, poi_file, tmpdir, poi_index):
        super().__init__()

        template_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__),
                '../../templates/poi_markers'))
        
        template_file = os.path.join(template_dir, 'template.xml')
        style_filename = tempfile.mktemp(suffix='.xml', dir=tmpdir)
        tmpfile = open(style_filename, 'w')        

        position_data = "lat,lon\n%f,%f\n" % (poi_index.lat, poi_index.lon)

        n = 0
        marker_data = "number,lat,lon,color\n"
        for category in poi_index.categories:
            for poi in category.items:
                n = n + 1
                lat, lon = poi.endpoint1.get_latlong()
                marker_data += "%d,%f,%f,%s\n" % (n, lat, lon, category.color)
                
        with open(template_file, 'r') as style_template:
            tmpstyle = Template(style_template.read())
            tmpfile.write(
                tmpstyle.substitute(
                    svgdir = template_dir,
                    position_data = position_data,
                    marker_data = marker_data
                ))
        tmpfile.close()

        shutil.copyfile(style_filename, "/tmp/poi_style")

        self.name = "POI overlay"
        self.path = style_filename
