"""
University configuration settings and mappings.
Ported from legacy settings.yaml.
"""

UNIVERSITY_SETTINGS = {
    "name": "University of Twente",
    "abbreviation": "UT",
}

# Key: Department Name (from raw data), Value: Faculty Abbreviation
DEPARTMENT_MAPPING = {
    # Manual overrides
    "Master Risicomanagement": "BMS",
    "Master Public Management": "BMS",
    "BMS: Behavioural, Management and Social Sciences": "BMS",
    "EEMCS: Electrical Engineering, Mathematics and Computer Science": "EEMCS",
    "ET: Engineering Technology": "ET",
}

FACULTIES = [
    {
        "name": "Faculty of Behavioural, Management and Social Sciences",
        "abbreviation": "BMS",
        "programmes": [
            ("Communication Science", "B-COM"),
            ("European Studies", "M-ES"),
            ("Psychology", "M-PSY"),
            ("Behavioural, Management and Social Sciences", "O-BMS"),
            ("Industrial Engineering and Management", "M-IEM"),
            ("Environmental and Energy Management", "M-EEM"),
            ("Psychology", "B-PSY"),
            ("Educational Science and Technology", "M-EST"),
            ("Philosophy of Science, Technology and Society", "M-PSTS"),
            ("Master Risicomanagement", "M-RIS"),
            ("Business Administration", "M-BA"),
            ("International Business Administration", "B-IBA"),
            ("Management, Society and Technology", "B-MST"),
            ("Industrial Engineering and Management", "B-IEM"),
            ("Communication Science", "M-COM"),
            ("Master Educatie in de Bètawetenschappen", "M-EB"),
            ("Public Administration", "M-PA"),
            ("Master Public Management", "M-PUB"),
        ]
    },
    {
        "name": "Faculty of Engineering Technology",
        "abbreviation": "ET",
        "programmes": [
            ("Mechanical Engineering", "M-ME"),
            ("Civil Engineering and Management", "M-CEM"),
            ("Industrial Design Engineering", "M-IDE"),
            ("Construction Management and Engineering", "M-CME"),
            ("Civil Engineering", "B-CE"),
            ("Industrial Design Engineering", "B-IDE"),
            ("Mechanical Engineering", "B-ME"),
            ("Mechanical Engineering - Amsterdam (VU-UT)", "B-ME-VU"),
            ("ET niet-OSIRIS", "O-ET-NOS"),
            ("Sustainable Energy Technology", "M-SET"),
            ("Engineering Technology", "O-ET"),
        ]
    },
    {
        "name": "Faculty of Electrical Engineering, Mathematics and Computer Science",
        "abbreviation": "EEMCS",
        "programmes": [
            ("Electrical Engineering", "M-EE"),
            ("Computer Science", "M-CS"),
            ("Interaction Technology", "M-ITECH"),
            ("Robotics", "M-ROB"),
            ("Business Information Technology", "M-BIT"),
            ("Applied Mathematics", "M-AM"),
            ("Applied Mathematics", "B-AM"),
            ("Embedded Systems", "M-EMSYS"),
            ("Electrical Engineering", "B-EE"),
            ("Electrical Engineering, Mathematics and Computer Science", "O-EEMCS"),
            ("Technical Computer Science", "B-TCS"),
            ("Creative Technology", "B-CREA"),
            ("Business Information Technology", "B-BIT"),
            ("Creative Technology - Amsterdam (VU-UT)", "B-CREA-VU"),
            ("2024-ELSE Aspects MSc Robotics", "M-ROB-ELSE"),
            ("EEMCS niet-OSIRIS", "O-EEMCS-NOS"),
        ]
    },
    {
        "name": "Faculty of Science and Technology",
        "abbreviation": "TNW",
        "programmes": [
            ("Chemical Engineering", "B-CSE"),
            ("Chemical Science & Engineering", "M-CSE"),
            ("Applied Physics", "M-AP"),
            ("Technische Natuurkunde", "B-TN"),
            ("Advanced Technology", "B-AT"),
            ("Nanotechnology", "M-NT"),
            ("Biomedische Technologie", "B-BMT"),
            ("Biomedical Engineering", "M-BME"),
            ("Gezondheidswetenschappen", "B-GZW"),
            ("Health Sciences", "M-HS"),
            ("Technische Geneeskunde", "B-TG"),
            ("Technical Medicine", "M-TM"),
        ]
    },
    {
        "name": "Faculty of Geo-Information Science and Earth Observation",
        "abbreviation": "ITC",
        "programmes": [
            ("Geo-information Science and Earth Observation", "M-GEO-WO"),
            ("Technology and Liberal Arts & Sciences", "B-ATLAS"),
            ("Spatial Engineering", "M-SE"),
            ("Humanitarian Engineering", "M-HE"),
        ]
    },
    {
        "name": "Unmapped",
        "abbreviation": "UNM",
        "programmes": [
            ("Testcourses", "O-TEST"),
        ]
    }
]

# Populate DEPARTMENT_MAPPING from FACULTIES list
for faculty in FACULTIES:
    abbr = faculty["abbreviation"]
    for prog_name, prog_abbr in faculty["programmes"]:
        DEPARTMENT_MAPPING[prog_name] = abbr
        # Also map the abbreviation itself if it appears as department?
        # Usually legacy logic mapped Name -> Faculty.
        # But sometimes input has abbreviation? Safe to add.
        DEPARTMENT_MAPPING[prog_abbr] = abbr
