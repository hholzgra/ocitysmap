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

from __future__ import print_function

import math

import shapely.wkt

import xml.sax

# Importing mapnik2 raises a DeprecationWarning as of mapnik
# commit 14700dba. As mapnik 2.1 (or git version with support for
# placement-type="simple") is required for OCitySMap (see INSTALL),
# instead of importing mapnik2, we import mapnik and assert it isn't
# an old version.
import mapnik
assert mapnik.mapnik_version() >= 300000, \
    "Mapnik module version %s is too old, see ocitysmap's INSTALL " \
    "for more details." % mapnik.mapnik_version_string()

_MAPNIK_PROJECTION = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 " \
                     "+lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m   " \
                     "+nadgrids=@null +no_defs +over"


EARTH_RADIUS = 6370986 # meters

# XML tag handler for parsing GPX files
class GpxElementHandler(xml.sax.ContentHandler):
  min_lat = 90
  max_lat = -90
  min_lon = 180
  max_lon = -180

  def startElement(self, name, attrs):
    if "lat" in attrs:
      lat = float(attrs.getValue("lat"));
      lon = float(attrs.getValue("lon"));

      self.min_lat = min(self.min_lat, lat)
      self.min_lon = min(self.min_lon, lon)
      self.max_lat = max(self.max_lat, lat)
      self.max_lon = max(self.max_lon, lon)


class Point:
    def __init__(self, lat, long_):
        self._lat, self._long = float(lat), float(long_)

    @staticmethod
    def parse_wkt(wkt):
        long_,lat = wkt[6:-1].split()
        return Point(lat, long_)

    def get_latlong(self):
        return self._lat, self._long

    def as_wkt(self, with_point_statement=True):
        contents = '%f %f' % (self._long, self._lat)
        if with_point_statement:
            return "POINT(%s)" % contents
        return contents

    def __str__(self):
        return 'Point(lat=%f, long_=%f)' % (self._lat, self._long)

    def spheric_spherical_vector(self, other):
        """Approx (self - other) vector converted to lat/long meters
        wrt the given other point"""
        delta_lat  = abs(self._lat - other._lat)
        delta_long = abs(self._long - other._long)
        radius_lat = EARTH_RADIUS * math.cos(math.radians(self._lat))
        return (EARTH_RADIUS * math.radians(delta_lat),
                radius_lat * math.radians(delta_long))


