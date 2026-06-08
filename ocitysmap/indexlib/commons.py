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

import os
import sys

import gi
if True: # hack to prevent consecutive E402 warings
    gi.require_version('Pango', '1.0')
from gi.repository import Pango

from abc import ABC
from gettext import gettext

import logging
LOG = logging.getLogger('ocitysmap')

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

class IndexEmptyError(Exception):
    """This exception is raised when no data is to be rendered in the index."""
    pass

class IndexDoesNotFitError(Exception):
    """This exception is raised when the index does not fit in the given
    graphical area, even after trying smaller font sizes."""
    pass

class Index(ABC):
    """
    The Index represents an Index, with categories and actual index items
    below it
    """

    name = "Index"
    description = gettext(u"Abstract base class index")
    _categories = []

    @property
    def categories(self):
        return self._categories

    def apply_grid(self, grid):
        """
        Update the location_str field of the streets and amenities by
        mapping them onto the given grid.

        Args:
           grid (ocitysmap.Grid): the Grid object from which we
           compute the location strings

        Returns:
           Nothing, but self._categories has been modified!
        """
        for category in self._categories:
            for item in category.items:
                item.update_location_str(grid)

class IndexCategory(ABC):
    """
    The IndexCategory represents a set of index items that belong to the same
    category (their first letter is the same or they are of the same amenity
    type).
    """
    name = None
    items = None
    is_street = False

    def __init__(self, name, items=None, is_street=True):
        assert name is not None
        self.name = name
        self.items = items or list()
        self.is_street = is_street

    def __str__(self):
        return '<%s (%s)>' % (self.name, map(str, self.items))

    def __repr__(self):
        return 'IndexCategory(%s, %s)' % (repr(self.name),
                                          repr(self.items))

    def get_all_item_labels(self):
        return [x.label for x in self.items]

    def get_all_item_squares(self):
        return [x.squares for x in self.items]


class IndexItem(ABC):
    """
    An IndexItem represents one item in the index (a street or a POI). It
    contains the item label (street name, POI name or description) and the
    humanized squares description.
    """
    __slots__    = ['label', 'endpoint1', 'endpoint2', 'location_str','page_number']
    # label        = None # str
    # endpoint1    = None # coords.Point
    # endpoint2    = None # coords.Point
    # location_str = None # str or None
    # page_number  = None # integer or None. Only used by multi-page renderer.

    def __init__(self, label, endpoint1, endpoint2, page_number=None):
        assert label is not None
        self.label        = label
        self.endpoint1    = endpoint1
        self.endpoint2    = endpoint2
        self.location_str = None
        self.page_number  = page_number

    def __str__(self):
        return '%s...%s' % (self.label, self.location_str)

    def __repr__(self):
        return ('IndexItem(%s, %s, %s, %s, %s)'
                % (repr(self.label), self.endpoint1, self.endpoint2,
                   repr(self.location_str), repr(self.page_number)))

    def update_location_str(self, grid):
        """
        Update the location_str field from the given Grid object.

        Args:
           grid (ocitysmap.Grid): the Grid object from which we
           compute the location strings

        Returns:
           Nothing, but the location_str field will have been altered
        """
        if self.endpoint1 is not None:
            coords = self.endpoint1.get_latlong()
            ep1_label = grid.get_location_str(coords[0], coords[1])
        else:
            ep1_label = None
        if self.endpoint2 is not None:
            coords = self.endpoint2.get_latlong()
            ep2_label = grid.get_location_str(coords[0], coords[1])
        else:
            ep2_label = None

        if ep1_label is None:
            ep1_label = ep2_label
        if ep2_label is None:
            ep2_label = ep1_label

        if ep1_label == ep2_label:
            if ep1_label is None:
                self.location_str = "???"
            self.location_str = ep1_label
        elif grid.rtl:
            self.location_str = "%s-%s" % (max(ep1_label, ep2_label),
                                           min(ep1_label, ep2_label))
        else:
            self.location_str = "%s-%s" % (min(ep1_label, ep2_label),
                                           max(ep1_label, ep2_label))

        if self.page_number is not None:
            if grid.rtl:
                self.location_str = "%s, %d" % (self.location_str,
                                                self.page_number)
            else:
                self.location_str = "%d, %s" % (self.page_number,
                                                self.location_str)





if __name__ == "__main__":
    import cairo
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import PangoCairo

    surface = cairo.PDFSurface('/tmp/idx_commons.pdf', 1000, 1000)

    ctx = cairo.Context(surface)
    pc = PangoCairo.create_context(ctx)

    font_desc = Pango.FontDescription('DejaVu')
    font_desc.set_size(12 * Pango.SCALE)

    layout = PangoCairo.create_layout(ctx)
    layout.set_font_description(font_desc)
    layout.set_width(200 * Pango.SCALE)

    font = layout.get_context().load_font(font_desc)
    font_metric = font.get_metrics()

    fascent = font_metric.get_ascent() / Pango.SCALE
    fheight = ((font_metric.get_ascent() + font_metric.get_descent())
               / Pango.SCALE)

    first_item  = IndexItem('First Item', None, None)
    second_item = IndexItem('Second Item', None, None)
    category    = IndexCategory('Hello world !', [first_item, second_item])

    category.draw(False, ctx, pc, layout, fascent, fheight,
                  72, 80)
    first_item.draw(False, ctx, pc, layout, fascent, fheight,
                    72, 100)
    second_item.draw(False, ctx, pc, layout, fascent, fheight,
                     72, 120)

    surface.finish()
    print("Generated /tmp/idx_commons.pdf")
