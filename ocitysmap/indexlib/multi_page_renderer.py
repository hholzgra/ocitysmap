# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2012  David Mentré
# Copyright (C) 2012  Thomas Petazzoni

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
import math
import pango
import pangocairo

import draw_utils
import ocitysmap.layoutlib.commons as UTILS
from ocitysmap.layoutlib.abstract_renderer import Renderer

# FIXME: refactoring
# We use the same 10mm as GRAYED_MARGIN_MM in the map multi-page renderer
PAGE_NUMBER_MARGIN_PT  = UTILS.convert_mm_to_pt(10)

class MultiPageStreetIndexRenderer:
    """
    The MultiPageStreetIndexRenderer class encapsulates all the logic
    related to the rendering of the street index on multiple pages
    """

    # ctx: Cairo context
    # surface: Cairo surface
    def __init__(self, i18n, ctx, surface, index_categories, rendering_area,
                 page_number):
        self._i18n           = i18n
        self.ctx            = ctx
        self.surface        = surface
        self.index_categories = index_categories
        self.rendering_area_x = rendering_area[0]
        self.rendering_area_y = rendering_area[1]
        self.rendering_area_w = rendering_area[2]
        self.rendering_area_h = rendering_area[3]
        self.page_number      = page_number

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

    def _draw_page_number(self):
        self.ctx.save()
        self.ctx.translate(Renderer.PRINT_SAFE_MARGIN_PT,
                           Renderer.PRINT_SAFE_MARGIN_PT)
        draw_utils.render_page_number(self.ctx, self.page_number,
                                      self.rendering_area_w,
                                      self.rendering_area_h,
                                      PAGE_NUMBER_MARGIN_PT,
                                      transparent_background = False)
        self.ctx.restore()

    def _new_page(self):
        self.surface.show_page()
        self.page_number = self.page_number + 1
        self._draw_page_number()

    def render(self, dpi = UTILS.PT_PER_INCH):
        self.ctx.save()

        # Create a PangoCairo context for drawing to Cairo
        pc = pangocairo.CairoContext(self.ctx)

        header_fd = pango.FontDescription("Georgia Bold 12")
        label_column_fd  = pango.FontDescription("DejaVu 8")

        header_layout, header_fascent, header_fheight, header_em = \
            self._create_layout_with_font(pc, header_fd)
        label_layout, label_fascent, label_fheight, label_em = \
            self._create_layout_with_font(pc, label_column_fd)
        column_layout, _, _, _ = \
            self._create_layout_with_font(pc, label_column_fd)

        # By OCitysmap's convention, the default resolution is 72 dpi,
        # which maps to the default pangocairo resolution (96 dpi
        # according to pangocairo docs). If we want to render with
        # another resolution (different from 72), we have to scale the
        # pangocairo resolution accordingly:
        pangocairo.context_set_resolution(column_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)
        pangocairo.context_set_resolution(label_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)
        pangocairo.context_set_resolution(header_layout.get_context(),
                                          96.*dpi/UTILS.PT_PER_INCH)

        margin = label_em

        # find largest label and location
        max_label_drawing_width = 0.0
        max_location_drawing_width = 0.0
        for category in self.index_categories:
            for street in category.items:
                w = street.label_drawing_width(label_layout)
                if w > max_label_drawing_width:
                    max_label_drawing_width = w

                w = street.location_drawing_width(label_layout)
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
                    (column_width - margin) * pango.SCALE, dpi)))
        label_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin - max_location_drawing_width
                     - 2 * label_em)
                    * pango.SCALE, dpi)))
        header_layout.set_width(int(UTILS.convert_pt_to_dots(
                    (column_width - margin) * pango.SCALE, dpi)))

        if not self._i18n.isrtl():
            orig_offset_x = offset_x = margin/2.
            orig_delta_x  = delta_x  = column_width
        else:
            orig_offset_x = offset_x = \
                self.rendering_area_w - column_width + margin/2.
            orig_delta_x  = delta_x  = - column_width

        actual_n_cols = 0
        offset_y = margin/2.

        # page number of first page
        self._draw_page_number()

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

            category.draw(self._i18n.isrtl(), self.ctx, pc, header_layout,
                          UTILS.convert_pt_to_dots(header_fascent, dpi),
                          UTILS.convert_pt_to_dots(header_fheight, dpi),
                          UTILS.convert_pt_to_dots(self.rendering_area_x
                                                   + offset_x, dpi),
                          UTILS.convert_pt_to_dots(self.rendering_area_y
                                                   + offset_y
                                                   + header_fascent, dpi))

            offset_y += header_fheight

            for street in category.items:
                label_height = street.label_drawing_height(label_layout)
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

                street.draw(self._i18n.isrtl(), self.ctx, pc, column_layout,
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


if __name__ == '__main__':
    import random
    import string

    import commons
    import coords

    width = UTILS.convert_mm_to_pt(210)
    height = UTILS.convert_mm_to_pt(297)

    surface = cairo.PDFSurface('/tmp/myindex_render.pdf', width, height)

    random.seed(42)

    def rnd_str(max_len, letters = string.letters + ' ' * 4):
        return ''.join(random.choice(letters)
                       for i in xrange(random.randint(1, max_len)))

    class i18nMock:
        def __init__(self, rtl):
            self.rtl = rtl
        def isrtl(self):
            return self.rtl

    streets = []
    for i in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
              'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
              'Schools', 'Public buildings']:
        items = []
        for label, location_str in [(rnd_str(40).capitalize(),
                                     '%s%d-%s%d' \
                                         % (rnd_str(2,
                                                    string.ascii_uppercase),
                                            random.randint(1,19),
                                            rnd_str(2,
                                                    string.ascii_uppercase),
                                            random.randint(1,19),
                                            ))]*random.randint(1, 20):
            item              = commons.IndexItem(label, None, None)
            item.location_str = location_str
            item.page_number  = random.randint(1, 100)
            items.append(item)
        streets.append(commons.IndexCategory(i, items))

    ctxtmp = cairo.Context(surface)

    rendering_area = \
        (15, 15, width - 2 * 15, height - 2 * 15)

    mpsir = MultiPageStreetIndexRenderer(i18nMock(False), ctxtmp, surface,
                                         streets, rendering_area, 1)
    mpsir.render()
    surface.show_page()

    mpsir2 = MultiPageStreetIndexRenderer(i18nMock(True), ctxtmp, surface,
                                          streets, rendering_area,
                                          mpsir.page_number + 1)
    mpsir2.render()

    surface.finish()
