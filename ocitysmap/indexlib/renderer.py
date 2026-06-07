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

from . import commons
import ocitysmap.layoutlib.commons as UTILS


LOG = logging.getLogger('ocitysmap')



class IndexRenderingArea:
    """
    The IndexRenderingArea class describes the parameters of the
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



if __name__ == '__main__':
    import random
    import string

    from GeneralIndex import GeneralIndexCategory, GeneralIndexTerm, GeneralIndexRenderer

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
                                     '%s%d-%s%d'
                                     % (rnd_str(2, string.ascii_uppercase),
                                        random.randint(1,19),
                                        rnd_str(2, string.ascii_uppercase),
                                        random.randint(1,19),
                                        ))] * 4:
            item              = GeneralIndexItem(label, None, None)
            item.location_str = location_str
            items.append(item)
        streets.append(GeneralIndexCategory(i, items))

    index = GeneralIndexRenderer(i18nMock(False), streets)

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

    index = GeneralIndexRenderer(i18nMock(True), streets)
    _render('height', 'top')
    surface.show_page()
    _render('height', 'bottom')
    surface.show_page()
    _render('width', 'left')
    surface.show_page()
    _render('width', 'right')

    surface.finish()
    print("Generated /tmp/myindex_render.pdf")
