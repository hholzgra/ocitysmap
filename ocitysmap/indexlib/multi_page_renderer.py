# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2012  David Mentré
# Copyright (C) 2012  Thomas Petazzoni

# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import cairo

import ocitysmap.layoutlib.commons as UTILS

import logging
LOG = logging.getLogger('ocitysmap')

# FIXME: refactoring
# We use the same 10mm as GRAYED_MARGIN_MM in the map multi-page renderer
PAGE_NUMBER_MARGIN_PT  = UTILS.convert_mm_to_pt(10)





if __name__ == '__main__':
    import random
    import string

    import commons

    from ocitysmap.indexlib.multi_page_renderer import MultiPageIndexRenderer

    width = UTILS.convert_mm_to_pt(210)
    height = UTILS.convert_mm_to_pt(297)

    surface = cairo.PDFSurface('/tmp/myindex_render.pdf', width, height)

    random.seed(42)

    def rnd_str(max_len, letters = string.letters + ' ' * 4):
        return ''.join(random.choice(letters)
                       for i in range(random.randint(1, max_len)))

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
                                     '%s%d-%s%d'
                                     % (rnd_str(2,
                                                string.ascii_uppercase),
                                        random.randint(1, 19),
                                        rnd_str(2,
                                                string.ascii_uppercase),
                                        random.randint(1, 19),
                                        ))]*random.randint(1, 20):
            item              = commons.GeneralIndexItem(label, None, None)
            item.location_str = location_str
            item.page_number  = random.randint(1, 100)
            items.append(item)
        streets.append(commons.StreetIndexCategory(i, items))

    ctxtmp = cairo.Context(surface)

    rendering_area = \
        (15, 15, width - 2 * 15, height - 2 * 15)

    mpsir = MultiPageIndexRenderer(i18nMock(False), ctxtmp, surface,
                                   streets, rendering_area, 1)
    mpsir.render()
    surface.show_page()

    mpsir2 = MultiPageIndexRenderer(i18nMock(True), ctxtmp, surface,
                                    streets, rendering_area,
                                    mpsir.page_number + 1)
    mpsir2.render()

    surface.finish()
