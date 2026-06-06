# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2022 Hartmut Holzgraefe

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

from natsort import natsorted
from itertools import groupby
from functools import reduce
import csv
import datetime
import math
import psycopg2
from sys import maxsize
from gettext import gettext

import cairo
import gi
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Pango, PangoCairo
import draw_utils

from .commons import Index, IndexCategory, IndexItem, IndexDoesNotFitError, IndexEmptyError
import ocitysmap.layoutlib.commons as UTILS
from ocitysmap.coords import Point
from .renderer import IndexRenderingArea
import logging
LOG = logging.getLogger('ocitysmap')

# TODO: define in single place, not in multiple files
PAGE_NUMBER_MARGIN_PT  = UTILS.convert_mm_to_pt(10)

class GeneralIndex(Index):
    name = "General"
    description = gettext(u"(* General Index *)")

    def __init__(self, db, renderer, bounding_box, polygon_wkt, i18n, page_number=None):
        """
        Prepare the index of the items inside the given WKT. This
        constructor will perform all the SQL queries.

        Parameters
        ----------
        db : psycopg2 DB) handle
            The GIS database
        renderer: ocitysmap.Renderer
            The renderer that called us
        bounding_box : ocitysmap.BoundingBox
            The bounding box of the map area
        polygon_wkt : str
            The WKT of the surrounding polygon of interest
        i18n : i18n.i18n
            Internationalization configuration
        page_number : int, optional
            Page number to show when creating multi page index pages
        """
        self._renderer = renderer
        self._bounding_box = bounding_box
        self._polygon_wkt = polygon_wkt
        self._i18n = i18n
        self._page_number = page_number

    @property
    def categories(self):
        return self._categories

    def add_category(self, name, items=None, is_street=False):
        """
        Add a new named category to the index.

        Parameters
        ----------
        name : str
            Display name of the category
        items : list of IndexItem, optional
            List of index entries if already known at this point
        is_street : bool, optional
            Whether this is a street index category (True) or a basic POI
            category (False, default)
        """
        self._categories.append(GeneralIndexCategory(name, items, is_street))

    def _build_query(self, tables, columns, where, group=False, join=None):
        """
        Helper function builing a SQL query string to extract index information
        from the osm2pgsql database.

        Parameters
        ----------
    tables: list of str
        osm2pgsql model tables to retrive data from, one or more of
        "point", "line", "polygon", "roads"
    columns: list of str
            One or more SQL expressions generating result columns
    where: str
        WHERE condition to filter for valid index entries
    group: bool, optional
        Whether to merge multiple items of same category and entry text

        Returns
        -------
        str
            SQL Query string ready to be executed
        """


        # first we create numbered aliases for all result column expressions
        # that we can easily refer to in GROUP BY, ORDER BY, and the outer query
        column_expressions = []
        column_aliases = []
        for column in columns:
            alias = "col_%d" % (len(column_aliases) + 1)
            column_expressions.append("%s AS %s" % (column, alias))
            column_aliases.append(alias)


        # next we generate one subquery per table to query, using a
        # template string and iterating over the table names
        subquery_template = """
SELECT %(columns)s,
       ST_INTERSECTION(%(wkb_limits)s, %(aggregate)stab1.%%(way)s%(aggreg_end)s) AS contour
           FROM planet_osm_%(table)s tab1
           %(join)s
          WHERE %(where)s
            AND ST_INTERSECTS(%%(way)s, %(wkb_limits)s)
          %(order_group)s
"""

        subquery_parts = []

        for table in tables:
            subquery_parts.append( subquery_template % {
                'table': table,
                'columns': ",".join(column_expressions),
                'where': where,
                'wkb_limits': ("ST_TRANSFORM(ST_GEOMFROMTEXT('%s' , 4326), 3857)"
                               % (self._polygon_wkt,)),
                'aggregate': "ST_LINEMERGE(ST_COLLECT(" if group else "",
                'aggreg_end': "))" if group else "",
                'order_group': ("GROUP BY %s" % (",".join(column_aliases))) if group else "",
                'join': join or '',
            })

        # finally we take all the subquery parts, join them with UNION,
        # and wrap them by the outer query returning the actual result
        subquery = ' UNION ' . join(subquery_parts)

        query = """
SELECT %(columns)s,
       ST_ASTEXT(ST_TRANSFORM(ST_LONGESTLINE(contour,contour),
                              4326)) AS longest_linestring
  FROM ( %(subquery)s
     ) AS foo
 ORDER BY %(columns)s
 """ % {'columns': (",".join(column_aliases)), 'subquery': subquery}

        return query

    @staticmethod
    def _run_query(cursor, query, debug=False):
        """
        Simple helper to execute a SQL query on the osm2pgsql tables

        First tries fast, but fragile way, falls back to stable but slower
        alternative in case of problems

        Parameters
        ----------
        cursor: psycopg2 database cursor
            Cursor to process the query with
        query: str
            The actual query string to execute, with '%(way)s'
            placeholder fo the actual Geometry column

        Returns
        -------
        void
        """
        try:
            if debug:
                LOG.warning(query % {'way':'way'})
            cursor.execute(query % {'way':'way'})
        except psycopg2.InternalError:
            # This exception generaly occurs when inappropriate ways have
            # to be cleaned. Using a buffer of 0 generaly helps to clean
            # them. This operation is not applied by default for
            # performance reasons.
            cursor.connection.rollback()
            cursor.execute(query % {'way':'st_buffer(way, 0)'})

    def get_index_entries(self, db, tables, columns, where, group=False, category_mapping=None, max_category_items=maxsize, join=None, debug=False):
        """
        Generates an index entry from query snippets. The generated query is supposed
        to return three columns: category name, index entry text, and the entries geometry.

        Parameters
        ----------
        db : psycopg2 database connection
        The database to retrieve the information from
    tables: list of str
        osm2pgsql model tables to retrive data from, one or more of
        "point", "line", "polygon", "roads"
    columns: list of str
            Two SQL expressions returning the category name (1st) and
        actual index entry text (2nd)
    where: str
        WHERE condition to filter for valid index entries
    group: bool, optional
        Whether to merge multiple items of same category and entry text
        category_mapping: dict, optional
            Map SQL category results to more readable values
        max_category_items: int, optional
            Maximum number of entries before a categorie is dismissed

        Returns
        -------
        dict
            A dictionary of IndexCategory objects with category name as key
        """
        cursor = db.cursor()
        result = {}

        query = self._build_query(tables, columns, where, group, join=join)

        self._run_query(cursor, query, debug)

        for amenity_type, amenity_name, linestring in cursor.fetchall():
            # Parse the WKT from the largest linestring in shape
            try:
                s_endpoint1, s_endpoint2 = map(lambda s: s.split(),
                                               linestring[11:-1].split(','))
            except (ValueError, TypeError):
                LOG.exception("Error parsing %s for %s"
                              % (repr(linestring),
                                 repr(amenity_name)))
                continue
            endpoint1 = Point(s_endpoint1[1], s_endpoint1[0])
            endpoint2 = Point(s_endpoint2[1], s_endpoint2[0])

            if category_mapping is not None and amenity_type in category_mapping:
                catname = category_mapping[amenity_type]
            else:
                catname = amenity_type

            if catname not in result:
                result[catname] = GeneralIndexCategory(catname, is_street=False)

            result[catname].items.append(GeneralIndexItem(amenity_name,
                                                          endpoint1,
                                                          endpoint2,
                                                          self._page_number))

        return [category for catname, category in sorted(result.items()) if (category.items and len(category.items) <= max_category_items)]

    def apply_grid(self, grid):
        """
        Update the location_str field of the streets and amenities by
        mapping them onto the given grid.

        Parameters
        ----------
            grid : ocitysmap.Grid
               The Grid object from which we compute the location strings

        Returns
        -------
            void
                Nothing, but self._categories has been modified as side effect
        """
        Index.apply_grid(self, grid)
        self._group_identical_grid_locations()

    def _group_identical_grid_locations(self):
        """
        Group locations whith the same name and the same position on the grid.

        Returns
        -------
            void
                Nothing, but self._categories has been modified as side effect
        """
        categories = []
        for category in self._categories:
            if category.is_street:
                categories.append(category)
                continue
            grouped_items = []
            sort_key = lambda item:(item.label, item.location_str)
            items = natsorted(category.items, key=sort_key)
            for label, same_items in groupby(items, key=sort_key):
                grouped_items.append(next(same_items))
            category.items = grouped_items

    def write_to_csv(self, title, output_filename):
        """
        Write out index data in CSV format

        Parameters
        ----------
        title: str
            Title to print to first line
        output_filename: str
            Path of the file to write to

        Returns
        -------
            void
        """
        # TODO: implement writing the index to CSV
        try:
            fd = open(output_filename, 'w', encoding='utf-8')
        except Exception as ex:
            LOG.warning('error while opening destination file %s: %s'
                      % (output_filename, ex))
            return

        LOG.debug("Creating CSV file %s..." % output_filename)
        writer = csv.writer(fd)

        # Try to treat indifferently unicode and str in CSV rows
        def csv_writerow(row):
            _r = []
            for e in row:
                _r.append(e)
            return writer.writerow(_r)

        copyright_notice = (u'© %(year)d MapOSMatic/ocitysmap authors. '
                            u'Map data © %(year)d OpenStreetMap.org '
                            u'and contributors (CC-BY-SA)' %
                            {'year': datetime.date.today().year})
        if title is not None:
            csv_writerow(['# (UTF-8)', title, copyright_notice])
        else:
            csv_writerow(['# (UTF-8)', '', copyright_notice])

        for category in self._categories:
            csv_writerow(['%s' % category.name])
            for item in category.items:
                csv_writerow(['', item.label, item.location_str or '???'])

        fd.close()

