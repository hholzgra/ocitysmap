# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import re
from . import i18n, _install_language

class i18n_ar_generic(i18n):
    APPELLATIONS = [ "شارع", "طريق", "زقاق", "نهج", "جادة",
                     "ممر", "حارة",
                     "كوبري", "كوبرى", "جسر", "مطلع", "منزل",
                     "مفرق", "ملف", "تقاطع",
                     "ساحل",
                     "ميدان", "ساحة", "دوار" ]

    DETERMINANTS = [ " ال", "" ]

    SPACE_REDUCE = re.compile(r"\s+")
    PREFIX_REGEXP = re.compile(r"^(?P<prefix>(%s)(%s)?)\s?(?P<name>.+)" %
                               ("|".join(APPELLATIONS),
                                "|".join(DETERMINANTS)), re.IGNORECASE
                               | re.UNICODE)

    # for IndexPageGenerator.upper_unaccent_string
    A_ACCENT = re.compile(r"[اإآ]", re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        s = self.A_ACCENT.sub("أ", s)
        return s.upper()

    def language_code(self):
        return self.language

    def user_readable_street(self, name):
        name = name.strip()
        name = self.SPACE_REDUCE.sub(" ", name)
        name = self.PREFIX_REGEXP.sub(r"\g<name> (\g<prefix>)", name)
        return name

    def first_letter_equal(self, a, b):
        return self.upper_unaccent_string(a) == self.upper_unaccent_string(b)

    def isrtl(self):
        return True

    def language_desc(self):
        return 'العربية (%s)' % self.language
