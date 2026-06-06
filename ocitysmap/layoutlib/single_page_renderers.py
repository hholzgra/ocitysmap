# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard
# Copyright (c) 2023  Hartmut Holzgraefe

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
import gi
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Pango, PangoCairo
import logging
import mapnik
assert mapnik.mapnik_version() >= 300000, \
    "Mapnik module version %s is too old, see ocitysmap's INSTALL " \
    "for more details." % mapnik.mapnik_version_string()
import math
from copy import copy
from gettext import gettext, ngettext

from ocitysmap.layoutlib import commons
from ocitysmap.layoutlib.abstract_renderer import Renderer
from ocitysmap.indexlib.GeneralIndex import GeneralIndexRenderer
# from ocitysmap.indexlib.StreetIndex import StreetIndex
from ocitysmap.indexlib.HealthIndex import HealthIndex
from ocitysmap.indexlib.NotesIndex import NotesIndex
from ocitysmap.indexlib.TreeIndex import TreeIndex
from ocitysmap.indexlib.PoiIndex import PoiIndexRenderer, PoiIndex
from ocitysmap.indexlib.commons import IndexDoesNotFitError, IndexEmptyError
import draw_utils
from ocitysmap.maplib.map_canvas import MapCanvas
from ocitysmap.stylelib.Gpx import GpxStylesheet
from ocitysmap.stylelib.Umap import UmapStylesheet


LOG = logging.getLogger('ocitysmap')


