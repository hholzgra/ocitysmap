# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data

# Copyright (C) 2012  Étienne Loks

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


import logging

from . import shapes

LOG = logging.getLogger('ocitysmap')

class OverviewGrid:
    """
    The OverviewGrid class draw the grid overlayed on the overview map of a
    multi-page render.
    """

    def __init__(self, bounding_box, pages_bounding_boxes, rtl=False):
        """Creates a new grid for the given bounding boxes.

        Args:
            bounding_box (coords.BoundingBox): the map bounding box.
            bounding_box (list of coords.BoundingBox): bounding boxes of the
                pages.
            rtl (boolean): whether the map is rendered in right-to-left mode or
                not. Defaults to False.
        """

        self._bbox = bounding_box
        self._pages_bbox = pages_bounding_boxes
        self.rtl   = rtl
        self._height_m, self._width_m = bounding_box.spheric_sizes()

        LOG.info('Laying out of overview grid on %.1fx%.1fm area...' %
                 (self._width_m, self._height_m))

    def generate_shape_file(self, filename):
        """Generates the grid shapefile with all the horizontal and
        vertical lines added.

        Args:
            filename (string): path to the temporary shape file that will be
                generated.
        Returns the ShapeFile object.
        """

        # Use a slightly larger bounding box for the shape file to accomodate
        # for the small imprecisions of re-projecting.
        g = shapes.BoxShapeFile(self._bbox.create_expanded(0.001, 0.001),
                                filename, 'grid')
        for box in self._pages_bbox:
            g.add_box(box)

        return g



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    pass
