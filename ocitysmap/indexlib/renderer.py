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

import cairo
import logging
import math
import pango
import pangocairo

import commons
import ocitysmap.layoutlib.commons as UTILS

LOG = logging.getLogger('ocitysmap')


class StreetIndexRenderingStyle:
    """
    The StreetIndexRenderingStyle class defines how the header and
    label items should be drawn (font family, size, etc.).
    """
    __slots__ = ["header_font_spec", "label_font_spec"]
    header_font_spec = None
    label_font_spec  = None

    def __init__(self, header_font_spec, label_font_spec):
        """
        Specify how the headers and label should be rendered. The
        Pango Font Speficication strings below are of the form
        "serif,monospace bold italic condensed 16". See
        http://www.pygtk.org/docs/pygtk/class-pangofontdescription.html
        for more details.

        Args:
           header_font_spec (str): Pango Font Specification for the headers.
           label_font_spec (str): Pango Font Specification for the labels.
        """
        self.header_font_spec = header_font_spec
        self.label_font_spec  = label_font_spec

    def __str__(self):
        return "Style(headers=%s, labels=%s)" % (repr(self.header_font_spec),
                                                 repr(self.label_font_spec))


class StreetIndexRenderingArea:
    """
    The StreetIndexRenderingArea class describes the parameters of the
    Cairo area and its parameters (fonts) where the index should be
    renedered. It is basically returned by
    StreetIndexRenderer::precompute_occupation_area() and used by
    StreetIndexRenderer::render(). All its attributes x,y,w,h may be
    used by the global map rendering engines.
    """

    def __init__(self, street_index_rendering_style, x, y, w, h, n_cols):
        """
        Describes the Cairo area to use when rendering the index.

        Args:
             street_index_rendering_style (StreetIndexRenderingStyle):
                   how to render the text inside the index
             x (int): horizontal origin position (cairo units).
             y (int): vertical origin position (cairo units).
             w (int): width of area to use (cairo units).
             h (int): height of area to use (cairo units).
             n_cols (int): number of columns in the index.
        """
        self.rendering_style = street_index_rendering_style
        self.x, self.y, self.w, self.h, self.n_cols = x, y, w, h, n_cols

    def __str__(self):
        return "Area(%s, %dx%d+%d+%d, n_cols=%d)" \
            % (self.rendering_style,
               self.w, self.h, self.x, self.y, self.n_cols)


