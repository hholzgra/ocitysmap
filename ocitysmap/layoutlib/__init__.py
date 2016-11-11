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

# Portrait paper sizes in milimeters
PAPER_SIZES = [('A5', 148, 210),
               ('A4', 210, 297),
               ('A3', 297, 420),
               ('A2', 420, 594),
               ('A1', 594, 841),
               ('A0', 841, 1189),

               ('A1-s', 594, 650),
               
               ('US letter', 216, 279),

               ('100x75cm', 750, 1000),
               ('80x60cm', 600, 800),
               ('60x45cm', 450, 600),
               ('40x30cm', 300, 400),

               ('60x60cm', 600, 600),
               ('50x50cm', 500, 500),
               ('40x40cm', 400, 400),

               ('Best fit', None, None),
               ]
