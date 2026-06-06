# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard
# Copyright (C) 2020 Hartmut Holzgraefe

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


import locale
from natsort import natsort_keygen, ns
from gettext import gettext

import ocitysmap
import ocitysmap.layoutlib.commons as UTILS

from .GeneralIndex import GeneralIndex, GeneralIndexCategory, GeneralIndexItem


import logging
LOG = logging.getLogger('ocitysmap')

# FIXME: refactoring
# We use the same 10mm as GRAYED_MARGIN_MM in the map multi-page renderer
PAGE_NUMBER_MARGIN_PT  = UTILS.convert_mm_to_pt(10)

# FIXME: make truely configurable
MAX_INDEX_STREETS = 1000

class StreetIndexCategory(GeneralIndexCategory):
    """
    The IndexCategory represents a set of index items that belong to the same
    category (their first letter is the same or they are of the same amenity
    type).
    """
    def __init__(self, name, items=None, is_street=True):
        GeneralIndexCategory.__init__(self, name, items, is_street)


class StreetIndex(GeneralIndex):
    name = "Street"
    description = gettext(u"Streets and selected amenities")

    def __init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number=None):
        GeneralIndex.__init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number)

        # Build the contents of the index
        self._categories = \
            (self._list_streets(db)
             + self._list_amenities(db)
             + self._list_villages(db))

    def _get_selected_amenities(self):
        """
        Return the kinds of amenities to retrieve from DB as a list of
        string tuples:
          1. Category, displayed headers in the final index
          2. db_amenity, description string stored in the DB
          3. Label, text to display in the index for this amenity

        Note: This has to be a function because gettext() has to be
        called, which takes i18n into account... It cannot be
        statically defined as a class attribute for example.
        """

        # Make sure gettext is available...
        try:
            selected_amenities = {
                "place_of_worship":  _(u"Places of worship"),
                "kindergarten":      _(u"Education"),
                "school":            _(u"Education"),
                "college":           _(u"Education"),
                "university":        _(u"Education"),
                "library":           _(u"Education"),
                "townhall":          _(u"Public buildings"),
                "post_office":       _(u"Public buildings"),
                "public_building":   _(u"Public buildings"),
                "police":            _(u"Public buildings"),
            }
        except NameError:
            LOG.exception("i18n has to be initialized beforehand")
            return []

        return selected_amenities

    def _convert_street_index(self, sl):
        """Given a list of street names, do some cleanup and pass it
        through the internationalization layer to get proper sorting,
        filtering of common prefixes, etc.

        Args:
            sl (list of tuple): list tuples of the form (street_name,
                                linestring_wkt) where linestring_wkt
                                is a WKT for the linestring between
                                the 2 most distant point of the
                                street, in 4326 SRID

        Returns the list of IndexCategory objects. Each IndexItem will
        have its square location still undefined at that point
        """

        # Street prefixes are postfixed, a human readable label is
        # built to represent the list of squares, and the list is
        # alphabetically-sorted.
        prev_locale = locale.getlocale(locale.LC_COLLATE)
        try:
            locale.setlocale(locale.LC_COLLATE, self._i18n.language_code())
        except Exception:
            LOG.warning('error while setting LC_COLLATE to "%s"' % self._i18n.language_code())

        try:
            sorted_sl = sorted(
                [(self._i18n.user_readable_street(name), linestring) for name,linestring in sl],
                key = natsort_keygen(alg=ns.LOCALE | ns.IGNORECASE, key=lambda street: street[0]))
        except Exception:
            sorted_sl = sl
        finally:
            locale.setlocale(locale.LC_COLLATE, prev_locale)

        result = []
        current_category = None
        for street_name, linestring in sorted_sl:
            # Create new category if needed
            cat_name = ""
            for c in street_name:
                if c.isdigit():
                    cat_name = self._i18n.number_category_name()
                    break
                if c.isalpha():
                    cat_name = self._i18n.upper_unaccent_string(c)
                    if cat_name != "":
                        break

            if (not current_category or current_category.name != cat_name):
                current_category = StreetIndexCategory(cat_name)
                result.append(current_category)

            # Parse the WKT from the largest linestring in shape
            try:
                s_endpoint1, s_endpoint2 = map(lambda s: s.split(),
                                               linestring[11:-1].split(','))
            except (ValueError, TypeError):
                LOG.exception("Error parsing %s for %s" % (repr(linestring),
                                                         repr(street_name)))
                continue
            endpoint1 = ocitysmap.coords.Point(s_endpoint1[1], s_endpoint1[0])
            endpoint2 = ocitysmap.coords.Point(s_endpoint2[1], s_endpoint2[0])
            current_category.items.append(GeneralIndexItem(street_name,
                                                           endpoint1,
                                                           endpoint2,
                                                           self._page_number))

        return result

    def _list_streets(self, db):
        """Get the list of streets inside the given polygon. Don't
        try to map them onto the grid of squares (there location_str
        field remains undefined).

        Args:
           db (psycopg2 DB): The GIS database

        Returns a list of commons.IndexCategory objects, with their IndexItems
        having no specific grid square location
        """

        cursor = db.cursor()
        LOG.debug("Getting streets...")

        query = self._build_query(["line"], ["name"], "TRIM(name) != '' AND highway IN ('primary','secondary','tertiary','unclassified','road','motorway','trunk','residential','living_street','pedestrian','track','construction')", True)
        self._run_query(cursor, query)

        sl = cursor.fetchall()

        LOG.debug("Got %d streets." % len(sl))

        if len(sl) > MAX_INDEX_STREETS:
            return []

        return self._convert_street_index(sl)


    def _list_amenities(self, db):
        """Get the list of amenities inside the given polygon. Don't
        try to map them onto the grid of squares (there location_str
        field remains undefined).

        Args:
           db (psycopg2 DB): The GIS database

        Returns a list of commons.IndexCategory objects, with their IndexItems
        having no specific grid square location
        """

        sep = "','"
        amenities = self._get_selected_amenities()
        amenities_in = "'" + sep.join(amenities) + "'"

        return self.get_index_entries(db,
                                      ["point","polygon"],
                                      ["amenity", "name"],
                                      ("TRIM(name) != '' AND amenity in (%s)" % amenities_in),
                                      category_mapping = amenities)

    def _list_villages(self, db):
        """Get the list of villages inside the given polygon. Don't
        try to map them onto the grid of squares (there location_str
        field remains undefined).

        Args:
           db (psycopg2 DB): The GIS database

        Returns a list of commons.IndexCategory objects, with their IndexItems
        having no specific grid square location
        """

        cursor = db.cursor()

        result = []
        current_category = StreetIndexCategory(_(u"Villages"),
                                               is_street=False)
        result.append(current_category)

        places = ['borough',
                  'suburb',
                  'quarter',
                  'neighbourhood',
                  'village',
                  'hamlet',
                  'isolated_dwelling']
        sep = "','"
        places_in = "'" + sep.join(places) + "'"

        return self.get_index_entries(db,
                                      ["point"],
                                      ["'Village'", "name"],
                                      ("TRIM(name) != '' AND place IN (%s)" % places_in),
                                      max_category_items=100)





