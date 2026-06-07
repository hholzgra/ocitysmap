#! /usr/bin/env python
# -*- coding: utf-8 -*-


# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2009  David Decotigny
# Copyright (C) 2009  Frédéric Lehobey
# Copyright (C) 2009  David Mentré
# Copyright (C) 2009  Maxime Petazzoni
# Copyright (C) 2009  Thomas Petazzoni
# Copyright (C) 2009  Gaël Utard

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

from distutils.core import setup

setup(name="ocitysmap",
      description="OcitySMap, a tool to render city maps based on OpenStreetMap data",
      long_description="""
OcitySMap is a tool that allows to render city maps based on
OpenStreetMap data, along with an index of the streets. These maps are
designed to be printed.
""",
      version="1.0",
      author="The Hackfest2009 team",
      author_email="staff@maposmatic.org",
      url="http://www.maposmatic.org",
      license="GPL",
      maintainer="The Hackfest2009 team",
      maintainer_email="staff@maposmatic.org",
      packages = ['ocitysmap',
                  'ocitysmap.maplib',
                  'ocitysmap.indexlib',
                  'ocitysmap.layoutlib' ],
      scripts = ['render.py' ],
      data_files = [
          ('share/images/ocitysmap', ['images/osm-logo.png',
                                      'images/osm-logo.svg'])
      ]
      )
