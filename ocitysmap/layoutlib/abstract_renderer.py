# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2012  David Decotigny
# Copyright (C) 2012  Frédéric Lehobey
# Copyright (C) 2012  Pierre Mauduit
# Copyright (C) 2012  David Mentré
# Copyright (C) 2012  Maxime Petazzoni
# Copyright (C) 2012  Thomas Petazzoni
# Copyright (C) 2012  Gaël Utard
# Copyright (C) 2012  Étienne Loks

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

import cairo
import rsvg
import logging
import mapnik
assert mapnik.mapnik_version >= 200100, \
    "Mapnik module version %s is too old, see ocitysmap's INSTALL " \
    "for more details." % mapnik.mapnik_version_string()
import math
import pango
import os
import re
import shapely.wkt
import sys

import commons
from ocitysmap.maplib.map_canvas import MapCanvas
from ocitysmap.maplib.grid import Grid
from ocitysmap import draw_utils, maplib

LOG = logging.getLogger('ocitysmap')


class Renderer:
    """
    The job of an OCitySMap layout renderer is to lay out the resulting map and
    render it from a given rendering configuration.
    """
    name = 'abstract'
    description = 'The abstract interface of a renderer'

    # The PRINT_SAFE_MARGIN_PT is a small margin we leave on all page borders
    # to ease printing as printers often eat up margins with misaligned paper,
    # etc.
    PRINT_SAFE_MARGIN_PT = 15

    GRID_LEGEND_MARGIN_RATIO = .02

    # The DEFAULT_KM_IN_MM represents the minimum acceptable mapnik scale
    # 12000 ensures that the zoom level will be 16 or higher
    # see entities.xml.inc file from osm style sheet
    DEFAULT_SCALE = 12000

    def __init__(self, db, rc, tmpdir, dpi):
        """
        Create the renderer.

        Args:
           rc (RenderingConfiguration): rendering parameters.
           tmpdir (os.path): Path to a temp dir that can hold temp files.
           street_index (StreetIndex): None or the street index object.
        """
        # Note: street_index may be None
        self.db           = db
        self.rc           = rc
        self.tmpdir       = tmpdir
        self.grid         = None # The implementation is in charge of it

        self.paper_width_pt = \
                commons.convert_mm_to_pt(self.rc.paper_width_mm)
        self.paper_height_pt = \
                commons.convert_mm_to_pt(self.rc.paper_height_mm)

    @staticmethod
    def _get_osm_logo(ctx, height):
        """
        Read the OSM logo file and rescale it to fit within height.

        Args:
           ctx (cairo.Context): The cairo context to use to draw.
           height (number): final height of the logo (cairo units).

        Return a tuple (cairo group object for the logo, logo width in
                        cairo units).
        """
        # TODO: read vector logo
        logo_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'images', 'osm-logo.svg'))
        if not os.path.exists(logo_path):
            logo_path = os.path.join(
                sys.exec_prefix, 'share', 'images', 'ocitysmap',
                'osm-logo.svg')

        try:
            with open(logo_path, 'rb') as f:
                svg = rsvg.Handle(logo_path);
                LOG.debug('Using copyright logo: %s.' % logo_path)
        except IOError:
            LOG.warning('Cannot open logo from %s.' % logo_path)
            return None, None

        ctx.push_group()
        ctx.save()
        ctx.move_to(0, 0)
        factor = height / svg.props.height
        ctx.scale(factor, factor)
        svg.render_cairo(ctx)
        ctx.restore()
        return ctx.pop_group(), svg.props.width * factor

    @staticmethod
    def _draw_labels(ctx, map_grid,
                     map_area_width_dots, map_area_height_dots,
                     grid_legend_margin_dots):
        """
        Draw the Grid labels at current position.

        Args:
           ctx (cairo.Context): The cairo context to use to draw.
           map_grid (Grid): the grid objects whose labels we want to draw.
           map_area_width_dots/map_area_height_dots (numbers): size of the
              map (cairo units).
           grid_legend_margin_dots (number): margin between border of
              map and grid labels (cairo units).
        """
        ctx.save()

        step_horiz = map_area_width_dots / map_grid.horiz_count
        last_horiz_portion = math.modf(map_grid.horiz_count)[0]

        step_vert = map_area_height_dots / map_grid.vert_count
        last_vert_portion = math.modf(map_grid.vert_count)[0]

        ctx.set_font_size(min(0.75 * grid_legend_margin_dots,
                              0.5 * step_horiz))
        ctx.set_source_rgba(0, 0, 0, 1)

        for i, label in enumerate(map_grid.horizontal_labels):
            x = i * step_horiz

            if i < len(map_grid.horizontal_labels) - 1:
                x += step_horiz/2.0
            elif last_horiz_portion >= 0.3:
                x += step_horiz * last_horiz_portion/2.0
            else:
                continue

            # At the top clear the right corner of the horizontal label
            if (i < map_grid.horiz_count-1):
                draw_utils.draw_simpletext_center(ctx, label,
                                             x, grid_legend_margin_dots/2.0)

            # At the bottom clear the left corner of the horizontal label
            if (i > 0):
                draw_utils.draw_simpletext_center(ctx, label,
                                             x, map_area_height_dots -
                                             grid_legend_margin_dots/2.0)

        for i, label in enumerate(map_grid.vertical_labels):
            y = i * step_vert

            if i < len(map_grid.vertical_labels) - 1:
                y += step_vert/2.0
            elif last_vert_portion >= 0.3:
                y += step_vert * last_vert_portion/2.0
            else:
                continue

            # On the left clear the upper corner of the vertical label
            if (i > 0):
                draw_utils.draw_simpletext_center(ctx, label,
                                         grid_legend_margin_dots/2.0, y)

            # On the right clear the bottom corner of the vertical label
            if (i < map_grid.vert_count -1):
                draw_utils.draw_simpletext_center(ctx, label,
                                         map_area_width_dots -
                                         grid_legend_margin_dots/2.0, y)

        ctx.restore()

    def _create_map_canvas(self, width, height, dpi,
                           draw_contour_shade = True):
        """
        Create a new MapCanvas object.

        Args:
           graphical_ratio (float): ratio W/H of the area to render into.
           draw_contour_shade (bool): whether to draw a shade around
               the area of interest or not.

        Return the MapCanvas object or raise ValueError.
        """

        # Prepare the map canvas
        canvas = MapCanvas(self.rc.stylesheet,
                           self.rc.bounding_box,
                           width, height, dpi)

        if draw_contour_shade:
            # Area to keep visible
            interior = shapely.wkt.loads(self.rc.polygon_wkt)

            # Surroundings to gray-out
            bounding_box \
                = canvas.get_actual_bounding_box().create_expanded(0.05, 0.05)
            exterior = shapely.wkt.loads(bounding_box.as_wkt())

            # Determine the shade WKT
            shade_wkt = exterior.difference(interior).wkt

            # Prepare the shade SHP
            shade_shape = maplib.shapes.PolyShapeFile(
                canvas.get_actual_bounding_box(),
                os.path.join(self.tmpdir, 'shade.shp'),
                'shade')
            shade_shape.add_shade_from_wkt(shade_wkt)

            # Add the shade SHP to the map
            canvas.add_shape_file(shade_shape,
                                  self.rc.stylesheet.shade_color,
                                  self.rc.stylesheet.shade_alpha,
                                  self.rc.stylesheet.grid_line_width)

        return canvas

    def _create_grid(self, canvas, dpi = 72):
        """
        Create a new Grid object for the given MapCanvas.

        Args:
           canvas (MapCanvas): Map Canvas (see _create_map_canvas).

        Return a new Grid object.
        """
        # Prepare the grid SHP
        map_grid = Grid(canvas.get_actual_bounding_box(), canvas.get_actual_scale() * dpi / 72, self.rc.i18n.isrtl())
        grid_shape = map_grid.generate_shape_file(
            os.path.join(self.tmpdir, 'grid.shp'))

        # Add the grid SHP to the map
        canvas.add_shape_file(grid_shape,
                              self.rc.stylesheet.grid_line_color,
                              self.rc.stylesheet.grid_line_alpha,
                              self.rc.stylesheet.grid_line_width)

        return map_grid

    # The next two methods are to be overloaded by the actual renderer.
    def render(self, cairo_surface, dpi):
        """Renders the map, the index and all other visual map features on the
        given Cairo surface.

        Args:
            cairo_surface (Cairo.Surface): the destination Cairo device.
            dpi (int): dots per inch of the device.
        """
        raise NotImplementedError

    @staticmethod
    def get_compatible_output_formats():
        return [ "png", "svgz", "pdf", "csv" ]

    @staticmethod
    def get_compatible_paper_sizes(bounding_box, scale):
        """Returns a list of the compatible paper sizes for the given bounding
        box. The list is sorted, smaller papers first, and a "custom" paper
        matching the dimensions of the bounding box is added at the end.

        Args:
            bounding_box (coords.BoundingBox): the map geographic bounding box.
            scale (int): minimum mapnik scale of the map.

        Returns a list of tuples (paper name, width in mm, height in
        mm, portrait_ok, landscape_ok, is_default). Paper sizes are
        represented in portrait mode.
        """
        raise NotImplementedError