class GeneralIndexCategory(IndexCategory):
    def __init__(self, name, items=None, is_street=False):
        IndexCategory.__init__(self, name, items, is_street)

    def draw(self, rtl, ctx, pc, layout, fascent, fheight,
             baseline_x, baseline_y):
        """Draw this category header.

        Parameters
        ----------
            rtl : boolean
                Whether to draw right-to-left or not.
            ctx : cairo.Context
                The Cairo context to draw to.
            pc : pangocairo.CairoContext
                The PangoCairo context to use.
            layout : pango.layout
                The Pango layout to draw text into.
            fascent : int
                Font ascent.
            fheight : int
                Font height.
            baseline_x : int
                Base X axis position.
            baseline_y : int
                Base Y axis position.

        Returns
        -------
        int
            Actual rendering height used
        """

        # calculate header dimensions based on layout
        layout.set_auto_dir(False)
        layout.set_alignment(Pango.Alignment.CENTER)
        layout.set_text(self.name, -1)
        width, height = [x / Pango.SCALE for x in layout.get_size()]
        wrap_width = layout.get_width() / Pango.SCALE

        # draw the category header background bar
        ctx.save()
        ctx.set_source_rgb(0.9, 0.9, 0.9)
        ctx.rectangle(baseline_x, baseline_y - fascent, wrap_width, height)
        ctx.fill()

        # draw the actual category title text
        ctx.set_source_rgb(0.0, 0.0, 0.0)
        draw_utils.draw_text_center(ctx, layout, fascent,
                                    baseline_x, baseline_y, self.name)
        ctx.restore()

        # return total document height used
        return height

