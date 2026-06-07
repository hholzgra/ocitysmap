import re
from . import i18n, _install_language

class i18n_ca_generic(i18n):

    APPELLATIONS = [ # Catalan
                     "Autopista", "Autovia", "Avinguda",
                     "Baixada", "Barranc", "Barri", "Barriada",
                     "Biblioteca", "Carrer", "Carreró", "Carretera",
                     "Cantonada", "Església", "Estació", "Hospital",
                     "Monestir", "Monument", "Museu", "Passatge",
                     "Passeig", "Plaça", "Planta", "Polígon",
                     "Pujada", "Rambla", "Ronda", "Travessera",
                     "Travessia", "Torrent", "Urbanització", "Via",

                     # Spanish (being distinct from Catalan)
                     "Acceso", "Acequia", "Alameda", "Alquería",
                     "Andador", "Angosta", "Apartamentos", "Apeadero",
                     "Arboleda", "Arrabal", "Arroyo", "Autovía",
                     "Avenida", "Bajada", "Balneario", "Banda",
                     "Barranco", "Barranquil", "Barrio", "Bloque",
                     "Brazal", "Bulevar", "Calle", "Calleja",
                     "Callejón", "Callejuela", "Callizo", "Calzada",
                     "Camino", "Camping", "Cantera", "Cantina",
                     "Cantón", "Carrera", "Carrero", "Carreterín",
                     "Carretil", "Carril", "Caserío", "Chalet",
                     "Cinturón", "Circunvalación", "Cobertizo",
                     "Colonia", "Complejo", "Conjunto", "Convento",
                     "Cooperativa", "Corral", "Corralillo", "Corredor",
                     "Cortijo", "Costanilla", "Costera", "Cuadra",
                     "Cuesta", "Dehesa", "Demarcación", "Diagonal",
                     "Diseminado", "Edificio", "Empresa", "Entrada",
                     "Escalera", "Escalinata", "Espalda", "Estación",
                     "Estrada", "Explanada", "Extramuros", "Extrarradio",
                     "Fábrica", "Galería", "Glorieta", "Gran Vía",
                     "Granja", "Hipódromo", "Jardín", "Ladera",
                     "Llanura", "Malecón", "Mercado", "Mirador",
                     "Monasterio", "Muelle", "Núcleo", "Palacio",
                     "Pantano", "Paraje", "Parque", "Particular",
                     "Partida", "Pasadizo", "Pasaje", "Paseo",
                     "Paseo marítimo", "Pasillo", "Plaza", "Plazoleta",
                     "Plazuela", "Poblado", "Polígono", "Polígono industrial",
                     "Portal", "Pórtico", "Portillo", "Prazuela",
                     "Prolongación", "Pueblo", "Puente", "Puerta",
                     "Puerto", "Punto kilométrico", "Rampla",
                     "Residencial", "Ribera", "Rincón", "Rinconada",
                     "Sanatorio", "Santuario", "Sector", "Sendera",
                     "Sendero", "Subida", "Torrente", "Tránsito",
                     "Transversal", "Trasera", "Travesía", "Urbanización",
                     "Vecindario", "Vereda", "Viaducto", "Viviendas",

                     # French (being distinct from Catalan and Spanish)
                     "Accès", "Allée", "Allées", "Autoroute", "Avenue", "Barrage",
                     "Boulevard", "Carrefour", "Chaussée", "Chemin",
                     "Cheminement", "Cale", "Cales", "Cavée", "Cité",
                     "Clos", "Coin", "Côte", "Cour", "Cours", "Descente",
                     "Degré", "Escalier",
                     "Escaliers", "Esplanade", "Funiculaire",
                     "Giratoire", "Hameau", "Impasse", "Jardin",
                     "Jardins", "Liaison", "Mail", "Montée", "Môle",
                     "Parc", "Passage", "Passerelle", "Passerelles",
                     "Place", "Placette", "Pont", "Promenade",
                     "Petite Avenue", "Petite Rue", "Quai",
                     "Rampe", "Rang", "Résidence", "Rond-Point",
                     "Route forestière", "Route", "Rue", "Ruelle",
                     "Square", "Sente", "Sentier", "Sentiers", "Terre-Plein",
                     "Télécabine", "Traboule", "Traverse", "Tunnel",
                     "Venelle", "Villa", "Virage"
                   ]

    DETERMINANTS = [ " dels", " de los",
                     " de les", " de ses", " de las",
                     " de la", " de sa", " de na",
                     " del", " de lo", " d'en",
                     " d'", " de l'", " de s'", " de n'",
                     " de", " du", "" ]

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
    N_ACCENT = re.compile(r"[ñ]", re.IGNORECASE | re.UNICODE)
    C_ACCENT = re.compile(r"[ç]", re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        s = self.E_ACCENT.sub("e", s)
        s = self.I_ACCENT.sub("i", s)
        s = self.A_ACCENT.sub("a", s)
        s = self.O_ACCENT.sub("o", s)
        s = self.U_ACCENT.sub("u", s)
        s = self.N_ACCENT.sub("n", s)
        s = self.C_ACCENT.sub("c", s)
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
        return 'Català (%s)' % self.language
