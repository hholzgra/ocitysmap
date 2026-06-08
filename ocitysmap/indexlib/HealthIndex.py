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

class HealthIndex(GeneralIndex):
    name = "Health"
    description = gettext(u"Health related facilities")

    def __init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number=None):
        GeneralIndex.__init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number)

        # Build the contents of the index
        self._categories = (self._list_amenities(db))

    def _list_amenities(self, db):
        facilities = {
            "centre":          _(u"Health Centre"),
            "hospital":        _(u"Hospital"),
            "clinic":          _(u"Clinic"),
            "doctor":          _(u"Doctor"),
            "dentist":         _(u"Dentist"),
            "birthing_centre": _(u"Birthing Centre"),
            "midwife":         _(u"Midwife"),
            "nurse":           _(u"Nurse"),
            "alternative":     _(u"Alternative"),
            "optometrist":     _(u"Optometrist"),
            "physiotherapist": _(u"Physiotherapist"),
            "psychotherapist": _(u"Psychotherapist"),
            # "audiologist":     _(u""),
            # "podiatrist": _(u""),
            # "blood_bank": _(u""),
            # "blood_donation": _(u""),
            # "counselling": _(u""),
            # "dialysis": _(u""),
            # "hospice": _(u""),
            # "laboratory": _(u""),
            # "occupational_therapist": _(u""),
            # "rehabilitation": _(u""),
            # "sample_collection": _(u""),
            # "speech_therapist": _(u""),
            # "vaccination_centre": _(u""),
            }

        return self.get_index_entries(db,
                                      ["point", "polygon"],
                                      ["tags->'healthcare'", "coalesce(name, '***???***')"],
                                      """    amenity = 'health_post'
                                         AND tags->'healthcare' IS NOT NULL
                                         AND tags->'healthcare' != ''""",
                                      category_mapping = facilities,
                                      )
