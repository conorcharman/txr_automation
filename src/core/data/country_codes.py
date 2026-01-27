"""
Country Codes Reference Data
=============================

Embedded country code data with ISO Alpha-2, Alpha-3 codes and EEA status.
Provides singleton manager for efficient lookups without external CSV dependencies.

This is the canonical location for country codes.
For backward compatibility, this is also re-exported from:
- accuracy_testing.core.country_codes

Data source: ISO 3166-1 country codes (249 countries)
Last updated: January 2026
"""

from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    """Immutable country data structure."""
    
    name: str
    alpha2: str
    alpha3: str
    is_eea: bool
    
    def __str__(self) -> str:
        return f"{self.name} ({self.alpha2})"


# Complete country code dataset - 249 countries
COUNTRIES = [
    Country("Afghanistan", "AF", "AFG", False),
    Country("Albania", "AL", "ALB", False),
    Country("Algeria", "DZ", "DZA", False),
    Country("American Samoa", "AS", "ASM", False),
    Country("Andorra", "AD", "AND", False),
    Country("Angola", "AO", "AGO", False),
    Country("Anguilla", "AI", "AIA", False),
    Country("Antarctica", "AQ", "ATA", False),
    Country("Antigua and Barbuda", "AG", "ATG", False),
    Country("Argentina", "AR", "ARG", False),
    Country("Armenia", "AM", "ARM", False),
    Country("Aruba", "AW", "ABW", False),
    Country("Australia", "AU", "AUS", False),
    Country("Austria", "AT", "AUT", True),
    Country("Azerbaijan", "AZ", "AZE", False),
    Country("Bahamas (the)", "BS", "BHS", False),
    Country("Bahrain", "BH", "BHR", False),
    Country("Bangladesh", "BD", "BGD", False),
    Country("Barbados", "BB", "BRB", False),
    Country("Belarus", "BY", "BLR", False),
    Country("Belgium", "BE", "BEL", True),
    Country("Belize", "BZ", "BLZ", False),
    Country("Benin", "BJ", "BEN", False),
    Country("Bermuda", "BM", "BMU", False),
    Country("Bhutan", "BT", "BTN", False),
    Country("Bolivia (Plurinational State of)", "BO", "BOL", False),
    Country("Bonaire, Sint Eustatius and Saba", "BQ", "BES", False),
    Country("Bosnia and Herzegovina", "BA", "BIH", False),
    Country("Botswana", "BW", "BWA", False),
    Country("Bouvet Island", "BV", "BVT", False),
    Country("Brazil", "BR", "BRA", False),
    Country("British Indian Ocean Territory (the)", "IO", "IOT", False),
    Country("Brunei Darussalam", "BN", "BRN", False),
    Country("Bulgaria", "BG", "BGR", True),
    Country("Burkina Faso", "BF", "BFA", False),
    Country("Burundi", "BI", "BDI", False),
    Country("Cabo Verde", "CV", "CPV", False),
    Country("Cambodia", "KH", "KHM", False),
    Country("Cameroon", "CM", "CMR", False),
    Country("Canada", "CA", "CAN", False),
    Country("Cayman Islands (the)", "KY", "CYM", False),
    Country("Central African Republic (the)", "CF", "CAF", False),
    Country("Chad", "TD", "TCD", False),
    Country("Chile", "CL", "CHL", False),
    Country("China", "CN", "CHN", False),
    Country("Christmas Island", "CX", "CXR", False),
    Country("Cocos (Keeling) Islands (the)", "CC", "CCK", False),
    Country("Colombia", "CO", "COL", False),
    Country("Comoros (the)", "KM", "COM", False),
    Country("Congo (the Democratic Republic of the)", "CD", "COD", False),
    Country("Congo (the)", "CG", "COG", False),
    Country("Cook Islands (the)", "CK", "COK", False),
    Country("Costa Rica", "CR", "CRI", False),
    Country("Croatia", "HR", "HRV", True),
    Country("Cuba", "CU", "CUB", False),
    Country("Curaçao", "CW", "CUW", False),
    Country("Cyprus", "CY", "CYP", True),
    Country("Czechia", "CZ", "CZE", True),
    Country("Côte d'Ivoire", "CI", "CIV", False),
    Country("Denmark", "DK", "DNK", True),
    Country("Djibouti", "DJ", "DJI", False),
    Country("Dominica", "DM", "DMA", False),
    Country("Dominican Republic (the)", "DO", "DOM", False),
    Country("Ecuador", "EC", "ECU", False),
    Country("Egypt", "EG", "EGY", False),
    Country("El Salvador", "SV", "SLV", False),
    Country("Equatorial Guinea", "GQ", "GNQ", False),
    Country("Eritrea", "ER", "ERI", False),
    Country("Estonia", "EE", "EST", True),
    Country("Eswatini", "SZ", "SWZ", False),
    Country("Ethiopia", "ET", "ETH", False),
    Country("Falkland Islands (the) [Malvinas]", "FK", "FLK", False),
    Country("Faroe Islands (the)", "FO", "FRO", False),
    Country("Fiji", "FJ", "FJI", False),
    Country("Finland", "FI", "FIN", True),
    Country("France", "FR", "FRA", True),
    Country("French Guiana", "GF", "GUF", False),
    Country("French Polynesia", "PF", "PYF", False),
    Country("French Southern Territories (the)", "TF", "ATF", False),
    Country("Gabon", "GA", "GAB", False),
    Country("Gambia (the)", "GM", "GMB", False),
    Country("Georgia", "GE", "GEO", False),
    Country("Germany", "DE", "DEU", True),
    Country("Ghana", "GH", "GHA", False),
    Country("Gibraltar", "GI", "GIB", False),
    Country("Greece", "GR", "GRC", True),
    Country("Greenland", "GL", "GRL", False),
    Country("Grenada", "GD", "GRD", False),
    Country("Guadeloupe", "GP", "GLP", False),
    Country("Guam", "GU", "GUM", False),
    Country("Guatemala", "GT", "GTM", False),
    Country("Guernsey", "GG", "GGY", False),
    Country("Guinea", "GN", "GIN", False),
    Country("Guinea-Bissau", "GW", "GNB", False),
    Country("Guyana", "GY", "GUY", False),
    Country("Haiti", "HT", "HTI", False),
    Country("Heard Island and McDonald Islands", "HM", "HMD", False),
    Country("Holy See (the)", "VA", "VAT", False),
    Country("Honduras", "HN", "HND", False),
    Country("Hong Kong", "HK", "HKG", False),
    Country("Hungary", "HU", "HUN", True),
    Country("Iceland", "IS", "ISL", True),
    Country("India", "IN", "IND", False),
    Country("Indonesia", "ID", "IDN", False),
    Country("Iran (Islamic Republic of)", "IR", "IRN", False),
    Country("Iraq", "IQ", "IRQ", False),
    Country("Ireland", "IE", "IRL", True),
    Country("Isle of Man", "IM", "IMN", False),
    Country("Israel", "IL", "ISR", False),
    Country("Italy", "IT", "ITA", True),
    Country("Jamaica", "JM", "JAM", False),
    Country("Japan", "JP", "JPN", False),
    Country("Jersey", "JE", "JEY", False),
    Country("Jordan", "JO", "JOR", False),
    Country("Kazakhstan", "KZ", "KAZ", False),
    Country("Kenya", "KE", "KEN", False),
    Country("Kiribati", "KI", "KIR", False),
    Country("Korea (the Democratic People's Republic of)", "KP", "PRK", False),
    Country("Korea (the Republic of)", "KR", "KOR", False),
    Country("Kuwait", "KW", "KWT", False),
    Country("Kyrgyzstan", "KG", "KGZ", False),
    Country("Lao People's Democratic Republic (the)", "LA", "LAO", False),
    Country("Latvia", "LV", "LVA", True),
    Country("Lebanon", "LB", "LBN", False),
    Country("Lesotho", "LS", "LSO", False),
    Country("Liberia", "LR", "LBR", False),
    Country("Libya", "LY", "LBY", False),
    Country("Liechtenstein", "LI", "LIE", True),
    Country("Lithuania", "LT", "LTU", True),
    Country("Luxembourg", "LU", "LUX", True),
    Country("Macao", "MO", "MAC", False),
    Country("Madagascar", "MG", "MDG", False),
    Country("Malawi", "MW", "MWI", False),
    Country("Malaysia", "MY", "MYS", False),
    Country("Maldives", "MV", "MDV", False),
    Country("Mali", "ML", "MLI", False),
    Country("Malta", "MT", "MLT", True),
    Country("Marshall Islands (the)", "MH", "MHL", False),
    Country("Martinique", "MQ", "MTQ", False),
    Country("Mauritania", "MR", "MRT", False),
    Country("Mauritius", "MU", "MUS", False),
    Country("Mayotte", "YT", "MYT", False),
    Country("Mexico", "MX", "MEX", False),
    Country("Micronesia (Federated States of)", "FM", "FSM", False),
    Country("Moldova (the Republic of)", "MD", "MDA", False),
    Country("Monaco", "MC", "MCO", False),
    Country("Mongolia", "MN", "MNG", False),
    Country("Montenegro", "ME", "MNE", False),
    Country("Montserrat", "MS", "MSR", False),
    Country("Morocco", "MA", "MAR", False),
    Country("Mozambique", "MZ", "MOZ", False),
    Country("Myanmar", "MM", "MMR", False),
    Country("Namibia", "NA", "NAM", False),
    Country("Nauru", "NR", "NRU", False),
    Country("Nepal", "NP", "NPL", False),
    Country("Netherlands (the)", "NL", "NLD", True),
    Country("New Caledonia", "NC", "NCL", False),
    Country("New Zealand", "NZ", "NZL", False),
    Country("Nicaragua", "NI", "NIC", False),
    Country("Niger (the)", "NE", "NER", False),
    Country("Nigeria", "NG", "NGA", False),
    Country("Niue", "NU", "NIU", False),
    Country("Norfolk Island", "NF", "NFK", False),
    Country("Northern Mariana Islands (the)", "MP", "MNP", False),
    Country("Norway", "NO", "NOR", True),
    Country("Oman", "OM", "OMN", False),
    Country("Pakistan", "PK", "PAK", False),
    Country("Palau", "PW", "PLW", False),
    Country("Palestine, State of", "PS", "PSE", False),
    Country("Panama", "PA", "PAN", False),
    Country("Papua New Guinea", "PG", "PNG", False),
    Country("Paraguay", "PY", "PRY", False),
    Country("Peru", "PE", "PER", False),
    Country("Philippines (the)", "PH", "PHL", False),
    Country("Pitcairn", "PN", "PCN", False),
    Country("Poland", "PL", "POL", True),
    Country("Portugal", "PT", "PRT", True),
    Country("Puerto Rico", "PR", "PRI", False),
    Country("Qatar", "QA", "QAT", False),
    Country("Republic of North Macedonia", "MK", "MKD", False),
    Country("Romania", "RO", "ROU", True),
    Country("Russian Federation (the)", "RU", "RUS", False),
    Country("Rwanda", "RW", "RWA", False),
    Country("Réunion", "RE", "REU", False),
    Country("Saint Barthélemy", "BL", "BLM", False),
    Country("Saint Helena, Ascension and Tristan da Cunha", "SH", "SHN", False),
    Country("Saint Kitts and Nevis", "KN", "KNA", False),
    Country("Saint Lucia", "LC", "LCA", False),
    Country("Saint Martin (French part)", "MF", "MAF", False),
    Country("Saint Pierre and Miquelon", "PM", "SPM", False),
    Country("Saint Vincent and the Grenadines", "VC", "VCT", False),
    Country("Samoa", "WS", "WSM", False),
    Country("San Marino", "SM", "SMR", False),
    Country("Sao Tome and Principe", "ST", "STP", False),
    Country("Saudi Arabia", "SA", "SAU", False),
    Country("Senegal", "SN", "SEN", False),
    Country("Serbia", "RS", "SRB", False),
    Country("Seychelles", "SC", "SYC", False),
    Country("Sierra Leone", "SL", "SLE", False),
    Country("Singapore", "SG", "SGP", False),
    Country("Sint Maarten (Dutch part)", "SX", "SXM", False),
    Country("Slovakia", "SK", "SVK", True),
    Country("Slovenia", "SI", "SVN", True),
    Country("Solomon Islands", "SB", "SLB", False),
    Country("Somalia", "SO", "SOM", False),
    Country("South Africa", "ZA", "ZAF", False),
    Country("South Georgia and the South Sandwich Islands", "GS", "SGS", False),
    Country("South Sudan", "SS", "SSD", False),
    Country("Spain", "ES", "ESP", True),
    Country("Sri Lanka", "LK", "LKA", False),
    Country("Sudan (the)", "SD", "SDN", False),
    Country("Suriname", "SR", "SUR", False),
    Country("Svalbard and Jan Mayen", "SJ", "SJM", False),
    Country("Sweden", "SE", "SWE", True),
    Country("Switzerland", "CH", "CHE", False),
    Country("Syrian Arab Republic", "SY", "SYR", False),
    Country("Taiwan (Province of China)", "TW", "TWN", False),
    Country("Tajikistan", "TJ", "TJK", False),
    Country("Tanzania, United Republic of", "TZ", "TZA", False),
    Country("Thailand", "TH", "THA", False),
    Country("Timor-Leste", "TL", "TLS", False),
    Country("Togo", "TG", "TGO", False),
    Country("Tokelau", "TK", "TKL", False),
    Country("Tonga", "TO", "TON", False),
    Country("Trinidad and Tobago", "TT", "TTO", False),
    Country("Tunisia", "TN", "TUN", False),
    Country("Turkey", "TR", "TUR", False),
    Country("Turkmenistan", "TM", "TKM", False),
    Country("Turks and Caicos Islands (the)", "TC", "TCA", False),
    Country("Tuvalu", "TV", "TUV", False),
    Country("Uganda", "UG", "UGA", False),
    Country("Ukraine", "UA", "UKR", False),
    Country("United Arab Emirates (the)", "AE", "ARE", False),
    Country("United Kingdom of Great Britain and Northern Ireland (the)", "GB", "GBR", True),
    Country("United States Minor Outlying Islands (the)", "UM", "UMI", False),
    Country("United States of America (the)", "US", "USA", False),
    Country("Uruguay", "UY", "URY", False),
    Country("Uzbekistan", "UZ", "UZB", False),
    Country("Vanuatu", "VU", "VUT", False),
    Country("Venezuela (Bolivarian Republic of)", "VE", "VEN", False),
    Country("Viet Nam", "VN", "VNM", False),
    Country("Virgin Islands (British)", "VG", "VGB", False),
    Country("Virgin Islands (U.S.)", "VI", "VIR", False),
    Country("Wallis and Futuna", "WF", "WLF", False),
    Country("Western Sahara", "EH", "ESH", False),
    Country("Yemen", "YE", "YEM", False),
    Country("Zambia", "ZM", "ZMB", False),
    Country("Zimbabwe", "ZW", "ZWE", False),
    Country("Åland Islands", "AX", "ALA", False),
]


