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
import cairo
import rsvg
import datetime
import locale
import logging
import mapnik
assert mapnik.mapnik_version >= 200100, \
    "Mapnik module version %s is too old, see ocitysmap's INSTALL " \
    "for more details." % mapnik.mapnik_version_string()
import math
import pango
import pangocairo

import commons
import ocitysmap
from abstract_renderer import Renderer
from ocitysmap.indexlib.renderer import StreetIndexRenderer
from indexlib.indexer import StreetIndex
from indexlib.commons import IndexDoesNotFitError, IndexEmptyError
import draw_utils
from ocitysmap.maplib.map_canvas import MapCanvas

LOG = logging.getLogger('ocitysmap')


class SinglePageRenderer(Renderer):
    """
    This Renderer creates a full-page map, with the overlayed features
    like the grid, grid labels, scale and compass rose and can draw an
    index.
    """

    name = 'generic_single_page'
    description = 'A generic full-page layout with or without index.'

    MAX_INDEX_OCCUPATION_RATIO = 1/3.

    def __init__(self, db, rc, tmpdir, dpi, file_prefix,
                 index_position = 'side'):
        """
        Create the renderer.

        Args:
           rc (RenderingConfiguration): rendering parameters.
           tmpdir (os.path): Path to a temp dir that can hold temp files.
           index_position (str): None or 'side' (index on side),
              'bottom' (index at bottom).
        """
        Renderer.__init__(self, db, rc, tmpdir, dpi)

        # Prepare the index
        self.street_index = StreetIndex(db,
                                        rc.polygon_wkt,
                                        rc.i18n)
        if not self.street_index.categories:
            LOG.warning("Designated area leads to an empty index")
            self.street_index = None

        self._grid_legend_margin_pt = \
            min(Renderer.GRID_LEGEND_MARGIN_RATIO * self.paper_width_pt,
                Renderer.GRID_LEGEND_MARGIN_RATIO * self.paper_height_pt)
        self._title_margin_pt = 0.05 * self.paper_height_pt
        self._copyright_margin_pt = 0.02 * self.paper_height_pt

        self._usable_area_width_pt = (self.paper_width_pt -
                                      2 * Renderer.PRINT_SAFE_MARGIN_PT)
        self._usable_area_height_pt = (self.paper_height_pt -
                                       (2 * Renderer.PRINT_SAFE_MARGIN_PT +
                                        self._title_margin_pt +
                                        self._copyright_margin_pt))

        # Prepare the Index (may raise a IndexDoesNotFitError)
        if ( index_position and self.street_index
             and self.street_index.categories ):
            self._index_renderer, self._index_area \
                = self._create_index_rendering(index_position == "side")
        else:
            self._index_renderer, self._index_area = None, None

        # Prepare the layout of the whole page
        if not self._index_area:
            # No index displayed
            self._map_coords = ( Renderer.PRINT_SAFE_MARGIN_PT,
                                 ( Renderer.PRINT_SAFE_MARGIN_PT
                                   + self._title_margin_pt ),
                                 self._usable_area_width_pt,
                                 self._usable_area_height_pt )
        elif index_position == 'side':
            # Index present, displayed on the side
            if self._index_area.x > Renderer.PRINT_SAFE_MARGIN_PT:
                # Index on the right -> map on the left
                self._map_coords = ( Renderer.PRINT_SAFE_MARGIN_PT,
                                     ( Renderer.PRINT_SAFE_MARGIN_PT
                                       + self._title_margin_pt ),
                                     ( self._usable_area_width_pt
                                       - self._index_area.w ),
                                     self._usable_area_height_pt )
            else:
                # Index on the left -> map on the right
                self._map_coords = ( self._index_area.x + self._index_area.w,
                                     ( Renderer.PRINT_SAFE_MARGIN_PT
                                       + self._title_margin_pt ),
                                     ( self._usable_area_width_pt
                                       - self._index_area.w ),
                                     self._usable_area_height_pt )
        elif index_position == 'bottom':
            # Index present, displayed at the bottom -> map on top
            self._map_coords = ( Renderer.PRINT_SAFE_MARGIN_PT,
                                 ( Renderer.PRINT_SAFE_MARGIN_PT
                                   + self._title_margin_pt ),
                                 self._usable_area_width_pt,
                                 ( self._usable_area_height_pt
                                   - self._index_area.h ) )
        else:
            raise AssertionError("Invalid index position %s"
                                 % repr(index_position))

        # Prepare the map
        self._map_canvas = self._create_map_canvas(
            float(self._map_coords[2]),  # W
            float(self._map_coords[3]),  # H
            dpi,
            rc.osmid is not None )

        # Prepare map overlay
        if self.rc.overlay:
            self._overlay_canvas = MapCanvas(self.rc.overlay,
                                             self.rc.bounding_box,
                                             float(self._map_coords[2]),  # W
                                             float(self._map_coords[3]),  # H
                                             dpi)

        # Prepare map overlay
        if self.rc.overlay:
            self._overlay_canvas = MapCanvas(self.rc.overlay,
                                             self.rc.bounding_box,
                                             float(self._map_coords[2]),  # W
                                             float(self._map_coords[3]),  # H
                                             dpi)

        # Prepare map overlay
        if self.rc.overlay:
            self._overlay_canvas = MapCanvas(self.rc.overlay,
                                             self.rc.bounding_box,
                                             float(self._map_coords[2]),  # W
                                             float(self._map_coords[3]),  # H
                                             dpi)

        # Prepare the grid
        self.grid = self._create_grid(self._map_canvas, dpi)

        # Update the street_index to reflect the grid's actual position
        if self.grid and self.street_index:
            self.street_index.apply_grid(self.grid)

        # Dump the CSV street index
        if self.street_index:
            self.street_index.write_to_csv(rc.title, '%s.csv' % file_prefix)

        # Commit the internal rendering stack of the map
        self._map_canvas.render()
        if self.rc.overlay:
           self._overlay_canvas.render()

    def _create_index_rendering(self, on_the_side):
        """
        Prepare to render the Street index.

        Args:
           on_the_side (bool): True=index on the side, False=at bottom.

        Return a couple (StreetIndexRenderer, StreetIndexRenderingArea).
        """
        # Now we determine the actual occupation of the index
        index_renderer = StreetIndexRenderer(self.rc.i18n,
                                             self.street_index.categories)

        # We use a fake vector device to determine the actual
        # rendering characteristics
        fake_surface = cairo.PDFSurface(None,
                                        self.paper_width_pt,
                                        self.paper_height_pt)

        if on_the_side:
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
        else:
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

        return index_renderer, index_area


    def _draw_title(self, ctx, w_dots, h_dots, font_face):
        """
        Draw the title at the current position inside a
        w_dots*h_dots rectangle.

        Args:
           ctx (cairo.Context): The Cairo context to use to draw.
           w_dots,h_dots (number): Rectangle dimension (ciaro units)
           font_face (str): Pango font specification.
        """

        # Title background
        ctx.save()
        ctx.set_source_rgb(0.8, 0.9, 0.96)
        ctx.rectangle(0, 0, w_dots, h_dots)
        ctx.fill()
        ctx.restore()

        # Retrieve and paint the OSM logo
        ctx.save()
        grp, logo_width = self._get_osm_logo(ctx, 0.8*h_dots)
        if grp:
            ctx.translate(w_dots - logo_width - 0.1*h_dots, 0.1*h_dots)
            ctx.set_source(grp)
            ctx.paint_with_alpha(0.5)
        else:
            LOG.warning("OSM Logo not available.")
            logo_width = 0
        ctx.restore()

        # Prepare the title
        pc = pangocairo.CairoContext(ctx)
        layout = pc.create_layout()
        layout.set_width(int((w_dots - 0.1*w_dots - logo_width) * pango.SCALE))
        if not self.rc.i18n.isrtl(): layout.set_alignment(pango.ALIGN_LEFT)
        else:                        layout.set_alignment(pango.ALIGN_RIGHT)
        fd = pango.FontDescription(font_face)
        fd.set_size(pango.SCALE)
        layout.set_font_description(fd)
        layout.set_text(self.rc.title)
        draw_utils.adjust_font_size(layout, fd, layout.get_width(), 0.8*h_dots)

        # Draw the title
        ctx.save()
        ctx.rectangle(0, 0, w_dots, h_dots)
        ctx.stroke()
        ctx.translate(0.1*h_dots,
                      (h_dots -
                       (layout.get_size()[1] / pango.SCALE)) / 2.0)
        pc.show_layout(layout)
        ctx.restore()


    def _draw_copyright_notice(self, ctx, w_dots, h_dots, notice=None,
                               osm_date=None):
        """
        Draw a copyright notice at current location and within the
        given w_dots*h_dots rectangle.

        Args:
           ctx (cairo.Context): The Cairo context to use to draw.
           w_dots,h_dots (number): Rectangle dimension (ciaro units).
           font_face (str): Pango font specification.
           notice (str): Optional notice to replace the default.
        """

        today = datetime.date.today()
        notice = notice or \
            _(u'Copyright © %(year)d MapOSMatic/OCitySMap developers. '
              u'Map data © %(year)d OpenStreetMap.org '
              u'and contributors (cc-by-sa).\n'
              u'Map rendered on: %(date)s. OSM data updated on: %(osmdate)s. '
              u'The map may be incomplete or inaccurate. '
              u'You can contribute to improve this map. '
              u'See http://wiki.openstreetmap.org')

        # We need the correct locale to be set for strftime().
        prev_locale = locale.getlocale(locale.LC_TIME)
        locale.setlocale(locale.LC_TIME, self.rc.i18n.language_code())
        try:
            if osm_date is None:
                osm_date_str = _(u'unknown')
            else:
                osm_date_str = osm_date.strftime("%d %B %Y %H:%M")

            notice = notice % {'year': today.year,
                               'date': today.strftime("%d %B %Y"),
                               'osmdate': osm_date_str}
        finally:
            locale.setlocale(locale.LC_TIME, prev_locale)

        ctx.save()
        pc = pangocairo.CairoContext(ctx)
        fd = pango.FontDescription('DejaVu')
        fd.set_size(pango.SCALE)
        layout = pc.create_layout()
        layout.set_font_description(fd)
        layout.set_text(notice)
        draw_utils.adjust_font_size(layout, fd, w_dots, h_dots)
        pc.show_layout(layout)
        ctx.restore()


    def render(self, cairo_surface, dpi, osm_date):
        """Renders the map, the index and all other visual map features on the
        given Cairo surface.

        Args:
            cairo_surface (Cairo.Surface): the destination Cairo device.
            dpi (int): dots per inch of the device.
        """
        LOG.info('SinglePageRenderer rendering on %dx%dmm paper at %d dpi.' %
                 (self.rc.paper_width_mm, self.rc.paper_height_mm, dpi))

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

        map_coords_dots = map(lambda l: commons.convert_pt_to_dots(l, dpi),
                              self._map_coords)

        ctx = cairo.Context(cairo_surface)

        # Set a white background
        ctx.save()
        ctx.set_source_rgb(1, 1, 1)
        ctx.rectangle(0, 0, commons.convert_pt_to_dots(self.paper_width_pt, dpi),
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
        scale_factor = dpi / 72
        rendered_map = self._map_canvas.get_rendered_map()
        LOG.debug('Map:')
        LOG.debug('Mapnik scale: 1/%f' % rendered_map.scale_denominator())
        LOG.debug('Actual scale: 1/%f' % self._map_canvas.get_actual_scale())
        mapnik.render(rendered_map, ctx, scale_factor, 0, 0)
        ctx.restore()

        # Draw the rescaled Overlay
        if self.rc.overlay:
            LOG.debug('Overlay:')
            ctx.save()
            scale_factor = dpi / 72
            rendered_overlay = self._overlay_canvas.get_rendered_map()
            mapnik.render(rendered_overlay, ctx, scale_factor, 0, 0)
            ctx.restore()

        # Draw a rectangle around the map
        ctx.rectangle(0, 0, map_coords_dots[2], map_coords_dots[3])
        ctx.stroke()

        # Place the vertical and horizontal square labels
        self._draw_labels(ctx, self.grid,
                          map_coords_dots[2],
                          map_coords_dots[3],
                          commons.convert_pt_to_dots(self._grid_legend_margin_pt,
                                                   dpi))
        ctx.restore()

        ##
        ## Draw the title
        ##
        ctx.save()
        ctx.translate(safe_margin_dots, safe_margin_dots)
        self._draw_title(ctx, usable_area_width_dots,
                         title_margin_dots, 'Georgia Bold')
        ctx.restore()

        ##
        ## Draw the index, when applicable
        ##
        if self._index_renderer and self._index_area:
            ctx.save()

            # NEVER use ctx.scale() here because otherwise pango will
            # choose different dont metrics which may be incompatible
            # with what has been computed by __init__(), which may
            # require more columns than expected !  Instead, we have
            # to trick pangocairo into believing it is rendering to a
            # device with the same default resolution, but with a
            # cairo resolution matching the 'dpi' specified
            # resolution. See
            # index::render::StreetIndexRenederer::render() and
            # comments within.

            self._index_renderer.render(ctx, self._index_area, dpi)

            ctx.restore()

            # Also draw a rectangle
            ctx.save()
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

        # Draw compass rose
        # TODO: proper positioning/scaling, move to abstract renderer
        ctx.save();
        ctx.translate(50, title_margin_dots + 50);
        ctx.scale(0.33, 0.33)
        compass_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'images', 'compass-rose.svg'))
        svg = rsvg.Handle(compass_path)
        svg.render_cairo(ctx)
        ctx.restore();

        # TODO: map scale

        cairo_surface.flush()

    @staticmethod
    def _generic_get_compatible_paper_sizes(bounding_box,
                                            scale=Renderer.DEFAULT_SCALE, index_position = None):
        """Returns a list of the compatible paper sizes for the given bounding
        box. The list is sorted, smaller papers first, and a "custom" paper
        matching the dimensions of the bounding box is added at the end.

        Args:
            bounding_box (coords.BoundingBox): the map geographic bounding box.
            scale (int): minimum mapnik scale of the map.
           index_position (str): None or 'side' (index on side),
              'bottom' (index at bottom).

        Returns a list of tuples (paper name, width in mm, height in
        mm, portrait_ok, landscape_ok, is_default). Paper sizes are
        represented in portrait mode.
        """

        # the mapnik scale depends on the latitude
        lat = bounding_box.get_top_left()[0]
        scale *= math.cos(math.radians(lat))

        # by convention, mapnik uses 90 ppi whereas cairo uses 72 ppi
        scale *= float(72) / 90

        geo_height_m, geo_width_m = bounding_box.spheric_sizes()
        paper_width_mm = geo_width_m * 1000 / scale
        paper_height_mm = geo_height_m * 1000 / scale

        LOG.debug('Map represents %dx%dm, needs at least %.1fx%.1fcm '
                  'on paper.' % (geo_width_m, geo_height_m,
                                 paper_width_mm/10., paper_height_mm/10.))

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
        paper_height_mm /= 1 - (Renderer.GRID_LEGEND_MARGIN_RATIO + 0.05 + 0.02)

        # Transform the values into integers
        paper_width_mm  = int(math.ceil(paper_width_mm))
        paper_height_mm = int(math.ceil(paper_height_mm))

        LOG.debug('Best fit is %.1fx%.1fcm.' % (paper_width_mm/10., paper_height_mm/10.))

        # Test both portrait and landscape orientations when checking for paper
        # sizes.
        valid_sizes = []
        for name, w, h in ocitysmap.layoutlib.PAPER_SIZES:
            portrait_ok  = paper_width_mm <= w and paper_height_mm <= h
            landscape_ok = paper_width_mm <= h and paper_height_mm <= w

            if portrait_ok or landscape_ok:
                valid_sizes.append([name, w, h, portrait_ok, landscape_ok, False])

        # Add a 'Custom' paper format to the list that perfectly matches the
        # bounding box.
        valid_sizes.append(['Best fit',
                            min(paper_width_mm, paper_height_mm),
                            max(paper_width_mm, paper_height_mm),
                            paper_width_mm < paper_height_mm,
                            paper_width_mm > paper_height_mm,
                            False])

        # select the first one as default
        valid_sizes[0][5] = True

        return valid_sizes