class SinglePageRenderer(Renderer):
    """
    This Renderer creates a full-page map, with the overlayed features
    like the grid, grid labels, scale and compass rose and can draw an
    index.
    """

    name = 'generic_single_page'
    description = gettext(u'A generic full-page layout with or without index.')

    # TODO make configurable
    MAX_INDEX_OCCUPATION_RATIO = 1/3.

    def __init__(self, db, rc, tmpdir, dpi, file_prefix,
                 index_position = 'side'):
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
           index_position : str, optional
               None or 'side' (index on side), 'bottom' (index at bottom),
               or 'extra_page' (index on 2nd page for PDF output only).
        """

        Renderer.__init__(self, db, rc, tmpdir, dpi)

        self.file_prefix = file_prefix

        # Prepare the index
        self.index_position = index_position
        if index_position is None:
            self.street_index = None
        else:
            try:
                indexer_class = globals()[rc.indexer+"Index"]
                # TODO: check that it actually implements a working indexer class
            except Exception:
                LOG.warning("Indexer class '%s' not found" % rc.indexer)
                self.street_index = None
                self.index_position = None
            else:
                try:
                    indexer_name = rc.indexer
                    #indexer_class = globals()[rc.indexer]
                    indexer_class = globals()[rc.indexer+"Index"]
                    # TODO : check that it actually implements a working indexer class
                except Exception:
                    LOG.warning("Indexer class '%s' not found" % rc.indexer)
                    self.street_index = None
                    self.index_position = None
                else:
                    self.street_index = indexer_class(db,
                                                      self,
                                                      rc.bounding_box,
                                                      rc.polygon_wkt,
                                                      rc.i18n,
                    )

            if self.street_index and not self.street_index.categories:
                LOG.warning("Designated area leads to an empty index")
                self.street_index = None
                self.index_position = None


        # grid marker offset (originally used for solid grid frame,
        # now just for the letter/number overlay offset inside the map)
        self._grid_legend_margin_pt = \
            min(Renderer.GRID_LEGEND_MARGIN_RATIO * self.paper_width_pt,
                Renderer.GRID_LEGEND_MARGIN_RATIO * self.paper_height_pt)

        # reserve space for the page title if given
        if self.rc.title:
            self._title_margin_pt = Renderer.TITLE_MARGIN_RATIO * self.paper_height_pt
        else:
            self._title_margin_pt = 0

        # reserve space for the page footer
        self._copyright_margin_pt = Renderer.ANNOTATION_MARGIN_RATIO * self.paper_height_pt

        # calculate remaining usable render space for the actual map
        # after taking header and footer into account
        self._usable_area_width_pt = (self.paper_width_pt -
                                      2 * Renderer.PRINT_SAFE_MARGIN_PT)
        self._usable_area_height_pt = (self.paper_height_pt -
                                       2 * Renderer.PRINT_SAFE_MARGIN_PT -
                                       self._title_margin_pt -
                                       self._copyright_margin_pt)

        # Prepare the Index (may raise a IndexDoesNotFitError)
        try:
            if ( index_position and self.street_index
                 and self.street_index.categories ):
                self.rc.status_update(_("%s: fetching index data") % self.rc.output_format)
                self._index_renderer, self._index_area \
                    = self._create_index_rendering(index_position)
            else:
                self._index_renderer, self._index_area = None, None
        except IndexDoesNotFitError as e:
            self._index_renderer, self._index_area = None, None

        self._map_coords = self._get_map_coords(index_position if self._index_area else None)

        # Prepare the map
        self._map_canvas = self._create_map_canvas(
            float(self._map_coords[2]),  # W
            float(self._map_coords[3]),  # H
            dpi,
            rc.osmid is not None )

        # Prepare overlay styles from config
        self._overlays = copy(self.rc.overlays)
        self._overlay_effects  = {}

        # Prepare overlays for all additional import files
        # we cycle through a predefined color list for gpx track colors
        gpx_colors = ['red', 'blue', 'green', 'violet', 'orange']
        gpx_color_index = 0
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
                elif file_type == 'umap':
                    try:
                        umap_style = UmapStylesheet(import_file, self.tmpdir)
                    except Exception as e:
                        LOG.warning("UMAP stylesheet error: %s" % e)
                    else:
                        self._overlays.append(umap_style)
                elif file_type == 'poi':
                    # TODO: refactor this special case
                    self._overlay_effects['poi_markers'] = self.get_plugin('poi_markers')
                    self.rc.poi_file = import_file
                else:
                    LOG.warning("Unsupported file type '%s' for file '%s" % (file_type, import_file))

        # Prepare map overlays
        self._overlay_canvases = []
        for overlay in self._overlays:
            path = overlay.path.strip()
            if path.startswith('internal:'):
                # overlay plugin implemented using Python code
                plugin_name = path.lstrip('internal:')
                self._overlay_effects[plugin_name] = self.get_plugin(plugin_name)
            else:
                # Mapnix style overlay
                self._overlay_canvases.append(MapCanvas(overlay,
                                              self.rc.bounding_box,
                                              float(self._map_coords[2]),  # W
                                              float(self._map_coords[3]),  # H
                                              dpi))

        # Prepare the grid
        self.grid = self._create_grid(self._map_canvas, dpi)
        if index_position: # only show grid if an actual index refers to it
            self._apply_grid(self.grid, self._map_canvas)

        # Commit the internal rendering stack of the map
        self._map_canvas.render()
        for overlay_canvas in self._overlay_canvases:
            overlay_canvas.render()

    def _get_map_coords(self, index_position):
        """ Determine actual map output dimensions

        Parameters
        ----------
        index_position : str, optional
            One of 'side' or 'bottom' if an index is to be rendered
            on the same page.

        Returns
        -------
        list of float
            A list containing x and y coordinates of the upper left
            of the actual map render area, and its widht and height.
        """

        x = Renderer.PRINT_SAFE_MARGIN_PT
        y = Renderer.PRINT_SAFE_MARGIN_PT + self._title_margin_pt
        w = self._usable_area_width_pt
        h = self._usable_area_height_pt

        if index_position is None or index_position == 'extra_page':
            # No index displayed
            pass
        elif index_position == 'side':
            # Index present, displayed on the side
            w = w - self._index_area.w
            if self._index_area.x == Renderer.PRINT_SAFE_MARGIN_PT:
                # Index on the left -> map on the right
                x = x + self._index_area.w
        elif index_position == 'bottom':
            # Index present, displayed at the bottom -> map on top
            h = h - self._index_area.h
        else:
            raise AssertionError("Invalid index position %s"
                                 % repr(index_position))

        return (x, y, w, h)

    def _create_index_rendering(self, index_position):
        """Prepare to render the index.

        Parameters
        ----------
           index_position : str, optional
               None, "side", "bottom" or "extra_page"

        Returns
        -------
        List of (IndexRenderer, IndexRenderingArea).
            The actual index renderer and the area it will cover.
        """

        index_area = None

        # Now we determine the actual occupation of the index
        # TODO: index type choice should not be hard coded here
        if self.rc.indexer == 'Poi':
            # a special index is createad when a POI file is attached
            index_renderer = PoiIndexRenderer(self.rc.i18n,
                                                 self.street_index.categories)
        else:
            # TODO: use actual renderer type here?
            index_renderer = GeneralIndexRenderer(self.rc.i18n,
                                                 self.street_index.categories)

        # We use a fake vector device to determine the actual
        # rendering characteristics
        fake_surface = cairo.PDFSurface(None,
                                        self.paper_width_pt,
                                        self.paper_height_pt)

        # calculate the area required for the index, depending on its position
        try:
            if index_position == 'side':
                index_max_width_pt \
                    = self.MAX_INDEX_OCCUPATION_RATIO * self._usable_area_width_pt

                if not self.rc.i18n.isrtl():
                    # non-RTL: Index is on the right
                    index_area = index_renderer.precompute_occupation_area(
                        fake_surface,
                        ( self.paper_width_pt - Renderer.PRINT_SAFE_MARGIN_PT
                          - index_max_width_pt ),
                        ( Renderer.PRINT_SAFE_MARGIN_PT + self._title_margin_pt ),
                        index_max_width_pt,
                        self._usable_area_height_pt,
                        'width', 'right')
                else:
                    # RTL: Index is on the left
                    index_area = index_renderer.precompute_occupation_area(
                        fake_surface,
                        Renderer.PRINT_SAFE_MARGIN_PT,
                        ( Renderer.PRINT_SAFE_MARGIN_PT + self._title_margin_pt ),
                        index_max_width_pt,
                        self._usable_area_height_pt,
                        'width', 'left')
            elif index_position == 'bottom':
                # Index at the bottom of the page
                index_max_height_pt \
                    = self.MAX_INDEX_OCCUPATION_RATIO * self._usable_area_height_pt

                index_area = index_renderer.precompute_occupation_area(
                    fake_surface,
                    Renderer.PRINT_SAFE_MARGIN_PT,
                    ( self.paper_height_pt
                      - Renderer.PRINT_SAFE_MARGIN_PT
                      - self._copyright_margin_pt
                      - index_max_height_pt ),
                    self._usable_area_width_pt,
                    index_max_height_pt,
                    'height', 'bottom')
        except IndexDoesNotFitError:
            index_area = None

        return index_renderer, index_area


    def _draw_title(self, ctx, w_dots, h_dots, font_face):
        """ Draw mao title

        Draw the title at the current position inside a
        w_dots*h_dots rectangle.

        Parameters
        ----------
        ctx : cairo.Context
            The context to draw into
        w_dots : float
            Width of title bar in cairo units
        h_dots : float
            Height of title bar in cairo units
        font_face : str
            Pango font name

        Returns
        -------
        void
        """

        # Title background bar
        ctx.save()
        ctx.set_source_rgb(0.8, 0.9, 0.96) # TODO: make title bar color configurable?
        ctx.rectangle(0, 0, w_dots, h_dots)
        ctx.fill()
        ctx.restore()

        # Retrieve and paint logo to put to the right of the title
        logo_width = 0
        if self.rc.logo:
            ctx.save()
            grp, logo_width = self._get_logo(ctx, self.rc.logo, 0.8*h_dots)
            # TODO catch exceptions and just print warning instead?
            ctx.translate(w_dots - logo_width - 0.1*h_dots, 0.1*h_dots)
            ctx.set_source(grp)
            ctx.paint_with_alpha(0.5)
            ctx.restore()

        # Retrieve and paint the extra logo to put to the left of the title
        logo_width2 = 0
        if self.rc.extra_logo:
            ctx.save()
            grp, logo_width2 = self._get_logo(ctx, self.rc.extra_logo, 0.8*h_dots)
            # TODO catch exceptions and just print warning instead?
            ctx.translate(0.4*h_dots, 0.1*h_dots)
            ctx.set_source(grp)
            ctx.paint_with_alpha(0.5)
            logo_width2 += 0.4*h_dots # TODO: why hardcoding the distance between logo and text?
            ctx.restore()

        # Prepare the title
        pc = PangoCairo.create_context(ctx)
        layout = PangoCairo.create_layout(ctx)
        layout.set_width(int((w_dots - 0.1*w_dots - logo_width - logo_width2) * Pango.SCALE))
        if not self.rc.i18n.isrtl():
            layout.set_alignment(Pango.Alignment.LEFT)
        else:
            layout.set_alignment(Pango.Alignment.RIGHT)
        fd = Pango.FontDescription(font_face)
        fd.set_size(Pango.SCALE)
        layout.set_font_description(fd)
        layout.set_text(self.rc.title, -1)
        draw_utils.adjust_font_size(layout, fd, layout.get_width(), 0.8*h_dots)

        # Draw the title
        ctx.save()
        ctx.set_line_width(1)
        ctx.rectangle(0, 0, w_dots, h_dots)
        ctx.stroke()
        ctx.translate(0.4*h_dots + logo_width2,
                      (h_dots -
                       (layout.get_size()[1] / Pango.SCALE)) / 2.0)
        PangoCairo.update_layout(ctx, layout)
        PangoCairo.show_layout(ctx, layout)
        ctx.restore()


    def _draw_copyright_notice(self, ctx, w_dots, h_dots, notice=None,
                               osm_date=None):
        """ Draw copyright / annotation notice

        Draw a copyright notice at current location and within the
        given w_dots*h_dots rectangle.

        Parameters
        ----------
        ctx : cairo.Context
            Cairo context to draw into
        w_dots : float
            Width of bottom bar in cairo units
        h_dots : float
            Height of bottom bar in cairo units
        notice : str, optional
            Optional notice text to replace the default.
        osm_date : datetime, optional
            Timestamp the OSM data was last updated at.

        Returns
        -------
        void

           w_dots,h_dots (number): Rectangle dimension (ciaro units).
           font_face (str): Pango font specification.
           notice (str): Optional notice to replace the default.
        """

        if notice is None:
            annotations = self._annotations(osm_date)

            notice = annotations['maposmatic'] + '\n'

            if annotations['styles']:
                notice+= ngettext(u'Map style:',u'Map styles:', len(annotations['styles']))
                notice+= ' ' + '; '.join(annotations['styles']) + '\n'

            if annotations['sources']:
                notice+= ngettext(u'Data source:',u'Data sources:', len(annotations['sources']))
                notice+= ' ' + '; '.join(list(annotations['sources'])) + '\n'

        # do the actual output drawing
        ctx.save()
        pc = PangoCairo.create_context(ctx)
        fd = Pango.FontDescription('DejaVu')
        fd.set_size(Pango.SCALE)
        layout = PangoCairo.create_layout(ctx)
        layout.set_font_description(fd)
        layout.set_text(notice, -1)
        draw_utils.adjust_font_size(layout, fd, w_dots, h_dots)
        PangoCairo.update_layout(ctx, layout)
        PangoCairo.show_layout(ctx, layout)
        ctx.restore()

    def render(self, cairo_surface, dpi, osm_date):
        """ Render the complete map page, including all components

        Renders the map, the index and all other visual map features on the
        given Cairo surface.

        Parameters
        ----------
        cairo_surface : cairo.Surface
            Cairo destination device surface to render into
        dpi : int
            Dots per inch to use with this surface
        osm_date : datetime
            Timestamp of last OSM database update

        Returns
        -------
        void
        """
        LOG.info('SinglePageRenderer rendering -%s- on %dx%dmm paper at %d dpi.' %
                 (self.rc.output_format, self.rc.paper_width_mm, self.rc.paper_height_mm, dpi))

        # First determine some useful drawing parameters
        safe_margin_dots \
            = commons.convert_pt_to_dots(Renderer.PRINT_SAFE_MARGIN_PT, dpi)

        usable_area_width_dots \
            = commons.convert_pt_to_dots(self._usable_area_width_pt, dpi)

        usable_area_height_dots \
            = commons.convert_pt_to_dots(self._usable_area_height_pt, dpi)

        title_margin_dots \
            = commons.convert_pt_to_dots(self._title_margin_pt, dpi)

        copyright_margin_dots \
            = commons.convert_pt_to_dots(self._copyright_margin_pt, dpi)

        map_coords_dots = list(map(lambda l: commons.convert_pt_to_dots(l, dpi),
                              self._map_coords))

        # create the cairo context to draw into
        ctx = cairo.Context(cairo_surface)

        # Set a white background (so that generated bitmaps are not transparent)
        ctx.save()
        ctx.set_source_rgb(1, 1, 1)
        ctx.rectangle(0, 0,
                      commons.convert_pt_to_dots(self.paper_width_pt, dpi),
                      commons.convert_pt_to_dots(self.paper_height_pt, dpi))
        ctx.fill()
        ctx.restore()

        ##
        ## Draw the map, scaled to fit the designated area
        ##
        ctx.save()

        # prevent map background from filling the full canvas
        ctx.rectangle(map_coords_dots[0], map_coords_dots[1], map_coords_dots[2], map_coords_dots[3])
        ctx.clip()

        # Prepare to draw the map at the right location
        ctx.translate(map_coords_dots[0], map_coords_dots[1])

        # Draw the rescaled Map
        ctx.save()
        scale_factor = int(dpi / 72)
        rendered_map = self._map_canvas.get_rendered_map()
        LOG.info('Map:')
        LOG.info('Mapnik scale: 1/%f' % rendered_map.scale_denominator())
        LOG.info('Actual scale: 1/%f' % self._map_canvas.get_actual_scale())
        LOG.info('Zoom factor: %d' % self.scaleDenominator2zoom(rendered_map.scale_denominator()))

        # now perform the actual map drawing
        self.rc.status_update(_("%s: rendering base map") % self.rc.output_format)
        mapnik.render(rendered_map, ctx, scale_factor, 0, 0)
        ctx.restore()

        # Draw the rescaled Overlays on top of the map one by one
        for overlay_canvas in self._overlay_canvases:
            ctx.save()
            rendered_overlay = overlay_canvas.get_rendered_map()
            LOG.info('Overlay: %s' % overlay_canvas.get_style_name())
            self.rc.status_update(_("%(format)s: rendering '%(style)s' overlay")
                                  % { 'format': self.rc.output_format,
                                      'style': overlay_canvas.get_style_name(),
                                     })
            mapnik.render(rendered_overlay, ctx, scale_factor, 0, 0)
            ctx.restore()

        # Place the vertical and horizontal square labels
        if self.grid and self.index_position:
            self._draw_labels(ctx, self.grid,
                              map_coords_dots[2],
                              map_coords_dots[3],
                              commons.convert_pt_to_dots(self._grid_legend_margin_pt,
                                                         dpi))
        ctx.restore()

        # Draw a rectangle frame around the map
        ctx.save()
        ctx.set_line_width(1)
        ctx.rectangle(map_coords_dots[0], map_coords_dots[1], map_coords_dots[2], map_coords_dots[3])
        ctx.stroke()
        ctx.restore()

        # make sure that plugins do not render outside the actual map area
        ctx.save()
        ctx.translate(map_coords_dots[0], map_coords_dots[1])
        ctx.rectangle(0, 0, map_coords_dots[2], map_coords_dots[3])
        ctx.clip()

        # apply effect plugin overlays
        for plugin_name, effect in self._overlay_effects.items():
            self.rc.status_update(_("%(format)s: rendering '%(style)s' overlay")
                                  % { 'format': self.rc.output_format,
                                      'style':  plugin_name,
                                     })
            try:
                effect.render(self, ctx)
            except Exception as e:
                # TODO better logging
                LOG.warning("Error while rendering overlay: %s\n%s" % (plugin_name, e))
        ctx.restore()

        ##
        ## Draw the title
        ##
        if self.rc.title:
            ctx.save()
            ctx.translate(safe_margin_dots, safe_margin_dots)
            self._draw_title(ctx, usable_area_width_dots,
                             title_margin_dots, 'Droid Sans Bold')
            ctx.restore()

        ##
        ## Draw the index, when applicable
        ##

        # Update the street_index to reflect the grid's actual position
        if self.grid and self.street_index and self.index_position is not None:
            self.rc.status_update(_("%s: writing CSV index file") % self.rc.output_format)
            self.street_index.apply_grid(self.grid)

            # Dump the CSV street index
            self.street_index.write_to_csv(self.rc.title, '%s.csv' % self.file_prefix)

        if self._index_renderer and self._index_area:
            ctx.save()

            # NEVER use ctx.scale() here because otherwise pango will
            # choose different font metrics which may be incompatible
            # with what has been computed by __init__(), which may
            # require more columns than expected !  Instead, we have
            # to trick pangocairo into believing it is rendering to a
            # device with the same default resolution, but with a
            # cairo resolution matching the 'dpi' specified
            # resolution. See
            # index::render::StreetIndexRenederer::render() and
            # comments within.

            self.rc.status_update(_("%s: rendering index") % self.rc.output_format)
            self._index_renderer.render(ctx, self._index_area, dpi)

            ctx.restore()

            # Also draw a rectangle frame around the index
            ctx.save()
            ctx.set_line_width(1)
            ctx.rectangle(commons.convert_pt_to_dots(self._index_area.x, dpi),
                          commons.convert_pt_to_dots(self._index_area.y, dpi),
                          commons.convert_pt_to_dots(self._index_area.w, dpi),
                          commons.convert_pt_to_dots(self._index_area.h, dpi))
            ctx.stroke()
            ctx.restore()

        ##
        ## Draw the copyright notice
        ##
        ctx.save()

        # Move to the right position
        ctx.translate(safe_margin_dots,
                      ( safe_margin_dots + title_margin_dots
                        + usable_area_height_dots
                        + copyright_margin_dots/4. ) )

        # Draw the copyright notice
        self._draw_copyright_notice(ctx, usable_area_width_dots,
                                    copyright_margin_dots,
                                    osm_date=osm_date)
        ctx.restore()

        # render index on 2nd page if requested, and output format supports it
        try:
            if self.index_position == 'extra_page' and self._has_multipage_format() and self._index_renderer is not None:
                self.rc.status_update(_("%s: rendering extra index page") % self.rc.output_format)

                # We use a fake vector device to determine the actual
                # rendering characteristics
                fake_surface = cairo.PDFSurface(None,
                                                self.paper_width_pt,
                                                self.paper_height_pt)

                usable_area_width_pt = (self.paper_width_pt -
                                        2 * Renderer.PRINT_SAFE_MARGIN_PT)
                usable_area_height_pt = (self.paper_height_pt -
                                         2 * Renderer.PRINT_SAFE_MARGIN_PT)

                index_area = self._index_renderer.precompute_occupation_area(
                    fake_surface,
                    Renderer.PRINT_SAFE_MARGIN_PT,
                    ( self.paper_height_pt
                      - Renderer.PRINT_SAFE_MARGIN_PT
                      - usable_area_height_pt
                    ),
                    usable_area_width_pt,
                    usable_area_height_pt,
                    'width', 'left')

                cairo_surface.show_page()

                # Set a white background (so that generated bitmaps are not transparent)
                ctx.save()
                ctx.set_source_rgb(1, 1, 1)
                ctx.rectangle(0, 0,
                              commons.convert_pt_to_dots(self.paper_width_pt, dpi),
                              commons.convert_pt_to_dots(self.paper_height_pt, dpi))
                ctx.fill()
                ctx.restore()

                # render the actual index
                ctx.save()
                self._index_renderer.render(ctx, index_area, dpi)
                ctx.restore()

                cairo_surface.show_page()
            else:
                cairo_surface.flush()
        except IndexDoesNotFitError:
            cairo_surface.flush()

    @staticmethod
    def _generic_get_minimal_paper_size(bounding_box,
                                        scale=Renderer.DEFAULT_SCALE,
                                        index_position = None):
        """

        Parameters
        ----------
        bounding_box : coords.BoundingBox
        scale : float, optional
        index_position : str, optional

        Returns
        -------
        list of int
            Minimal necessary widht and height
        """

        # the mapnik scale depends on the latitude
        lat = bounding_box.get_top_left()[0]
        scale *= math.cos(math.radians(lat))

        # by convention, mapnik uses 90 ppi whereas cairo uses 72 ppi
        scale *= float(72) / 90

        geo_height_m, geo_width_m = bounding_box.spheric_sizes()
        canvas_width_mm = geo_width_m * 1000 / scale
        canvas_height_mm = geo_height_m * 1000 / scale

        LOG.info('Map represents %dx%dm, needs at least %.0fx%.fmm '
                 'on paper at scale %f.' % (geo_width_m, geo_height_m,
                                            canvas_width_mm, canvas_height_mm, scale))

        paper_width_mm  = canvas_width_mm
        paper_height_mm = canvas_height_mm

        # Take index into account, when applicable
        if index_position == 'side':
            paper_width_mm /= (1. -
                               SinglePageRenderer.MAX_INDEX_OCCUPATION_RATIO)
        elif index_position == 'bottom':
            paper_height_mm /= (1. -
                                SinglePageRenderer.MAX_INDEX_OCCUPATION_RATIO)

        # Take margins into account
        paper_width_mm += 2 * commons.convert_pt_to_mm(Renderer.PRINT_SAFE_MARGIN_PT)
        paper_height_mm += 2 * commons.convert_pt_to_mm(Renderer.PRINT_SAFE_MARGIN_PT)

        # Take grid legend, title and copyright into account
        paper_width_mm /= 1 - Renderer.GRID_LEGEND_MARGIN_RATIO
        paper_height_mm /= 1 - (Renderer.GRID_LEGEND_MARGIN_RATIO
                                + Renderer.TITLE_MARGIN_RATIO
                                + Renderer.ANNOTATION_MARGIN_RATIO)

        # enforce minimal paper size
        if paper_width_mm < Renderer.MIN_PAPER_WIDTH:
            paper_height_mm = paper_height_mm * Renderer.MIN_PAPER_WIDTH / paper_width_mm
            paper_width_mm = Renderer.MIN_PAPER_WIDTH
        if paper_height_mm < Renderer.MIN_PAPER_HEIGHT:
            paper_width_mm = paper_width_mm * Renderer.MIN_PAPER_HEIGHT / paper_height_mm
            paper_height_mm = Renderer.MIN_PAPER_HEIGHT

        # Transform the values into integers
        paper_width_mm  = int(math.ceil(paper_width_mm))
        paper_height_mm = int(math.ceil(paper_height_mm))

        return (paper_width_mm, paper_height_mm)

    @staticmethod
    def _generic_get_compatible_paper_sizes(bounding_box,
                                            paper_sizes,
                                            scale=Renderer.DEFAULT_SCALE,
                                            index_position = None):
        """Returns a list of the compatible paper sizes for the given bounding
        box. The list is sorted, smaller papers first, and a "custom" paper
        matching the dimensions of the bounding box is added at the end.

        Args:
            bounding_box (coords.BoundingBox): the map geographic bounding box.
            scale (int): minimum mapnik scale of the map.
            index_position (str): None or 'side' (index on side),
              'bottom' (index at bottom), 'extra_page' (index on 2nd page for PDF).

        Returns a list of tuples (paper name, width in mm, height in
        mm, portrait_ok, landscape_ok, is_default). Paper sizes are
        represented in portrait mode.
        """

        paper_width_mm, paper_height_mm = SinglePageRenderer._generic_get_minimal_paper_size(bounding_box, scale, index_position)
        LOG.info('Best fit including decorations is %.0fx%.0fmm.' % (paper_width_mm, paper_height_mm))


        valid_sizes = []

        # Add a 'Custom' paper format to the list that perfectly matches the
        # bounding box.
        best_fit_is_portrait = paper_width_mm < paper_height_mm
        valid_sizes.append({
            "name": 'Best fit',
            "width": paper_width_mm,
            "height": paper_height_mm,
            "portrait_ok": best_fit_is_portrait,
            "portrait_scale": scale if best_fit_is_portrait else None,
            "portrait_zoom": Renderer.scaleDenominator2zoom(scale) if best_fit_is_portrait else None,
            "landscape_ok": not best_fit_is_portrait,
            "landscape_scale": scale if not best_fit_is_portrait else None,
            "landscape_zoom": Renderer.scaleDenominator2zoom(scale) if not best_fit_is_portrait else None,
        })

        # Test both portrait and landscape orientations when checking for paper
        # sizes.
        for name, w, h in paper_sizes:
            if w is None:
                continue

            portrait_ok  = paper_width_mm <= w and paper_height_mm <= h
            landscape_ok = paper_width_mm <= h and paper_height_mm <= w

            if portrait_ok:
                portrait_scale = scale / min(w / paper_width_mm, h / paper_height_mm)
                portrait_zoom = Renderer.scaleDenominator2zoom(portrait_scale)
            else:
                portrait_scale = None
                portrait_zoom = None

            if landscape_ok:
                landscape_scale = scale / min(h / paper_width_mm, w / paper_height_mm)
                landscape_zoom = Renderer.scaleDenominator2zoom(landscape_scale)
            else:
                landscape_scale = None
                landscape_zoom = None

            if portrait_ok or landscape_ok:
                valid_sizes.append({
                    "name": name,
                    "width": w,
                    "height": h,
                    "portrait_ok": portrait_ok,
                    "portrait_scale": portrait_scale,
                    "portrait_zoom": portrait_zoom,
                    "landscape_ok": landscape_ok,
                    "landscape_scale": landscape_scale,
                    "landscape_zoom": landscape_zoom,
                })

        return valid_sizes





if __name__ == '__main__':
    import renderers
    import coords
    from ocitysmap import i18n

    # Hack to fake gettext
    try:
        _(u"Test gettext")
    except NameError:
        __builtins__.__dict__["_"] = lambda x: x

    logging.basicConfig(level=logging.DEBUG)

    bbox = coords.BoundingBox(48.8162, 2.3417, 48.8063, 2.3699)
    zoom = 16

    renderer_cls = renderers.get_renderer_class_by_name('plain')
    papers = renderer_cls.get_compatible_paper_sizes(bbox, zoom)

    print('Compatible paper sizes:')
    for p in papers:
        print('  * %s (%.1fx%.1fcm)' % (p[0], p[1]/10.0, p[2]/10.0))
    print('Using first available:', papers[0])

    class StylesheetMock:
        def __init__(self):
            # self.path = '/home/sam/src/python/maposmatic/mapnik-osm/osm.xml'
            self.path = '/mnt/data1/common/home/d2/Downloads/svn/mapnik-osm/osm.xml'
            self.grid_line_color = 'black'
            self.grid_line_alpha = 0.9
            self.grid_line_width = 2
            self.shade_color = 'black'
            self.shade_alpha = 0.7

    class RenderingConfigurationMock:
        def __init__(self):
            self.stylesheet = StylesheetMock()
            self.bounding_box = bbox
            self.paper_width_mm = papers[0][1]
            self.paper_height_mm = papers[0][2]
            self.i18n  = i18n.i18n()
            self.title = 'Au Kremlin-Bycêtre'
            self.polygon_wkt = bbox.as_wkt()

    config = RenderingConfigurationMock()

    plain = renderer_cls(config, '/tmp', None)
    surface = cairo.PDFSurface('/tmp/plain.pdf',
                   commons.convert_mm_to_pt(config.paper_width_mm),
                   commons.convert_mm_to_pt(config.paper_height_mm))

    plain.render(surface, commons.PT_PER_INCH)
    surface.finish()

    print("Generated /tmp/plain.pdf")
