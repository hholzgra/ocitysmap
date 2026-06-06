# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard
# Copyright (C) 2020 Hartmut Holzgraefe

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
import cairo
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
import codecs
import json
from colour import Color
import re
from gettext import gettext

import ocitysmap
import ocitysmap.layoutlib.commons as UTILS

from .commons import Index, IndexCategory, IndexItem # TODO:  IndexDoesNotFitError
from .renderer import IndexRenderingArea

import logging
LOG = logging.getLogger('ocitysmap')

class PoiIndexCategory(IndexCategory):
    name  = None
    color = None
    col_r = 0
    col_g = 0
    col_b = 0
    icon  = None
    items = None

    def __init__(self, name, items=None, color=None, icon=None):
        IndexCategory.__init__(self, name, items)
        self.color = color

        c = Color(color)
        self.col_r = c.red
        self.col_g = c.green
        self.col_b = c.blue

        self.icon  = icon


    def draw(self, rtl, ctx, pc, layout, fascent, fheight,
             baseline_x, baseline_y):
        ctx.save()

        ctx.set_source_rgb(self.col_r, self.col_g, self.col_b)

        ctx.restore()


class PoiIndexItem(IndexItem):

    __slots__    = ['icon']
    # icon = None

    def __init__(self, label, coords, icon=None):
        IndexItem.__init__(self, label, coords, None)
        self.icon = icon


class PoiIndex(Index):
    name = "POI"
    description = gettext(u"POI marker index")

    def __init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number=None):
        # import the first POI file only (there should never be more than one)
        for (file_type, import_file) in renderer.rc.import_files:
            if file_type == 'poi':
                f = codecs.open(import_file, "r", "utf-8-sig")
                self._read_json(f)
                f.close()
                break

    @property
    def lat(self):
        return self._center_lat

    @property
    def lon(self):
        return self._center_lon

    def _read_json(self, f):
        self._categories = []

        try:
            j = json.load(f)
        except ValueError as e:
            LOG.warning('invalid json in POI file: %s' % e)
            return False

        title = j['title']
        self._center_lat = float(j['center_lat'])
        self._center_lon = float(j['center_lon'])

        for cat in j['nodes']:
            c = PoiIndexCategory(cat['text'], color=cat['color'], icon=cat['icon'])
            for node in cat['nodes']:
                try:
                    c.items.append(
                        PoiIndexItem(node['text'],
                                     ocitysmap.coords.Point(float(node['lat']),
                                                            float(node['lon'])),
                                     icon = node['icon']))
                except Exception as ex:
                    LOG.warning("Could not add POI index item: %s" % str(ex))
                    pass

            self._categories.append(c)
        return True

    def write_to_csv(self, title, output_filename):
        return


