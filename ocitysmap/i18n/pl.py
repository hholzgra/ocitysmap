import re
import gettext
from . import i18n, _install_language

class i18n_pl_generic(i18n):

    APPELLATIONS = [ "Dr.", "Doktora", "Ks.", "Księdza",
                     "Generała", "Gen.",
                     "Aleja", "Plac", "Pl.",
                     "Rondo", "rondo", "Profesora",
                     "Prof.",
                     "" ]

    DETERMINANTS = [ r"\s?im.",
                     r"\s?imienia",
                     r"\s?pw.",
                     "" ]

    SPACE_REDUCE = re.compile(r"\s+")
    PREFIX_REGEXP = re.compile(r"^(?P<prefix>(%s)(%s)?)\s?\b(?P<name>.+)" %
                                    ("|".join(APPELLATIONS),
                                     "|".join(DETERMINANTS)),
                                      re.IGNORECASE | re.UNICODE)


    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def language_code(self):
        return self.language

    def user_readable_street(self, name):
        #
        # Make sure name actually contains something,
        # the PREFIX_REGEXP.match fails on zero-length strings
        #
        if len(name) == 0:
            return name

        name = name.strip()
        name = self.SPACE_REDUCE.sub(" ", name)
        matches = self.PREFIX_REGEXP.match(name)
        #
        # If no prefix was captured, that's okay. Don't substitute
        # the name however, "<name> ()" looks silly
        #
        if matches is None:
            return name

        if matches.group('prefix'):
            name = self.PREFIX_REGEXP.sub(r"\g<name>, \g<prefix>", name)
        return name

    def first_letter_equal(self, a, b):
        return a == b


    def language_desc(self):
        return 'Polski (%s)' % self.language
