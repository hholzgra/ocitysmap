# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2022 Hartmut Holzgraefe

# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

from gettext import gettext

import ocitysmap.layoutlib.commons as UTILS

from .GeneralIndex import GeneralIndex

import logging
LOG = logging.getLogger('ocitysmap')

# FIXME: refactoring
# We use the same 10mm as GRAYED_MARGIN_MM in the map multi-page renderer
PAGE_NUMBER_MARGIN_PT  = UTILS.convert_mm_to_pt(10)

# FIXME: make truely configurable
MAX_INDEX_CATEGORY_ITEMS = 300

class TreeIndex(GeneralIndex):
    name = "Tree"
    description = gettext(u"Tree genus / species index")

    def __init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number=None):
        GeneralIndex.__init__(self, renderer, db, bbox, polygon_wkt, i18n, page_number)

        # Build the contents of the index
        self._categories = (self._list_amenities(db))

    def _list_amenities(self, db):
        return self.get_index_entries(db,
                                      ["point"],
                                      ["TRIM(COALESCE( tab1.tags->'genus:de', tab1.tags->'genus', SUBSTR(tab1.tags->'species',1, POSITION(' ' IN tab1.tags->'species')) ))",
                                       "COALESCE( tab1.tags->'species:de', s.name, tab1.tags->'species', tab1.tags->'genus:de' , tab1.tags->'genus' )"],
                                      """    tags->'natural' = 'tree'
                                         AND (tags->'genus' IS NOT NULL OR tags->'species' IS NOT NULL)
                                      """,
                                      join="LEFT JOIN tree_species s ON LOWER(tab1.tags->'species') = s.species AND s.lang='de_DE'",
                                      group=False,
                                      debug=False,
                                      )
