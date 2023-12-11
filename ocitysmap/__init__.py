# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard
# Copyright (C) 2023  Hartmut Holzgraefe

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
import configparser
import gzip
import logging
import os
import shutil
import mapnik
import psycopg2
import re
import tempfile
import shapely
import shapely.wkt
import shapely.geometry
import gpxpy
import gettext

from . import coords
from . import i18n
from .indexlib.commons import IndexDoesNotFitError, IndexEmptyError
from .layoutlib import renderers
from .layoutlib import commons
from .indexlib import indexers
from .stylelib import Stylesheet

LOG = logging.getLogger('ocitysmap')


def guess_filetype(import_file):
    """ Try to find out file type via content inspection

    Parameters
    ----------
    import_file : str or UploadedFile
        Either a file path string, or a Django UploadedFile object

    Returns
    -------
    str or None
        File type name, currently one of "gpx", "umap", "poi"
    """
    need_close = False
    result = None
    try:
        if type(import_file) == str:
            file_name = import_file
            import_file = open(import_file, 'rb')
            need_close = True
        else: # UploadedFile
            file_name = import_file.name
            import_file.open()

        first_line = import_file.readline(100).decode('utf-8-sig')
        if first_line.startswith('<?xml'):
            try:
                import_file.seek(0)
                gpxpy.parse(import_file)
                result = "gpx"
            except:
                pass
        elif first_line.startswith('{'):
            second_line = import_file.readline(100).decode('utf-8-sig')
            if second_line.strip().startswith('"title":'):
                result = "poi"
            else:
                result = "umap" # also supports generic GeoJSON

        if result is None:
            raise RuntimeError("Can't determine import file type for %s" % file_name)
    except Exception as e:
        raise RuntimeError("Error processing import file %s" % e)

    if need_close:
        import_file.close()
    else:
        import_file.seek(0) # rewind to start
    return result

class RenderingConfiguration:
    """
    The RenderingConfiguration class encapsulate all the information concerning
    a rendering request. This data is used by the layout renderer, in
    conjonction with its rendering mode (defined by its implementation), to
    produce the map.
    """

    def __init__(self):
        self.origin_url      = None # URL this request was generated by
        self.title           = None # str
        self.osmid           = None # None / int (shading + city name)
        self.bounding_box    = None # bbox (from osmid if None)
        self.language        = None # str (locale)

        self.stylesheet      = None # Obj Stylesheet
        self.overlays        = [] # Array of Obj Stylesheet

        self.indexer         = "StreetIndex"

        self.paper_width_mm  = None
        self.paper_height_mm = None

        # Setup by OCitySMap::render() from osmid and bounding_box fields:
        self.polygon_wkt     = None # str (WKT of interest)

        # Setup by OCitySMap::render() from language field:
        self.i18n            = None # i18n object

        # Extra upload files
        self.import_files    = []

        # Logos
        self.logo            = "bundled:osm-logo.svg"
        self.extra_logo      = None
        self.extra_text      = None

        # custom QRcode text
        self.qrcode_text     = None

        # progress / status message callback
        self.status_update   = lambda msg: None

