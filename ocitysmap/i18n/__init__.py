# -*- coding: utf-8; mode: Python -*-

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

import gettext

def _install_language(language, locale_path):
    t = gettext.translation(domain='ocitysmap',
                            localedir=locale_path,
                            languages=[language],
                            fallback=True)
    t.install()

class i18n:
    """Functions needed to be implemented for a new language.
       See i18n_fr_FR_UTF8 below for an example. """
    def language_code(self):
        pass

    def user_readable_street(self, name):
        return name

    def first_letter_equal(self, a, b):
        pass

    def isrtl(self):
        return False

    def upper_unaccent_string(self, s):
        return s.upper()

    def number_category_name(self):
        return "0-9"

class i18n_generic(i18n):
    def __init__(self, language, locale_path):
        """Install the _() function for the chosen locale other
           object initialisation"""

        # It's important to convert to str() here because the map_language
        # value coming from the database is Unicode, but setlocale() needs a
        # non-unicode string as the locale name, otherwise it thinks it's a
        # locale tuple.
        self.language = str(language)
        _install_language(language, locale_path)

    def language_code(self):
        """returns the language code of the specific language
           supported, e.g. fr_FR.UTF-8"""
        return self.language

    def user_readable_street(self, name):
        """ transforms a street name into a suitable form for
            the map index, e.g. Paris (Rue de) for French"""
        return name

    def first_letter_equal(self, a, b):
        """returns True if the letters a and b are equal in the map index,
           e.g. É and E are equals in French map index"""
        return a == b

    def isrtl(self):
        return False

    def language_desc(self):
        return self.language_code()

# TODO: find more clean way to deal with import cross-dependencies
# for now this construct keeps flake8 and isort happy
# isort: off
if True:
    from .ar    import i18n_ar_generic
    from .al    import i18n_al_generic
    from .ast   import i18n_ast_generic
    from .be    import i18n_be_generic
    from .ca    import i18n_ca_generic
    from .de    import i18n_de_generic
    from .es    import i18n_es_generic
    from .fa    import i18n_fa_generic
    from .fr    import i18n_fr_generic
    from .hr    import i18n_hr_HR
    from .it    import i18n_it_generic
    from .nl    import i18n_nl_generic
    from .pl    import i18n_pl_generic
    from .pt_br import i18n_pt_br_generic
    from .ro    import i18n_ro_generic
    from .ru    import i18n_ru_generic
    from .tr    import i18n_tr_generic
# isort: on

