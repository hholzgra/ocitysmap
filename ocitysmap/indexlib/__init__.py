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

if __name__ == '__main__':
    import cairo
    import logging
    import os
    import psycopg2
    import random
    import string

    import ocitysmap.layoutlib.commons as UTILS

    from ocitysmap import i18n, coords
    from ocitysmap.maplib.grid import Grid
    from indexer  import StreetIndex
    from renderer import StreetIndexRenderer
    from commons  import IndexCategory, IndexItem


    logging.basicConfig(level=logging.DEBUG)
    random.seed(42)

    lang = "fr_FR.UTF-8"
    #lang = "ar_MA.UTF-8"
    #lang = "zh_CN.utf8"
    i18n = i18n.install_translation(lang,
                os.path.join(os.path.dirname(__file__),
                             "..", "..", "locale"))

    bbox = coords.BoundingBox(48.8162, 2.3417, 48.8063, 2.3699) # France
    #bbox = coords.BoundingBox(34.0322, -6.8648, 34.0073, -6.8133) # Moroco
    #bbox = bbox = coords.BoundingBox(22.5786, 114.0308, 22.5231, 114.1338) # CN

    # Build the list of index items
    db = psycopg2.connect(user='maposmatic',
                          password='waeleephoo3Aew3u',
                          host='localhost',
                          database='maposmatic')

    street_index = StreetIndex(db, bbox.as_wkt(), i18n)
    print street_index.categories

    # Render the items
    class i18nMock:
        def __init__(self, rtl):
            self.rtl = rtl
        def isrtl(self):
            return self.rtl

    width = 2.5 * contert_mm_to_pt(210)
    height = 2.5 * contert_mm_to_pt(297)

    surface = cairo.PDFSurface('/tmp/myindex.pdf', width, height)

    # Map index to grid
    grid = Grid(bbox, rtl = False)
    street_index.apply_grid(grid)

    index = StreetIndexRenderer(i18nMock(False), street_index.categories)

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

    ##
    ## Now demo with RTL = True
    ##

    # Map index to grid
    grid = Grid(bbox, rtl = True)
    street_index.apply_grid(grid)

    index = StreetIndexRenderer(i18nMock(True), street_index.categories)
    _render('height', 'top')
    surface.show_page()
    _render('height', 'bottom')
    surface.show_page()
    _render('width', 'left')
    surface.show_page()
    _render('width', 'right')

    surface.finish()
    print "Generated /tmp/myindex.pdf."
