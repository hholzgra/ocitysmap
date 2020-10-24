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

import os
import logging
import configparser


LOG = logging.getLogger('ocitysmap')

def parse_bbox(bbox_str):
    str_parts = bbox_str.split(',')
    lat1 = float(str_parts[0])
    lon1 = float(str_parts[1])
    lat2 = float(str_parts[2])
    lon2 = float(str_parts[3])
    return {'min_lat': min(lat1, lat2),
            'min_lon': min(lon1, lon2),
            'max_lat': max(lat1, lat2),
            'max_lon': max(lon1, lon2)}

class Stylesheet:
    """
    A Stylesheet object defines how the map features will be rendered. It
    contains information pointing to the Mapnik stylesheet and other styling
    parameters.
    """
    DEFAULT_ZOOM_LEVEL = 16

    def __init__(self):
        self.name        = None # str
        self.path        = None # str
        self.description = '' # str
        self.annotation  = '' # str
        self.datasource  = '' # str
        self.url         = '' # str
        self.group       = '' # str
        self.aliases     = [] # array of str

        self.exclude_layers = []

        self.grid_line_color = 'black'
        self.grid_line_alpha = 0.5
        self.grid_line_width = 1

        self.shade_color = 'black'
        self.shade_alpha = 0.1

        # shade color for town contour in multi-pages
        self.shade_color_2 = 'white'
        self.shade_alpha_2 = 0.4

        # optionally limit style choice to a specific area
        self.bbox        = None

    @staticmethod
    def create_from_config_section(parser, section_name):
        """Creates a Stylesheet object from the OCitySMap configuration.

        Args:
            parser (ConfigParser.ConfigParser): the configuration parser
                object.
            section_name (string): the stylesheet section name in the
                configuration.
        """
        s = Stylesheet()

        def assign_if_present(key, cast_fn=str):
            if parser.has_option(section_name, key):
                setattr(s, key, cast_fn(parser.get(section_name, key)))

        def assign_list_if_present(key):
            if parser.has_option(section_name, key):
                setattr(s, key, parser.get(section_name, key).split(','))

        s.name = parser.get(section_name, 'name')
        s.path = parser.get(section_name, 'path')
        if not s.path.startswith('internal:') and not os.path.exists(s.path):
            raise ValueError(
                'Could not find stylesheet file for stylesheet %s!' % s.name)
        assign_if_present('description')
        assign_if_present('annotation')
        assign_if_present('datasource')
        assign_if_present('url')
        assign_if_present('group')
        assign_list_if_present('aliases')

        assign_if_present('grid_line_color')
        assign_if_present('grid_line_alpha', float)
        assign_if_present('grid_line_width', int)

        assign_if_present('shade_color')
        assign_if_present('shade_alpha', float)

        assign_if_present('shade_color_2')
        assign_if_present('shade_alpha_2', float)

        assign_if_present('bbox', parse_bbox)

        assign_list_if_present('exclude_layers')

        return s

    @staticmethod
    def create_all_from_config(parser, type='stylesheets'):
        try:
            styles = parser.get('rendering', 'available_'+type)
        except (configparser.NoOptionError, ValueError):
            return []

        results = []

        for name in styles.split(','):
            try:
                results.append(Stylesheet.create_from_config_section(parser, name.strip()))
            except Exception:
                LOG.warning("%s overlay '%s' not found or incomplete" % (type, name.strip()))

        return results

from .Gpx import GpxStylesheet
from .Umap import UmapStylesheet
from .Poi import PoiStylesheet