class BoundingBox:
    """
    The BoundingBox class defines a geographic rectangle area specified by the
    coordinates of its top left and bottom right corners, in latitude and
    longitude (4326 projection).
    """

    def __init__(self, lat1, long1, lat2, long2):
        (self._lat1, self._long1) = float(lat1), float(long1)
        (self._lat2, self._long2) = float(lat2), float(long2)

        # make sure lat1/long1 is the upper left, and the others the btm right
        if (self._lat1 < self._lat2):
            self._lat1, self._lat2 = self._lat2, self._lat1
        if (self._long1 > self._long2):
            self._long1, self._long2 = self._long2, self._long1

    @staticmethod
    def parse_wkt(wkt):
        """Returns a BoundingBox object created from the coordinates of a
        polygon given in WKT format."""
        try:
            geom_envelope = shapely.wkt.loads(wkt).bounds
        except Exception as rx:
            raise ValueError("Invalid input WKT: %s" % ex)
        return BoundingBox(geom_envelope[1], geom_envelope[0],
                           geom_envelope[3], geom_envelope[2])

    @staticmethod
    def parse_latlon_strtuple(points):
        """Returns a BoundingBox object from a tuple of strings
        [("lat1,lon1"), ("lat2,lon2")]"""
        (lat1, long1) = points[0].split(',')
        (lat2, long2) = points[1].split(',')
        return BoundingBox(lat1, long1, lat2, long2)

    @staticmethod
    def parse_gpx(gpx_file):
        """ Returs a BoundingBox object extraced from GPX file contents"""
        # create GPX XML parser
        parser = xml.sax.make_parser()
        handler = GpxElementHandler()
        parser.setContentHandler(handler)

        # parse given GPX file
        parser.parse(open(gpx_file, "r"))

        # we don't want gpx track to touch the page border, so we add ~5% on each side
        dlat = (handler.max_lat - handler.min_lat) * 0.05
        dlon = (handler.max_lon - handler.min_lon) * 0.05

        # create bounding box object from detected GPX bounds plus 5% extra margin
        return BoundingBox(handler.min_lat - dlat, handler.min_lon - dlon, handler.max_lat + dlat, handler.max_lon + dlon)

    def get_top_left(self):
        return (self._lat1, self._long1)

    def get_bottom_right(self):
        return (self._lat2, self._long2)

    def create_expanded(self, dlat, dlong):
        """Return a new bbox of the same size + dlat/dlong added
           on the top-left sides"""
        return BoundingBox(self._lat1 + dlat, self._long1 - dlong,
                           self._lat2 - dlat, self._long2 + dlong)

    def create_grown(self, factor):
      """Return a new bbox with size grown by factor (1.0 for same size)"""
      wlat = abs(self._lat2 - self._lat1)
      wlon = abs(self._long2 - self._long1)

      dlat = ((wlat * factor) - wlat) / 2
      dlon = ((wlon * factor) - wlon) / 2

      return self.create_expanded(dlat, dlon)
      
    def merge(self, bbox):
        self._lat1 = max(self._lat1, bbox._lat1)
        self._lat2 = min(self._lat2, bbox._lat2)
        self._long1 = min(self._long1, bbox._long1)
        self._long2 = max(self._long2, bbox._long2)

    @staticmethod
    def _ptstr(point):
        return '%.4f,%.4f' % (point[0], point[1])

    def __str__(self):
        return 'BoundingBox(%s %s)' \
            % (BoundingBox._ptstr(self.get_top_left()),
               BoundingBox._ptstr(self.get_bottom_right()))

    def as_wkt(self, with_polygon_statement=True):
        xmax, ymin = self.get_top_left()
        xmin, ymax = self.get_bottom_right()
        s_coords = ("%f %f, %f %f, %f %f, %f %f, %f %f"
                    % (ymin, xmin, ymin, xmax, ymax, xmax,
                       ymax, xmin, ymin, xmin))
        if with_polygon_statement:
            return "POLYGON((%s))" % s_coords
        return s_coords

    def spheric_sizes(self):
        """Metric distances at the bounding box top latitude.
        Returns the tuple (metric_size_lat, metric_size_long)
        """
        delta_lat = abs(self._lat1 - self._lat2)
        delta_long = abs(self._long1 - self._long2)
        radius_lat = EARTH_RADIUS * math.cos(math.radians(self._lat1))
        return (EARTH_RADIUS * math.radians(delta_lat),
                radius_lat * math.radians(delta_long))

    def get_pixel_size_for_zoom_factor(self, zoom):
        """Return the size in pixels (tuple height,width) needed to
        render the bounding box at the given zoom factor."""
        delta_long = abs(self._long1 - self._long2)
        # 2^zoom tiles (1 tile = 256 pix) for the whole earth
        pix_x = delta_long * (2 ** (zoom + 8)) / 360

        # http://en.wikipedia.org/wiki/Mercator_projection
        yplan = lambda lat: math.log(math.tan(math.pi/4.0 +
                                              math.radians(lat)/2.0))

        # OSM maps are drawn between -85 deg and + 85, the whole amplitude
        # is 256*2^(zoom)
        pix_y = (yplan(self._lat1) - yplan(self._lat2)) \
                * (2 ** (zoom + 7)) / yplan(85)

        return (int(math.ceil(pix_y)), int(math.ceil(pix_x)))

    def to_mercator(self):
        envelope = mapnik.Box2d(self.get_top_left()[1],
                                self.get_top_left()[0],
                                self.get_bottom_right()[1],
                                self.get_bottom_right()[0])
        _proj = mapnik.Projection(_MAPNIK_PROJECTION)
        bottom_left = _proj.forward(mapnik.Coord(envelope.minx, envelope.miny))
        top_right = _proj.forward(mapnik.Coord(envelope.maxx, envelope.maxy))
        top_left = mapnik.Coord(bottom_left.x, top_right.y)
        bottom_right = mapnik.Coord(top_right.x, bottom_left.y)
        return (bottom_right, bottom_left, top_left, top_right)

    def as_javascript(self, name=None, color=None):
        if name:
            name_str = ", \"%s\"" % name
        else:
            name_str = ""

        if color:
            color_str = ", { color: \"%s\" }" % color
        else:
            color_str = ""

        return 'BoundingBox(%f,%f,%f,%f%s%s)' % \
            (self._lat1, self._long1, self._lat2, self._long2,
             name_str, color_str)

    def as_json_bounds(self):
        """Returns this bounding box as an array of arrays that can be
        serialized as JSON."""
        return [[self._lat1, self._long1],
                [self._lat2, self._long2]]

if __name__ == "__main__":
    wkt = 'POINT(2.0333 48.7062132250362)'
    pt = Point.parse_wkt(wkt)
    print(wkt, pt, pt.as_wkt())
