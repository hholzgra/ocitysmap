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

# PT/metrics conversion routines
PT_PER_INCH = 72.0
MM_PER_INCH = 25.4

def convert_pt_to_dots(pt, dpi = PT_PER_INCH):
    return float(pt * dpi) / PT_PER_INCH

def convert_mm_to_pt(mm):
    return mm / MM_PER_INCH * PT_PER_INCH

def convert_pt_to_mm(pt):
    return float(pt) * MM_PER_INCH / PT_PER_INCH
