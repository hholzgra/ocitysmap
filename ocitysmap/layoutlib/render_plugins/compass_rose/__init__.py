import cairo
import os
import sys
import logging
from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer

LOG = logging.getLogger('ocitysmap')

def render(renderer, ctx):
    svg_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 'svg', 'default.svg'))

    if not os.path.exists(svg_path):
        LOG.warning("No compass rose image found")
        return
        
    h = convert_pt_to_dots(0.05 * renderer.paper_height_pt, renderer.dpi)

    if type(renderer).__name__ == "MultiPageRenderer":
        x = 0
        y = 0
    else:
        x = convert_pt_to_dots(renderer._map_coords[0], renderer.dpi)
        y = convert_pt_to_dots(renderer._map_coords[1], renderer.dpi)
        
    ctx.save()   
    ctx.translate(x + h/2, y + h/2)
    rose_grp, rose_width = Renderer._get_svg(ctx, svg_path, h)
    ctx.set_source(rose_grp)
    ctx.paint_with_alpha(0.75)
    ctx.stroke()
    ctx.restore()

