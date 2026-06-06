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
import json
import re
import urllib3
import tempfile
import logging
from string import Template
import codecs
import copy
from colour import Color
from jsonpath_ng import parse
import validators
import glob

LOG = logging.getLogger('ocitysmap')

def color2hex(name):
    try:
        c = Color(name)
        return c.hex_l
    except (AttributeError, ValueError):
        return name

# get first match for a JSONpath search only
def first(json, path, default=None):
    try:
        expr = parse(path)
        list = expr.find(json)
        return list[0].value
    except Exception:
        return default

# confinence wrapper for JSONpath parse->find
def find(json, path):
    return parse(path).find(json)

# return JSONpath find() results as flattened array
# where the dict key is converted to a plain string
# for easy lookups by key
def flattened(json, path):
    result = {}
    for match in find(json, path):
        result[str(match.path)] = match.value
    return result

# UMAP files store style properties in different places
# depending on where in the UMAP file we are, so we
# iterate over all the different possible paths for a
# one-size-fits-all lookup
def get_default_properties(json, umap_defaults, create_copy=True):
    if create_copy:
        umap_defaults = copy.deepcopy(umap_defaults)

    values = {}
    for path in ['$.properties.*', '$.properties._storage.*', '$._storage.*', '$.properties._storage_options.*', '$._storage_options.*', '$.properties._umap_options.*', '$._umap_options.*']:
        for key,value in flattened(json, path).items():
            if key in ['name', 'opacity', 'fillOpacity', 'weight', 'dashArray', 'iconClass', 'iconUrl']:
                if value is True:
                    value = 'yes'
                values[key] = value
            elif key in ['color', 'fillColor']:
                values[key] = color2hex(value)

    # fillColor defaults to color if not set
    if 'color' in values and 'fillColor' not in values:
        values['fillColor'] = values['color']

    for key, value in values.items():
        umap_defaults[key] = value

    if create_copy:
        return umap_defaults

def _find_icon(basedir, basename):
    for match in glob.glob("%s/%s*" % (basedir, basename)):
        if os.path.isfile(match):
            return match
    return None


class UmapProcessor:
    def __init__(self, umap_file):
        fp = codecs.open(umap_file, 'r', 'utf-8-sig')
        self.umap = json.load(fp)
        fp.close()

    def getBoundingBox(self):
        lon_vals = []
        lat_vals = []

        # UMAP files have one or more layers with extended GeoJSON within
        # general GeoJson files do not have that, but by treating the whole
        # file as a layer we can render both general GeoJSON and UMAP files
        if 'layers' in self.umap:
            layers = self.umap['layers']
        else:
            layers = [ self.umap ]

        for layer in layers:
            for feature in layer['features']:
                geom = feature['geometry']
                for coord in geom['coordinates']:
                    if isinstance(coord, float):  # then its a point feature
                        lon_vals.append(geom['coordinates'][0])
                        lat_vals.append(geom['coordinates'][1])
                    elif isinstance(coord, list):
                        for c in coord:
                            if isinstance(c, float):  # then its a linestring feature
                                lon_vals.append(coord[0])
                                lat_vals.append(coord[1])
                            elif isinstance(c, list):  # then its a polygon feature
                                lon_vals.append(c[0])
                                lat_vals.append(c[1])

        return BoundingBox(min(lat_vals), min(lon_vals), max(lat_vals), max(lon_vals))

    def getTitle(self):
        try:
            return self.umap['properties']['name']
        except (KeyError, TypeError):
            return None

