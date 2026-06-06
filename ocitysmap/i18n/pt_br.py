import re, gettext
from . import i18n, _install_language

class i18n_pt_br_generic(i18n):
    APPELLATIONS = [ u"Aeroporto", u"Aer.", u"Alameda", u"Al.", u"Apartamento", u"Ap.",
                     u"Área", u"Avenida", u"Av.", u"Beco", u"Bc.", u"Bloco", u"Bl.",
                     u"Caminho", u"Cam.", u"Campo", u"Chácara", u"Colônia",
                     u"Condomínio", u"Conjunto", u"Cj.", u"Distrito", u"Esplanada", u"Espl.",
                     u"Estação", u"Est.", u"Estrada", u"Estr.", u"Favela", u"Fazenda",
                     u"Feira", u"Jardim", u"Jd.", u"Ladeira", u"Lago",
                     u"Lagoa", u"Largo", u"Loteamento", u"Morro", u"Núcleo",
                     u"Parque", u"Pq.", u"Passarela", u"Pátio", u"Praça", u"Pç.", u"Quadra",
                     u"Recanto", u"Residencial", u"Resid.", u"Rua", u"R.",
                     u"Setor", u"Sítio", u"Travessa", u"Tv.", u"Trecho", u"Trevo",
                     u"Vale", u"Vereda", u"Via", u"V.", u"Viaduto", u"Viela",
                     u"Vila", u"Vl." ]
    DETERMINANTS = [ u" do", u" da", u" dos", u" das", u"" ]
    SPACE_REDUCE = re.compile(r"\s+")
    PREFIX_REGEXP = re.compile(r"^(?P<prefix>(%s)(%s)?)\s?\b(?P<name>.+)" %
                                    ("|".join(APPELLATIONS),
                                     "|".join(DETERMINANTS)), re.IGNORECASE
                                                                 | re.UNICODE)

    # for IndexPageGenerator.upper_unaccent_string
    E_ACCENT = re.compile(r"[éèêëẽ]", re.IGNORECASE | re.UNICODE)
    I_ACCENT = re.compile(r"[íìîïĩ]", re.IGNORECASE | re.UNICODE)
    A_ACCENT = re.compile(r"[áàâäã]", re.IGNORECASE | re.UNICODE)
    O_ACCENT = re.compile(r"[óòôöõ]", re.IGNORECASE | re.UNICODE)
    U_ACCENT = re.compile(r"[úùûüũ]", re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        s = self.E_ACCENT.sub("e", s)
        s = self.I_ACCENT.sub("i", s)
        s = self.A_ACCENT.sub("a", s)
        s = self.O_ACCENT.sub("o", s)
        s = self.U_ACCENT.sub("u", s)
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
        return 'Português do Brasil (%s)' % self.language