# When not listed in the following map, default language class will be
# i18n_generic
language_class_map = {
    'fr_BE.UTF-8': i18n_fr_generic,
    'fr_FR.UTF-8': i18n_fr_generic,
    'fr_CA.UTF-8': i18n_fr_generic,
    'fr_CH.UTF-8': i18n_fr_generic,
    'fr_LU.UTF-8': i18n_fr_generic,
    'en_AG': i18n_generic,
    'en_AU.UTF-8': i18n_generic,
    'en_BW.UTF-8': i18n_generic,
    'en_CA.UTF-8': i18n_generic,
    'en_DK.UTF-8': i18n_generic,
    'en_GB.UTF-8': i18n_generic,
    'en_HK.UTF-8': i18n_generic,
    'en_IE.UTF-8': i18n_generic,
    'en_IN': i18n_generic,
    'en_NG': i18n_generic,
    'en_NZ.UTF-8': i18n_generic,
    'en_PH.UTF-8': i18n_generic,
    'en_SG.UTF-8': i18n_generic,
    'en_US.UTF-8': i18n_generic,
    'en_ZA.UTF-8': i18n_generic,
    'en_ZW.UTF-8': i18n_generic,
    'nl_BE.UTF-8': i18n_nl_generic,
    'nl_NL.UTF-8': i18n_nl_generic,
    'it_IT.UTF-8': i18n_it_generic,
    'it_CH.UTF-8': i18n_it_generic,
    'de_AT.UTF-8': i18n_de_generic,
    'de_BE.UTF-8': i18n_de_generic,
    'de_DE.UTF-8': i18n_de_generic,
    'de_LU.UTF-8': i18n_de_generic,
    'de_CH.UTF-8': i18n_de_generic,
    'es_ES.UTF-8': i18n_es_generic,
    'es_AR.UTF-8': i18n_es_generic,
    'es_BO.UTF-8': i18n_es_generic,
    'es_CL.UTF-8': i18n_es_generic,
    'es_CR.UTF-8': i18n_es_generic,
    'es_DO.UTF-8': i18n_es_generic,
    'es_EC.UTF-8': i18n_es_generic,
    'es_SV.UTF-8': i18n_es_generic,
    'es_GT.UTF-8': i18n_es_generic,
    'es_HN.UTF-8': i18n_es_generic,
    'es_MX.UTF-8': i18n_es_generic,
    'es_NI.UTF-8': i18n_es_generic,
    'es_PA.UTF-8': i18n_es_generic,
    'es_PY.UTF-8': i18n_es_generic,
    'es_PE.UTF-8': i18n_es_generic,
    'es_PR.UTF-8': i18n_es_generic,
    'es_US.UTF-8': i18n_es_generic,
    'es_UY.UTF-8': i18n_es_generic,
    'es_VE.UTF-8': i18n_es_generic,
    'ca_ES.UTF-8': i18n_ca_generic,
    'ca_AD.UTF-8': i18n_ca_generic,
    'ca_FR.UTF-8': i18n_ca_generic,
    'pt_BR.UTF-8': i18n_pt_br_generic,
    'da_DK.UTF-8': i18n_generic,
    'ar_AE.UTF-8': i18n_ar_generic,
    'ar_BH.UTF-8': i18n_ar_generic,
    'ar_DZ.UTF-8': i18n_ar_generic,
    'ar_EG.UTF-8': i18n_ar_generic,
    'ar_IN': i18n_ar_generic,
    'ar_IQ.UTF-8': i18n_ar_generic,
    'ar_JO.UTF-8': i18n_ar_generic,
    'ar_KW.UTF-8': i18n_ar_generic,
    'ar_LB.UTF-8': i18n_ar_generic,
    'ar_LY.UTF-8': i18n_ar_generic,
    'ar_MA.UTF-8': i18n_ar_generic,
    'ar_OM.UTF-8': i18n_ar_generic,
    'ar_QA.UTF-8': i18n_ar_generic,
    'ar_SA.UTF-8': i18n_ar_generic,
    'ar_SD.UTF-8': i18n_ar_generic,
    'ar_SY.UTF-8': i18n_ar_generic,
    'ar_TN.UTF-8': i18n_ar_generic,
    'ar_YE.UTF-8': i18n_ar_generic,
    'hr_HR.UTF-8': i18n_hr_HR,
    'ro_RO.UTF-8': i18n_ro_generic,
    'ru_RU.UTF-8': i18n_ru_generic,
    'pl_PL.UTF-8': i18n_pl_generic,
    'nb_NO.UTF-8': i18n_generic,
    'nn_NO.UTF-8': i18n_generic,
    'tr_TR.UTF-8': i18n_tr_generic,
    'ast_ES.UTF-8': i18n_ast_generic,
    'sk_SK.UTF-8': i18n_generic,
    'be_BY.UTF-8': i18n_be_generic,
    'fa_IR.UTF-8': i18n_fa_generic,
    'sq_AL.UTF-8': i18n_al_generic,
}

def install_translation(locale_name, locale_path):
    """Return a new i18n class instance, depending on the specified
    locale name (eg. "fr_FR.UTF-8"). See output of "locale -a" for a
    list of system-supported locale names. When none matching, default
    class is i18n_generic"""
    language_class = language_class_map.get(locale_name, i18n_generic)
    return language_class(locale_name, locale_path)