class CountryDataManager:
    """
    Singleton manager for country code reference data.
    Provides efficient O(1) lookups by Alpha-2 or Alpha-3 codes.
    
    Usage:
        manager = CountryDataManager()
        country = manager.get_by_alpha2("GB")
        is_eea = manager.is_eea("DE")
        all_eea = manager.get_eea_countries()
    """
    
    _instance: Optional['CountryDataManager'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'CountryDataManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize lookup dictionaries (only once)."""
        if CountryDataManager._initialized:
            return
        
        # Build lookup dictionaries for O(1) access
        self._by_alpha2: Dict[str, Country] = {}
        self._by_alpha3: Dict[str, Country] = {}
        self._by_name: Dict[str, Country] = {}
        
        for country in COUNTRIES:
            self._by_alpha2[country.alpha2.upper()] = country
            self._by_alpha3[country.alpha3.upper()] = country
            self._by_name[country.name.upper()] = country
        
        CountryDataManager._initialized = True
    
    def get_by_alpha2(self, code: str) -> Optional[Country]:
        """Get country by ISO Alpha-2 code."""
        return self._by_alpha2.get(code.upper())
    
    def get_by_alpha3(self, code: str) -> Optional[Country]:
        """Get country by ISO Alpha-3 code."""
        return self._by_alpha3.get(code.upper())
    
    def get_by_name(self, name: str) -> Optional[Country]:
        """Get country by name (case-insensitive)."""
        return self._by_name.get(name.upper())
    
    def is_eea(self, code: str) -> bool:
        """Check if a country is in the European Economic Area."""
        country = self.get_by_alpha2(code) or self.get_by_alpha3(code)
        return country.is_eea if country else False
    
    def get_eea_countries(self) -> List[Country]:
        """Get list of all EEA countries."""
        return [c for c in COUNTRIES if c.is_eea]
    
    def get_all_countries(self) -> List[Country]:
        """Get list of all countries."""
        return COUNTRIES.copy()
    
    def validate_code(self, code: str) -> bool:
        """Validate if a code exists (Alpha-2 or Alpha-3)."""
        return (code.upper() in self._by_alpha2 or 
                code.upper() in self._by_alpha3)
    
    def get_alpha3_from_alpha2(self, alpha2: str) -> Optional[str]:
        """Convert Alpha-2 code to Alpha-3."""
        country = self.get_by_alpha2(alpha2)
        return country.alpha3 if country else None
    
    def get_alpha2_from_alpha3(self, alpha3: str) -> Optional[str]:
        """Convert Alpha-3 code to Alpha-2."""
        country = self.get_by_alpha3(alpha3)
        return country.alpha2 if country else None
    
    @property
    def total_countries(self) -> int:
        """Get total number of countries in dataset."""
        return len(COUNTRIES)
    
    @property
    def eea_count(self) -> int:
        """Get total number of EEA countries."""
        return sum(1 for c in COUNTRIES if c.is_eea)


# Pre-instantiate singleton for convenient imports
country_manager = CountryDataManager()
