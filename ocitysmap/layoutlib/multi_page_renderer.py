# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2012  David Mentré
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
import datetime
from itertools import groupby
import locale
import logging
import mapnik
assert mapnik.mapnik_version() >= 300000, \
    "Mapnik module version %s is too old, see ocitysmap's INSTALL " \
    "for more details." % mapnik.mapnik_version_string()
import math
import os
import gi
gi.require_version('Rsvg', '2.0')
gi.require_version('Pango', '1.0')
from gi.repository import Rsvg, Pango
import shapely.wkt
from string import Template
from functools import cmp_to_key
from copy import copy
import qrcode
import qrcode.image.svg
from io import BytesIO
import html
from submodules.robinson import robinson
from gettext import gettext

import coords
from . import commons
from ocitysmap.layoutlib.abstract_renderer import Renderer
from ocitysmap.indexlib.GeneralIndex import GeneralIndex, GeneralIndexCategory, MultiPageIndexRenderer
from ocitysmap.indexlib.StreetIndex import StreetIndex
from ocitysmap.indexlib.HealthIndex import HealthIndex
from ocitysmap.indexlib.NotesIndex import NotesIndex
from ocitysmap.indexlib.TreeIndex import TreeIndex
from ocitysmap import draw_utils, maplib
from ocitysmap.maplib.map_canvas import MapCanvas
from ocitysmap.maplib.grid import Grid
from ocitysmap.maplib.overview_grid import OverviewGrid
from ocitysmap.stylelib.Gpx import GpxStylesheet
from ocitysmap.stylelib.Umap import UmapStylesheet

LOG = logging.getLogger('ocitysmap')


def load_resourcefn (fn):
    res = None
    with open(fn, 'rb') as f:
        res = f.read()
    return res

def text_extents(ctx, font_face, font_size, text):
    ctx.select_font_face (font_face)
    ctx.set_font_size (font_size)
    return ctx.text_extents (text)

def font_extents(ctx, font_face, font_size):
    ctx.select_font_face (font_face)
    ctx.set_font_size (font_size)
    return ctx.font_extents ()