class SinglePageRendererNoIndex(SinglePageRenderer):

    name = 'plain'
    description = 'Full-page layout without index.'

    def __init__(self, db, rc, tmpdir, dpi, file_prefix):
        """
        Create the renderer.

        Args:
           rc (RenderingConfiguration): rendering parameters.
           tmpdir (os.path): Path to a temp dir that can hold temp files.
        """
        SinglePageRenderer.__init__(self, db, rc, tmpdir, dpi, file_prefix, None)


    @staticmethod
    def get_compatible_paper_sizes(bounding_box,
                                   scale=Renderer.DEFAULT_SCALE):
        """Returns a list of the compatible paper sizes for the given bounding
        box. The list is sorted, smaller papers first, and a "custom" paper
        matching the dimensions of the bounding box is added at the end.

        Args:
            bounding_box (coords.BoundingBox): the map geographic bounding box.
            scale (int): minimum mapnik scale of the map.

        Returns a list of tuples (paper name, width in mm, height in
        mm, portrait_ok, landscape_ok). Paper sizes are represented in
        portrait mode.
        """
        return SinglePageRenderer._generic_get_compatible_paper_sizes(
            bounding_box, scale, None)


class SinglePageRendererIndexOnSide(SinglePageRenderer):

    name = 'single_page_index_side'
    description = 'Full-page layout with the index on the side.'

    def __init__(self, db, rc, tmpdir, dpi, file_prefix):
        """
        Create the renderer.

        Args:
           rc (RenderingConfiguration): rendering parameters.
           tmpdir (os.path): Path to a temp dir that can hold temp files.
        """
        SinglePageRenderer.__init__(self, db, rc, tmpdir, dpi, file_prefix, 'side')

    @staticmethod
    def get_compatible_paper_sizes(bounding_box,
                                   scale=Renderer.DEFAULT_SCALE):
        """Returns a list of the compatible paper sizes for the given bounding
        box. The list is sorted, smaller papers first, and a "custom" paper
        matching the dimensions of the bounding box is added at the end.

        Args:
            bounding_box (coords.BoundingBox): the map geographic bounding box.
            scale (int): minimum mapnik scale of the map.

        Returns a list of tuples (paper name, width in mm, height in
        mm, portrait_ok, landscape_ok). Paper sizes are represented in
        portrait mode.
        """
        return SinglePageRenderer._generic_get_compatible_paper_sizes(
            bounding_box, scale, 'side')


