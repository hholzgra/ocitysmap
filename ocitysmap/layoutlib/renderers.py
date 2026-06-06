# -*- coding: utf-8 -*-

from ocitysmap.layoutlib.single_page_renderer.no_index import SinglePageRendererNoIndex
from ocitysmap.layoutlib.single_page_renderer.side_index import SinglePageRendererIndexOnSide
from ocitysmap.layoutlib.single_page_renderer.bottom_index import SinglePageRendererIndexBottom
from ocitysmap.layoutlib.single_page_renderer.extra_page import SinglePageRendererIndexExtraPage
from ocitysmap.layoutlib.multi_page_renderer import MultiPageRenderer
# from ocitysmap.layoutlib.tk25 import TK25Renderer

# The renderers registry
_RENDERERS = [
    SinglePageRendererNoIndex,
    SinglePageRendererIndexOnSide,
    SinglePageRendererIndexBottom,
    SinglePageRendererIndexExtraPage,
    # TK25Renderer,
    MultiPageRenderer,
    ]

def get_renderer_class_by_name(name):
    """Retrieves a renderer class, by name."""
    for renderer in _RENDERERS:
        if renderer.name == name:
            return renderer
    raise LookupError('The requested renderer %s was not found!' % name)

def get_renderers():
    """Returns the list of available renderers' names."""
    return _RENDERERS
