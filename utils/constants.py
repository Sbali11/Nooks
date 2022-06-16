EPSILON = 0.001
MIN_NUM_MEMS = 3
SAME_HOMOPHILY_FACTORS = {"Gender"}
RANGE_HOMOPHILY_FACTORS = {"Age", "Role", "Number of years in the organization"}
HOMOPHILY_FACTORS = {
    "Age": {"18-25": 0, "26-35": 1, "35-50": 2, ">50": 3},
    "Role": {
        "Professor": 0,
        "PhD Student": 1,
        "Master's Student": 2,
        "Undergrad Student": 3,
        "Summer Research Assistant": 4,
        "Old Company Employee(More than 6 months)": 5,
        "New Employee(Less than 6 months)": 6
    },
    "Gender": {"Male": 0, "Female": 1, "Non-Binary": 2, "Prefer Not to Disclose": 3, "Prefer To Self Describe": 4},
    "Number of years in the organization": {
        "0-1 yrs": 0,
        "1-5 yrs": 1,
        "5-10 yrs": 2,
        ">10 yrs": 3,
    },
}


def get_fibonacci(n):
    # calculate fibonacci series
    i = 0
    j = 1
    fib = []
    fib.append(j)
    for i in range(n - 1):
        new_i = j
        j = i + j
        i = new_i
        fib.append(j)
    return fib


FIBONACCI = get_fibonacci(len(HOMOPHILY_FACTORS))
MAX_NUM_CONNECTIONS = 10
ALL_REACTIONS = [
    "eyes",
    "tiger",
    "speech_balloon",
    "though_balloon",
    "ear",
    "hatching_chick",
    "dolphin",
    "butterfly",
    "pig",
    "cherry_blossom",
    "tulip",
    "candy",
]
ALL_TIMEZONES = {
    "LMT": "W-SU",
    "GMT": "Iceland",
    "EAT": "Indian/Mayotte",
    "PMT": "Europe/Paris",
    "WET": "WET",
    "WEST": "WET",
    "CET": "Portugal",
    "CEST": "Portugal",
    "WAT": "Africa/Windhoek",
    "CAT": "Africa/Windhoek",
    "EET": "W-SU",
    "EEST": "W-SU",
    "SAST": "Africa/Windhoek",
    "CAST": "Africa/Khartoum",
    "MMT": "W-SU",
    "WAST": "Africa/Ndjamena",
    "NST": "US/Aleutian",
    "NWT": "US/Aleutian",
    "NPT": "US/Aleutian",
    "BST": "US/Aleutian",
    "BDT": "US/Aleutian",
    "AHST": "US/Aleutian",
    "HST": "US/Hawaii",
    "HDT": "US/Hawaii",
    "AST": "US/Alaska",
    "AWT": "US/Alaska",
    "APT": "US/Alaska",
    "AHDT": "US/Alaska",
    "YST": "US/Alaska",
    "AKST": "US/Alaska",
    "AKDT": "US/Alaska",
    "CMT": "Europe/Tiraspol",
    "AMT": "Europe/Athens",
    "EST": "US/Michigan",
    "MST": "W-SU",
    "CST": "US/Michigan",
    "PST": "US/Pacific",
    "MDT": "US/Mountain",
    "CDT": "US/Indiana-Starke",
    "ADT": "Canada/Atlantic",
    "CWT": "US/Indiana-Starke",
    "CPT": "US/Indiana-Starke",
    "BMT": "Europe/Tiraspol",
    "PDT": "US/Pacific",
    "EDT": "US/Michigan",
    "SJMT": "America/Costa_Rica",
    "YPT": "Canada/Yukon",
    "PWT": "US/Pacific",
    "PPT": "US/Pacific",
    "EWT": "US/Michigan",
    "EPT": "US/Michigan",
    "NDT": "Canada/Newfoundland",
    "ADDT": "America/Pangnirtung",
    "KMT": "Jamaica",
    "QMT": "America/Guayaquil",
    "HMT": "Europe/Mariehamn",
    "PDDT": "America/Inuvik",
    "FFMT": "America/Martinique",
    "SMT": "Singapore",
    "SDMT": "America/Santo_Domingo",
    "AEST": "Australia/Victoria",
    "AEDT": "Australia/Victoria",
    "NZMT": "Pacific/Auckland",
    "NZST": "Pacific/Auckland",
    "NZDT": "Pacific/Auckland",
    "IST": "Israel",
    "IDT": "Israel",
    "HKT": "Hongkong",
    "JST": "ROK",
    "WIB": "Asia/Pontianak",
    "WIT": "Asia/Jayapura",
    "JMT": "Israel",
    "PKT": "Asia/Karachi",
    "WITA": "Asia/Ujung_Pandang",
    "KST": "ROK",
    "RMT": "Europe/Riga",
    "KDT": "ROK",
    "TMT": "Iran",
    "JDT": "Japan",
    "FMT": "Atlantic/Madeira",
    "ACST": "Australia/Yancowinna",
    "ACDT": "Australia/Yancowinna",
    "AWST": "Australia/West",
    "AWDT": "Australia/West",
    "EMT": "Pacific/Easter",
    "DMT": "Europe/Dublin",
    "UTC": "Zulu",
    "BDST": "GB-Eire",
    "CEMT": "Europe/Berlin",
    "MSK": "W-SU",
    "MSD": "W-SU",
    "LST": "Europe/Riga",
    "WMT": "Poland",
    "GST": "Pacific/Saipan",
    "GDT": "Pacific/Saipan",
    "ChST": "Pacific/Saipan",
    "HWT": "US/Hawaii",
    "HPT": "US/Hawaii",
    "SST": "US/Samoa",
}
