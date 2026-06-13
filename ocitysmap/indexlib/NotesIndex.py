# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2022 Hartmut Holzgraefe

# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

from gettext import gettext

import ocitysmap.layoutlib.commons as UTILS
from ocitysmap.coords import Point

from .GeneralIndex import GeneralIndex, GeneralIndexCategory, GeneralIndexItem

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import json

import logging
LOG = logging.getLogger('ocitysmap')

# FIXME: refactoring
# We use the same 10mm as GRAYED_MARGIN_MM in the map multi-page renderer
PAGE_NUMBER_MARGIN_PT  = UTILS.convert_mm_to_pt(10)

# FIXME: make truely configurable
MAX_INDEX_CATEGORY_ITEMS = 300

class NotesIndex(GeneralIndex):
    name = "Notes"
    description = gettext(u"OSM Notes index")

    def __init__(self, db, renderer, bounding_box, polygon_wkt, i18n, page_number=None):
        GeneralIndex.__init__(self, db, renderer, bounding_box, polygon_wkt, i18n, page_number)

        # Build the contents of the index
        self._categories = self._list_amenities(db)

    def _list_amenities(self, db):
        results = []

        bbox = self._bounding_box
        url  = ("https://api.openstreetmap.org/api/0.6/notes.json?closed=0&bbox=%f,%f,%f,%f"
                % (bbox.get_left(), bbox.get_bottom(), bbox.get_right(), bbox.get_top()))
        LOG.info("OSM Notes URL: %s" % url)

        req = Request(url)

        try:
            response = urlopen(req)
        except HTTPError as e:
            LOG.error('The server couldn\'t fulfill the request.')
            LOG.error('Error code: %s' % e.code)
            return
        except URLError as e:
            LOG.error('We failed to reach a server.')
            LOG.error('Reason: %s' % e.reason)
            return

        notes_json = response.read()

        try:
            notes = json.loads(notes_json)
        except Exception as e:
            LOG.error("JSON decode exception %s / %s." % (e.code, e.reason))
            return

        index_category =  GeneralIndexCategory("OSM Notes", is_street=False)

        n = 0
        for note in notes['features']:
            n = n + 1
            lat = note['geometry']['coordinates'][1]
            lon = note['geometry']['coordinates'][0]

            point = Point(lat, lon)

            try:
                index_text = "Note %d - %s" % (n, note['properties']['comments'][0]['text'].replace('\n', ' '))
                index_category.items.append(GeneralIndexItem(index_text[0:50], point, point, self._page_number))
            except IndexError:
                pass

            # renderer._marker('red', str(n), lat, lon, ctx, renderer.dpi)

        results.append(index_category)
        return results
