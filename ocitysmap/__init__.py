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

"""OCitySMap 2.

OCitySMap is a Mapnik-based map rendering engine from OpenStreetMap.org data.
It is architectured around the concept of Renderers, in charge of rendering the
map and all the visual features that go along with it (scale, grid, legend,
index, etc.) on the given paper size using a provided Mapnik stylesheet,
according to their implemented layout.

The PlainRenderer for example renders a full-page map with its grid, a title
header and copyright notice, but without the index.

How to use OCitySMap?
---------------------

The API of OCitySMap is very simple. First, you need to instanciate the main
OCitySMap class with the path to your OCitySMap configuration file (see
ocitysmap.conf.dist):


    renderer = ocitysmap.OCitySMap('/path/to/your/config')

The next step is to create a RenderingConfiguration, the object that
encapsulates all the information to parametize the rendering, including the
Mapnik stylesheet. You can retrieve the list of supported stylesheets (directly
as Stylesheet objects) with:

    styles = renderer.get_all_style_configurations()

Fill in your RenderingConfiguration with the map title, the OSM ID or bounding
box, the chosen map language, the Stylesheet object and the paper size (in
millimeters) and simply pass it to OCitySMap's render method:

    renderer.render(rendering_configuration, layout_name,
                    output_formats, prefix)

The layout name is the renderer's key name. You can get the list of all
supported renderers with renderer.get_all_renderers(). The output_formats is a
list of output formats. For now, the following formats are supported:

    * PNG at 72dpi
    * PDF
    * SVG
    * SVGZ (gzipped-SVG)
    * PS

The prefix is the filename prefix for all the rendered files. This is usually a
path to the destination's directory, eventually followed by some unique, yet
common prefix for the files rendered for a job.
"""

__author__ = 'The MapOSMatic developers'
__version__ = '0.2'

import cairo
import ConfigParser
import gzip
import logging
import os
import psycopg2
import re
import tempfile
import shapely
import shapely.wkt
import shapely.geometry

import coords
import i18n
from indexlib.indexer import StreetIndex
from indexlib.commons import IndexDoesNotFitError, IndexEmptyError
from layoutlib import PAPER_SIZES, renderers
import layoutlib.commons

LOG = logging.getLogger('ocitysmap')

class RenderingConfiguration:
    """
    The RenderingConfiguration class encapsulate all the information concerning
    a rendering request. This data is used by the layout renderer, in
    conjonction with its rendering mode (defined by its implementation), to
    produce the map.
    """

    def __init__(self):
        self.title           = None # str
        self.osmid           = None # None / int (shading + city name)
        self.bounding_box    = None # bbox (from osmid if None)
        self.language        = None # str (locale)

        self.stylesheet      = None # Obj Stylesheet
        self.overlay         = None # Obj Stylesheet

        self.paper_width_mm  = None
        self.paper_height_mm = None

        # Setup by OCitySMap::render() from osmid and bounding_box fields:
        self.polygon_wkt     = None # str (WKT of interest)

        # Setup by OCitySMap::render() from language field:
        self.i18n            = None # i18n object


class Stylesheet:
    """
    A Stylesheet object defines how the map features will be rendered. It
    contains information pointing to the Mapnik stylesheet and other styling
    parameters.
    """
    DEFAULT_ZOOM_LEVEL = 16

    def __init__(self):
        self.name        = None # str
        self.path        = None # str
        self.description = '' # str

        self.grid_line_color = 'black'
        self.grid_line_alpha = 0.5
        self.grid_line_width = 1

        self.shade_color = 'black'
        self.shade_alpha = 0.1

        # shade color for town contour in multi-pages
        self.shade_color_2 = 'white'
        self.shade_alpha_2 = 0.4

    @staticmethod
    def create_from_config_section(parser, section_name):
        """Creates a Stylesheet object from the OCitySMap configuration.

        Args:
            parser (ConfigParser.ConfigParser): the configuration parser
                object.
            section_name (string): the stylesheet section name in the
                configuration.
        """
        s = Stylesheet()

        def assign_if_present(key, cast_fn=str):
            if parser.has_option(section_name, key):
                setattr(s, key, cast_fn(parser.get(section_name, key)))

        s.name = parser.get(section_name, 'name')
        s.path = parser.get(section_name, 'path')
        if not os.path.exists(s.path):
            raise ValueError, \
                'Could not find stylesheet file for stylesheet %s!' % s.name
        assign_if_present('description')

        assign_if_present('grid_line_color')
        assign_if_present('grid_line_alpha', float)
        assign_if_present('grid_line_width', int)

        assign_if_present('shade_color')
        assign_if_present('shade_alpha', float)

        assign_if_present('shade_color_2')
        assign_if_present('shade_alpha_2', float)
        return s

    @staticmethod
    def create_all_from_config(parser):
        styles = parser.get('rendering', 'available_stylesheets')
        if not styles:
            raise ValueError, \
                    'OCitySMap configuration does not contain any stylesheet!'

        return [Stylesheet.create_from_config_section(parser, name.strip())
                for name in styles.split(',')]

