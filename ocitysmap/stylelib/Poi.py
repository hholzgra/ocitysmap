# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard

# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

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