class UmapStylesheet(Stylesheet):
    def __init__(self, umap_file, tmpdir):
        super().__init__()

        template_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__),
                '../../templates/umap'))

        json_filename = tempfile.mktemp(suffix='.json', dir=tmpdir)
        json_tmpfile = open(json_filename, 'w')
        json_tmpfile.write(self.umap_preprocess(umap_file, tmpdir))
        json_tmpfile.close()

        template_file = os.path.join(template_dir, 'template.xml')
        style_filename = tempfile.mktemp(suffix='.xml', dir=tmpdir)
        style_tmpfile = open(style_filename, 'w')

        with open(template_file, 'r') as style_template:
            tmpstyle = Template(style_template.read())
            style_tmpfile.write(
                tmpstyle.substitute(
                    umapfile = json_filename,
                    basedir  = template_dir
                ))

        style_tmpfile.close()

        self.name = "UMAP overlay"
        self.path = style_filename

    def umap_preprocess(self, umap_file, tmpdir):
        maki_icon_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__),
                '../../templates/umap/maki/icons'))

        osmic_icon_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__),
                '../../templates/umap/osmic'))

        umap_defaults = {
            'color'      :'#0000ff',
            'opacity'    :      0.5,
            'fillColor'  :'#0000ff',
            'fillOpacity':      0.2,
            'weight'     :        3,
            'dashArray'  :       '',
            'fill'       :    'yes',
            'stroke'     :    'yes',
            'name'       :       '',
            'iconClass'  : 'Square',
            'iconUrl'    : maki_icon_dir + '/circle-15.svg',
            'iconFill'   : "white",
        }

        marker_offsets = {
            'Default': -18,
            'Square' : -18,
            'Drop'   : -18,
            'Circle' :   0,
            'Ball'   : -16,
        }

        http = urllib3.PoolManager()

        fp = codecs.open(umap_file, 'r', 'utf-8-sig')

        umap = json.load(fp)

        # extract license & credit annotation information
        licence = first(umap, "$.properties.licence.name", "")
        credit  = first(umap, "$.properties.shortCredit" , "")
        if licence or credit:
            self.annotation = "Umap overlay © %s %s" % (licence, credit)

        # override default properties with global defaults from the file
        get_default_properties(umap, umap_defaults, create_copy=False)

        # UMAP files have one or more layers with extended GeoJSON within
        # general GeoJson files do not have that, but by treating the whole
        # file as a layer we can render both general GeoJSON and UMAP files
        if 'layers' in umap:
            layers = umap['layers']
        else:
            layers = [ umap ]

        new_features = []
        icon_cache = {}

        # go over all layers now
        for layer in layers:
            # layers can have default properties for all their features
            # overriding the global defaults
            layer_defaults = get_default_properties(layer, umap_defaults)

            # now go over the actual geometry features in that layer
            for feature in layer['features']:
                if not feature['geometry']['coordinates']:
                    continue
                try:
                    # feature properties override previous defaults
                    new_props = get_default_properties(feature, layer_defaults)

                    # POINT features require special handling as they actually
                    # usually represent a marker
                    if feature['geometry']['type'] == 'Point':
                        iconClass = new_props['iconClass']
                        iconUrl   = new_props['iconUrl']

                        # if icon class is one of those used by Umap:
                        if iconClass in ['Circle', 'Square', 'Drop', 'Default']:
                            # check whether one of the default UMAP icons is used
                            # by known URL pattern, or external
                            if validators.url(iconUrl):
                                # external URL: use cached if present already,
                                # otherwise download it and cache for later re-use
                                if iconUrl in icon_cache:
                                    new_props['iconUrl'] = icon_cache[iconUrl]
                                else:
                                    try:
                                        filename, file_extension = os.path.splitext(iconUrl)
                                        response = http.request('GET', iconUrl)
                                        iconFile = tempfile.NamedTemporaryFile(suffix=file_extension, delete=False, mode='wb', dir=tmpdir)
                                        iconFile.write(response.data)
                                        iconFile.close()

                                        iconPath = os.path.realpath(iconFile.name)
                                    except Exception as Argument:
                                        LOG.exception("Could not get icon from URL %s" % iconUrl)
                                        iconPath = maki_icon_dir + '/circle-15.svg'

                                    new_props['iconUrl'] = iconPath
                                    icon_cache[iconUrl] = iconPath
                            elif m := re.match(r'/uploads/pictogram/(.*)-24(.*)\.png', iconUrl):
                                # known UMAP icon URL -> replace with local files on our server
                                # there are different naming conventions
                                # the .fr server has basename-24.png for black maki icons
                                #         and basename-24_1.png for white ones
                                # the .de server has basename-24_???????.png for black osmic icons
                                if m.group(2) == '':
                                    new_props['iconUrl']  = maki_icon_dir + '/' +  m.group(1) + "-15.svg"
                                    new_props['iconFill'] = 'white'
                                elif m.group(2) == '_1':
                                    new_props['iconUrl']  = maki_icon_dir + '/' +  m.group(1) + "-15.svg"
                                    new_props['iconFill'] = 'white'
                                else:
                                    icon_path = _find_icon(osmic_icon_dir + "/*", m.group(1))
                                    if icon_path is None:
                                        icon_path =  maki_icon_dir + '/circle-15.svg'
                                    new_props['iconUrl']  = icon_path
                                    new_props['iconFill'] = 'black'
                            elif iconUrl[0] != '/' or len(iconUrl) < 10:
                                # short text or not a file path: use as verbatim text label
                                new_props['iconLabel'] = iconUrl
                                new_props['iconUrl']   = ''

                        if iconClass in marker_offsets:
                            new_props['offset'] = marker_offsets[iconClass]

                    new_props['weight'] = float(new_props['weight']) / 4

                    new_features.append({
                        'type'       : 'Feature',
                        'properties' : new_props,
                        'geometry'   : feature['geometry']
                    })
                except Exception as Argument:
                    LOG.warning("Exception: %s" % Argument)

        new_umap = {
            'type'     : 'FeatureCollection',
            'features' : new_features
        }

        LOG.debug("rewritten JSON:\n %s" % json.dumps(new_umap, indent=2))
        return json.dumps(new_umap, indent=2)
