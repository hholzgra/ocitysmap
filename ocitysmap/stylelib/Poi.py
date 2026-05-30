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

import codecs
import json

import logging

LOG = logging.getLogger('ocitysmap')

class PoiProcessor:
    def __init__(self, poi_file):
        fp = codecs.open(poi_file, "r", "utf-8-sig")
        self.poi = json.load(fp)
        fp.close()

    def getBoundingBox(self):
        min_lat = float(self.poi['center_lat'])
        max_lat = float(self.poi['center_lat'])
        min_lon = float(self.poi['center_lon'])
        max_lon = float(self.poi['center_lon'])

        for group in self.poi['nodes']:
            for node in group['nodes']:
                min_lat = min(min_lat, node['lat'])
                min_lon = min(min_lon, node['lon'])
                max_lat = max(max_lat, node['lat'])
                max_lon = max(max_lon, node['lon'])

        return BoundingBox(min_lat, min_lon, max_lat, max_lon)

    def getTitle(self):
        try:
            return self.poi['title']
        except Exception:
            return None

class PoiStylesheet(Stylesheet):
    def __init__(self, poi_file, tmpdir):
        super().__init__()

        self.name = "POI overlay"
        self.path = "internal:poi_markers"
