import qrcode
import qrcode.image.svg
import gi
if True: # hack to prevent consecutive E402 warnings
    gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg

from io import BytesIO

from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer
from ocitysmap.layoutlib.multi_page_renderer import MultiPageRenderer

import logging
LOG = logging.getLogger('ocitysmap')

def render(renderer, ctx):
    if isinstance(renderer, MultiPageRenderer):
        # the multi page renderer has the QR code in the front page footer
        # no need to also have it repeated on all individual map pages
        return

    if renderer.rc.qrcode_text:
        qrcode_text = renderer.rc.qrcode_text
    else:
        qrcode_text = renderer.rc.origin_url

    if not qrcode_text:
        return

    x  = 0
    y  = 0
    w  = convert_pt_to_dots(renderer._map_coords[2], renderer.dpi)
    h  = convert_pt_to_dots(renderer._map_coords[3], renderer.dpi)

    size = convert_pt_to_dots(max(renderer.paper_width_pt, renderer.paper_height_pt),
                              renderer.dpi) / 12

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    qr.add_data(qrcode_text)
    qr.make(fit=True)

    img = qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage,
                        fill_color='lightblue')
    svgstr = BytesIO()
    img.save(svgstr)

    svg_val = svgstr.getvalue()

    rsvg = Rsvg.Handle()
    svg = rsvg.new_from_data(svg_val)
    svgstr.close()

    ctx.save()

    ctx.push_group()
    ctx.save()
    ctx.translate(x + w - size,
                  y + h - size)
    ctx.move_to(0, 0)
    factor = size / svg.props.height
    ctx.scale(factor, factor)
    svg.render_cairo(ctx)
    ctx.restore()

    ctx.set_source(ctx.pop_group())
    ctx.paint_with_alpha(0.75)
    ctx.stroke()

    ctx.restore()
