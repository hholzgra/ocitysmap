# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2012  David Decotigny
# Copyright (C) 2012  Frédéric Lehobey
# Copyright (C) 2012  Pierre Mauduit
# Copyright (C) 2012  David Mentré
# Copyright (C) 2012  Maxime Petazzoni
# Copyright (C) 2012  Thomas Petazzoni
# Copyright (C) 2012  Gaël Utard
# Copyright (C) 2012  Étienne Loks
# Copyright (C) 2023  Hartmut Holzgraefe

# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import cairo
import gi
if True:  # hack to prevent consecutive E402 warings
    gi.require_version('Pango', '1.0')
    gi.require_version('PangoCairo', '1.0')
from gi.repository import Pango, PangoCairo

import layoutlib.commons as commons

LEFT_SIDE = 1
RIGHT_SIDE = 2

def create_layout_with_font(ctx, font_desc):
    """ Create a Pango layout from given font destription

    Parameters
    ----------
    ctx : cairo.Context
        The Cairo context to use
    font_desc :  Pango.FontDescription or str
        Font description string or already prepared Pango FontDescription

    Returns
    -------
    list of (PangoCairo.Layout, float, float, em)
        A list containing:
        * the actual Pango Layout created
        * the font ascent
        * the font height
        * the font character width ('em')
    """


    if isinstance(font_desc, str):
        font_desc = Pango.FontDescription(font_desc)
    layout = PangoCairo.create_layout(ctx)
    layout.set_font_description(font_desc)
    font = layout.get_context().load_font(font_desc)
    font_metric = font.get_metrics()

    fascent = float(font_metric.get_ascent()) / Pango.SCALE
    fheight = float((font_metric.get_ascent() + font_metric.get_descent())
                    / Pango.SCALE)
    em = float(font_metric.get_approximate_char_width()) / Pango.SCALE

    return layout, fascent, fheight, em

def draw_text(ctx, layout, fascent,
              baseline_x, baseline_y, text, pango_alignment):
    """ General text drawing function

    Draws the given text into the provided Cairo
    context through the Pango layout (get_width() expected to be
    correct in order to position the text correctly) with the
    specified pango.ALIGN_x alignment.

    Parameters
    ----------
        ctx : cairo.Context
            The context to draw into
        layout : pango.Layout
            Pango layout to draw into (get_with() important)
        fascent : float
            Current font ascent (TODO: get from layout?)
        baseline_x : float
            Horizontal position of baseline start point
        baseline_y : float
            Vertical position of baseline start point
        pango_alignment : enum
            A pango.ALIGN_* constant value specifying the alignment to use

    Results
    -------
    list of float
        Actual width and height of the rendered text
    """
    layout.set_auto_dir(False)  # TODO: Make sure ALIGN_RIGHT is independent on RTL...
    layout.set_alignment(pango_alignment)
    layout.set_text(text, -1)
    width, height = [x/Pango.SCALE for x in layout.get_size()]

    ctx.save()
    ctx.move_to(baseline_x, baseline_y - fascent)
    PangoCairo.update_layout(ctx, layout)
    PangoCairo.show_layout(ctx, layout)
    ctx.restore()

    return (width, height)

def draw_text_left(ctx, layout, fascent, baseline_x, baseline_y, text):
    """ Draw left alinged text

    Draws the given text left aligned into the provided Cairo
    context through the Pango layout (get_width() expected to be
    correct in order to position the text correctly).

    Parameters
    ----------
        ctx : cairo.Context
            The context to draw into
        layout : pango.Layout
            Pango layout to draw into (get_with() important)
        fascent : float
            Current font ascent (TODO: get from layout?)
        baseline_x : float
            Horizontal position of baseline start point
        baseline_y : float
            Vertical position of baseline start point

    Results
    -------
    list of float
        Horizontal start and end position of drawn text
    """
    text_width, text_height = draw_text(ctx, layout, fascent,
                                        baseline_x, baseline_y,
                                        text, Pango.Alignment.LEFT)

    return (baseline_x, baseline_x + text_width)

