#! /usr/bin/env python3
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

import os
import sys
import shutil
import optparse
import subprocess
import glob

def make_pot():
    print("Make locale/ocitysmap.pot")
    # TODO auto-generate source file list
    cmd = ['xgettext',
           '--output=ocitysmap.pot',
           '--output-dir=locale',
           '--language=Python',
           '--from-code=UTF-8',
           ]
    cmd += glob.glob("./**/*.py", recursive = True)
    subprocess.check_call(cmd)
    return

def make_po(languages):
    print("Merge locale/ocitysmap.pot into locale/*/LC_MESSAGES/ocitysmap.po")
    for language in languages:
        print(" * %s" % language)
        subprocess.check_call(['msgmerge', '-U',
                               'locale/%s/LC_MESSAGES/ocitysmap.po' % language,
                               'locale/ocitysmap.pot'])
    return

def compile_mo(languages):
    print("Compile locale/*/LC_MESSAGES/ocitysmap.mo files")
    for language in languages:
        print(" * %s" % language)
        subprocess.check_call(['msgfmt', '-o',
                               'locale/%s/LC_MESSAGES/ocitysmap.mo' % language,
                               'locale/%s/LC_MESSAGES/ocitysmap.po' % language])
    return

def create_language(country_code):
    print("Create directory for %s" % country_code)
    os.makedirs('locale/%s/LC_MESSAGES' % country_code)
    shutil.copyfile('locale/ocitysmap.pot',
                    'locale/%s/LC_MESSAGES/ocitysmap.po' % country_code)
    return

def get_languages():
    language = os.listdir('locale')
    return list(filter(lambda s: s != 'ocitysmap.pot', language))

def main():
    usage = '%prog [options]\n WARNING: This program should be called from ocitysmap/ directory!'

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-P', '--make-pot', dest='make_pot',
                      action='store_true', default=False,
                      help="make locale/ocitysmap.pot")
    parser.add_option('-p', '--make-po', dest='make_po',
                      action='store_true', default=False,
                      help="merge locale/ocitysmap.pot with locale/*/LC_MESSAGES/ocitysmap.po")
    parser.add_option('-m', '--compile-mo', dest='compile_mo',
                      action='store_true', default=False,
                      help="compile locale/*/LC_MESSAGES/ocitysmap.mo files")
    parser.add_option('-n', '--new-language', dest='new_language',
                      metavar='LANGUAGE_CODE',
                      help='create .pot file for a new language. '
                      'LANGUAGE_CODE is like "fr_FR".',
                      default=None)

    (options, args) = parser.parse_args()
    if len(args):
        parser.print_help()
        return 1

    languages = get_languages()

    if options.make_pot:
        make_pot()
    if options.make_po:
        make_po(languages)
    if options.compile_mo:
        compile_mo(languages)
    if options.new_language:
        create_language(options.new_language)

if __name__ == '__main__':
    sys.exit(main())
