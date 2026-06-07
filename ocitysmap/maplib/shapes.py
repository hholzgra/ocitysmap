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

import locale
import logging
import os

# The ogr module is now known as osgeo.ogr in recent versions of the
# module, but we want to keep compatibility with older versions
try:
    from osgeo import ogr
except ImportError:
    import ogr

LOG = logging.getLogger('ocitysmap')

class _ShapeFile:
    """
    This class represents a shapefile (.shp) that can be added to a Mapnik map
    as a layer. It provides a few methods to add some geometry 'features' to
    the shape file.

    This is a private base class and is not meant to be used directly from the
    outside.
    """

    def __init__(self, bounding_box, out_filename, layer_name):
        """
        Args:
            bounding_box (BoundingBox): bounding box of the map area.
            out_filename (string): path to the output shape file to generate.
            layer_name (string): layer name for the shape file.
        """

        self._bbox = bounding_box
        self._filepath = out_filename
        self._layer_name = layer_name

        driver = ogr.GetDriverByName('ESRI Shapefile')
        if os.path.exists(out_filename):
            # Delete the detination file first
            driver.DeleteDataSource(out_filename)

        self._ds = driver.CreateDataSource(out_filename)
        self._layer = None

    def _add_feature(self, feature):
        f = ogr.Feature(feature_def=self._layer.GetLayerDefn())
        f.SetGeometryDirectly(feature)
        self._layer.CreateFeature(f)
        f.Destroy()

    def flush(self):
        """
        Commit the file to disk and prevent any further addition of
        new longitude/latitude lines
        """
        self._ds.Destroy()
        self._ds = None

    def get_layer_name(self):
        """Returns the name of the layer used for this shape file."""
        return self._layer_name

    def get_filepath(self):
        """Returns the path to the destination shape file."""
        return self._filepath

    def __str__(self):
        return "ShapeFile(%s)" % self._filepath

class LineShapeFile(_ShapeFile):
    """
    Shape file for LineString geometries.
    """

    def __init__(self, bounding_box, out_filename, layer_name):
        _ShapeFile.__init__(self, bounding_box, out_filename, layer_name)
        self._layer = self._ds.CreateLayer(self._layer_name,
                                           geom_type=ogr.wkbLineString)
        LOG.debug('Created layer %s in LineShapeFile %s.' %
                  (layer_name, out_filename))

    def add_bounding_rectangle(self):
        self.add_horiz_line(self._bbox.get_top_left()[0])
        self.add_horiz_line(self._bbox.get_bottom_right()[0])
        self.add_vert_line(self._bbox.get_top_left()[1])
        self.add_vert_line(self._bbox.get_bottom_right()[1])
        return self

    def add_horiz_line(self, y):
        """Add a new latitude line at the given latitude."""
        line = ogr.Geometry(type = ogr.wkbLineString)
        line.AddPoint_2D(self._bbox.get_top_left()[1], y)
        line.AddPoint_2D(self._bbox.get_bottom_right()[1], y)
        self._add_feature(line)
        return self

    def add_vert_line(self, x):
        """Add a new longitude line at the given longitude."""
        line = ogr.Geometry(type = ogr.wkbLineString)
        line.AddPoint_2D(x, self._bbox.get_top_left()[0])
        line.AddPoint_2D(x, self._bbox.get_bottom_right()[0])
        self._add_feature(line)
        return self

class BoxShapeFile(LineShapeFile):
    """
    Shape file for Box geometries.
    """

    def add_box(self, box):
        top_left, bottom_right = box.get_top_left(), box.get_bottom_right()

        line = ogr.Geometry(type = ogr.wkbLineString)
        line.AddPoint_2D(*list(reversed(top_left)))
        line.AddPoint_2D(bottom_right[1], top_left[0])
        self._add_feature(line)

        line = ogr.Geometry(type = ogr.wkbLineString)
        line.AddPoint_2D(bottom_right[1], top_left[0])
        line.AddPoint_2D(*list(reversed(bottom_right)))
        self._add_feature(line)

        line = ogr.Geometry(type = ogr.wkbLineString)
        line.AddPoint_2D(*list(reversed(bottom_right)))
        line.AddPoint_2D(top_left[1], bottom_right[0])
        self._add_feature(line)

        line = ogr.Geometry(type = ogr.wkbLineString)
        line.AddPoint_2D(top_left[1], bottom_right[0])
        line.AddPoint_2D(*list(reversed(top_left)))
        self._add_feature(line)
        return self

class PolyShapeFile(_ShapeFile):
    """
    Shape file for Polygon geometries.
    """

    def __init__(self, bounding_box, out_filename, layer_name):
        _ShapeFile.__init__(self, bounding_box, out_filename, layer_name)
        self._layer = self._ds.CreateLayer(self._layer_name,
                                           geom_type=ogr.wkbPolygon)
        LOG.debug('Created layer %s in PolyShapeFile %s.' %
                  (layer_name, out_filename))

    def add_shade_from_wkt(self, wkt):
        """Add the polygon feature to the shape file."""
        # Prevent the current locale from influencing how the WKT data is
        # parsed by OGR.
        try:
            prev_locale = locale.getlocale(locale.LC_ALL)
        except Exception:
            prev_locale = ''
        locale.setlocale(locale.LC_ALL, "C")

        try:
            poly = ogr.CreateGeometryFromWkt(wkt)
        finally:
            locale.setlocale(locale.LC_ALL, prev_locale)

        self._add_feature(poly)
        return self

if __name__ == "__main__":
    from ocitysmap import coords

    logging.basicConfig(level=logging.DEBUG)
    (LineShapeFile(coords.BoundingBox(44.4883, -1.0901, 44.4778, -1.0637),
                   '/tmp/mygrid.shp', 'test')
        .add_horiz_line(44.48)
        .add_vert_line(-1.08)
        .flush())