class PoiIndexRenderer:

    def __init__(self, i18n, index_categories):
        self._index_categories = index_categories

    def precompute_occupation_area(self, surface, x, y, w, h,
                                   freedom_direction, alignment):

        if (freedom_direction != 'width' or alignment != 'right'):
            raise ValueError('Incompatible freedom direction and alignment!')

        x += w * 0.2
        w = w * 0.8

        area = IndexRenderingArea("default_poi_style",
                                  x, y, w, h, 1)

        return area

    def _render_header(self, ctx, area, dpi, color, label, logo = None):
        """
        Render index category header bar
        """
        f = dpi / UTILS.PT_PER_INCH

        ctx.save()

        # keep a little distance from the outer frame
        ctx.translate(10*f, 10*f)

        # draw colored background bar
        c = Color(color)
        ctx.set_source_rgb(c.red, c.green, c.blue)
        ctx.rectangle( 0, 0, (area.w - 20)*f, dpi * 0.8)
        ctx.fill()

        # keep a little distance from color bar outline to content
        x = 5*f

        # show logo if one is defined and found
        if logo is not None:
            logo_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), '..', '..', 'templates', 'poi_markers', 'Font-Awesome-SVG-PNG', 'white', 'svg', logo + '.svg'))

            if os.path.isfile(logo_path):
                rsvg = Rsvg.Handle()
                svg = rsvg.new_from_file(logo_path)

                scale = dpi * 0.6 / svg.props.height
                x += svg.props.width * scale + 10*f

                ctx.save()
                ctx.translate(5*f, 5*f)
                ctx.scale(scale, scale)
                svg.render_cairo(ctx)
                ctx.restore()
            else:
                LOG.warning("icon not found %s" % logo_path)

        # print category name in white
        ctx.set_source_rgb(1, 1, 1)
        ctx.select_font_face("Droid Sans Bold",
                             cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(dpi*0.6)
        x_bearing, y_bearing, width, height = ctx.text_extents(label)[:4]
        ctx.move_to(x, 10*f - y_bearing)
        ctx.show_text(label)
        ctx.restore()

        return dpi * 0.8

    def _render_item(self, ctx, area, dpi, color, number, label, gridlabel, logo = None):
        """
        Render a single item line
        """
        f = dpi / UTILS.PT_PER_INCH
        x = 5*f

        # clip the index row area
        ctx.save()
        ctx.rectangle( 0, 0, area.w * f, dpi * 0.7)
        ctx.clip()

        # find the marker icon
        marker_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'images', 'marker.svg'))
        fp = open(marker_path,'r')
        data = fp.read()
        fp.close()

        # replace black with the actual marker color
        if color[0] != '#':
            c = Color(color)
            color = c.hex_l
        data = data.replace('#000000', color)

        # create actual SVG marker
        rsvg = Rsvg.Handle()
        svg = rsvg.new_from_data(data.encode())

        # scale the marker to correct size
        scale = 50.0 * f / svg.props.height
        x += 35*f

        # draw the marker
        ctx.save()
        ctx.scale(scale, scale)
        svg.render_cairo(ctx)
        ctx.restore()

        # put the marker number into the center of the marker circle
        ctx.save()
        ctx.set_source_rgb(0, 0, 0)
        ctx.select_font_face("Droid Sans Mono",
                             cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)

        x_bearing, y_bearing, width, height = ctx.text_extents(number)[:4]
        ctx.set_font_size((dpi*0.6)/(len(number)+1))
        ctx.move_to(20*f - f*width/2, 25*f)
        ctx.show_text(number)
        ctx.restore()

        # add item logo if defined and found
        if logo is not None:
            logo_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), '..', '..', 'templates', 'poi_markers', 'Font-Awesome-SVG-PNG', 'black', 'svg', logo + '.svg'))

            if os.path.isfile(logo_path):
                rsvg = Rsvg.Handle()
                svg = rsvg.new_from_file(logo_path)

                scale = min(dpi * 0.6 / svg.props.height, dpi * 0.6 / svg.props.width)

                ctx.save()
                ctx.translate(x + 5, 5*f)
                ctx.scale(scale, scale)
                svg.render_cairo(ctx)
                ctx.restore()

                x += svg.props.width * scale + 10*f
            else:
                LOG.warning("icon not found %s" % logo_path)

        # print marker text
        ctx.save()
        ctx.set_source_rgb(0, 0, 0)
        ctx.select_font_face("Droid Sans",
                             cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        ctx.set_font_size(dpi*0.6)
        x_bearing, y_bearing, width, height, x_adv, y_adv = ctx.text_extents(label)
        ctx.move_to(x, 10*f - y_bearing)
        ctx.show_text(label)

        # print grid coordinate
        ctx.select_font_face("Aerial Mono",
                             cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)

        gridParts = re.match('^([A-Z]+)([0-9]+)$', gridlabel)
        gridlabel = gridParts.group(1) + '-' + gridParts.group(2)

        x_bearing, y_bearing, width, height, x_adv, y_adv = ctx.text_extents(gridlabel)

        # white background (clear long label text)
        # IDEA: make this fade slowly instead of cutting hard?
        ctx.set_source_rgb(1, 1, 1)
        ctx.rectangle( (area.w - 15)*f - x_adv - width/4, 8*f, width * 2, height + 4*f)
        ctx.fill()

        # black grid coordinate text
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to((area.w - 15)*f - x_adv, 10*f + height)
        ctx.show_text(gridlabel)

        ctx.restore()

        ctx.restore()

        # return fixed row height
        return dpi * 0.7

    def render(self, ctx, area, dpi = UTILS.PT_PER_INCH):
        f = dpi / UTILS.PT_PER_INCH

        ctx.save()
        ctx.translate(area.x*f, area.y*f)
        ctx.set_source_rgb(1, 1, 1)
        ctx.rectangle(0, 0, area.w*f, area.h*f)
        ctx.clip()
        ctx.fill()

        n = 0

        for category in self._index_categories:
            dy = self._render_header(ctx, area, dpi, category.color, category.name, category.icon)
            ctx.translate(0, dy + 20)

            for poi in category.items:
                n = n + 1
                lat, lon = poi.endpoint1.get_latlong()
                dy = self._render_item(ctx, area, dpi, category.color, str(n), poi.label, poi.location_str, poi.icon)
                ctx.translate(0, dy + 10)

        ctx.restore()