class SinglePageRendererIndexBottom(SinglePageRenderer):

    name = 'single_page_index_bottom'
    description = 'Full-page layout with the index at the bottom.'

    def __init__(self, db, rc, tmpdir, dpi, file_prefix):
        """
        Create the renderer.

        Args:
           rc (RenderingConfiguration): rendering parameters.
           tmpdir (os.path): Path to a temp dir that can hold temp files.
        """
        SinglePageRenderer.__init__(self, db, rc, tmpdir, dpi, file_prefix, 'bottom')

    @staticmethod
    def get_compatible_paper_sizes(bounding_box,
                                   scale=Renderer.DEFAULT_SCALE):
        """Returns a list of the compatible paper sizes for the given bounding
        box. The list is sorted, smaller papers first, and a "custom" paper
        matching the dimensions of the bounding box is added at the end.

        Args:
            bounding_box (coords.BoundingBox): the map geographic bounding box.
            scale (int): minimum mapnik scale of the map.

        Returns a list of tuples (paper name, width in mm, height in
        mm, portrait_ok, landscape_ok). Paper sizes are represented in
        portrait mode.
        """
        return SinglePageRenderer._generic_get_compatible_paper_sizes(
            bounding_box, scale, 'bottom')


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

    print 'Compatible paper sizes:'
    for p in papers:
        print '  * %s (%.1fx%.1fcm)' % (p[0], p[1]/10.0, p[2]/10.0)
    print 'Using first available:', papers[0]

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

    print "Generated /tmp/plain.pdf"