class GeneralIndexItem(IndexItem):
    """
    An IndexItem represents one item in the index (a street or a POI). It
    contains the item label (street name, POI name or description) and the
    humanized squares description.
    """
    def label_drawing_width(self, layout):
        """
        Category item text width

        Parameters
        ----------
           layout: pango.layout
               Layout to use to render index items

        Returns
        -------
        float
            Index entry type text width
        """
        layout.set_text(self.label, -1)
        return float(layout.get_size()[0]) / Pango.SCALE

    def label_drawing_height(self, layout):
        """
        Category item height width

        Parameters
        ----------
           layout: pango.layout
               Layout to use to render index items

        Returns
        -------
        float
            Index entry type text height
        """
        layout.set_text(self.label, -1)
        return float(layout.get_size()[1]) / Pango.SCALE

    def location_drawing_width(self, layout):
        """
        Parameters
        ----------
           layout: pango.layout
               Layout to use to render index items

        Returns
        -------
        float
            Index entry type text width
        """
        layout.set_text(self.location_str, -1)
        return float(layout.get_size()[0]) / Pango.SCALE

    def draw(self, rtl, ctx, pc, column_layout, fascent, fheight,
             baseline_x, baseline_y,
             label_layout=None, label_height=0, location_width=0):
        """Draw this index item to the provided Cairo context. It prints the
        label, the squares definition and the dotted line, with respect to the
        RTL setting.

        Args:
            rtl (boolean): right-to-left localization.
            ctx (cairo.Context): the Cairo context to draw to.
            pc (pangocairo.PangoCairo): the PangoCairo context for text
                drawing.
            column_layout (pango.Layout): the Pango layout to use for text
                rendering, pre-configured with the appropriate font.
            fascent (int): font ascent.
            fheight (int): font height.
            baseline_x (int): X axis coordinate of the baseline.
            baseline_y (int): Y axis coordinate of the baseline.
        Optional args (in case of label wrapping):
            label_layout (pango.Layout): the Pango layout to use for text
                rendering, in case the label should be wrapped
            label_height (int): height of the big label
            location_width (int): width of the 'location' part
        """

        # Fallbacks in case we dont't have a wrapping label
        if label_layout is None:
            label_layout = column_layout
        if label_height == 0:
            label_height = fheight

        if not self.location_str:
            location_str = '???'
        else:
            location_str = self.location_str

        ctx.save()
        ctx.set_source_rgb(0.0, 0.0, 0.0)
        if not rtl:
            # _, _,
            _, line_start = draw_utils.draw_text_left(ctx, label_layout,
                                            fascent,
                                            baseline_x, baseline_y,
                                            self.label)
            line_end, _ = draw_utils.draw_text_right(ctx, column_layout,
                                                     fascent,
                                                     baseline_x, baseline_y,
                                                     location_str)
        else:
            _, line_start = draw_utils.draw_text_left(ctx, column_layout,
                                                      fascent,
                                                      baseline_x, baseline_y,
                                                      location_str)
            line_end, _ = draw_utils.draw_text_right(ctx, label_layout,
                                                     fascent,
                                                     (baseline_x
                                                      + location_width),
                                                     baseline_y,
                                                     self.label)

        # In case of empty label, we don't draw the dots
        if self.label != '':
            draw_utils.draw_dotted_line(ctx, fheight/12,
                                        line_start + fheight/4, baseline_y,
                                        line_end - line_start - fheight/2)
        ctx.restore()