class MultiPageRenderer(Renderer):
    """
    This Renderer creates a multi-pages map, with all the classic overlayed
    features and no index page.
    """

    name = 'multi_page'
    description = gettext('A multi-page layout.')
    multipages = True

    # The DEFAULT SCALE values represents the minimum acceptable mapnik scale
    # 70000 ensures that the zoom level will be 10 or higher
    # 12000 ensures that the zoom level will be 16 or higher
    # 4200 -> zoom level 17
    # 2100 -> zoom level 18
    # see entities.xml.inc file from osm style sheet
    # TODO: make configurable
    DEFAULT_MULTIPAGE_SCALE = 4200
    MAX_MULTIPAGE_MAPPAGES  = 50

    def __init__(self, db, rc, tmpdir, dpi, file_prefix):
        """
        Create the renderer.

        Parameters
        ----------
           db : psycopg2 DB
               GIS database connection handle
           rc : RenderingConfiguration
               Rendering configurationparameters.
           tmpdir : str
               Path to a temp dir that can hold temp files the renderer creates.
           dpi : int
               Output resolution for bitmap formats
           file_prefix : str
               File name refix for all output file formats to be generated
        """

        Renderer.__init__(self, db, rc, tmpdir, dpi)

        self.rc.status_update(_("Initializing ..."))

        self._grid_legend_margin_pt = \
            min(Renderer.GRID_LEGEND_MARGIN_RATIO * self.paper_width_pt,
                Renderer.GRID_LEGEND_MARGIN_RATIO * self.paper_height_pt)

        # Compute the usable area per page
        self._usable_area_width_pt = (self.paper_width_pt -
                                      (2 * Renderer.PRINT_SAFE_MARGIN_PT))
        self._usable_area_height_pt = (self.paper_height_pt -
                                       (2 * Renderer.PRINT_SAFE_MARGIN_PT))

        self._map_coords = ( Renderer.PRINT_SAFE_MARGIN_PT,
                             Renderer.PRINT_SAFE_MARGIN_PT,
                             self._usable_area_width_pt,
                             self._usable_area_height_pt )

        scale_denom = self.DEFAULT_MULTIPAGE_SCALE

        # offset to the first map page number
        # there are currently three header pages
        # making the first actual map detail page number 1
        self._first_map_page_number = 1

        # the mapnik scale depends on the latitude. However we are
        # always using Mapnik conversion functions (lat,lon <->
        # mercator_meters) so we don't need to take into account
        # latitude in following computations

        # by convention, mapnik uses 90 ppi whereas cairo uses 72 ppi
        scale_denom *= float(72) / 90

        GRAYED_MARGIN_MM  = 10
        OVERLAP_MARGIN_MM = 20

        # Convert the original Bounding box into Mercator meters
        self._proj = coords.get_proj_transformation()
        orig_envelope = self._project_envelope(self.rc.bounding_box)

        while True:
            # Extend the bounding box to take into account the lost outer
            # margin
            off_x  = orig_envelope.minx - GRAYED_MARGIN_MM * 9.6
            off_y  = orig_envelope.miny - GRAYED_MARGIN_MM * 9.6
            width  = orig_envelope.width() + (2 * GRAYED_MARGIN_MM) * 9.6
            height = orig_envelope.height() + (2 * GRAYED_MARGIN_MM) * 9.6

            # Calculate the total width and height of paper needed to
            # render the geographical area at the current scale.
            total_width_pt   = commons.convert_mm_to_pt(float(width) * 1000 / scale_denom)
            total_height_pt  = commons.convert_mm_to_pt(float(height) * 1000 / scale_denom)
            self.grayed_margin_pt = commons.convert_mm_to_pt(GRAYED_MARGIN_MM)
            overlap_margin_pt = commons.convert_mm_to_pt(OVERLAP_MARGIN_MM)

            # Calculate the number of pages needed in both directions
            if total_width_pt < self._usable_area_width_pt:
                nb_pages_width = 1
            else:
                nb_pages_width = \
                    (float(total_width_pt - self._usable_area_width_pt) / \
                         (self._usable_area_width_pt - overlap_margin_pt)) + 1

            if total_height_pt < self._usable_area_height_pt:
                nb_pages_height = 1
            else:
                nb_pages_height = \
                    (float(total_height_pt - self._usable_area_height_pt) / \
                         (self._usable_area_height_pt - overlap_margin_pt)) + 1

            # Round up the number of pages needed so that we have integer
            # number of pages
            self.nb_pages_width = int(math.ceil(nb_pages_width))
            self.nb_pages_height = int(math.ceil(nb_pages_height))

            total_pages = self.nb_pages_width * self.nb_pages_height

            if self.MAX_MULTIPAGE_MAPPAGES and \
               total_pages < self.MAX_MULTIPAGE_MAPPAGES:
                break

            new_scale_denom = scale_denom * 1.41

            if new_scale_denom > Renderer.DEFAULT_SCALE:
                break

            scale_denom = new_scale_denom


        # Calculate the entire paper area available
        total_width_pt_after_extension = self._usable_area_width_pt + \
            (self._usable_area_width_pt - overlap_margin_pt) * (self.nb_pages_width - 1)
        total_height_pt_after_extension = self._usable_area_height_pt + \
            (self._usable_area_height_pt - overlap_margin_pt) * (self.nb_pages_height - 1)

        # Convert this paper area available in the number of Mercator
        # meters that can be rendered on the map
        total_width_merc = \
            commons.convert_pt_to_mm(total_width_pt_after_extension) * scale_denom / 1000
        total_height_merc = \
            commons.convert_pt_to_mm(total_height_pt_after_extension) * scale_denom / 1000

        # Extend the geographical boundaries so that we completely
        # fill the available paper size. We are careful to extend the
        # boundaries evenly on all directions (so the center of the
        # previous boundaries remain the same as the new one)
        off_x -= (total_width_merc - width) / 2
        width = total_width_merc
        off_y -= (total_height_merc - height) / 2
        height = total_height_merc

        # Calculate what is the final global bounding box that we will render
        envelope = mapnik.Box2d(off_x, off_y, off_x + width, off_y + height)
        self._geo_bbox = self._inverse_envelope(envelope)

        # Convert the usable area on each sheet of paper into the
        # amount of Mercator meters we can render in this area.
        usable_area_merc_m_width  = commons.convert_pt_to_mm(self._usable_area_width_pt) * scale_denom / 1000
        usable_area_merc_m_height = commons.convert_pt_to_mm(self._usable_area_height_pt) * scale_denom / 1000
        grayed_margin_merc_m      = (GRAYED_MARGIN_MM * scale_denom) / 1000
        overlap_margin_merc_m     = (OVERLAP_MARGIN_MM * scale_denom) / 1000

        # Prepare overlays for all additional import files
        self._overlays = copy(self.rc.overlays)
        gpx_colors = ['red', 'blue', 'green', 'violet', 'orange']
        gpx_color_index = 0
        track_linestrings = []
        if self.rc.import_files:
            for (file_type, import_file) in self.rc.import_files:
                if file_type == 'gpx':
                    try:
                        color = gpx_colors[gpx_color_index]
                        gpx_color_index += 1
                        if gpx_color_index == len(gpx_colors):
                            gpx_color_index = 0
                        gpx_style = GpxStylesheet(import_file, self.tmpdir, color)
                    except Exception as e:
                        LOG.warning("GPX stylesheet error: %s" % e)
                    else:
                        self._overlays.append(gpx_style)
                        try:
                            for l in gpx_style.linestrings:
                                track_linestrings.append(l)
                        except Exception as e:
                            LOG.warning("GPX linestring extraction error: %s" % e)
                            pass
                elif file_type == 'umap':
                    try:
                        umap_style = UmapStylesheet(import_file, self.tmpdir)
                    except Exception as e:
                        LOG.warning("UMAP stylesheet error: %s" % e)
                    else:
                        self._overlays.append(umap_style)
                else:
                    LOG.warning("Unsupported file type '%s' for file '%s" % (file_type, import_file))


        # Calculate all the bounding boxes that correspond to the
        # geographical area that will be rendered on each sheet of
        # paper.
        area_polygon = shapely.wkt.loads(self.rc.polygon_wkt)
        bboxes = []
        self.page_disposition = {}
        map_number = 0
        for j in reversed(range(0, self.nb_pages_height)):
            col = self.nb_pages_height - j - 1
            self.page_disposition[col] = []
            for i in range(0, self.nb_pages_width):
                cur_x = off_x + i * (usable_area_merc_m_width - overlap_margin_merc_m)
                cur_y = off_y + j * (usable_area_merc_m_height - overlap_margin_merc_m)
                envelope = mapnik.Box2d(cur_x, cur_y,
                                        cur_x+usable_area_merc_m_width,
                                        cur_y+usable_area_merc_m_height)

                envelope_inner = mapnik.Box2d(cur_x + grayed_margin_merc_m,
                                              cur_y + grayed_margin_merc_m,
                                              cur_x + usable_area_merc_m_width  - grayed_margin_merc_m,
                                              cur_y + usable_area_merc_m_height - grayed_margin_merc_m)
                inner_bb = self._inverse_envelope(envelope_inner)
                inner_bb_shp = shapely.wkt.loads(inner_bb.as_wkt())
                show_page = False
                if len(track_linestrings) > 0:
                    for l in track_linestrings:
                        if l.intersects(inner_bb_shp):
                            show_page = True
                            break
                elif not area_polygon.disjoint(inner_bb_shp):
                    show_page = True

                if show_page:
                    self.page_disposition[col].append(map_number)
                    map_number += 1
                    bboxes.append((self._inverse_envelope(envelope),
                                   inner_bb))
                else:
                    self.page_disposition[col].append(None)

        self.pages = []

        # Create an overview map

        self.rc.status_update(_("Preparing overview page"))

        overview_bb = self._geo_bbox.create_expanded(0.001, 0.001)
        # Create the overview grid
        self.overview_grid = OverviewGrid(overview_bb,
                     [bb_inner for bb, bb_inner in bboxes], self.rc.i18n.isrtl())

        grid_shape = self.overview_grid.generate_shape_file(
                    os.path.join(self.tmpdir, 'grid_overview.shp'))

        # Create a canvas for the overview page
        self.overview_canvas = MapCanvas(self.rc.stylesheet,
                                         overview_bb, self._usable_area_width_pt,
                                         self._usable_area_height_pt, dpi,
                                         extend_bbox_to_ratio=True,
                                         )

        # Create the gray shape around the overview map
        exterior = shapely.wkt.loads(self.overview_canvas.get_actual_bounding_box()\
                                                                .as_wkt())
        interior = shapely.wkt.loads(self.rc.polygon_wkt)
        shade_wkt = exterior.difference(interior).wkt
        shade = maplib.shapes.PolyShapeFile(self.rc.bounding_box,
                os.path.join(self.tmpdir, 'shape_overview.shp'),
                             'shade-overview')
        shade.add_shade_from_wkt(shade_wkt)

        if self.rc.osmid is not None:
            self.overview_canvas.add_shape_file(shade)
        self.overview_canvas.add_shape_file(grid_shape,
                                  self.rc.stylesheet.grid_line_color, 1,
                                  self.rc.stylesheet.grid_line_width)

        self.rc.status_update(_("Preparing overview page: base map"))
        self.overview_canvas.render()

        self.overview_overlay_canvases = []
        self.overview_overlay_effects  = {}

        for overlay in self._overlays:
            path = overlay.path.strip()
            if path.startswith('internal:'):
                plugin_name = path.lstrip('internal:')
                LOG.warning("plugin: %s - %s" % (path, plugin_name))
                if plugin_name == 'qrcode':
                    if not self.rc.qrcode_text:
                        self.rc.qrcode_text = self.rc.origin_url
                else:
                    self.overview_overlay_effects[plugin_name] = self.get_plugin(plugin_name)
            else:
                self.rc.status_update(_("Preparing overview page: %s") % overlay.name)
                ov_canvas = MapCanvas(overlay,
                                      overview_bb,
                                      self._usable_area_width_pt,
                                      self._usable_area_height_pt,
                                      dpi,
                                      extend_bbox_to_ratio=True)
                ov_canvas.render()
                self.overview_overlay_canvases.append(ov_canvas)

        # Create the map canvas for each page
        indexes = []
        for i, (bb, bb_inner) in enumerate(bboxes):
            self.rc.status_update(_("Preparing map page %(page)d of %(total)d: base map")
                                  % {'page':  i + 1,
                                     'total': len(bboxes),
                                     })

            # Create the gray shape around the map
            exterior = shapely.wkt.loads(bb.as_wkt())
            interior = shapely.wkt.loads(bb_inner.as_wkt())
            shade_wkt = exterior.difference(interior).wkt
            shade = maplib.shapes.PolyShapeFile(
                bb, os.path.join(self.tmpdir, 'shade%d.shp' % i),
                'shade%d' % i)
            shade.add_shade_from_wkt(shade_wkt)

            # Create the contour shade

            # Area to keep visible
            interior_contour = shapely.wkt.loads(self.rc.polygon_wkt)
            # Determine the shade WKT
            shade_contour_wkt = interior.difference(interior_contour).wkt
            # Prepare the shade SHP
            shade_contour = maplib.shapes.PolyShapeFile(bb,
                os.path.join(self.tmpdir, 'shade_contour%d.shp' % i),
                'shade_contour%d' % i)
            shade_contour.add_shade_from_wkt(shade_contour_wkt)


            # Create one canvas for the current page
            map_canvas = MapCanvas(self.rc.stylesheet,
                                   bb, self._usable_area_width_pt,
                                   self._usable_area_height_pt, dpi,
                                   extend_bbox_to_ratio=False)

            # Create canvas for overlay on current page
            overlay_canvases = []
            overlay_effects  = {}
            for overlay in self._overlays:
                path = overlay.path.strip()
                if path.startswith('internal:'):
                    plugin_name = path.lstrip('internal:')
                    overlay_effects[plugin_name] = self.get_plugin(plugin_name)
                else:
                    overlay_canvases.append(MapCanvas(overlay,
                                               bb, self._usable_area_width_pt,
                                               self._usable_area_height_pt, dpi,
                                               extend_bbox_to_ratio=False))

            # Create the grid
            map_grid = Grid(bb_inner, map_canvas.get_actual_scale(), self.rc.i18n.isrtl())
            grid_shape = map_grid.generate_shape_file(
                os.path.join(self.tmpdir, 'grid%d.shp' % i))

            map_canvas.add_shape_file(shade)
            if self.rc.osmid is not None:
                map_canvas.add_shape_file(shade_contour,
                                          self.rc.stylesheet.shade_color_2,
                                          self.rc.stylesheet.shade_alpha_2)
            map_canvas.add_shape_file(grid_shape,
                                      self.rc.stylesheet.grid_line_color,
                                      self.rc.stylesheet.grid_line_alpha,
                                      self.rc.stylesheet.grid_line_width)

            map_canvas.render()

            for overlay_canvas in overlay_canvases:
                self.rc.status_update(_("Preparing map page %(page)d of %(total)d: %(style)s")
                                      % { 'page':  i + 1,
                                          'total': len(bboxes),
                                          'style': overlay_canvas._style_name,
                                         })
                overlay_canvas.render()

            self.pages.append((map_canvas, map_grid, overlay_canvases, overlay_effects))

            # Create the index for the current page
            inside_contour_wkt = interior_contour.intersection(interior).wkt
            # TODO: other index types
            self.rc.status_update(_("Preparing map page %(page)d of %(total)d: collecting index data")
                                  % { 'page':  i + 1,
                                      'total': len(bboxes),
                                     })
            try:
                indexer_class = globals()[self.rc.indexer+"Index"]
                # TODO: check that it actually implements a working indexer class
            except Exception:
                LOG.warning("Indexer class '%s' not found" % self.rc.indexer)
            else:
                index = indexer_class(self.db,
                                      self,
                                      bb_inner,
                                      inside_contour_wkt,
                                      self.rc.i18n, page_number=(i + self._first_map_page_number))

                index.apply_grid(map_grid)
                indexes.append(index)

        # Merge all indexes
        self.index_categories = self._merge_page_indexes(indexes)

        # Prepare the small map for the front page
        self._prepare_front_page_map(dpi)

    def _merge_page_indexes(self, indexes):
        # First, we split street categories and "other" categories,
        # because we sort them and we don't want to have the "other"
        # categories intermixed with the street categories. This
        # sorting is required for the groupby Python operator to work
        # properly.
        all_categories_streets = []
        all_categories_others  = []
        for page_number, idx in enumerate(indexes):
            for cat in idx.categories:
                # Split in two lists depending on the category type
                # (street or other)
                if cat.is_street:
                    all_categories_streets.append(cat)
                else:
                    all_categories_others.append(cat)

        all_categories_streets_merged = \
            self._merge_index_same_categories(all_categories_streets, is_street=True)
        all_categories_others_merged = \
            self._merge_index_same_categories(all_categories_others, is_street=False)

        all_categories_merged = \
            all_categories_streets_merged + all_categories_others_merged

        return all_categories_merged

    @staticmethod
    def _my_cmp(x, y):
        """Helper method used for sorting later
        """
        return locale.strcoll(x.label, y.label)

    def _merge_index_same_categories(self, categories, is_street=True):
        # Sort by categories. Now we may have several consecutive
        # categories with the same name (i.e category for letter 'A'
        # from page 1, category for letter 'A' from page 3).
        categories.sort(key=lambda s:s.name)

        categories_merged = []
        for category_name,grouped_categories in groupby(categories,
                                                        key=lambda s:s.name):

            # Group the different IndexItem from categories having the
            # same name. The groupby() function guarantees us that
            # categories with the same name are grouped together in
            # grouped_categories[].

            grouped_items = []
            for cat in grouped_categories:
                grouped_items.extend(cat.items)

            # Re-sort alphabetically all the IndexItem according to
            # the street name.

            prev_locale = locale.getlocale(locale.LC_COLLATE)
            try:
                locale.setlocale(locale.LC_COLLATE, self.rc.i18n.language_code())
            except Exception:
                LOG.warning('error while setting LC_COLLATE to "%s"' % self._i18n.language_code())

            try:
                grouped_items_sorted = \
                    sorted(grouped_items, key = cmp_to_key(self._my_cmp))
            finally:
                locale.setlocale(locale.LC_COLLATE, prev_locale)

            self._blank_duplicated_names(grouped_items_sorted)

            # Rebuild a IndexCategory object with the list of merged
            # and sorted IndexItem
            categories_merged.append(
                GeneralIndexCategory(category_name, grouped_items_sorted, is_street))

        return categories_merged

    @staticmethod
    def _blank_duplicated_names(grouped_items_sorted):
        """
        We set the label to empty string in case of duplicated item. In
        multi-page renderer we won't draw the dots in that case
        """
        prev_label = ''
        for item in grouped_items_sorted:
            if prev_label == item.label:
                item.label = ''
            else:
                prev_label = item.label

    def _project_envelope(self, bbox):
        """
        Project the given bounding box into the rendering projection.
        """
        envelope = mapnik.Box2d(bbox.get_top_left()[1],
                                bbox.get_top_left()[0],
                                bbox.get_bottom_right()[1],
                                bbox.get_bottom_right()[0])
        c0 = self._proj.forward(mapnik.Coord(envelope.minx, envelope.miny))
        c1 = self._proj.forward(mapnik.Coord(envelope.maxx, envelope.maxy))
        return mapnik.Box2d(c0.x, c0.y, c1.x, c1.y)

    def _inverse_envelope(self, envelope):
        """
        Inverse the given cartesian envelope (in 3587) back to a 4326
        bounding box.
        """
        c0 = self._proj.backward(mapnik.Coord(envelope.minx, envelope.miny))
        c1 = self._proj.backward(mapnik.Coord(envelope.maxx, envelope.maxy))
        return coords.BoundingBox(c0.y, c0.x, c1.y, c1.x)

    def _prepare_page(self, ctx):
        # make whole page un-transparent white
        ctx.set_source_rgb(1.0, 1.0, 1.0)
        ctx.rectangle(0, 0, self.paper_width_pt, self.paper_height_pt)
        ctx.fill()

        # Prepare to draw the map within the right bounding area
        ctx.translate(
                commons.convert_pt_to_dots(Renderer.PRINT_SAFE_MARGIN_PT),
                commons.convert_pt_to_dots(Renderer.PRINT_SAFE_MARGIN_PT))
        ctx.rectangle(0, 0, self._usable_area_width_pt, self._usable_area_height_pt)
        ctx.clip()

    def _prepare_front_page_map(self, dpi):
        self.rc.status_update(_("Preparing front page"))
        front_page_map_w = \
            self._usable_area_width_pt - 2 * Renderer.PRINT_SAFE_MARGIN_PT
        front_page_map_h = \
            (self._usable_area_height_pt - 2 * Renderer.PRINT_SAFE_MARGIN_PT) / 2

        # Create the nice small map
        front_page_map = \
            MapCanvas(self.rc.stylesheet,
                      self.rc.bounding_box,
                      front_page_map_w,
                      front_page_map_h,
                      dpi,
                      extend_bbox_to_ratio=True)

        # Add the shape that greys out everything that is outside of
        # the administrative boundary.
        exterior = shapely.wkt.loads(front_page_map.get_actual_bounding_box().as_wkt())
        interior = shapely.wkt.loads(self.rc.polygon_wkt)
        shade_wkt = exterior.difference(interior).wkt
        shade = maplib.shapes.PolyShapeFile(self.rc.bounding_box,
                os.path.join(self.tmpdir, 'shape_overview_cover.shp'),
                             'shade-overview-cover')
        shade.add_shade_from_wkt(shade_wkt)
        front_page_map.add_shape_file(shade)
        self.rc.status_update(_("Preparing front page: base map"))
        front_page_map.render()
        self._front_page_map = front_page_map

        self._frontpage_overlay_canvases = []
        self._frontpage_overlay_effects  = {}
        for overlay in self._overlays:
            path = overlay.path.strip()
            if path.startswith('internal:'):
                plugin_name = path.lstrip('internal:')
                self._frontpage_overlay_effects[plugin_name] = self.get_plugin(plugin_name)
            else:
                ov_canvas = MapCanvas(overlay,
                                      self.rc.bounding_box,
                                      front_page_map_w,
                                      front_page_map_h,
                                      dpi,
                                      extend_bbox_to_ratio=True)
                self.rc.status_update(_("Preparing front page: %s") % ov_canvas._style_name)
                ov_canvas.render()
                self._frontpage_overlay_canvases.append(ov_canvas)

    def _render_front_page_header(self, ctx, w, h):
        ctx.save()

        # Draw a grey block which will contain the map title
        blue_w = w
        blue_h = 0.3 * h
        ctx.set_source_rgb(.80,.80,.80)
        ctx.rectangle(0, 0, blue_w, blue_h)
        ctx.fill()
        draw_utils.draw_text_adjusted(ctx, html.escape(self.rc.title), blue_w/2, blue_h/2,
                 blue_w, blue_h)
        ctx.restore()

    def _render_front_page_map(self, ctx, dpi, w, h):
        # We will render the map slightly below the title
        ctx.save()
        ctx.translate(0, 0.3 * h + Renderer.PRINT_SAFE_MARGIN_PT)

        # prevent map background from filling the full canvas
        ctx.rectangle(0, 0, w, h / 2)
        ctx.clip()

        # Render the map !
        self.rc.status_update(_("Rendering front page: base map"))
        mapnik.render(self._front_page_map.get_rendered_map(), ctx)

        for ov_canvas in self._frontpage_overlay_canvases:
            self.rc.status_update(_("Rendering front page: %s") % ov_canvas._style_name)
            rendered_map = ov_canvas.get_rendered_map()
            mapnik.render(rendered_map, ctx)

        # TODO offsets are not correct here, so we skip overlay plugins for now
        # apply effect overlays
        # ctx.save()
        # we have to undo border adjustments here
        # ctx.translate(0, -(0.3 * h + Renderer.PRINT_SAFE_MARGIN_PT))
        # self._map_canvas = self._front_page_map
        # for plugin_name, effect in self._frontpage_overlay_effects.items():
        #    try:
        #        effect.render(self, ctx)
        #    except Exception as e:
        #        # TODO better logging
        #        LOG.warning("Error while rendering overlay: %s\n%s" % (plugin_name, e))
        # ctx.restore()



        ctx.restore()

    def _render_front_page_footer(self, ctx, w, h, osm_date=None, notice=None):
        ctx.save()

        # Draw the footer
        ctx.translate(0, 0.8 * h + 2 * Renderer.PRINT_SAFE_MARGIN_PT)

        # Display a nice grey rectangle as the background of the
        # footer
        footer_w = w
        footer_h = 0.2 * h - 2 * Renderer.PRINT_SAFE_MARGIN_PT
        ctx.set_source_rgb(.80,.80,.80)
        ctx.rectangle(0, 0, footer_w, footer_h)
        ctx.fill()

        # Draw the OpenStreetMap logo to the right of the footer
        if self.rc.logo:
            logo_height = footer_h / 2
            grp, logo_width = self._get_logo(ctx, self.rc.logo, logo_height)
            if grp:
                ctx.save()
                ctx.translate(w - logo_width - Renderer.PRINT_SAFE_MARGIN_PT,
                              logo_height / 2)
                ctx.set_source(grp)
                ctx.paint_with_alpha(0.8)
                ctx.restore()

        # add QRcode if qrcode text is provided
        if self.rc.qrcode_text:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )

                qr.add_data(self.rc.qrcode_text)
                qr.make(fit=True)

                img = qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage,
                                    fill_color='lightblue')
                svgstr = BytesIO()
                img.save(svgstr)

                svg_val = svgstr.getvalue()

                rsvg = Rsvg.Handle()
                svg = rsvg.new_from_data(svg_val)
                svgstr.close()

                ctx.save()
                ctx.translate(w - 2*logo_width - 2*Renderer.PRINT_SAFE_MARGIN_PT,
                              logo_height/2)
                ctx.move_to(0, 0)
                factor = logo_height / svg.props.height
                ctx.scale(factor, factor)
                svg.render_cairo(ctx)
                ctx.restore()

        # Prepare the text for the left of the footer
        if notice is None:
            annotations = self._annotations(osm_date)

            notice = html.escape(annotations['maposmatic']) + '\n'

            if annotations['styles']:
                notice+= "<u>" + html.escape(_('Map style(s):')) + '</u>\n'
                notice+= html.escape('; '.join(annotations['styles'])) + '\n'

            if annotations['sources']:
                notice+= "<u>"+html.escape(_('Data source(s):')) + '</u>\n'
                notice+= html.escape('; '.join(list(annotations['sources']))) + '\n'

        # draw footer text
        draw_utils.draw_text_adjusted(ctx, notice,
                Renderer.PRINT_SAFE_MARGIN_PT, footer_h/2, footer_w,
                footer_h, align=Pango.Alignment.LEFT)

        ctx.restore()

    def _render_front_page(self, ctx, cairo_surface, dpi, osm_date):
        self.rc.status_update(_("Rendering front page"))
        ctx.save()
        self._prepare_page(ctx)

        # Translate into the working area, taking another
        # PRINT_SAFE_MARGIN_PT inside the grey area.
        ctx.translate(Renderer.PRINT_SAFE_MARGIN_PT,Renderer.PRINT_SAFE_MARGIN_PT)
        w = self._usable_area_width_pt - 2 * Renderer.PRINT_SAFE_MARGIN_PT
        h = self._usable_area_height_pt - 2 * Renderer.PRINT_SAFE_MARGIN_PT

        self._render_front_page_map(ctx, dpi, w, h)
        self._render_front_page_header(ctx, w, h)
        self._render_front_page_footer(ctx, w, h, osm_date)

        try: # set_page_label() does not exist in older pycairo versions
            cairo_surface.set_page_label(_('Front page'))
        except Exception:
            pass

        ctx.restore()
        cairo_surface.show_page()

    def _render_contents_page(self, ctx, cairo_surface, dpi, osm_date):
        """
        Render table of contents and map setting details
        """

        self.rc.status_update(_("Rendering table of contents page"))

        ctx.save()
        self._prepare_page(ctx)

        w = self._usable_area_width_pt
        h = self._usable_area_height_pt

        ctx.save()
        ctx.rectangle( 0, 0, w, 0.9 * h)
        ctx.clip()

        template_dir = os.path.abspath(os.path.join(
                os.path.dirname(__file__), '..', '..', 'templates', 'markup'))

        with open(os.path.join(template_dir, "multipage-details.html")) as f:
            html_template = Template(f.read())

        with open(os.path.join(template_dir, "multipage-details.css")) as f:
            css = f.read()

        bbox_txt = self.rc.bounding_box.as_text()
        bbox_txt+= "<br/>("
        (bbox_h, bbox_w) = self.rc.bounding_box.spheric_sizes()
        if bbox_w >= 1000 and bbox_h >= 1000:
            bbox_txt += "ca. %d x %d km²" % (bbox_w/1000, bbox_h/1000)
        else:
            bbox_txt += "ca. %d x %d m²" % (bbox_w, bbox_h)
        bbox_txt+= ")"

        overlay_names = ""
        if self.rc.overlays:
            for overlay in self.rc.overlays:
                overlay_names+= overlay.name + "<br/>"

        import_names = ""
        if self.rc.import_files:
            for (file_type, import_file) in self.rc.import_files:
                import_names+= os.path.basename(import_file) + "<br/>"

        html = html_template.substitute(
            bbox       = bbox_txt,
            paper      = '%d × %d mm²' % (self.rc.paper_width_mm, self.rc.paper_height_mm),
            layout     = 'Multi Page',
            stylesheet = self.rc.stylesheet.name,
            overlays   = overlay_names,
            indexer    = self.rc.indexer,
            locale     = self.rc.i18n.language_desc(),
            first_index_page = len(self.pages) + 1,
            imports    = import_names,
            # TODO use current locale for date fromatting below
            render_date= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data_date  = osm_date,
        )

        rob = robinson.html (html, css, w/2, load_resourcefn, text_extents, font_extents, ctx)
        rob.render(ctx)

        ctx.restore()

        # footer notice
        draw_utils.render_page_number(ctx, 'ii',
                                      self._usable_area_width_pt,
                                      self._usable_area_height_pt,
                                      self.grayed_margin_pt,
                                      transparent_background = False,
                                      side = draw_utils.LEFT_SIDE
        )
        try: # set_page_label() does not exist in older pycairo versions
            cairo_surface.set_page_label(_('Contents'))
        except Exception:
            pass

        ctx.restore()
        cairo_surface.show_page()

    def _render_overview_page(self, ctx, cairo_surface, dpi):
        self.rc.status_update(_("Rendering overview page"))

        ctx.save()
        self._prepare_page(ctx)

        rendered_map = self.overview_canvas.get_rendered_map()
        self.rc.status_update(_("Rendering overview page: base map"))
        mapnik.render(rendered_map, ctx)

        for ov_canvas in self.overview_overlay_canvases:
            self.rc.status_update(_("Rendering overview page: %s") % ov_canvas._style_name)
            rendered_map = ov_canvas.get_rendered_map()
            mapnik.render(rendered_map, ctx)

        # apply effect overlays
        ctx.save()
        self._map_canvas = self.overview_canvas
        for plugin_name, effect in self.overview_overlay_effects.items():
            try:
                effect.render(self, ctx)
            except Exception as e:
                # TODO better logging
                LOG.warning("Error while rendering overlay: %s\n%s" % (plugin_name, e))

        ctx.restore()

        # draw pages numbers
        self._draw_overview_labels(ctx, self.overview_canvas, self.overview_grid,
              commons.convert_pt_to_dots(self._usable_area_width_pt),
              commons.convert_pt_to_dots(self._usable_area_height_pt))

        # Render the page number
        draw_utils.render_page_number(ctx, "iii",
                                      self._usable_area_width_pt,
                                      self._usable_area_height_pt,
                                      self.grayed_margin_pt,
                                      transparent_background = True,
                                      side = draw_utils.RIGHT_SIDE
        )

        try: # set_page_label() does not exist in older pycairo versions
            cairo_surface.set_page_label(_('Overview'))
        except AttributeError:
            pass

        ctx.restore()
        cairo_surface.show_page()

    def _draw_arrow(self, ctx, cairo_surface, number, max_digit_number,
                    reverse_text=False):
        arrow_edge = self.grayed_margin_pt*.6
        ctx.save()
        ctx.set_source_rgb(0, 0, 0)
        ctx.translate(-arrow_edge/2, -arrow_edge*0.45)

        dest_name = "mypage%d" % number
        draw_utils.begin_internal_link(ctx, dest_name)

        ctx.line_to(0, 0)
        ctx.line_to(0, arrow_edge)
        ctx.line_to(arrow_edge, arrow_edge)
        ctx.line_to(arrow_edge, 0)
        ctx.line_to(arrow_edge/2, -arrow_edge*.25)
        ctx.close_path()
        ctx.fill()
        draw_utils.end_link(ctx)
        ctx.restore()

        ctx.save()
        if reverse_text:
            ctx.rotate(math.pi)
        draw_utils.begin_internal_link(ctx, dest_name)
        draw_utils.draw_text_adjusted(ctx, str(number), 0, 0, arrow_edge,
                        arrow_edge, max_char_number=max_digit_number,
                        text_color=(1, 1, 1, 1), width_adjust=0.85,
                        height_adjust=0.9)
        draw_utils.end_link(ctx)
        ctx.restore()

    def _render_neighbour_arrows(self, ctx, cairo_surface, map_number,
                                 max_digit_number):
        current_line, current_col = None, None
        for line_nb in range(self.nb_pages_height):
            if map_number in self.page_disposition[line_nb]:
                current_line = line_nb
                current_col = self.page_disposition[line_nb].index(
                                                             map_number)
                break
        if current_line is None:
            # page not referenced
            return

        # north arrow
        for line_nb in reversed(range(current_line)):
            if self.page_disposition[line_nb][current_col] is not None:
                north_arrow = self.page_disposition[line_nb][current_col]
                ctx.save()
                ctx.translate(self._usable_area_width_pt/2,
                    commons.convert_pt_to_dots(self.grayed_margin_pt)/2)
                self._draw_arrow(ctx, cairo_surface,
                              north_arrow + self._first_map_page_number, max_digit_number)
                ctx.restore()
                break

        # south arrow
        for line_nb in range(current_line + 1, self.nb_pages_height):
            if self.page_disposition[line_nb][current_col] is not None:
                south_arrow = self.page_disposition[line_nb][current_col]
                ctx.save()
                ctx.translate(self._usable_area_width_pt/2,
                     self._usable_area_height_pt \
                      - commons.convert_pt_to_dots(self.grayed_margin_pt)/2)
                ctx.rotate(math.pi)
                self._draw_arrow(ctx, cairo_surface,
                      south_arrow + self._first_map_page_number, max_digit_number,
                      reverse_text=True)
                ctx.restore()
                break

        # west arrow
        for col_nb in reversed(range(0, current_col)):
            if self.page_disposition[current_line][col_nb] is not None:
                west_arrow = self.page_disposition[current_line][col_nb]
                ctx.save()
                ctx.translate(
                    commons.convert_pt_to_dots(self.grayed_margin_pt)/2,
                    self._usable_area_height_pt/2)
                ctx.rotate(-math.pi/2)
                self._draw_arrow(ctx, cairo_surface,
                               west_arrow + self._first_map_page_number, max_digit_number)
                ctx.restore()
                break

        # east arrow
        for col_nb in range(current_col + 1, self.nb_pages_width):
            if self.page_disposition[current_line][col_nb] is not None:
                east_arrow = self.page_disposition[current_line][col_nb]
                ctx.save()
                ctx.translate(
                    self._usable_area_width_pt \
                     - commons.convert_pt_to_dots(self.grayed_margin_pt)/2,
                    self._usable_area_height_pt/2)
                ctx.rotate(math.pi/2)
                self._draw_arrow(ctx, cairo_surface,
                               east_arrow + self._first_map_page_number, max_digit_number)
                ctx.restore()
                break

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

        ctx.set_source_rgba(0, 0, 0, 0.7)
        ctx.set_operator(cairo.Operator.OVER)

        step_horiz = map_area_width_dots / map_grid.horiz_count
        last_horiz_portion = math.modf(map_grid.horiz_count)[0]

        step_vert = map_area_height_dots / map_grid.vert_count
        last_vert_portion = math.modf(map_grid.vert_count)[0]

        ctx.set_font_size(min(0.75 * grid_legend_margin_dots,
                              0.5 * step_horiz))
        ctx.set_source_rgba(0, 0, 0, 1)

        # TODO labels can overlap with next page arrows,
        # if they do -> hide them? or move them out of the
        # grid center a bit?

        for i, label in enumerate(map_grid.horizontal_labels):
            x = i * step_horiz

            if i < len(map_grid.horizontal_labels) - 1:
                x += step_horiz/2.0
            elif last_horiz_portion >= 0.3:
                x += step_horiz * last_horiz_portion/2.0
            else:
                continue

            if map_grid.rtl:
                x = map_area_width_dots - x

            draw_utils.draw_halotext_center(ctx, label,
                                            x, - grid_legend_margin_dots/1.0)

            draw_utils.draw_halotext_center(ctx, label,
                                            x, map_area_height_dots +
                                            grid_legend_margin_dots/1.0)

        for i, label in enumerate(map_grid.vertical_labels):
            y = i * step_vert

            if i < len(map_grid.vertical_labels) - 1:
                y += step_vert/2.0
            elif last_vert_portion >= 0.3:
                y += step_vert * last_vert_portion/2.0
            else:
                continue

            draw_utils.draw_halotext_center(ctx, label,
                                            -grid_legend_margin_dots, y)

            draw_utils.draw_halotext_center(ctx, label,
                                            map_area_width_dots +
                                            grid_legend_margin_dots, y)

        ctx.restore()



    def render(self, cairo_surface, dpi, osm_date):
        ctx = cairo.Context(cairo_surface)

        self._render_front_page(ctx, cairo_surface, dpi, osm_date)
        self._render_contents_page(ctx, cairo_surface, dpi, osm_date)
        self._render_overview_page(ctx, cairo_surface, dpi)

        map_number = 0

        for map_number, (canvas, grid, overlay_canvases, overlay_effects) in enumerate(self.pages):
            self.rc.status_update(_("Rendering map page %(page)d of %(total)d")
                                  % { 'page':  map_number + 1,
                                      'total': len(self.pages),
                                     })

            ctx.save()
            self._prepare_page(ctx)

            rendered_map = canvas.get_rendered_map()
            if (map_number == 0):
                LOG.debug('Mapnik scale: 1/%f' % rendered_map.scale_denominator())
                LOG.debug('Actual scale: 1/%f' % canvas.get_actual_scale())

            LOG.info('Map page %d of %d' % (map_number + 1, len(self.pages)))

            dest_tag = "mypage%d" % (map_number + self._first_map_page_number)
            draw_utils.anchor(ctx, dest_tag)

            self.rc.status_update(_("Rendering map page %(page)d of %(total)d: base map")
                                  % { 'page':  map_number + 1,
                                      'total': len(self.pages),
                                     })

            mapnik.render(rendered_map, ctx)

            for overlay_canvas in overlay_canvases:
                self.rc.status_update(_("Rendering map page %(page)d of %(total)d: %(style)s") %
                                      { 'page':  map_number + 1,
                                        'total': len(self.pages),
                                        'style': overlay_canvas._style_name,
                                       })

                rendered_overlay = overlay_canvas.get_rendered_map()
                mapnik.render(rendered_overlay, ctx)

            # Place the vertical and horizontal square labels
            ctx.save()
            ctx.translate(commons.convert_pt_to_dots(self.grayed_margin_pt),
                      commons.convert_pt_to_dots(self.grayed_margin_pt))
            self._draw_labels(ctx, grid,
                  commons.convert_pt_to_dots(self._usable_area_width_pt) \
                        - 2 * commons.convert_pt_to_dots(self.grayed_margin_pt),
                  commons.convert_pt_to_dots(self._usable_area_height_pt) \
                        - 2 * commons.convert_pt_to_dots(self.grayed_margin_pt),
                  commons.convert_pt_to_dots(self._grid_legend_margin_pt))
            ctx.restore()


            # apply effect overlays
            ctx.save()
            for plugin_name, effect in overlay_effects.items():
                self.grid = grid
                self._map_canvas = canvas
                try:
                    effect.render(self, ctx)
                except Exception as e:
                    # TODO better logging
                    LOG.warning("Error while rendering overlay: %s\n%s" % (plugin_name, e))
            ctx.restore()


            # Render the page number
            draw_utils.render_page_number(ctx, map_number + self._first_map_page_number,
                                          self._usable_area_width_pt,
                                          self._usable_area_height_pt,
                                          self.grayed_margin_pt,
                                          transparent_background = True)
            self._render_neighbour_arrows(ctx, cairo_surface, map_number,
                                          len(str(len(self.pages) + self._first_map_page_number)))

            try: # set_page_label() does not exist in older pycairo versions
                cairo_surface.set_page_label(_('Map page %d') % (map_number + self._first_map_page_number))
            except AttributeError:
                pass
            cairo_surface.show_page()
            ctx.restore()

        self.rc.status_update(_("Rendering index pages"))
        mpsir = MultiPageIndexRenderer(self.rc.i18n,
                                       ctx, cairo_surface,
                                       self.index_categories,
                                       (self.paper_width_pt, self.paper_height_pt),
                                       (Renderer.PRINT_SAFE_MARGIN_PT,
                                        Renderer.PRINT_SAFE_MARGIN_PT,
                                        self._usable_area_width_pt,
                                        self._usable_area_height_pt),
                                       map_number + 2) # TODO: actually calc. the page offset here

        mpsir.render()

        cairo_surface.flush()

    # In multi-page mode, we only render pdf format
    @staticmethod
    def get_compatible_output_formats():
        return [ "pdf" ]

    @staticmethod
    def get_minimal_paper_size(bounding_box, scale=None):
        return (100, 100)

    @staticmethod
    def get_compatible_paper_sizes(bounding_box,
                                   renderer_context,
                                   scale=None,
                                   index_position=None, hsplit=1, vsplit=1):
        valid_sizes = []
        if scale is None:
            scale = scale=MultiPageRenderer.DEFAULT_MULTIPAGE_SCALE
        LOG.warning("getting multipage paper size options")
        is_default = True
        for sz in renderer_context.get_all_paper_sizes('multipage'):
            valid_sizes.append({
                    "name": sz[0],
                    "width": sz[1],
                    "height": sz[2],
                    "portrait_ok": True,
                    "landscape_ok": True,
                    "default": is_default,
                    "landscape_preferred": False
                })
            is_default = False

        return valid_sizes

    def _draw_overview_labels(self, ctx, map_canvas, overview_grid,
                     area_width_dots, area_height_dots):
        """
        Draw the page numbers for the overview grid.

        Args:
           ctx (cairo.Context): The cairo context to use to draw.
           overview_grid (OverViewGrid): the overview grid object
           area_width_dots/area_height_dots (numbers): size of the
              drawing area (cairo units).
        """
        ctx.save()
        ctx.set_font_size(14)
        ctx.set_operator(cairo.Operator.OVER)

        bbox = map_canvas.get_actual_bounding_box()
        bottom_right, bottom_left, top_left, top_right = bbox.to_mercator()
        bottom, left = bottom_right.y, top_left.x
        coord_delta_y = top_left.y - bottom_right.y
        coord_delta_x = bottom_right.x - top_left.x
        w, h = None, None
        for idx, page_bb in enumerate(overview_grid._pages_bbox):
            p_bottom_right, p_bottom_left, p_top_left, p_top_right = \
                                                        page_bb.to_mercator()
            center_x = p_top_left.x+(p_top_right.x-p_top_left.x)/2
            center_y = p_bottom_left.y+(p_top_right.y-p_bottom_right.y)/2
            y_percent = 100 - 100.0*(center_y - bottom)/coord_delta_y
            y = int(area_height_dots*y_percent/100)

            x_percent = 100.0*(center_x - left)/coord_delta_x
            x = int(area_width_dots*x_percent/100)

            if not w or not h:
                w = area_width_dots*(p_bottom_right.x - p_bottom_left.x
                                                         )/coord_delta_x
                h = area_height_dots*(p_top_right.y - p_bottom_right.y
                                                         )/coord_delta_y

            draw_utils.draw_text_adjusted(ctx, str(idx + self._first_map_page_number),
                                          x, y, w, h,
                                          max_char_number=len(str(len(overview_grid._pages_bbox)+3)),
                                          text_color=(0, 0, 0, 0.6))

            ctx.save()
            ctx.translate(x-w/2, y-h/2)
            ctx.set_source_rgba(0,0,0,0.1)
            draw_utils.begin_internal_link(ctx, "mypage%d" % (idx + self._first_map_page_number))
            ctx.rectangle(0,0,w,h)
            ctx.stroke()
            draw_utils.end_link(ctx)
            ctx.restore()

        ctx.restore()

