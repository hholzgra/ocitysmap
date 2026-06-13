# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard

# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

# PT/metrics conversion routines
PT_PER_INCH = 72.0
MM_PER_INCH = 25.4

def convert_pt_to_dots(pt, dpi = PT_PER_INCH):
    return float(pt * dpi) / PT_PER_INCH

def convert_mm_to_pt(mm):
    return mm / MM_PER_INCH * PT_PER_INCH

def convert_mm_to_dots(mm, dpi = PT_PER_INCH):
    return float(convert_mm_to_pt(mm) * dpi) / PT_PER_INCH

def convert_pt_to_mm(pt):
    return float(pt) * MM_PER_INCH / PT_PER_INCH