class OCitySMap:
    """
    This is the main entry point of the OCitySMap map rendering engine. Read
    this module's documentation for more details on its API.
    """

    DEFAULT_REQUEST_TIMEOUT_MIN = 15 # TODO make this a config file setting

    DEFAULT_RENDERING_PNG_DPI = 300 # TODO make this a config file setting

    STYLESHEET_REGISTRY = []

    OVERLAY_REGISTRY = []

    PAPER_SIZES = []

    MULTIPAGE_PAPER_SIZES = []

    def __init__(self, config_files=None, language=None):
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

        self._language = language
        self._translator = None
        if language is not None:
            try:
                self._translator = gettext.translation(
                    'ocitysmap',
                    localedir = os.path.join(os.path.dirname(__file__), '..', 'locale'),
                    languages=[language])
                self._translator.install()
            except Exception:
                pass

        config_files = set(map(os.path.expanduser, config_files))
        LOG.debug('Reading OCitySMap configuration from %s...' %
                 ', '.join(config_files))

        self._parser = configparser.ConfigParser()
        self._parser.optionxform = str # make option names case sensitive

        if not self._parser.read(config_files, encoding='utf-8'):
            raise IOError('None of the configuration files could be read!')

        self._locale_path = os.path.join(os.path.dirname(__file__), '..', 'locale')
        self.__dbs = {}

        # Read stylesheet configuration
        self.STYLESHEET_REGISTRY = Stylesheet.create_all_from_config(self._parser, locale = language)
        if not self.STYLESHEET_REGISTRY:
            raise ValueError( \
                    'OCitySMap configuration does not contain any stylesheet!')
        LOG.debug('Found %d Mapnik stylesheets.' % len(self.STYLESHEET_REGISTRY))

        self.OVERLAY_REGISTRY = Stylesheet.create_all_from_config(self._parser, "overlays", locale=language)
        LOG.debug('Found %d Mapnik overlay styles.' % len(self.OVERLAY_REGISTRY))

        # register additional font path directories if set
        try:
            font_path = self._parser.get('rendering', 'font_path')
            for font_dir in font_path.split(os.pathsep):
                mapnik.register_fonts(font_dir)
        except configparser.NoOptionError:
            pass

        r_paper = re.compile('^\s*(\d+)\s*x\s*(\d+)\s*$')

        if self._parser.has_section('paper_sizes'):
            self.PAPER_SIZES = []
            for key in self._parser['paper_sizes']:
                value = self._parser['paper_sizes'][key]
                try:
                    (w,h) = r_paper.match(value).groups()
                    self.PAPER_SIZES.append((key, int(w), int(h)))
                except:
                    LOG.warning("Ignoring invalid paper size '%s' for format '%s'" % (key, value))
        else:
            # minimal fallback configuration
            self.PAPER_SIZES = [('DinA4',     210, 297),
                                ('US_letter', 216, 279),
                               ]

        self.PAPER_SIZES.append(('Best fit', None, None))
        self.PAPER_SIZES.append(('Custom', None, None))

        if self._parser.has_section('multipage_paper_sizes'):
            self.MULTIPAGE_PAPER_SIZES = []
            for key in self._parser['multipage_paper_sizes']:
                value = self._parser['multipage_paper_sizes'][key]
                try:
                    (w,h) = r_paper.match(value).groups()
                    self.MULTIPAGE_PAPER_SIZES.append((key, int(w), int(h)))
                except Exception as e:
                    LOG.warning("Ignoring invalid paper size '%s' for multi page format '%s'" % (key, value))
        else:
            # minimal fallback configuration
            self.MULTIPAGE_PAPER_SIZES = [('DinA4',     210, 297),
                                          ('US_letter', 216, 279),
                                         ]

    def translate(self, txt):
        if self._translator is None:
            result = txt
        else:
            result = self._translator.gettext(txt)
        return result

    @property
    def _db(self, name='default'):
        """ Connect to configured database

        Actual config entry name is `[datasource]` for the default db,
        and `[datasource_...name...]` for everything else

        Parameters
        ----------
        name : str, optional
             Name of datasource to use.

        Returns
        -------
        psycopg2.connection
            Database connection for the given name.
        """

        # check db chache for already opened connection for this name
        if name in self.__dbs:
            return self.__dbs[name]

        # Database connection
        if name == 'default':
            datasource = dict(self._parser.items('datasource'))
        else:
            datasource = dict(self._parser.items('datasource_' + name))

        # The port is not a mandatory configuration option, so make
        # sure we define a default value.
        if not 'port' in datasource:
            datasource['port'] = 5432

        LOG.debug('Connecting to database %s on %s:%s as %s...' %
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

        # set request timeout from configuration, or static default if not configured
        try:
            timeout = int(self._parser.get('datasource', 'request_timeout'))
        except (configparser.NoOptionError, ValueError):
            timeout = OCitySMap.DEFAULT_REQUEST_TIMEOUT_MIN
        self._set_request_timeout(db, timeout)

        # cache result
        self.__dbs[name] = db

        # return result
        return db

    def _set_request_timeout(self, db, timeout_minutes=15):
        """ Set db statement timeout

        Sets the PostgreSQL request timeout to avoid long-running queries on
        the database.

        Parameters
        ----------
        timeout_minutes : int, optional
            Statement execution timeout in minutes (default: 15)

        Returns
        -------
        void
        """
        cursor = db.cursor()
        cursor.execute('set session statement_timeout=%d;' %
                       (timeout_minutes * 60 * 1000))
        cursor.execute('show statement_timeout;')
        LOG.debug('Configured statement timeout: %s.' %
                  cursor.fetchall()[0][0])

    def _cleanup_tempdir(self, tmpdir):
        """ Remove a temporary directory including all contents

        Parameters
        ----------
        tmpdir : str
            Path to the temporary directory

        Returns
        -------
        void
        """
        LOG.debug('Cleaning up %s...' % tmpdir)
        shutil.rmtree(tmpdir)

    def _get_geographic_info(self, osmid, table):
        """ Get geograpich info for an OSM object

        Return the area for the given osm id in the given table, or raise
        LookupError when not found

        Parameters
        ----------
        osmid : int
            Openstreetmap in osm2pgsql table (may be negative)
        table : str
            Table to search in, either 'polygon' or 'line'

        Returns
        -------
        shapely.geometry
            The geometry corresponding to the OSM id
        """

        # Ensure all OSM IDs are integers, bust cast them back to strings
        # afterwards.
        LOG.debug('Looking up bounding box and contour of OSM ID %d...'
                  % osmid)

        cursor = self._db.cursor()
        cursor.execute("""select
                            st_astext(st_transform(st_buildarea(st_union(way)),
                                                   4326))
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
        """ Get geometry information for OSM object by Id

        Return a tuple (WKT_envelope, WKT_buildarea) or raise
        LookupError when not found

        Parameters
        ----------
        osmid : int
            OpenStreetMap object Id to search for in `polygon'
            and `line` table (may be negative)

        Returns
        -------
        list of str
            WKT representations of
            * object geometry envelope
            * actual object geometry itself
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
        """ Get last update timestamp from osm2pgsql database

        Parameters
        ----------
        none

        Returns
        -------
        datetime.datetime
            Time the last successful update of the osm2pgsql database has happened
        """
        cursor = self._db.cursor()
        query = "select last_update from maposmatic_admin;"
        try:
            cursor.execute(query)
        except psycopg2.ProgrammingError:
            self._db.rollback()
            return None
        # Extract datetime object. It is located as the first element
        # of a tuple, itself the first element of an array.
        result = cursor.fetchall()[0][0]
        cursor.close()

        return result

    def get_all_style_configurations(self):
        """ Get all configured stylesheets

        Returns the list of all available stylesheet configurations (list of
        Stylesheet objects).

        Parameters
        ----------
        none

        Returns
        -------
        list of Stylesheet
            All configured stylesheets that have successfully been loaded
        """
        return self.STYLESHEET_REGISTRY

    def get_all_style_names(self):
        """Returns the list of all available stylesheet names

        Parameters
        ----------
        none

        Returns
        -------
        list of str
            Names of all configured stylesheets that have been loaded successfully

        """
        style_names = []
        for s in self.STYLESHEET_REGISTRY:
            style_names.append(s.name)
        return style_names;

    def get_stylesheet_by_name(self, name):
        """Returns a stylesheet by its key name.

        Parameters
        ----------
        name : str
            Name of stylesheet to retrieve

        Returns
        -------
        Stylesheet
            Full stylesheet data for the given stylesheet name


        Throws
        ------
        LookupError
            When no stylesheet is found by the given name
        """
        for style in self.STYLESHEET_REGISTRY:
            if style.name == name:
                return style
            if name in style.aliases:
                return style
        raise LookupError( 'The requested stylesheet %s was not found!' % name)

    def get_all_overlay_configurations(self):
        """ Get all configured overlay styles

        Returns the list of all available overlay configurations (list of
        Stylesheet objects).

        Parameters
        ----------
        none

        Returns
        -------
        list of Stylesheet
            All configured overlays that have successfully been loaded
        """
        return self.OVERLAY_REGISTRY

    def get_all_overlay_names(self):
        """Returns the list of all available overlay names

        Parameters
        ----------
        none

        Returns
        -------
        list of str
            Names of all configured overlays that have been loaded successfully

        """
        overlay_names = []
        for o in self.OVERLAY_REGISTRY:
            overlay_names.append(o.name)
        return overlay_names;

    def get_overlay_by_name(self, name):
        """Returns an overlay by its key name.

        Parameters
        ----------
        name : str
            Name of overlay style to retrieve

        Returns
        -------
        Stylesheet
            Full stylesheet data for the given overlay name


        Throws
        ------
        LookupError
            When no overlay style is found by the given name
        """
        for style in self.OVERLAY_REGISTRY:
            if style.name == name:
                return style
            if name in style.aliases:
                return style
        raise LookupError( 'The requested overlay stylesheet %s was not found!' % name)

    def get_all_renderers(self):
        """Returns the list of all available layout renderers (list of
        Renderer classes)."""
        return renderers.get_renderers()

    def get_all_renderer_names(self):
        """Returns the list of all available layout renderers names"""
        renderer_names = []
        for r in renderers.get_renderers():
            renderer_names.append(r.name)
        return renderer_names;

    def get_all_renderer_name_desc(self):
        result = []
        for renderer in renderers.get_indexers():
            result.append((renderer.name, renderer.description))
        return result

    def get_all_indexers(self):
        """Returns the list of all available layout indexers (list of
        Indexer classes)."""
        return indexers.get_indexers()

    def get_all_indexer_names(self):
        """Returns the list of all available layout indexers names"""
        indexer_names = []
        for r in indexers.get_indexers():
            indexer_names.append(r.name)
        return indexer_names;

    def get_all_indexers_name_desc(self):
        result = []
        for indexer in indexers.get_indexers():
            result.append((indexer.name, (self.translate(indexer.description))))
        return result

    def get_all_paper_sizes(self, section = None):
        if section in ['single', 'single_page', 'singlepage']:
            return self.PAPER_SIZES
        elif section in ['multi', 'multi_page', 'multipage']:
            return self.MULTIPAGE_PAPER_SIZES
        else:
            return self.PAPER_SIZES

    def get_all_paper_size_names(self, section = None):
        paper_names = []
        for p in self.get_all_paper_sizes(section):
            paper_names.append(p[0])
        return paper_names

    def get_paper_size_by_name(self, name, section = None):
        for p in self.get_all_paper_sizes(section):
            if p[0] == name:
                return [p[1], p[2]]
        raise LookupError( 'The requested paper size %s was not found!' % name)

    def get_paper_size_name_by_size(self, width, height, section = None):
        for p in self.get_all_paper_sizes(section):
            if (p[1] == width and p[2] == height) or (p[1] == height and p[2] == width):
                if width > height:
                    return "%s (landsacape)" % p[0]
                else:
                    return "%s (portrait)" % p[0]

        return None

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

        if 'PGAPPNAME' not in os.environ:
            os.environ['PGAPPNAME'] = "ocitysmap"

        os.environ['PGOPTIONS'] = "-c mapnik.language=" + config.language[:2] + " -c mapnik.locality=" + config.language[:5] + " -c mapnik.country=" + config.language[3:5]
        LOG.debug("PGOPTIONS '%s'" % os.environ.get('PGOPTIONS', 'not set'))

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

        # Make sure bounding box has non-zero width / height
        LOG.warning("checking bounds")
        if config.bounding_box.get_left() ==  config.bounding_box.get_right():
            config.bounding_box = config.bounding_box.create_expanded(1.0 / 3600, 1.0 / 3600)
        if config.bounding_box.get_top() ==  config.bounding_box.get_bottom():
            config.bounding_box = config.bounding_box.create_expanded(1.0 / 3600, 1.0 / 3600)
        assert config.bounding_box.get_left() !=  config.bounding_box.get_right(), \
                "Bounding box has zero width"
        assert config.bounding_box.get_top()  !=  config.bounding_box.get_bottom(), \
                "Bounding box has zero height"

        # Make sure paper has non-zero widht / height
        assert config.paper_width_mm > 0, \
                "Paper needs non-zero width"
        assert config.paper_height_mm > 0, \
                "Paper needs non-zero height"

        osm_date = self.get_osm_database_last_update()

        # Create a temporary directory for all our temporary helper files
        tmpdir = tempfile.mkdtemp(prefix='ocitysmap')

        # count successfully created output files
        output_count = 0

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
                    raise
                except OSError as e:
                    LOG.warning("OS Error while rendering %s: %s" % (output_format, e))
                    raise

                output_count = output_count + 1
        finally:
            config.status_update("")
            self._cleanup_tempdir(tmpdir)

        return output_count

    def _render_one(self, config, tmpdir, renderer_cls,
                    output_format, output_filename, osm_date, file_prefix):
        """ Render one output format

        Parameters
        ----------
        config :
            The renderer / request settings.
        tmpdir : str
            Path to temporary directory to use for this job
        renderer_cls :
        output_format : str
            One of `pdf`, `ps`, `ps.gz`, `svg`, `svgz`, `csv`
        osm_date :
        file_prefix : str

        Returns
        -------
        void
        """
        tmp_output_filename = output_filename + ".tmp"
        config.output_format = output_format.upper()
        LOG.debug('Rendering to %s format...' % config.output_format)
        config.status_update(_("Rendering %s") % config.output_format)

        dpi = layoutlib.commons.PT_PER_INCH

        renderer = renderer_cls(self._db, config, tmpdir, dpi, file_prefix)

        if output_format == 'png':
            try:
                dpi = int(self._parser.get('rendering', 'png_dpi'))
            except configparser.NoOptionError:
                dpi = OCitySMap.DEFAULT_RENDERING_PNG_DPI

            w_px = int(layoutlib.commons.convert_mm_to_dots(config.paper_width_mm, dpi))
            h_px = int(layoutlib.commons.convert_mm_to_dots(config.paper_height_mm, dpi))

            if w_px > 25000 or h_px > 25000:
                dpi = layoutlib.commons.PT_PER_INCH
                w_px = int(layoutlib.commons.convert_pt_to_dots(renderer.paper_width_pt, dpi))
                h_px = int(layoutlib.commons.convert_pt_to_dots(renderer.paper_height_pt, dpi))
                if w_px > 25000 or h_px > 25000:
                    LOG.warning("Paper size too large for PNG output, skipping")
                    return
                LOG.warning("%d DPI to high for this paper size, using 72dpi instead" % dpi)

            # as the dpi value may have changed we need to re-create the renderer
            renderer = renderer_cls(self._db, config, tmpdir, dpi, file_prefix)

            # As strange as it may seem, we HAVE to use a vector
            # device here and not a raster device such as
            # ImageSurface. Because, for some reason, with
            # ImageSurface, the font metrics would NOT match those
            # pre-computed by renderer_cls.__init__() and used to
            # layout the whole page
            LOG.debug("Rendering PNG into %dpx x %dpx area at %ddpi ..."
                      % (w_px, h_px, dpi))
            surface = cairo.PDFSurface(None, w_px, h_px)

        elif output_format == 'svg':
            surface = cairo.SVGSurface(tmp_output_filename,
                                       renderer.paper_width_pt, renderer.paper_height_pt)
            surface.restrict_to_version(cairo.SVGVersion.VERSION_1_2);
        elif output_format == 'svgz':
            surface = cairo.SVGSurface(gzip.GzipFile(tmp_output_filename, 'wb'),
                                       renderer.paper_width_pt, renderer.paper_height_pt)
            surface.restrict_to_version(cairo.SVGVersion.VERSION_1_2);
        elif output_format == 'pdf':
            surface = cairo.PDFSurface(tmp_output_filename,
                                       renderer.paper_width_pt, renderer.paper_height_pt)
            surface.restrict_to_version(cairo.PDFVersion.VERSION_1_5);

            try:
                surface.set_metadata(cairo.PDFMetadata.CREATOR,
                                     'MyOSMatic <https://print.get-map.org/>')

                surface.set_metadata(cairo.PDFMetadata.TITLE,
                                     config.title)

                surface.set_metadata(cairo.PDFMetadata.AUTHOR,
                                     "Created using MapOSMatic/OCitySMap\n" +
                                     "Map data © 2018 OpenStreetMap contributors (see http://osm.org/copyright)")

                surface.set_metadata(cairo.PDFMetadata.SUBJECT,
                                     renderer.description) # TODO add style annotations here

                surface.set_metadata(cairo.PDFMetadata.KEYWORDS,
                                     "OpenStreetMap, MapOSMatic, OCitysMap")
            except:
              LOG.warning("Installed Cairo version does not support PDF annotations yet")

        elif output_format == 'ps':
            surface = cairo.PSSurface(tmp_output_filename,
                                      renderer.paper_width_pt, renderer.paper_height_pt)
        elif output_format == 'ps.gz':
            surface = cairo.PSSurface(gzip.GzipFile(tmp_output_filename, 'wb'),
                                      renderer.paper_width_pt, renderer.paper_height_pt)
        elif output_format == 'csv':
            # We don't render maps into CSV.
            return
        else:
            raise ValueError( \
                'Unsupported output format: %s!' % output_format.upper())

        renderer.render(surface, dpi, osm_date)

        LOG.debug('Writing %s...' % output_filename)

        config.status_update(_("%s: writing output file") % output_format.upper())

        if output_format == 'png':
            surface.write_to_png(tmp_output_filename)

        surface.finish()

        os.rename(tmp_output_filename, output_filename)

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
