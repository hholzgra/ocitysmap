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

import logging

import mapnik
if True:  # hack to prevent consecutive E402 warings
    assert mapnik.mapnik_version() >= 300000, \
        "Mapnik module version %s is too old, see ocitysmap's INSTALL " \
        "for more details." % mapnik.mapnik_version_string()

import math
import os

import ocitysmap
from ocitysmap.layoutlib.commons import convert_pt_to_dots
import ocitysmap.maplib.shapes

LOG = logging.getLogger('ocitysmap')

_MAPNIK_PROJECTION = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 " \
                     "+lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m   " \
                     "+nadgrids=@null +no_defs +over"

class MapCanvas:
    """
    The MapCanvas renders a geographic bounding box into a Cairo surface of a
    given width and height (in pixels). Shape files can be overlayed on the
    map; the order they are added to the map being important with regard to
    their respective alpha levels.
    """

    def __init__(self, stylesheet, bounding_box, _width, _height, dpi=72.0,
                 extend_bbox_to_ratio=True):
        """Initialize the map canvas for rendering.

        Args:
            stylesheet (Stylesheet): map stylesheet.
            bounding_box (coords.BoundingBox): geographic bounding box.
            graphical_ratio (float): ratio of the map area (width/height).
            dpi (float): map resolution (default: 72dpi)
            extend_bbox_to_ratio (boolean): allow MapCanvas to extend
            the bounding box to make it match the ratio of the
            provided rendering area. Needed by SinglePageRenderer.
        """

        self._style_name = stylesheet.name
        self._proj = ocitysmap.coords.get_proj_transformation()
        self._dpi  = dpi

        # This is where the magic of the map canvas happens. Given an original
        # bounding box and a graphical ratio for the output, the bounding box
        # is adjusted (extended) to fill the destination zone. See
        # _fix_bbox_ratio for more details on how this is done.
        orig_envelope = self._project_envelope(bounding_box)
        graphical_ratio = _width / _height

        if extend_bbox_to_ratio:
            off_x, off_y, width, height = self._fix_bbox_ratio(
                orig_envelope.minx, orig_envelope.miny,
                orig_envelope.width(), orig_envelope.height(),
                graphical_ratio)

            envelope = mapnik.Box2d(off_x, off_y, off_x+width, off_y+height)
            self._geo_bbox = self._inverse_envelope(envelope)
            LOG.debug('Corrected bounding box from %s to %s, ratio: %.2f.' %
                      (bounding_box, self._geo_bbox, graphical_ratio))
        else:
            envelope = orig_envelope
            self._geo_bbox = bounding_box

        g_width  = int(convert_pt_to_dots(_width, dpi))
        g_height = int(convert_pt_to_dots(_height, dpi))

        # Create the Mapnik map with the corrected width and height and zoom to
        # the corrected bounding box ('envelope' in the Mapnik jargon)
        self._map = mapnik.Map(g_width, g_height, _MAPNIK_PROJECTION)
        mapnik.load_map(self._map, stylesheet.path)
        self._map.zoom_to_box(envelope)

        # exclude layers based on configuration setting "exclude_layers"
        for layer in self._map.layers:
            if layer.name in stylesheet.exclude_layers:
                LOG.debug("Excluding layer: %s" % layer.name)
                layer.status = False

        # Added shapes to render
        self._shapes = []

        LOG.debug('MapCanvas rendering map on %dx%dpx.' % (g_width, g_height))

    def _fix_bbox_ratio(self, off_x, off_y, width, height, dest_ratio):
        """Adjusts the area expressed by its origin's offset and its size to
        the given destination ratio by tweaking one of the two dimensions
        depending on the current ratio and the destination ratio."""
        cur_ratio = float(width)/height

        if cur_ratio < dest_ratio:
            w = width
            width *= float(dest_ratio)/cur_ratio
            off_x -= (width - w)/2.0
        else:
            h = height
            height *= float(cur_ratio)/dest_ratio
            off_y -= (height - h)/2.0

        return map(int, (off_x, off_y, width, height))

    def add_shape_file(self, shape_file, str_color='grey', alpha=0.5,
                       line_width=1.0):
        """
        Args:
            shape_file (shapes.ShapeFile): path to the shape file to overlay on
                this map canvas.
            str_color (string): litteral name of the layer's color, needs to be
                understood by mapnik.Color.
            alpha (float): transparency factor in the range 0 (invisible) -> 1
                (opaque).
            line_width (float): line width for the features that will be drawn.
        """
        col = mapnik.Color(str_color)
        col.a = int(255 * alpha)
        self._shapes.append({'shape_file': shape_file,
                             'color': col,
                             'line_width': line_width})
        LOG.debug('Added shape file %s to map canvas as layer %s.' %
                  (shape_file.get_filepath(), shape_file.get_layer_name()))

    def render(self):
        """Render the map in memory with all the added shapes. The Mapnik Map
        object can be accessed with self.get_rendered_map()."""

        # Add all shapes to the map
        for shape in self._shapes:
            self._render_shape_file(**shape)

    def get_rendered_map(self):
        return self._map

    def get_style_name(self):
        return self._style_name

    def get_actual_bounding_box(self):
        """Returns the actual geographic bounding box that will be rendered by
        Mapnik."""
        return self._geo_bbox

    def get_actual_scale(self):
        # get the scale denominator computed by mapnik
        scale = self._map.scale_denominator()
        # the actual scale depends on the latitude
        lat = self._geo_bbox.get_top_left()[0]
        scale *= math.cos(math.radians(lat))
        # by convention, the scale denominator uses 90 ppi whereas cairo uses 72 ppi
        scale *= float(self._dpi) / 90
        return scale

    def _render_shape_file(self, shape_file, color, line_width):
        LOG.debug("render_shape_file")
        shape_file.flush()

        shpid = os.path.basename(shape_file.get_filepath())
        s, r = mapnik.Style(), mapnik.Rule()

        poly_sym = mapnik.PolygonSymbolizer()
        poly_sym.fill = color
        r.symbols.append(poly_sym)
        line_sym = mapnik.LineSymbolizer()
        line_sym.stroke = color
        line_sym.stroke_width = float(line_width)
        r.symbols.append(line_sym)
        s.rules.append(r)

        self._map.append_style('style_%s' % shpid, s)
        layer = mapnik.Layer(shpid)
        layer.datasource = mapnik.Shapefile(file=shape_file.get_filepath())
        layer.styles.append('style_%s' % shpid)

        self._map.layers.append(layer)

    def _project_envelope(self, bbox):
        """Project the given bounding box into the rendering projection."""
        envelope = mapnik.Box2d(bbox.get_top_left()[1],
                                bbox.get_top_left()[0],
                                bbox.get_bottom_right()[1],
                                bbox.get_bottom_right()[0])
        c0 = self._proj.forward(mapnik.Coord(envelope.minx, envelope.miny))
        c1 = self._proj.forward(mapnik.Coord(envelope.maxx, envelope.maxy))
        return mapnik.Box2d(c0.x, c0.y, c1.x, c1.y)

    def _inverse_envelope(self, envelope):
        """Inverse the given cartesian envelope (in 3587) back to a 4326
        bounding box."""
        c0 = self._proj.backward(mapnik.Coord(envelope.minx, envelope.miny))
        c1 = self._proj.backward(mapnik.Coord(envelope.maxx, envelope.maxy))
        return ocitysmap.coords.BoundingBox(c0.y, c0.x, c1.y, c1.x)