def draw_text_center(ctx, layout, fascent,
                     baseline_x, baseline_y, text):
    """ Draw center alinged text

    Draws the given text ceter aligned into the provided Cairo
    context through the Pango layout (get_width() expected to be
    correct in order to position the text correctly).

    Parameters
    ----------
        ctx : cairo.Context
            The context to draw into
        layout : pango.Layout
            Pango layout to draw into (get_with() important)
        fascent : float
            Current font ascent (TODO: get from layout?)
        baseline_x : float
            Horizontal position of baseline start point
        baseline_y : float
            Vertical position of baseline start point

    Results
    -------
    list of float
        Horizontal start and end position of drawn text
    """
    text_width, text_height = draw_text(ctx, layout, fascent,
                                        baseline_x, baseline_y, text,
                                        Pango.Alignment.CENTER)
    layout_width = layout.get_width() / Pango.SCALE
    return (baseline_x + (layout_width - text_width) / 2.0,
            baseline_x + (layout_width + text_width) / 2.0)


def draw_text_right(ctx, layout, fascent,
                    baseline_x, baseline_y, text):
    """ Draw right alinged text

    Draws the given text right aligned into the provided Cairo
    context through the Pango layout (get_width() expected to be
    correct in order to position the text correctly).

    Parameters
    ----------
        ctx : cairo.Context
            The context to draw into
        layout : pango.Layout
            Pango layout to draw into (get_with() important)
        fascent : float
            Current font ascent (TODO: get from layout?)
        baseline_x : float
            Horizontal position of baseline start point
        baseline_y : float
            Vertical position of baseline start point

    Results
    -------
    list of float
        Horizontal start and end position of drawn text
    """
    text_width, text_height = draw_text(ctx, layout, fascent,
                                        baseline_x, baseline_y,
                                        text, Pango.Alignment.RIGHT)
    layout_width = layout.get_width() / Pango.SCALE
    return (baseline_x + layout_width - text_width,
            baseline_x + layout_width)

def draw_simpletext_center(ctx, text, x, y):
    """
    Draw the given text centered at position x,y.

    Parameters
    ----------
       ctx : cairo.Context)
         The cairo context to use to draw.
       text : str
         The text to draw.
       x : float
           Horizontal center position in cairo units
       y : float
           Vertical position of the center in cairo units

    Returns
    -------
    void
    """
    ctx.save()
    xb, yb, tw, th, xa, ya = ctx.text_extents(text)
    ctx.move_to(x - tw/2.0 - xb, y - yb/2.0)
    ctx.show_text(text)
    ctx.stroke()
    ctx.restore()

def draw_halotext_center(ctx, text, x, y):
    """
    Draw the given text centered at x,y, with a semi-transparent halo below

    Parameters
    ----------
       ctx : cairo.Context)
         The cairo context to use to draw.
       text : str
         The text to draw.
       x : float
           Horizontal center position in cairo units
       y : float
           Vertical position of the center in cairo units

    Returns
    -------
    void
    """

    # get full text dimensions
    xb, yb, tw, th, xa, ya = ctx.text_extents(text)

    # first draw the semi-transparent halo
    ctx.save()
    ctx.move_to(x - tw/2.0 - xb, y - yb/2.0)
    ctx.set_line_width(10)
    ctx.set_source_rgba(1, 1, 1, 0.5)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.text_path(text)
    ctx.stroke()
    ctx.restore()

    # then put the actual text on top
    ctx.save()
    ctx.move_to(x - tw/2.0 - xb, y - yb/2.0)
    ctx.show_text(text)
    ctx.stroke()
    ctx.restore()