class StreetIndexRenderer:
    """
    The StreetIndex class encapsulates all the logic related to the querying and
    rendering of the street index.
    """

    def __init__(self, i18n, index_categories,
                 street_index_rendering_styles \
                     = [ StreetIndexRenderingStyle('Georgia Bold 16',
                                                   'DejaVu 12'),
                         StreetIndexRenderingStyle('Georgia Bold 14',
                                                   'DejaVu 10'),
                         StreetIndexRenderingStyle('Georgia Bold 12',
                                                   'DejaVu 8'),
                         StreetIndexRenderingStyle('Georgia Bold 10',
                                                   'DejaVu 7'),
                         StreetIndexRenderingStyle('Georgia Bold 8',
                                                   'DejaVu 6'),
                         StreetIndexRenderingStyle('Georgia Bold 6',
                                                   'DejaVu 5'),
                         StreetIndexRenderingStyle('Georgia Bold 5',
                                                   'DejaVu 4'),
                         StreetIndexRenderingStyle('Georgia Bold 4',
                                                   'DejaVu 3'),
                         StreetIndexRenderingStyle('Georgia Bold 3',
                                                   'DejaVu 2'),
                         StreetIndexRenderingStyle('Georgia Bold 2',
                                                   'DejaVu 2'),
                         StreetIndexRenderingStyle('Georgia Bold 1',
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

        Args:
            surface (cairo.Surface): the cairo surface to render into.
            x (int): horizontal origin position, in pixels.
            y (int): vertical origin position, in pixels.
            w (int): maximum usable width for the index, in dots (Cairo unit).
            h (int): maximum usable height for the index, in dots (Cairo unit).
            freedom_direction (string): freedom direction, can be 'width' or
                'height'. See _compute_columns_split for more details.
            alignment (string): 'top' or 'bottom' for a freedom_direction
                of 'height', 'left' or 'right' for 'width'. Tells which side to
                stick the index to.

        Returns the actual graphical StreetIndexRenderingArea defining
        how and where the index should be rendered. Raise
        IndexDoesNotFitError when the provided area's surface is not
        enough to hold the index.
        """
        if ((freedom_direction == 'height' and
             alignment not in ('top', 'bottom')) or
            (freedom_direction == 'width' and
             alignment not in ('left', 'right'))):
            raise ValueError, 'Incompatible freedom direction and alignment!'

        if not self._index_categories:
            raise commons.IndexEmptyError

        LOG.debug("Determining index area within %dx%d+%d+%d aligned %s/%s..."
                  % (w,h,x,y, alignment, freedom_direction))

        # Create a PangoCairo context for drawing to Cairo
        ctx = cairo.Context(surface)
        pc  = pangocairo.CairoContext(ctx)

        # Iterate over the rendering_styles until we find a suitable layout
        rendering_style = None
        for rs in self._rendering_styles:
            LOG.debug("Trying index fit using %s..." % rs)
            try:
                n_cols, min_dimension \
                    = self._compute_columns_split(pc, rs, w, h,
                                                  freedom_direction)

                # Great: index did fit OK !
                rendering_style = rs
                break

            except commons.IndexDoesNotFitError:
                # Index did not fit => try smaller...
                LOG.debug("Index %s too large: should try a smaller one."
                        % rs)
                continue

        # Index really did not fit with any of the rendering styles ?
        if not rendering_style:
            raise commons.IndexDoesNotFitError("Index does not fit in area")

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

        area = StreetIndexRenderingArea(rendering_style,
                                        x+base_offset_x, y+base_offset_y,
                                        index_width, index_height, n_cols)
        LOG.debug("Will be able to render index in %s" % area)
        return area


    def render(self, ctx, rendering_area, dpi = UTILS.PT_PER_INCH):
        """
        Render the street and amenities index at the given (x,y)
        coordinates into the provided Cairo surface. The index must
        not be larger than the provided surface (use
        precompute_occupation_area() to adjust it).

        Args:
            ctx (cairo.Context): the cairo context to use for the rendering.
            rendering_area (StreetIndexRenderingArea): the result from
                precompute_occupation_area().
            dpi (number): resolution of the target device.
        """

        if not self._index_categories:
            raise commons.IndexEmptyError

        LOG.debug("Rendering the street index within %s at %sdpi..."
                  % (rendering_area, dpi))

        ##
        ## In the following, the algorithm only manipulates values
        ## expressed in 'pt'. Only the drawing-related functions will
        ## translate them to cairo units
        ##

        ctx.save()
        ctx.move_to(UTILS.convert_pt_to_dots(rendering_area.x, dpi),
                    UTILS.convert_pt_to_dots(rendering_area.y, dpi))

        # Create a PangoCairo context for drawing to Cairo
        pc = pangocairo.CairoContext(ctx)

        header_fd = pango.FontDescription(
            rendering_area.rendering_style.header_font_spec)
        label_fd  = pango.FontDescription(
            rendering_area.rendering_style.label_font_spec)

        header_layout, header_fascent, header_fheight, header_em = \
                self._create_layout_with_font(pc, header_fd)
        label_layout, label_fascent, label_fheight, label_em = \
                self._create_layout_with_font(pc, label_fd)

        #print "RENDER", header_layout, header_fascent, header_fheight, header_em
        #print "RENDER", label_layout, label_fascent, label_fheight, label_em

        # By OCitysmap's convention, the default resolution is 72 dpi,
        # which maps to the default pangocairo resolution (96 dpi
        # according to pangocairo docs). If we want to render with
        # another resolution (different from 72), we have to scale the
        # pangocairo resolution accordingly:
        pangocairo.context_set_resolution(label_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)
        pangocairo.context_set_resolution(header_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)
        # All this is because we want pango to have the exact same
        # behavior as with the default 72dpi resolution. If we instead
        # decided to call cairo::scale, then pango might choose
        # different font metrics which don't fit in the prepared
        # layout anymore...

        margin = label_em
        column_width = int(rendering_area.w / rendering_area.n_cols)

        label_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin) * pango.SCALE, dpi)))
        header_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin) * pango.SCALE, dpi)))

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

            category.draw(self._i18n.isrtl(), ctx, pc, header_layout,
                          UTILS.convert_pt_to_dots(header_fascent, dpi),
                          UTILS.convert_pt_to_dots(header_fheight, dpi),
                          UTILS.convert_pt_to_dots(rendering_area.x
                                                   + offset_x, dpi),
                          UTILS.convert_pt_to_dots(rendering_area.y
                                                   + offset_y
                                                   + header_fascent, dpi))

            offset_y += header_fheight

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
        assert actual_n_cols <= rendering_area.n_cols


    def _create_layout_with_font(self, pc, font_desc):
        layout = pc.create_layout()
        layout.set_font_description(font_desc)
        font = layout.get_context().load_font(font_desc)
        font_metric = font.get_metrics()

        fascent = float(font_metric.get_ascent()) / pango.SCALE
        fheight = float((font_metric.get_ascent() + font_metric.get_descent())
                        / pango.SCALE)
        em = float(font_metric.get_approximate_char_width()) / pango.SCALE

        return layout, fascent, fheight, em


    def _compute_lines_occupation(self, pc, font_desc, n_em_padding,
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

        layout, fascent, fheight, em = self._create_layout_with_font(pc,
                                                                     font_desc)
        #print "PREPARE", layout, fascent, fheight, em

        width = max(map(lambda x: self._label_width(layout, x), text_lines))
        # Save some extra space horizontally
        width += n_em_padding * em

        height = fheight * len(text_lines)

        return {'column_width': width, 'column_height': height,
                'fascent': fascent, 'fheight': fheight, 'em': em}


    def _label_width(self, layout, label):
        layout.set_text(label)
        return float(layout.get_size()[0]) / pango.SCALE

    def _compute_column_occupation(self, pc, rendering_style):
        """Returns the size of the tall column with all headers, labels and
        squares for the given font sizes.

        Args:
            pc (pangocairo.CairoContext): the PangoCairo context.
            rendering_style (StreetIndexRenderingStyle): how to render the
                headers and labels.

        Return a tuple (width of tall column, height of tall column,
                        vertical margin to reserve after each small column).
        """

        header_fd = pango.FontDescription(rendering_style.header_font_spec)
        label_fd  = pango.FontDescription(rendering_style.label_font_spec)

        # Account for maximum square width (at worst " " + "Z99-Z99")
        label_block = self._compute_lines_occupation(pc, label_fd, 1+7,
                reduce(lambda x,y: x+y.get_all_item_labels(),
                       self._index_categories, []))

        # Reserve a small margin around the category headers
        headers_block = self._compute_lines_occupation(pc, header_fd, 2,
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


    def _compute_columns_split(self, pc, rendering_style,
                               zone_width_dots, zone_height_dots,
                               freedom_direction):
        """Computes the columns split for this index. From the one tall column
        width and height it finds the number of columns fitting on the zone
        dedicated to the index on the Cairo surface.

        If the columns split does not fit on the index zone,
        commons.IndexDoesNotFitError is raised.

        Args:
            pc (pangocairo.CairoContext): the PangoCairo context.
            rendering_style (StreetIndexRenderingStyle): how to render the
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
                self._compute_column_occupation(pc, rendering_style)

        if zone_width_dots < tall_width:
            raise commons.IndexDoesNotFitError

        if freedom_direction == 'height':
            n_cols = math.floor(zone_width_dots / float(tall_width))
            if n_cols <= 0:
                raise commons.IndexDoesNotFitError

            min_required_height \
                = math.ceil(float(tall_height + n_cols*vertical_extra)
                            / n_cols)

            LOG.debug("min req H %f vs. allocatable H %f"
                      % (min_required_height, zone_height_dots))

            if min_required_height > zone_height_dots:
                raise commons.IndexDoesNotFitError

            return int(n_cols), min_required_height

        elif freedom_direction == 'width':
            n_cols = math.ceil(float(tall_height) / zone_height_dots)
            extra = n_cols * vertical_extra
            min_required_width = n_cols * tall_width

            if ( (min_required_width > zone_width_dots)
                 or (tall_height + extra > n_cols * zone_height_dots) ):
                raise commons.IndexDoesNotFitError

            return int(n_cols), min_required_width

        raise ValueError, 'Invalid freedom direction!'


if __name__ == '__main__':
    import random
    import string

    import commons

    logging.basicConfig(level=logging.DEBUG)

    width = UTILS.convert_mm_to_pt(210)
    height = UTILS.convert_mm_to_pt(294)

    random.seed(42)

    bbox = ocitysmap.coords.BoundingBox(48.8162, 2.3417, 48.8063, 2.3699)

    surface = cairo.PDFSurface('/tmp/myindex_render.pdf', width, height)

    def rnd_str(max_len, letters = string.letters):
        return ''.join(random.choice(letters)
                       for i in xrange(random.randint(1, max_len)))

    class i18nMock:
        def __init__(self, rtl):
            self.rtl = rtl
        def isrtl(self):
            return self.rtl

    streets = []
    for i in ['A', 'B', # 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
              'N', 'O', # 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
              'Schools', 'Public buildings']:
        items = []
        for label, location_str in [(rnd_str(10).capitalize(),
                                     '%s%d-%s%d' \
                                         % (rnd_str(2,
                                                    string.ascii_uppercase),
                                            random.randint(1,19),
                                            rnd_str(2,
                                                    string.ascii_uppercase),
                                            random.randint(1,19),
                                            ))]*4:
            item              = commons.IndexItem(label, None, None)
            item.location_str = location_str
            items.append(item)
        streets.append(commons.IndexCategory(i, items))

    index = StreetIndexRenderer(i18nMock(False), streets)

    def _render(freedom_dimension, alignment):
        x,y,w,h = 50, 50, width-100, height-100

        # Draw constraining rectangle
        ctx = cairo.Context(surface)

        ctx.save()
        ctx.set_source_rgb(.2,0,0)
        ctx.rectangle(x,y,w,h)
        ctx.stroke()

        # Precompute index area
        rendering_area = index.precompute_occupation_area(surface, x,y,w,h,
                                                          freedom_dimension,
                                                          alignment)

        # Draw a green background for the precomputed area
        ctx.set_source_rgba(0,1,0,.5)
        ctx.rectangle(rendering_area.x, rendering_area.y,
                      rendering_area.w, rendering_area.h)
        ctx.fill()
        ctx.restore()

        # Render the index
        index.render(ctx, rendering_area)


    _render('height', 'top')
    surface.show_page()
    _render('height', 'bottom')
    surface.show_page()
    _render('width', 'left')
    surface.show_page()
    _render('width', 'right')
    surface.show_page()

    index = StreetIndexRenderer(i18nMock(True), streets)
    _render('height', 'top')
    surface.show_page()
    _render('height', 'bottom')
    surface.show_page()
    _render('width', 'left')
    surface.show_page()
    _render('width', 'right')

    surface.finish()
    print "Generated /tmp/myindex_render.pdf"