if __name__ == '__main__':
    import shapes

    logging.basicConfig(level=logging.DEBUG)

    class StylesheetMock:
        def __init__(self):
            self.path = '/home/sam/src/python/maposmatic/mapnik-osm/osm.xml'

    bbox = ocitysmap.coords.BoundingBox(48.7148, 2.0155, 48.6950, 2.0670)
    canvas = MapCanvas(StylesheetMock(), bbox, 297.0/210)
    new_bbox = canvas.get_actual_bounding_box()

    canvas.add_shape_file(
        shapes.LineShapeFile(new_bbox, '/tmp/mygrid.shp', 'grid')
        .add_vert_line(2.04)
        .add_horiz_line(48.7),
        'red', 0.3, 10.0)

    canvas.add_shape_file(
        shapes.PolyShapeFile(new_bbox, '/tmp/mypoly.shp', 'shade')
        .add_shade_from_wkt('POLYGON((2.04537559754772 48.702794853359,2.0456929723376 48.7033682610593,2.0457757970068 48.7037022715908,2.04577876144723 48.7043963708738,2.04589724923321 48.7043963708738,2.04589428479277 48.704519562418,2.04746445007788 48.7044706533954,2.04723043894637 48.7024665875529,2.04674876229103 48.7024238422904,2.04615641319268 48.702500973452,2.04537559754772 48.702794853359))'),
        'blue', 0.3)

    canvas.render()
    mapnik.render_to_file(canvas.get_rendered_map(), '/tmp/mymap.png', 'png')

    print("Generated /tmp/mymap.png")
