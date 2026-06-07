import re
import gettext
from . import i18n, _install_language

class i18n_hr_HR(i18n):
    # for upper_unaccent_string
    C_ACCENT = re.compile(r"[ćč]", re.IGNORECASE | re.UNICODE)
    D_ACCENT = re.compile(r"đ|dž", re.IGNORECASE | re.UNICODE)
    N_ACCENT = re.compile(r"nj", re.IGNORECASE | re.UNICODE)
    L_ACCENT = re.compile(r"lj", re.IGNORECASE | re.UNICODE)
    S_ACCENT = re.compile(r"š", re.IGNORECASE | re.UNICODE)
    Z_ACCENT = re.compile(r"ž", re.IGNORECASE | re.UNICODE)

    def upper_unaccent_string(self, s):
        s = self.C_ACCENT.sub("c", s)
        s = self.D_ACCENT.sub("d", s)
        s = self.N_ACCENT.sub("n", s)
        s = self.L_ACCENT.sub("l", s)
        s = self.S_ACCENT.sub("s", s)
        s = self.Z_ACCENT.sub("z", s)
        return s.upper()

    def __init__(self, language, locale_path):
        """Install the _() function for the chosen locale other
           object initialisation"""
        self.language = str(language) # FIXME: why do we have unicode here?
        _install_language(language, locale_path)

    def language_code(self):
        """returns the language code of the specific language
           supported, e.g. fr_FR.UTF-8"""
        return self.language

    def user_readable_street(self, name):
        """ transforms a street name into a suitable form for
            the map index, e.g. Paris (Rue de) for French"""
        return name

    # FIXME: only first letter does not work for Croatian digraphs (dž, lj, nj)
    def first_letter_equal(self, a, b):
        """returns True if the letters a and b are equal in the map index,
           e.g. É and E are equals in French map index"""
        return self.upper_unaccent_string(a) == self.upper_unaccent_string(b)


    def language_desc(self):
        return 'Magyarország (%s)' % self.language
