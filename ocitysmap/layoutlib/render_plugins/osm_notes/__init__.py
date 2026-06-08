from ocitysmap.layoutlib.abstract_renderer import Renderer
from ocitysmap.coords import Point

from ocitysmap.indexlib.GeneralIndex import GeneralIndexItem

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import json

import logging
LOG = logging.getLogger('ocitysmap')

def render(renderer, ctx):
    if not hasattr(renderer, 'street_index'):
        return

    bbox = renderer._map_canvas.get_actual_bounding_box()
    url  = ("https://api.openstreetmap.org/api/0.6/notes.json?closed=0&bbox=%f,%f,%f,%f"
            % (bbox.get_left(), bbox.get_bottom(), bbox.get_right(), bbox.get_top()))
    LOG.info("OSM Notes URL: %s" % url)

    req = Request(url)
    try:
        response = urlopen(req)
    except HTTPError as e:
        LOG.error('The server couldn\'t fulfill the request.')
        LOG.error('Error code: %s' % e.code)
        return
    except URLError as e:
        LOG.error('We failed to reach a server.')
        LOG.error('Reason: %s' % e.reason)
        return

    notes_json = response.read()

    try:
        notes = json.loads(notes_json)
    except Exception as e:
        LOG.error("JSON decode exception %s / %s." % (e.code, e.reason))
        return

    index_items = []

    n = 0
    for note in notes['features']:
        n = n + 1
        lat = note['geometry']['coordinates'][1]
        lon = note['geometry']['coordinates'][0]

        point = Point(lat, lon)

        try:
            index_text = "Note %d - %s" % (n, note['properties']['comments'][0]['text'])
            index_items.append(GeneralIndexItem(index_text[0:50], point, point, None))
            renderer._marker('red', str(n), lat, lon, ctx, renderer.dpi)
        except IndexError:
            pass

#    renderer.street_index.add_category("OSM Notes", index_items)