def draw_dotted_line(ctx, line_width, baseline_x, baseline_y, length):
    """ Draw a dotted line

    Useful for e.g. index entries to have a visual connection between actual
    index text and the map square reference at the other side of the column.

    Parameters
    ----------
    ctx : cairo.Context
        Cairo context to draw into
    line_width : float
        Width to use for the actual line dots
    baseline_x : float
        Horizontal start position
    baseline_y : float
        Vertical start position
    length : float
        Horizontal line length to draw

    Returns
    -------
    void
    """

    ctx.save()
    ctx.set_line_width(line_width)
    ctx.set_dash([line_width, line_width*2])  # gaps twice as wide as the actual dots
    ctx.move_to(baseline_x, baseline_y)
    ctx.rel_line_to(length, 0)
    ctx.stroke()
    ctx.restore()

def adjust_font_size(layout, fd, constraint_x, constraint_y):
    """ Adjust font size to available space

    Grow the given font description (20% by 20%) until it fits in
    designated area. The font descriptors size setting is changed
    directly as an intended side effect.

    Parameters
    ----------
    layout : Pango.Layout
        The layout to use for this
    fd : Pango.FontDescriptor
        The font to use for this
    constraint_x : float
        Available width to fit the text into
    constraint_y : float
        Available height to fit the text into

    Returns
    -------
    void
    """
    # TODO: are we sure changing the passed font descriptor by reference
    # is safe to do here? Or should we rather create a copy and return that
    # to avoid side effects?

    # try increasing the size by 20% until we exceed the given constraints
    while (layout.get_size()[0] / Pango.SCALE < constraint_x and
           layout.get_size()[1] / Pango.SCALE < constraint_y):
        fd.set_size(int(fd.get_size()*1.2))
        layout.set_font_description(fd)

    # take back the last 20% increment we did to get back within the constraints
    fd.set_size(int(fd.get_size()/1.2))

    # make the new font settings effective for the given layout
    layout.set_font_description(fd)

def draw_text_adjusted(ctx, text, x, y, width, height, max_char_number=None,
                       text_color=(0, 0, 0, 1), align=Pango.Alignment.CENTER,
                       width_adjust=0.7, height_adjust=0.8):
    """
    Draw a text adjusted to a maximum character number

    Args:
       ctx (cairo.Context): The cairo context to use to draw.
       text (str): the text to draw.
       x/y (numbers): The position on the canvas.
       width/height (numbers): The area we want to
           write into (cairo units).
       max_char_number (number): If set a maximum character number.
    """
    layout = PangoCairo.create_layout(ctx)
    layout.set_width(int(width_adjust * width * Pango.SCALE))
    layout.set_alignment(align)
    fd = Pango.FontDescription("Georgia Bold")
    fd.set_size(Pango.SCALE)
    layout.set_font_description(fd)

    if max_char_number:
        # adjust size with the max character number
        layout.set_text('0'*max_char_number, -1)
        adjust_font_size(layout, fd, width_adjust*width, height_adjust*height)

    # set the real text
    layout.set_markup(text, -1)
    if not max_char_number:
        adjust_font_size(layout, fd, width_adjust*width, height_adjust*height)
    layout.set_wrap(Pango.WrapMode.WORD)

    # draw
    ink, logical = layout.get_extents()
    ctx.save()
    ctx.set_source_rgba(*text_color)
    if align == Pango.Alignment.CENTER:
        x = x - (ink.width/2.0)/Pango.SCALE - int(float(ink.x)/Pango.SCALE)
        y = y - (ink.height/2.0)/Pango.SCALE - int(float(ink.y)/Pango.SCALE)
    else:
        y = y - (ink.height/2.0)/Pango.SCALE - ink.y/Pango.SCALE
    ctx.translate(x, y)

    if align == Pango.Alignment.LEFT:
        # Hack to workaround what appears to be a Cairo bug: without
        # drawing a rectangle here, the translation above is not taken
        # into account for rendering the text.
        ctx.rectangle(0, 0, 0, 0)
    PangoCairo.update_layout(ctx, layout)
    PangoCairo.show_layout(ctx, layout)
    ctx.restore()

