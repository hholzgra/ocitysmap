#! /usr/bin/env python
# -*- coding: utf-8 -*-


# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2009  David Decotigny
# Copyright (C) 2009  Frédéric Lehobey
# Copyright (C) 2009  David Mentré
# Copyright (C) 2009  Maxime Petazzoni
# Copyright (C) 2009  Thomas Petazzoni
# Copyright (C) 2009  Gaël Utard

# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

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
