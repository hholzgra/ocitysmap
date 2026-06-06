# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2019  Hartmut Holzgraefe

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

import math
import logging
import utm

from ocitysmap.draw_utils import draw_halotext_center
from ocitysmap.layoutlib.commons import convert_pt_to_dots

LOG = logging.getLogger('ocitysmap')

# draw a blue UTM grid with 1km grid size on top of the map

def render(renderer, ctx):
    def pt2px(pt):
        # convert dots into screen pixels
        return convert_pt_to_dots(pt, renderer.dpi)

    def superscript(i):
        # return the unicode superscript form of a single digit
        if i == 0:
            return '\N{SUPERSCRIPT ZERO}'
        if i == 1:
            return '\N{SUPERSCRIPT ONE}'
        elif i == 2:
            return '\N{SUPERSCRIPT TWO}'
        elif i == 3:
            return '\N{SUPERSCRIPT THREE}'
        elif i == 4:
            return '\N{SUPERSCRIPT FOUR}'
        elif i == 5:
            return '\N{SUPERSCRIPT FIVE}'
        elif i == 6:
            return '\N{SUPERSCRIPT SIX}'
        elif i == 7:
            return '\N{SUPERSCRIPT SEVEN}'
        elif i == 8:
            return '\N{SUPERSCRIPT EIGHT}'
        elif i == 9:
            return '\N{SUPERSCRIPT NINE}'
        else:
            return i

    def beautify_km(km):
        # show a kilometer value in 'beautified' form with the last two digits
        # in larger size, as these change value more often
        txt = ''

        t1 = int(km/100)
        t2 = int(km)%100

        t11 =int(t1/10)
        t12 =int(t1)%10

        if t11 > 0:
            txt = txt + superscript(t11)
        txt = txt + superscript(t12)

        txt = txt + ("%02d" % t2)

        return txt

    def utm_zonefield2epsg(number, letter):
        # return EPSG spatial reference ID for UTM zone
        # northern hemisphere zones (>= 'M') use 32600 + zone number
        # southern hemisphere zones (<= 'N') use 32700 + zone number
        if letter.upper() >= 'N':
            return 'epsg:326%02d' % number
        else:
            return 'epsg:327%02d' % number

    def utm_zonefield2proj(number, letter):
        # return proj4 / pyproj projection string for UTM zone 
        if letter.upper() <= 'M':
            south = '+south '
        else:
            south = ''

        return '+proj=utm +zone=%d %s +ellps=WGS84 +datum=WGS84 +units=m +no_defs' % (number, south)

    def grid_line(lat1, lon1, lat2, lon2):
        # draw a blue grid line between two coordinates
        (x1, y1) = renderer._latlon2xy(lat1, lon1)
        (x2, y2) = renderer._latlon2xy(lat2, lon2)

        ctx.save()
        ctx.set_source_rgba(0, 0, 1.0, 0.5)
        ctx.set_line_width(pt2px(1))
        ctx.move_to(x1, y1)
        ctx.line_to(x2, y2)
        ctx.stroke()
        ctx.restore()

    def show_grid(lat1, lon1, lat2, lon2):
        # draw grid over given bounding box

        if (lat1 > 0 and lat2 < 0):
            # split into two grids when bbox crosses the equator
            # TODO: should be handled by vertical zone boundary detection
            #       see also other TODO below
            show_grid(lat1, lon1, 0.000001, lon2)
            show_grid(-0.000001, lon1, lat2, lon2)
            return

        # determine default UTM coordinates for bounding box corners
        (west, north, zone1_number, zone1_letter) = utm.from_latlon(lat1, lon1)
        (east, south, zone2_number, zone2_letter) = utm.from_latlon(lat2, lon2)
        (east2, north2, zone3_number, zone3_letter) = utm.from_latlon(lat1, lon2)
        (west2, south2, zone4_number, zone4_letter) = utm.from_latlon(lat2, lon1)

        west  = min(west, west2)
        east  = max(east, east2)
        north = max(north, north2)
        south = min(south, south2)

        # exclude the polar zones for now
        # TODO: add support for polar zones
        polar_zones = ['A','B','Y','Z']
        if zone1_letter in polar_zones or zone2_letter in polar_zones:
            LOG.warning('No support for UTM polar zones yet')
            return

        # split into two grids when bbox crosses a zone border
        # TODO this need to be four zones, not just two
        #      zones are changing by latitude, too
        if zone1_number != zone2_number:
            # TODO: handle special cases for Sweden/Norway and Spitzbergen
            #       zone fileds 32N-V, 32N-X to 37N-X
            split_lon = int(math.floor(lon2/6)) * 6

            show_grid(lat1, lon1,               lat2, split_lon - 0.000001)
            show_grid(lat1, split_lon+0.000001, lat2, lon2                )
            return

        # determine grid bounding box pixel coordinates
        (x1, y1) = renderer._latlon2xy(lat1, lon1)
        (x2, y2) = renderer._latlon2xy(lat2, lon2)
        width  = abs(x2 - x1)
        height = abs(y2 - y1)

        # clip to grid bounding box
        ctx.save()
        ctx.rectangle(x1, y1, width, height)
        ctx.clip()

        # we only need one line every kilometer, so we can round things up or down
        w_km = math.floor(west/1000)
        e_km = math.ceil(east/1000)
        n_km = math.ceil(north/1000)
        s_km = math.floor(south/1000)

        dv_km = abs(n_km - s_km)
        dh_km = abs(e_km - w_km)

        # even one line per kilometer can be too much for large maps
        # so when things get too tight we only do every 10th line,
        # or every 100th etc.
        # TODO: this is hacky, as originally this was written for
        #       single kilometer resolution only, it should actually
        #       calculate a good grid line distance up front instead
        #       of doing it iteratively ... which would also have
        #       the advantage of allowing for sub-kilometer grid sizes
        factor = 1000
        while (height / dv_km) < 100:
            w_km = math.floor(w_km / 10)
            e_km = math.ceil(e_km / 10)
            n_km = math.ceil(n_km / 10)
            s_km = math.floor(s_km / 10)
            dv_km = abs(n_km - s_km)
            dh_km = abs(e_km - w_km)
            factor = factor * 10

        # draw the vertical grid lines
        for v in range(w_km, e_km):
            # calc line endings and draw line
            # TODO: the vertical lines are not really straight?
            (lat1, lon1) = utm.to_latlon(v * factor, n_km * factor, zone1_number, zone1_letter)
            (lat2, lon2) = utm.to_latlon(v * factor, s_km * factor, zone1_number, zone1_letter)
            grid_line(lat1, lon1, lat2, lon2)

            # draw easting value right next to upper visible end of the grid line
            (x1, y1) = renderer._latlon2xy(lat1, lon1)
            ctx.save()
            ctx.set_font_size(pt2px(8))
            ctx.set_source_rgba(0, 0, 0.5, 0.5)
            draw_halotext_center(ctx, beautify_km(v*factor/1000), x1 + 18, pt2px(8 + renderer.PRINT_SAFE_MARGIN_PT)) 
            ctx.restore()

        # draw the horizontal grid lines
        for h in range(s_km, n_km):
            # calc line endings and draw line
            # TODO: the horizontal lines are not really straight?
            (lat1, lon1) = utm.to_latlon(w_km * factor, h * factor, zone1_number, zone1_letter)
            (lat2, lon2) = utm.to_latlon(e_km * factor, h * factor, zone1_number, zone1_letter)
            grid_line(lat1, lon1, lat2, lon2)

            # draw northing value right below left visible end of the line
            (x1, y1) = renderer._latlon2xy(lat1, lon1)
            ctx.save()
            ctx.set_font_size(pt2px(8))
            ctx.set_source_rgba(0, 0, 0.5, 0.5)
            draw_halotext_center(ctx, beautify_km(h*factor/1000), pt2px(12 + renderer.PRINT_SAFE_MARGIN_PT), y1 + 25)
            ctx.restore()

        # draw zone field info in upper left map corner
        # TODO avoid overlap with northing/easting values
        ctx.set_source_rgba(0, 0, 0.5, 0.5)
        ctx.set_font_size(pt2px(12))
        draw_halotext_center(ctx, ("%d%s" % (zone1_number, zone1_letter)), pt2px(12 + renderer.PRINT_SAFE_MARGIN_PT), pt2px(5 + renderer.PRINT_SAFE_MARGIN_PT))

        ctx.restore()

    # determine drawing area bounding box coordinates
    bbox = renderer._map_canvas.get_actual_bounding_box()
    (lat1, lon1) = bbox.get_top_left()
    (lat2, lon2) = bbox.get_bottom_right()

    # perform the actual work
    show_grid(lat1, lon1, lat2, lon2)