class GeneralIndexRenderingStyle:
    """
    The GeneralIndexRenderingStyle class defines how the header and
    label items should be drawn (font family, size, etc.).
    """
    __slots__ = ["header_font_spec", "label_font_spec"]

    def __init__(self, header_font_spec, label_font_spec):
        """
        Specify how the headers and label should be rendered. The
        Pango Font Speficication strings below are of the form
        "serif,monospace bold italic condensed 16". See
        http://www.pygtk.org/docs/pygtk/class-pangofontdescription.html
        for more details.

        Parameters
        ----------
            header_font_spec : str
                Pango Font Specification for the headers.
            label_font_spec : str
                Pango Font Specification for the labels.
        """
        self.header_font_spec = header_font_spec
        self.label_font_spec  = label_font_spec

    def __str__(self):
        return "Style(headers=%s, labels=%s)" % (repr(self.header_font_spec),
                                                 repr(self.label_font_spec))


class GeneralIndexRenderer:
    """
    """

    def __init__(self, i18n, index_categories,
                 street_index_rendering_styles \
                     = [ GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 16',
                                                   'DejaVu 12'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 14',
                                                   'DejaVu 10'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 12',
                                                   'DejaVu 8'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 10',
                                                   'DejaVu 7'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 8',
                                                   'DejaVu 6'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 6',
                                                   'DejaVu 5'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 5',
                                                   'DejaVu 4'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 4',
                                                   'DejaVu 3'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 3',
                                                   'DejaVu 2'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 2',
                                                   'DejaVu 2'),
                         GeneralIndexRenderingStyle('DejaVu Sans Condensed Bold 1',
                                                   'DejaVu 1'), ] ):
        self._i18n             = i18n
        self._index_categories = index_categories
        self._rendering_styles = street_index_rendering_styles

    def precompute_occupation_area(self, surface, x, y, w, h,
                                   freedom_direction, alignment):
        """Prepare to render the street and amenities index at the
        given (x,y) coordinates into the provided Cairo surface. The
        index must not be larger than the provided width and height
        (in pixels). Nothing will be drawn on surface.

        Parameters
        ----------
            surface : cairo.Surface
                The cairo surface to render into.
            x : int
                Horizontal origin position, in pixels.
            y : int
                Vertical origin position, in pixels.
            w : int
                Maximum usable width for the index, in dots (Cairo unit).
            h : int
                Maximum usable height for the index, in dots (Cairo unit).
            freedom_direction : str
                 Freedom direction, can be 'width' or
                'height'. See _compute_columns_split for more details.
            alignment : str
                'top' or 'bottom' for a freedom_direction of
                'height', 'left' or 'right' for 'width'.
                Tells which side to stick the index to.

        Returns
        -------
        Returns the actual graphical IndexRenderingArea defining
        how and where the index should be rendered. Raise
        IndexDoesNotFitError when the provided area's surface is not
        enough to hold the index.
        """
        if ((freedom_direction == 'height' and
             alignment not in ('top', 'bottom')) or
            (freedom_direction == 'width' and
             alignment not in ('left', 'right'))):
            raise ValueError('Incompatible freedom direction and alignment!')

        if not self._index_categories:
            raise IndexEmptyError

        LOG.debug("Determining index area within %dx%d+%d+%d aligned %s/%s..."
                  % (w,h,x,y, alignment, freedom_direction))

        # Create a PangoCairo context for drawing to Cairo
        ctx = cairo.Context(surface)
        pc  = PangoCairo.create_context(ctx)

        # Iterate over the rendering_styles until we find a suitable layout
        rendering_style = None
        for rs in self._rendering_styles:
            LOG.debug("Trying index fit using %s..." % rs)
            try:
                n_cols, min_dimension \
                    = self._compute_columns_split(ctx, pc, rs, w, h,
                                                  freedom_direction)

                # Great: index did fit OK !
                rendering_style = rs
                break

            except IndexDoesNotFitError:
                # Index did not fit => try smaller...
                LOG.debug("Index %s too large: should try a smaller one."
                        % rs)
                continue

        # Index really did not fit with any of the rendering styles ?
        if not rendering_style:
            raise IndexDoesNotFitError("Index does not fit in area")

        # Realign at bottom/top left/right
        if freedom_direction == 'height':
            index_width  = w
            index_height = min_dimension
        elif freedom_direction == 'width':
            index_width  = min_dimension
            index_height = h

        base_offset_x = 0
        base_offset_y = 0
        if alignment == 'bottom':
            base_offset_y = h - index_height
        if alignment == 'right':
            base_offset_x = w - index_width

        area = IndexRenderingArea(rendering_style,
                                  x+base_offset_x, y+base_offset_y,
                                  index_width, index_height, n_cols)
        LOG.debug("Will be able to render index in %s" % area)
        return area


    def render(self, ctx, p_rendering_area, dpi = UTILS.PT_PER_INCH):
        """
        Render the street and amenities index at the given (x,y)
        coordinates into the provided Cairo surface. The index must
        not be larger than the provided surface (use
        precompute_occupation_area() to adjust it).

        Args:
            ctx (cairo.Context): the cairo context to use for the rendering.
            rendering_area (IndexRenderingArea): the result from
                precompute_occupation_area().
            dpi (number): resolution of the target device.
        """

        rendering_area = p_rendering_area
        rendering_area.x = rendering_area.x + 1
        rendering_area.y = rendering_area.y + 1
        rendering_area.w = rendering_area.w - 2
        rendering_area.h = rendering_area.h - 2

        if not self._index_categories:
            raise IndexEmptyError

        LOG.debug("Rendering the street index within %s at %sdpi..."
                  % (rendering_area, dpi))

        #
        # In the following, the algorithm only manipulates values
        # expressed in 'pt'. Only the drawing-related functions will
        # translate them to cairo units
        #

        ctx.save()
        ctx.move_to(UTILS.convert_pt_to_dots(rendering_area.x, dpi),
                    UTILS.convert_pt_to_dots(rendering_area.y, dpi))

        # Create a PangoCairo context for drawing to Cairo
        pc = PangoCairo.create_context(ctx)

        header_fd = Pango.FontDescription(
            rendering_area.rendering_style.header_font_spec)
        label_fd  = Pango.FontDescription(
            rendering_area.rendering_style.label_font_spec)

        header_layout, header_fascent, header_fheight, header_em = \
                draw_utils.create_layout_with_font(ctx, header_fd)
        label_layout, label_fascent, label_fheight, label_em = \
                draw_utils.create_layout_with_font(ctx, label_fd)

        # By OCitysmap's convention, the default resolution is 72 dpi,
        # which maps to the default pangocairo resolution (96 dpi
        # according to pangocairo docs). If we want to render with
        # another resolution (different from 72), we have to scale the
        # pangocairo resolution accordingly:
        PangoCairo.context_set_resolution(label_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)
        PangoCairo.context_set_resolution(header_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)
        # All this is because we want pango to have the exact same
        # behavior as with the default 72dpi resolution. If we instead
        # decided to call cairo::scale, then pango might choose
        # different font metrics which don't fit in the prepared
        # layout anymore...

        margin = label_em
        column_width = int(rendering_area.w / rendering_area.n_cols)

        label_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin) * Pango.SCALE, dpi)))
        header_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin) * Pango.SCALE, dpi)))

        if not self._i18n.isrtl():
            offset_x = margin/2.
            delta_x  = column_width
        else:
            offset_x = rendering_area.w - column_width + margin/2.
            delta_x  = - column_width

        actual_n_cols = 1
        offset_y = margin/2.
        for category in self._index_categories:
            if ( offset_y + header_fheight + label_fheight
                 + margin/2. > rendering_area.h ):
                offset_y       = margin/2.
                offset_x      += delta_x
                actual_n_cols += 1

            height = category.draw(self._i18n.isrtl(), ctx, pc, header_layout,
                                   UTILS.convert_pt_to_dots(header_fascent, dpi),
                                   UTILS.convert_pt_to_dots(header_fheight, dpi),
                                   UTILS.convert_pt_to_dots(rendering_area.x
                                                            + offset_x, dpi),
                                   UTILS.convert_pt_to_dots(rendering_area.y
                                                            + offset_y
                                                            + header_fascent, dpi))

            offset_y += height * 72.0 / dpi

            for street in category.items:
                if ( offset_y + label_fheight + margin/2.
                     > rendering_area.h ):
                    offset_y       = margin/2.
                    offset_x      += delta_x
                    actual_n_cols += 1

                street.draw(self._i18n.isrtl(), ctx, pc, label_layout,
                            UTILS.convert_pt_to_dots(label_fascent, dpi),
                            UTILS.convert_pt_to_dots(label_fheight, dpi),
                            UTILS.convert_pt_to_dots(rendering_area.x
                                                     + offset_x, dpi),
                            UTILS.convert_pt_to_dots(rendering_area.y
                                                     + offset_y
                                                     + label_fascent, dpi))

                offset_y += label_fheight

        # Restore original context
        ctx.restore()

        # Simple verification...
        if actual_n_cols < rendering_area.n_cols:
            LOG.warning("Rounding/security margin lost some space (%d actual cols vs. allocated %d" % (actual_n_cols, rendering_area.n_cols))
        if actual_n_cols > rendering_area.n_cols:
            LOG.warning("Rounding/security margin used more space (%d actual cols vs. allocated %d" % (actual_n_cols, rendering_area.n_cols))


    def _compute_lines_occupation(self, ctx, pc, font_desc, n_em_padding,
                                  text_lines):
        """Compute the visual dimension parameters of the initial long column
        for the given text lines with the given font.

        Args:
            pc (pangocairo.CairoContext): the PangoCairo context.
            font_desc (pango.FontDescription): Pango font description,
                representing the used font at a given size.
            n_em_padding (int): number of extra em space to account for.
            text_lines (list): the list of text labels.

        Returns a dictionnary with the following key,value pairs:
            column_width: the computed column width (pixel size of the longest
                label).
            column_height: the total height of the column.
            fascent: scaled font ascent.
            fheight: scaled font height.
        """

        layout, fascent, fheight, em = draw_utils.create_layout_with_font(ctx,
                                                                     font_desc)
        #print "PREPARE", layout, fascent, fheight, em

        if len(text_lines):
            width = max(map(lambda x: self._label_width(layout, x), text_lines))
            # Save some extra space horizontally
            width += n_em_padding * em
        else:
            width = 0

        height = fheight * len(text_lines)

        return {'column_width': width, 'column_height': height,
                'fascent': fascent, 'fheight': fheight, 'em': em}


    def _label_width(self, layout, label):
        layout.set_text(label, -1)
        return float(layout.get_size()[0]) / Pango.SCALE

    def _compute_column_occupation(self, ctx, pc, rendering_style):
        """Returns the size of the tall column with all headers, labels and
        squares for the given font sizes.

        Args:
            pc (pangocairo.CairoContext): the PangoCairo context.
            rendering_style (GeneralIndexRenderingStyle): how to render the
                headers and labels.

        Return a tuple (width of tall column, height of tall column,
                        vertical margin to reserve after each small column).
        """

        header_fd = Pango.FontDescription(rendering_style.header_font_spec)
        label_fd  = Pango.FontDescription(rendering_style.label_font_spec)

        # Account for maximum square width (at worst " " + "Z99-Z99")
        label_block = self._compute_lines_occupation(ctx, pc, label_fd, 1+7,
                reduce(lambda x,y: x+y.get_all_item_labels(),
                       self._index_categories, []))

        # Reserve a small margin around the category headers
        headers_block = self._compute_lines_occupation(ctx, pc, header_fd, 2,
                [x.name for x in self._index_categories])

        column_width = max(label_block['column_width'],
                           headers_block['column_width'])
        column_height = label_block['column_height'] + \
                        headers_block['column_height']

        # We make sure there will be enough space for a header and a
        # label at the bottom of each column plus an additional
        # vertical margin (arbitrary set to 1em, see render())
        vertical_extra = ( label_block['fheight'] + headers_block['fheight']
                           + label_block['em'] )
        return column_width, column_height, vertical_extra


    def _compute_columns_split(self, ctx, pc, rendering_style,
                               zone_width_dots, zone_height_dots,
                               freedom_direction):
        """Computes the columns split for this index. From the one tall column
        width and height it finds the number of columns fitting on the zone
        dedicated to the index on the Cairo surface.

        If the columns split does not fit on the index zone,
        commons.IndexDoesNotFitError is raised.

        Args:
            pc (pangocairo.CairoContext): the PangoCairo context.
            rendering_style (GeneralIndexRenderingStyle): how to render the
                headers and labels.
            zone_width_dots (float): maximum width of the Cairo zone dedicated
                to the index.
            zone_height_dots (float): maximum height of the Cairo zone
                dedicated to the index.
            freedom_direction (string): the zone dimension that is flexible for
                rendering this index, can be 'width' or 'height'. If the
                streets don't fill the zone dedicated to the index, we need to
                try with a zone smaller in the freedom_direction.

        Returns a tuple (number of columns that will be in the index,
                         the new value for the flexible dimension).
        """

        tall_width, tall_height, vertical_extra = \
                self._compute_column_occupation(ctx, pc, rendering_style)

        if zone_width_dots < tall_width:
            raise IndexDoesNotFitError

        if freedom_direction == 'height':
            n_cols = math.floor(zone_width_dots / float(tall_width))
            if n_cols <= 0:
                raise IndexDoesNotFitError

            min_required_height \
                = math.ceil(float(tall_height + n_cols*vertical_extra)
                            / n_cols)

            LOG.debug("min req H %f vs. allocatable H %f"
                      % (min_required_height, zone_height_dots))

            if min_required_height > zone_height_dots:
                raise IndexDoesNotFitError

            return int(n_cols), min_required_height

        elif freedom_direction == 'width':
            n_cols = math.ceil(float(tall_height) / zone_height_dots)
            extra = n_cols * vertical_extra
            min_required_width = n_cols * tall_width

            if ( (min_required_width > zone_width_dots)
                 or (tall_height + extra > n_cols * zone_height_dots) ):
                raise IndexDoesNotFitError

            return int(n_cols), min_required_width

        raise ValueError('Invalid freedom direction!')

