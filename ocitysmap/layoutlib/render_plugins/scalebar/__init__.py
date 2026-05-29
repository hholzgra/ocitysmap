import cairo
import math
import os
import psycopg2
import logging
import mapnik
from ocitysmap.draw_utils import draw_simpletext_center
from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer
from math import floor, log10

LOG = logging.getLogger('ocitysmap')

def render(renderer, ctx):
    def pt2px(dot):
        return dot * renderer.dpi / 72.0

    m = renderer._map_canvas.get_rendered_map()

    # get the desired width of the scalebar in m
    try: # TODO find better way to deal with multi page maps
        meter = renderer.grid.grid_size_m
    except AttributeError:
        return

    oom   = 10 ** floor(log10(meter))

    # get the desired width of the scalebar in dots
    map_coords_dots = list(map(lambda l: pt2px(l), renderer._map_coords))

    dots = map_coords_dots[2]

    if isinstance(renderer, MultiPageRenderer):
        dots = dots - 2 * renderer.grayed_margin_pt

    step_horiz = dots / renderer.grid.horiz_count

    # make some text for the scalebar (sort units)
    if oom >= 1000:
        scaleText = str(int(meter/1000)) + "km"
    else:
        scaleText = str(int(meter)) + "m"

    pxScaleBar = dots / renderer.grid.horiz_count

    barBuffer  = pt2px(5) 	# distance from scale bar to edge of image
    lBuffer    = pt2px(5)      # distance from the line to the end of the background
    tickHeight = pt2px(15)	# height of the tick marks

    x = barBuffer
    if instanceof(renderer, MultiPageRenderer):
        # TODO more perfectly align actual scale bar with grid here?
        x += renderer.grayed_margin_pt

    y = m.height
    y-= barBuffer+lBuffer+lBuffer+tickHeight

    w = pxScaleBar + 2*lBuffer
    h = lBuffer+lBuffer+tickHeight

    ctx.save()

    # scalebar box with border and semi-transparent background
    ctx.rectangle(x,y,w,h)
    ctx.set_source_rgba(0, 0, 0, 0.5)
    ctx.set_line_width(pt2px(1))
    ctx.stroke_preserve()
    ctx.set_source_rgba(1, 1, 1, 0.5)
    ctx.fill()

    # scalebar line
    ctx.move_to(x + lBuffer, y + lBuffer)
    ctx.rel_line_to(0, tickHeight/2)
    ctx.rel_line_to(w-lBuffer-lBuffer, 0)
    ctx.rel_line_to(0, -tickHeight/2)
    ctx.set_source_rgba(0, 0, 0, 0.85)
    ctx.stroke()

    # scalebar line length
    ctx.set_font_size(pt2px(10))
    draw_simpletext_center(ctx, scaleText, x+w/2, y+h*0.25)

    # scale factor text
    ctx.set_font_size(pt2px(8))
    draw_simpletext_center(ctx, "1:%d" % renderer._map_canvas.get_actual_scale(), x+w/2, y+h*0.75)
    
    ctx.restore()
