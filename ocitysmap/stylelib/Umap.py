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

LOG = logging.getLogger('ocitysmap')

def color2hex(name):
    try:
        c = Color(name)
        return c.hex_l
    except:
        LOG.warning("Can't resolve color: %s" % name)
        return name

def first(json, path, default=None):
  try:
    expr = parse(path)
    list = expr.find(json)
    return list[0].value
  except:
    return default

def has(json, path):
  expr = parse(path)
  list = expr.find(json)
  return ( len(list) > 0)

def find(json, path):
  return parse(path).find(json)

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
        icon_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__),
                '../../templates/umap/maki/icons'))

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
            'iconUrl'    : icon_dir + '/circle-15.svg',
        }

        marker_offsets = {
            'Default': -18,
            'Square': -18,
            'Drop'  : -18,
            'Circle': 0,
            'Ball'  : -16
        }

        http = urllib3.PoolManager()

        fp = codecs.open(umap_file, 'r', 'utf-8-sig')

        umap = json.load(fp)

        if has(umap, "$.properties"):
            licence = first(umap, "$.properties.licence.name", "")
            credit  = first(umap, "$.properties.shortCredit" , "")
            if licence or credit:
                self.annotation = "Umap overlay © %s %s" % (licence, credit)

            for prop in ['color', 'opacity', 'fillColor', 'fillOpacity', 'weight', 'dashArray', 'iconClass', 'iconUrl']:
                path = "$.properties.%s" % prop
                val = first(umap, path)
                if val:
                    if prop in ['color', 'fillColor']:
                        val = color2hex(val)
                    umap_defaults[prop] = val

        if 'layers' in umap:
            layers = umap['layers']
        else:
            layers = [ umap ]

        new_features = []

        icon_cache = {}

        for layer in layers:
            layer_defaults = copy.deepcopy(umap_defaults)

            for name in ['_storage', '_storage_options', '_umap_options']:
                if name in layer:
                    for prop in ['color', 'opacity', 'fillColor', 'fillOpacity', 'weight', 'dashArray', 'iconClass', 'iconUrl']:
                        if prop in layer[name]:
                            val = layer[name][prop]
                            if val is True:
                                val = 'yes'
                            if prop in ['color', 'fillColor']:
                                val = color2hex(val)
                            layer_defaults[prop] = val

            for feature in layer['features']:
                new_props = copy.deepcopy(layer_defaults)
                if 'properties' in feature:
                    if name in feature['properties']:
                        for prop in ['name', 'color', 'opacity', 'fillColor', 'fillOpacity', 'weight', 'dashArray', 'fill', 'stroke']:
                            if prop in feature['properties']:
                                val = feature['properties'][prop]
                                if val is True:
                                    val = 'yes'
                                if prop in ['color', 'fillColor']:
                                    val = color2hex(val)
                                new_props[prop] = val
                    for name in ['_storage', '_storage_options', '_umap_options']:
                        if name in feature['properties']:
                            for prop in ['name', 'color', 'opacity', 'fillColor', 'fillOpacity', 'weight', 'dashArray', 'fill', 'stroke']:
                                if prop in feature['properties'][name]:
                                    val = feature['properties'][name][prop]
                                    if val is True:
                                        val = 'yes'
                                    if prop in ['color', 'fillColor']:
                                        val = color2hex(val)
                                    new_props[prop] = val
                if feature['geometry']['type'] == 'Point':
                    iconClass = layer_defaults['iconClass']
                    iconUrl = layer_defaults['iconUrl']

                    if 'properties' in feature:
                        for name in ['_storage', '_storage_options', '_umap_options']:
                            if name in feature['properties']:
                                if 'iconClass' in feature['properties'][name]:
                                    iconClass = feature['properties'][name]['iconClass']
                                if 'iconUrl' in feature['properties'][name]:
                                    iconUrl = feature['properties'][name]['iconUrl']

                    new_props['iconClass'] = iconClass

                    if iconClass == 'Square' or iconClass == 'Drop' or iconClass == 'Default':
                        m = re.match(r'/uploads/pictogram/(.*)-24(.*)\.png', iconUrl)
                        if m:
                            new_props['iconUrl']  = icon_dir + '/' +  m.group(1) + "-15.svg"
                            if m.group(2) == '':
                                new_props['iconFill'] = 'black'
                            else:
                                new_props['iconFill'] = 'white'
                        else:
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
                                except:
                                    iconPath = icon_dir + '/circle-15.svg'

                                new_props['iconUrl'] = iconPath
                                icon_cache[iconUrl] = iconPath

                    try:
                        new_props['offset'] = marker_offsets[iconClass]
                    except:
                        pass

                new_props['weight'] = float(new_props['weight']) / 4

                new_features.append({
                    'type'       : 'Feature', 
                    'properties' : new_props, 
                    'geometry'   : feature['geometry']
                })

        new_umap = {
            'type'     : 'FeatureCollection', 
            'features' : new_features
        }

        LOG.debug("rewritten JSON:\n %s" % json.dumps(new_umap, indent=2))
        return json.dumps(new_umap, indent=2)