def render_page_number(ctx, page_number,
                       usable_area_width_pt, usable_area_height_pt, margin_pt,
                       transparent_background = True, side = None):
    """ Render page number

    Parameters
    ----------
    ctx : Cairo.context
        The Cairo context to draw into
    page_number : int
        The page number to render
    usable_area_width_pt : float
        The usable horizontal page size
    usable_area_height_pt : float
        The usable vertical page size
    margin_pt : float
        Page margin before usable area begins (same horizontally and vertically)
    transparent_background : bool
       Should the number be printed on opaque white background, or should
       map content below it shine through?
    side : int
       Side of the page to render the page number at:
       LEFT_SIDE, RIGHT_SIDE, or None to auto-detect

    Returns
    -------
    """
    ctx.save()

    if side is None:
        if page_number % 2:
            side = RIGHT_SIDE
        else:
            side = LEFT_SIDE

    x_offset = 0
    if side == RIGHT_SIDE:
        x_offset += commons.convert_pt_to_dots(usable_area_width_pt)\
            - commons.convert_pt_to_dots(margin_pt)
    y_offset = commons.convert_pt_to_dots(usable_area_height_pt)\
        - commons.convert_pt_to_dots(margin_pt)

    ctx.translate(x_offset, y_offset)

    # TODO: these are actually both tranparent, just using different shades of white/gray?
    if transparent_background:
        ctx.set_source_rgba(1, 1, 1, 0.6)
    else:
        ctx.set_source_rgba(0.8, 0.8, 0.8, 0.6)


    ctx.rectangle(0, 0, commons.convert_pt_to_dots(margin_pt),
                  commons.convert_pt_to_dots(margin_pt))
    ctx.fill()

    ctx.set_source_rgba(0, 0, 0, 1)
    x_offset = commons.convert_pt_to_dots(margin_pt)/2
    y_offset = commons.convert_pt_to_dots(margin_pt)/2
    ctx.translate(x_offset, y_offset)
    draw_simpletext_center(ctx, str(page_number), 0, 0)
    ctx.restore()



def begin_internal_link(ctx, target):
    """Start an internal link

    Used for links to anchors within a multi page PDF,
    e.g for index entries linking to the actual map position,
    or for the "continues on page #" markers.

    Note: requires PyCairo 1.18.0 or higher to work, if that's
    not present we fall back to doing nothing.

    See also: `end_link()`, `anchor()`

    Parameters
    ----------
    target : sring
        Name of the internal anchor to link to.

    Returns
    -------
    void
    """
    try:  # tag_begin() only available starting with PyCairo 1.18.0
        ctx.tag_begin(cairo.TAG_LINK, "dest='%s'" % target)
    except Exception:
        pass

def end_link(ctx):
    """ End internal link

    Note: requires PyCairo 1.18.0 or higher to work, if that's
    not present we fall back to doing nothing.

    See also `start_internal_link()`.

    Parameters
    ----------
    none

    Returns
    -------
    void
    """
    try:  # tag_end() only available starting with PyCairo 1.18.0
        ctx.tag_end(cairo.TAG_LINK)
    except Exception:
        pass

def anchor(ctx, name):
    """ Add an internal anchor that internal links can refer to

    Used for anchors within a multi page PDF, e.g as target for
    index entries linking to the actual map position,
    or for the "continues on page #" markers.

    Note: requires PyCairo 1.18.0 or higher to work, if that's
    not present we fall back to doing nothing.

    See also: `start_internal_link()`

    Parameters
    ----------
    name : sring
        Name of the internal anchor to add.

    Returns
    -------
    void
    """
    try:  # tag_begin() only available starting with PyCairo 1.18.0
        ctx.tag_begin(cairo.TAG_DEST, "name='%s'" % name)
        ctx.tag_end(cairo.TAG_DEST)
    except Exception:
        pass
