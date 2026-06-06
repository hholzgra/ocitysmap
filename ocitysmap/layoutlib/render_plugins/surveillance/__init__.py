# import cairo
from gi.repository import Rsvg
import math
import os
# import psycopg2
import logging

LOG = logging.getLogger('ocitysmap')

def _camera_view(renderer, ctx, map_scale, surveillance, lat, lon, camera_type, direction, angle, height):
    if camera_type == 'dome':
        symbol = 'dome-camera'
        direction = '0'
    elif camera_type == 'fixed':
        symbol = 'camera-fixed'
    elif camera_type == 'panning':
        symbol = 'camera-panning'
    else:
        symbol = 'camera'

    if direction:
        if direction.isdigit():
            direction = float(direction)
        else:
            mapping = {
              'N':     0.0,
               'NNE':  22.5,
               'NE':   45.0,
               'ENE':  67.5,
               'E':    90.0,
               'ESE': 112.5,
               'SE':  135.0,
               'SSE': 157.5,
               'S':   180.0,
               'SSW': 202.5,
               'SW':  225.0,
               'WSW': 247.5,
               'W':   270.0,
               'WNW': 292.5,
               'NW':  315.0,
               'NNW': 337.5,
             }

             direction = mapping.get(direction, None)

    if angle and angle.isdigit():
        angle = float(angle)
    else:
        angle=60

    ctx.save()

    x,y = renderer._latlon2xy(lat, lon, renderer.dpi)

    if isinstance(direction, float) and surveillance != 'indoor':
        if height and height.isdigit():
           height = float(height)
        else:
           height = 5.0

        if height < 3.0:
           height = 3.0
        elif height > 12.0:
           height = 12.0

        if isinstance(angle, float):
            if angle < 0:
               angle = - angle
            if angle <= 15:
               angle = 1
            else:
               angle = math.cos((angle - 15) * math.pi / 180)
        else:
            angle = 1

        radius = 20000 * height * angle / map_scale

        if camera_type == 'dome':
            ctx.arc(x, y, radius, 0, 6.28)
        else:
            a1 = direction - 120
            a2 = direction -  60

            if a1 < 0:
              a1 += 360
              a2 += 360

            ctx.arc(x, y, radius, a1*math.pi/180, a2*math.pi/180)
            ctx.line_to(x, y)

        ctx.close_path()
        ctx.set_line_width(renderer.dpi/72.0)
        ctx.set_source_rgba(1, 0, 0, 0.5)
        ctx.stroke_preserve()
        ctx.set_source_rgba(1, 0.5, 0.5, 0.5)
        ctx.fill()

    ctx.restore()

    return symbol



def _show_symbol(renderer, ctx, lat, lon, surveillance, symbol):
    if surveillance != 'public' and surveillance != 'outdoor' and surveillance != 'indoor':
        surveillance = 'public'

    symbol_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images', surveillance, (symbol+'.svg')))

    fp = open(symbol_path,'rb')
    data = fp.read()
    fp.close()

    rsvg = Rsvg.Handle()
    svg  = rsvg.new_from_data(data)
    x,y = renderer._latlon2xy(lat, lon, renderer.dpi)

    svg_scale = renderer.dpi / (4 * svg.props.height)
    sx = x - svg.props.width  * svg_scale/2
    sy = y - svg.props.height * svg_scale/2

    ctx.save()
    ctx.translate(sx, sy)
    ctx.scale(svg_scale, svg_scale)
    svg.render_cairo(ctx)
    ctx.restore()





def render(renderer, ctx):
    query = """SELECT ST_Y(ST_TRANSFORM(way, 4326)) AS lat
                    , ST_X(ST_TRANSFORM(way, 4326)) AS lon
                    , tags->'surveillance'      AS surveillance
                    , COALESCE(tags->'surveillance:type', 'camera') AS type
                    , tags->'camera:direction'  AS camera_direction
                    , tags->'camera:angle'      AS camera_angle
                    , tags->'camera:type'       AS camera_type
                    , tags->'height'            AS camera_height
                 FROM planet_osm_point
                WHERE tags->'man_made' = 'surveillance'
                  AND ST_CONTAINS(ST_TRANSFORM(ST_GeomFromText('%s', 4326), 3857), way)
         UNION SELECT ST_Y(ST_TRANSFORM(way, 4326)) AS lat
                    , ST_X(ST_TRANSFORM(way, 4326)) AS lon
                    , tags->'surveillance'      AS surveillance
                    , COALESCE(tags->'surveillance:type', 'camera') AS type
                    , tags->'camera:direction'  AS camera_direction
                    , tags->'camera:angle'      AS camera_angle
                    , tags->'camera:type'       AS camera_type
                    , tags->'height'            AS camera_height
                 FROM planet_osm_point
                WHERE tags->'surveillance' IS NOT NULL
                  AND ST_CONTAINS(ST_TRANSFORM(ST_GeomFromText('%s', 4326), 3857), way)
             """ % ( renderer.rc.polygon_wkt, renderer.rc.polygon_wkt)

    cursor = renderer.db.cursor()
    cursor.execute(query)

    map_scale = renderer._map_canvas.get_actual_scale() * 72.0 / renderer.dpi

    for lat, lon, surveillance, surveillance_type, direction, angle, camera_type, height in cursor.fetchall():
        if surveillance_type == 'camera':
            symbol = _camera_view(renderer, ctx, map_scale, surveillance, lat, lon, camera_type, direction, angle, height)
        elif surveillance_type == 'guard':
            symbol = 'guard-shield'
        elif surveillance_type == 'ALPR':
            symbol = 'speed-camera'
        else:
            continue

        _show_symbol(renderer, ctx, lat, lon, surveillance, symbol) 