class OCitySMap:
    """
    This is the main entry point of the OCitySMap map rendering engine. Read
    this module's documentation for more details on its API.
    """

    DEFAULT_REQUEST_TIMEOUT_MIN = 15

    DEFAULT_RENDERING_PNG_DPI = 72

    STYLESHEET_REGISTRY = []

    def __init__(self, config_files=None):
        """Instanciate a new configured OCitySMap instance.

        Args:
            config_file (string or list or None): path, or list of paths to
                the OCitySMap configuration file(s). If None, sensible defaults
                are tried.
        """

        if config_files is None:
            config_files = ['/etc/ocitysmap.conf', '~/.ocitysmap.conf']
        elif not isinstance(config_files, list):
            config_files = [config_files]

        config_files = map(os.path.expanduser, config_files)
        LOG.debug('Reading OCitySMap configuration from %s...' %
                 ', '.join(config_files))

        self._parser = ConfigParser.RawConfigParser()
        if not self._parser.read(config_files):
            raise IOError, 'None of the configuration files could be read!'

        self._locale_path = os.path.join(os.path.dirname(__file__), '..', 'locale')
        self.__db = None

        # Read stylesheet configuration
        self.STYLESHEET_REGISTRY = Stylesheet.create_all_from_config(self._parser)
        LOG.debug('Found %d Mapnik stylesheets.' % len(self.STYLESHEET_REGISTRY))

    @property
    def _db(self):
        if self.__db:
            return self.__db

        # Database connection
        datasource = dict(self._parser.items('datasource'))
        # The port is not a mandatory configuration option, so make
        # sure we define a default value.
        if not datasource.has_key('port'):
            datasource['port'] = 5432
        LOG.info('Connecting to database %s on %s:%s as %s...' %
                 (datasource['dbname'], datasource['host'], datasource['port'],
                  datasource['user']))

        db = psycopg2.connect(user=datasource['user'],
                              password=datasource['password'],
                              host=datasource['host'],
                              database=datasource['dbname'],
                              port=datasource['port'])

        # Force everything to be unicode-encoded, in case we run along Django
        # (which loads the unicode extensions for psycopg2)
        db.set_client_encoding('utf8')

        # Make sure the DB is correctly installed
        self._verify_db(db)

        try:
            timeout = int(self._parser.get('datasource', 'request_timeout'))
        except (ConfigParser.NoOptionError, ValueError):
            timeout = OCitySMap.DEFAULT_REQUEST_TIMEOUT_MIN
        self._set_request_timeout(db, timeout)

        self.__db = db
        return self.__db

    def _verify_db(self, db):
        """Make sure the PostGIS DB is compatible with us."""
        cursor = db.cursor()
        cursor.execute("""
SELECT ST_AsText(ST_LongestLine(
                    'POINT(100 100)'::geometry,
		    'LINESTRING(20 80, 98 190, 110 180, 50 75 )'::geometry)
	        ) As lline;
""")
        assert cursor.fetchall()[0][0] == "LINESTRING(100 100,98 190)", \
            LOG.fatal("PostGIS >= 1.5 required for correct operation !")

    def _set_request_timeout(self, db, timeout_minutes=15):
        """Sets the PostgreSQL request timeout to avoid long-running queries on
        the database."""
        cursor = db.cursor()
        cursor.execute('set session statement_timeout=%d;' %
                       (timeout_minutes * 60 * 1000))
        cursor.execute('show statement_timeout;')
        LOG.debug('Configured statement timeout: %s.' %
                  cursor.fetchall()[0][0])

    def _cleanup_tempdir(self, tmpdir):
        LOG.debug('Cleaning up %s...' % tmpdir)
        for root, dirs, files in os.walk(tmpdir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(tmpdir)

    def _get_geographic_info(self, osmid, table):
        """Return the area for the given osm id in the given table, or raise
        LookupError when not found

        Args:
            osmid (integer): OSM ID
            table (str): either 'polygon' or 'line'

        Return:
            Geos geometry object
        """

        # Ensure all OSM IDs are integers, bust cast them back to strings
        # afterwards.
        LOG.debug('Looking up bounding box and contour of OSM ID %d...'
                  % osmid)

        cursor = self._db.cursor()
        cursor.execute("""select
                            st_astext(st_transform(st_buildarea(st_union(way)),
                                                   4002))
                          from planet_osm_%s where osm_id = %d
                          group by osm_id;""" %
                       (table, osmid))
        records = cursor.fetchall()
        try:
            ((wkt,),) = records
            if wkt is None:
                raise ValueError
        except ValueError:
            raise LookupError("OSM ID %d not found in table %s" %
                              (osmid, table))

        return shapely.wkt.loads(wkt)

    def get_geographic_info(self, osmid):
        """Return a tuple (WKT_envelope, WKT_buildarea) or raise
        LookupError when not found

        Args:
            osmid (integer): OSM ID

        Return:
            tuple (WKT bbox, WKT area)
        """
        found = False

        # Scan polygon table:
        try:
            polygon_geom = self._get_geographic_info(osmid, 'polygon')
            found = True
        except LookupError:
            polygon_geom = shapely.geometry.Polygon()

        # Scan line table:
        try:
            line_geom = self._get_geographic_info(osmid, 'line')
            found = True
        except LookupError:
            line_geom = shapely.geometry.Polygon()

        # Merge results:
        if not found:
            raise LookupError("No such OSM id: %d" % osmid)

        result = polygon_geom.union(line_geom)
        return (result.envelope.wkt, result.wkt)

    def get_osm_database_last_update(self):
        cursor = self._db.cursor()
        query = "select last_update from maposmatic_admin;"
        try:
            cursor.execute(query)
        except psycopg2.ProgrammingError:
            self._db.rollback()
            return None
        # Extract datetime object. It is located as the first element
        # of a tuple, itself the first element of an array.
        return cursor.fetchall()[0][0]

    def get_all_style_configurations(self):
        """Returns the list of all available stylesheet configurations (list of
        Stylesheet objects)."""
        return self.STYLESHEET_REGISTRY

    def get_stylesheet_by_name(self, name):
        """Returns a stylesheet by its key name."""
        for style in self.STYLESHEET_REGISTRY:
            if style.name == name:
                return style
        raise LookupError, 'The requested stylesheet %s was not found!' % name

    def get_all_renderers(self):
        """Returns the list of all available layout renderers (list of
        Renderer classes)."""
        return renderers.get_renderers()

    def get_all_paper_sizes(self):
        return PAPER_SIZES

    def render(self, config, renderer_name, output_formats, file_prefix):
        """Renders a job with the given rendering configuration, using the
        provided renderer, to the given output formats.

        Args:
            config (RenderingConfiguration): the rendering configuration
                object.
            renderer_name (string): the layout renderer to use for this rendering.
            output_formats (list): a list of output formats to render to, from
                the list of supported output formats (pdf, svgz, etc.).
            file_prefix (string): filename prefix for all output files.
        """

        assert config.osmid or config.bounding_box, \
                'At least an OSM ID or a bounding box must be provided!'

        output_formats = map(lambda x: x.lower(), output_formats)
        config.i18n = i18n.install_translation(config.language,
                                               self._locale_path)

        LOG.info('Rendering with renderer %s in language: %s (rtl: %s).' %
                 (renderer_name, config.i18n.language_code(),
                  config.i18n.isrtl()))

        # Determine bounding box and WKT of interest
        if config.osmid:
            osmid_bbox, osmid_area \
                = self.get_geographic_info(config.osmid)

            # Define the bbox if not already defined
            if not config.bounding_box:
                config.bounding_box \
                    = coords.BoundingBox.parse_wkt(osmid_bbox)

            # Update the polygon WKT of interest
            config.polygon_wkt = osmid_area
        else:
            # No OSM ID provided => use specified bbox
            config.polygon_wkt = config.bounding_box.as_wkt()

        # Make sure we have a bounding box
        assert config.bounding_box is not None
        assert config.polygon_wkt is not None

        osm_date = self.get_osm_database_last_update()

        # Create a temporary directory for all our shape files
        tmpdir = tempfile.mkdtemp(prefix='ocitysmap')
        try:
            LOG.debug('Rendering in temporary directory %s' % tmpdir)

            # Prepare the generic renderer
            renderer_cls = renderers.get_renderer_class_by_name(renderer_name)

            # Perform the actual rendering to the Cairo devices
            for output_format in output_formats:
                output_filename = '%s.%s' % (file_prefix, output_format)
                try:
                    self._render_one(config, tmpdir, renderer_cls,
                                     output_format, output_filename, osm_date,
                                     file_prefix)
                except IndexDoesNotFitError:
                    LOG.exception("The actual font metrics probably don't "
                                  "match those pre-computed by the renderer's"
                                  "constructor. Backtrace follows...")
        finally:
            self._cleanup_tempdir(tmpdir)

    def _render_one(self, config, tmpdir, renderer_cls,
                    output_format, output_filename, osm_date, file_prefix):

        LOG.info('Rendering to %s format...' % output_format.upper())

        factory = None
        dpi = layoutlib.commons.PT_PER_INCH

        if output_format == 'png':
            try:
                dpi = int(self._parser.get('rendering', 'png_dpi'))
            except ConfigParser.NoOptionError:
                dpi = OCitySMap.DEFAULT_RENDERING_PNG_DPI

            # As strange as it may seem, we HAVE to use a vector
            # device here and not a raster device such as
            # ImageSurface. Because, for some reason, with
            # ImageSurface, the font metrics would NOT match those
            # pre-computed by renderer_cls.__init__() and used to
            # layout the whole page
            def factory(w,h):
                w_px = int(layoutlib.commons.convert_pt_to_dots(w, dpi))
                h_px = int(layoutlib.commons.convert_pt_to_dots(h, dpi))
                LOG.debug("Rendering PNG into %dpx x %dpx area..."
                          % (w_px, h_px))
                return cairo.PDFSurface(None, w_px, h_px)

        elif output_format == 'svg':
            factory = lambda w,h: cairo.SVGSurface(output_filename, w, h)
        elif output_format == 'svgz':
            factory = lambda w,h: cairo.SVGSurface(
                    gzip.GzipFile(output_filename, 'wb'), w, h)
        elif output_format == 'pdf':
            factory = lambda w,h: cairo.PDFSurface(output_filename, w, h)
        elif output_format == 'ps':
            factory = lambda w,h: cairo.PSSurface(output_filename, w, h)
        elif output_format == 'ps.gz':
            factory = lambda w,h: cairo.PSSurface(
                gzip.GzipFile(output_filename, 'wb'), w, h)
        elif output_format == 'csv':
            # We don't render maps into CSV.
            return

        else:
            raise ValueError, \
                'Unsupported output format: %s!' % output_format.upper()

        renderer = renderer_cls(self._db, config, tmpdir, dpi, file_prefix)

        surface = factory(renderer.paper_width_pt, renderer.paper_height_pt)

        renderer.render(surface, dpi, osm_date)

        LOG.debug('Writing %s...' % output_filename)
        if output_format == 'png':
            surface.write_to_png(output_filename)

        surface.finish()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    o = OCitySMap([os.path.join(os.path.dirname(__file__), '..',
                                'ocitysmap.conf.mine')])

    c = RenderingConfiguration()
    c.title = 'Chevreuse, Yvelines, Île-de-France, France, Europe, Monde'
    c.osmid = -943886 # Chevreuse
    # c.osmid = -7444   # Paris
    c.language = 'fr_FR.UTF-8'
    c.paper_width_mm = 297
    c.paper_height_mm = 420
    c.stylesheet = o.get_stylesheet_by_name('Default')

    # c.paper_width_mm,c.paper_height_mm = c.paper_height_mm,c.paper_width_mm
    o.render(c, 'single_page_index_bottom',
             ['png', 'pdf', 'ps.gz', 'svgz', 'csv'],
             '/tmp/mymap_index_bottom')

    c.paper_width_mm,c.paper_height_mm = c.paper_height_mm,c.paper_width_mm
    o.render(c, 'single_page_index_side',
             ['png', 'pdf', 'ps.gz', 'svgz', 'csv'],
             '/tmp/mymap_index_side')

    o.render(c, 'plain',
             ['png', 'pdf', 'ps.gz', 'svgz', 'csv'],
             '/tmp/mymap_plain')
