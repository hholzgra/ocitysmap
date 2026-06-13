# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data

# Copyright (C) 2012  Étienne Loks

# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors


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
