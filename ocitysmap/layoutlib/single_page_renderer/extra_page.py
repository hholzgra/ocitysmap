from gettext import gettext

from ocitysmap.layoutlib.abstract_renderer import Renderer
from ocitysmap.layoutlib.single_page_renderers import SinglePageRenderer

class SinglePageRendererIndexExtraPage(SinglePageRenderer):
    """
    Single page renderer that renders the index on a separate 2nd page
    if the output file format supports multiple pages.
    """
    name = 'single_page_index_extra_page'
    description = gettext('Full-page layout with index on extra page (PDF only).')

    def __init__(self, db, rc, tmpdir, dpi, file_prefix):
        """
        Create the renderer.

        Parameters
        ----------
           db : psycopg2 DB
               GIS database connection handle
           rc : RenderingConfiguration
               Rendering configurationparameters.
           tmpdir : str
               Path to a temp dir that can hold temp files the renderer creates.
           file_prefix : str
               File name refix for all output file formats to be generated
           dpi : int
               Output resolution for bitmap formats
        """
        SinglePageRenderer.__init__(self, db, rc, tmpdir, dpi, file_prefix, 'extra_page')

    @staticmethod
    def get_compatible_paper_sizes(bounding_box, render_context,
                                   scale=Renderer.DEFAULT_SCALE):
        """Returns a list of the compatible paper sizes for the given bounding
        box. The list is sorted, smaller papers first, and a "custom" paper
        matching the dimensions of the bounding box is added at the end.

        Args:
            bounding_box (coords.BoundingBox): the map geographic bounding box.
            paper_sizes (list): the complete list of configured paper sizes
            scale (int): minimum mapnik scale of the map.

        Returns a list of tuples (paper name, width in mm, height in
        mm, portrait_ok, landscape_ok). Paper sizes are represented in
        portrait mode.
        """
        return SinglePageRenderer._generic_get_compatible_paper_sizes(
            bounding_box, render_context.get_all_paper_sizes(), scale, None)

    @staticmethod
    def get_minimal_paper_size(bounding_box, scale=Renderer.DEFAULT_SCALE):
        return SinglePageRenderer._generic_get_minimal_paper_size(
            bounding_box, scale, None)
