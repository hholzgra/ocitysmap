import re
import gettext
from . import i18n, _install_language

class i18n_fr_generic(i18n):
    APPELLATIONS = [ u"Accès", u"Allée", u"Allées", u"Autoroute", u"Avenue",
                     u"Avenues", u"Barrage",
                     u"Boulevard", u"Carrefour", u"Chaussée", u"Chemin",
                     u"Chemin rural",
                     u"Cheminement", u"Cale", u"Cales", u"Cavée", u"Cité",
                     u"Clos", u"Coin", u"Côte", u"Cour", u"Cours", u"Descente",
                     u"Degré", u"Escalier",
                     u"Escaliers", u"Esplanade", u"Funiculaire",
                     u"Giratoire", u"Hameau", u"Impasse", u"Jardin",
                     u"Jardins", u"Liaison", u"Lotissement", u"Mail",
                     u"Montée", u"Môle",
                     u"Parc", u"Passage", u"Passerelle", u"Passerelles",
                     u"Place", u"Placette", u"Pont", u"Promenade",
                     u"Petite Avenue", u"Petite Rue", u"Quai",
                     u"Rampe", u"Rang", u"Résidence", u"Rond-Point",
                     u"Route forestière", u"Route", u"Rue", u"Ruelle",
                     u"Square", u"Sente", u"Sentier", u"Sentiers", u"Terre-Plein",
                     u"Télécabine", u"Traboule", u"Traverse", u"Tunnel",
                     u"Venelle", u"Villa", u"Virage"
                    ]
    DETERMINANTS = [ u" des", u" du", u" de la", u" de l'",
                     u" de", u" d'", u" aux", u""
                    ]

    SPACE_REDUCE = re.compile(r"\s+")
    PREFIX_REGEXP = re.compile(r"^(?P<prefix>(%s)(%s)?)\s?\b(?P<name>.+)" %
                                    ("|".join(APPELLATIONS),
                                     "|".join(DETERMINANTS)), re.IGNORECASE
                                                                 | re.UNICODE)

    # for IndexPageGenerator.upper_unaccent_string
    E_ACCENT = re.compile(r"[éèêëẽ]", re.IGNORECASE | re.UNICODE)
    I_ACCENT = re.compile(r"[íìîïĩ]", re.IGNORECASE | re.UNICODE)
    A_ACCENT = re.compile(r"[áàâäãæ]", re.IGNORECASE | re.UNICODE)
    O_ACCENT = re.compile(r"[óòôöõœ]", re.IGNORECASE | re.UNICODE)
    U_ACCENT = re.compile(r"[úùûüũ]", re.IGNORECASE | re.UNICODE)
    Y_ACCENT = re.compile(r"[ÿ]", re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        s = self.E_ACCENT.sub("e", s)
        s = self.I_ACCENT.sub("i", s)
        s = self.A_ACCENT.sub("a", s)
        s = self.O_ACCENT.sub("o", s)
        s = self.U_ACCENT.sub("u", s)
        s = self.Y_ACCENT.sub("y", s)
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


    def language_desc(self):
        return 'Français (%s)' % self.language