class MultiPageIndexRenderer:
    """
    The MultiPageIndexRenderer class encapsulates all the logic
    related to the rendering of the street index on multiple pages
    """

    # ctx: Cairo context
    # surface: Cairo surface
    def __init__(self, i18n, ctx, surface, index_categories, paper_size, rendering_area,
                 page_offset):
        self._i18n           = i18n
        self.ctx            = ctx
        self.surface        = surface
        self.index_categories = index_categories
        self.paper_width_pt   = paper_size[0]
        self.paper_height_pt  = paper_size[1]
        self.rendering_area_x = rendering_area[0]
        self.rendering_area_y = rendering_area[1]
        self.rendering_area_w = rendering_area[2]
        self.rendering_area_h = rendering_area[3]
        self.page_offset      = page_offset
        self.index_page_num   = 0

    def _draw_page_number(self):
        self.ctx.save()
        self.ctx.translate(self.rendering_area_x,
                           self.rendering_area_y)
        draw_utils.render_page_number(self.ctx,
                                      self.index_page_num + self.page_offset,
                                      self.rendering_area_w,
                                      self.rendering_area_h,
                                      PAGE_NUMBER_MARGIN_PT,
                                      transparent_background = False)
        self.ctx.restore()
        try:
            self.surface.set_page_label(_(u'Index page %d') % (self.index_page_num + 1))
        except Exception:
            pass

    def _new_page(self):
        if self.index_page_num > 0:
            self.surface.show_page()

        # Set a white background (so that generated bitmaps are not transparent)
        self.ctx.save()
        self.ctx.set_source_rgb(1, 1, 1)
        self.ctx.rectangle(0, 0, self.paper_width_pt, self.paper_height_pt)
        self.ctx.fill()
        self.ctx.restore()

        self._draw_page_number()
        self.index_page_num = self.index_page_num + 1

    def render(self, dpi = UTILS.PT_PER_INCH):
        self.ctx.save()

        LOG.warning("render multipage index")

        # Create a PangoCairo context for drawing to Cairo
        pc = PangoCairo.create_context(self.ctx)

        header_fd = Pango.FontDescription("Georgia Bold 12")
        label_column_fd  = Pango.FontDescription("DejaVu 6")

        header_layout, header_fascent, header_fheight, header_em = \
            draw_utils.create_layout_with_font(self.ctx, header_fd)
        label_layout, label_fascent, label_fheight, label_em = \
            draw_utils.create_layout_with_font(self.ctx, label_column_fd)
        column_layout, _, _, _ = \
            draw_utils.create_layout_with_font(self.ctx, label_column_fd)

        # By OCitysmap's convention, the default resolution is 72 dpi,
        # which maps to the default pangocairo resolution (96 dpi
        # according to pangocairo docs). If we want to render with
        # another resolution (different from 72), we have to scale the
        # pangocairo resolution accordingly:
        PangoCairo.context_set_resolution(column_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)
        PangoCairo.context_set_resolution(label_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)
        PangoCairo.context_set_resolution(header_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)

        margin = label_em

        # find largest label and location
        max_label_drawing_width = 0.0
        max_location_drawing_width = 0.0
        for category in self.index_categories:
            for item in category.items:
                w = item.label_drawing_width(label_layout)
                if w > max_label_drawing_width:
                    max_label_drawing_width = w

                w = item.location_drawing_width(label_layout)
                if w > max_location_drawing_width:
                    max_location_drawing_width = w

        # No street to render, bail out
        if max_label_drawing_width == 0.0:
            return

        # Find best number of columns
        max_drawing_width = \
            max_label_drawing_width + max_location_drawing_width + 2 * margin
        max_drawing_height = self.rendering_area_h - PAGE_NUMBER_MARGIN_PT

        columns_count = int(math.ceil(self.rendering_area_w / max_drawing_width))
        # following test should not be needed. No time to prove it. ;-)
        if columns_count == 0:
            columns_count = 1

        # We have now have several columns
        column_width = self.rendering_area_w / columns_count

        column_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin) * Pango.SCALE, dpi)))
        label_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin - max_location_drawing_width
                     - 2 * label_em)
                    * Pango.SCALE, dpi)))
        header_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin) * Pango.SCALE, dpi)))

        if not self._i18n.isrtl():
            orig_offset_x = offset_x = margin/2.
            orig_delta_x  = delta_x  = column_width
        else:
            orig_offset_x = offset_x = \
                self.rendering_area_w - column_width + margin/2.
            orig_delta_x  = delta_x  = - column_width

        actual_n_cols = 0
        offset_y = margin/2.

        self._new_page()

        for category in self.index_categories:
            if ( offset_y + header_fheight + label_fheight
                 + margin/2. > max_drawing_height ):
                offset_y       = margin/2.
                offset_x      += delta_x
                actual_n_cols += 1

                if actual_n_cols == columns_count:
                    self._new_page()
                    actual_n_cols = 0
                    offset_y = margin / 2.
                    offset_x = orig_offset_x
                    delta_x  = orig_delta_x

            height = category.draw(self._i18n.isrtl(), self.ctx, pc, header_layout,
                                   UTILS.convert_pt_to_dots(header_fascent, dpi),
                                   UTILS.convert_pt_to_dots(header_fheight, dpi),
                                   UTILS.convert_pt_to_dots(self.rendering_area_x
                                                            + offset_x, dpi),
                                   UTILS.convert_pt_to_dots(self.rendering_area_y
                                                            + offset_y
                                                            + header_fascent, dpi))

            offset_y += height

            for item in category.items:
                label_height = item.label_drawing_height(label_layout)
                if ( offset_y + label_height + margin/2.
                     > max_drawing_height ):
                    offset_y       = margin/2.
                    offset_x      += delta_x
                    actual_n_cols += 1

                    if actual_n_cols == columns_count:
                        self._new_page()
                        actual_n_cols = 0
                        offset_y = margin / 2.
                        offset_x = orig_offset_x
                        delta_x  = orig_delta_x

                item.draw(self._i18n.isrtl(), self.ctx, pc, column_layout,
                            UTILS.convert_pt_to_dots(label_fascent, dpi),
                            UTILS.convert_pt_to_dots(label_fheight, dpi),
                            UTILS.convert_pt_to_dots(self.rendering_area_x
                                                     + offset_x, dpi),
                            UTILS.convert_pt_to_dots(self.rendering_area_y
                                                     + offset_y
                                                     + label_fascent, dpi),
                            label_layout,
                            UTILS.convert_pt_to_dots(label_height, dpi),
                            UTILS.convert_pt_to_dots(max_location_drawing_width,
                                                     dpi))

                offset_y += label_height


        self.ctx.restore()
