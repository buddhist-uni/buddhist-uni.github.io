#!/bin/python

# Journals
# See e.g. https://openalex.org/sources/s4210198890 for more info
ALT      = "S4210189124"
ARIRIAB  = "S4306473384"
ARIRIAB_JP = "S4306544351"
BSR      = "S139284966"
JIABS    = "S2764843907"
JGB      = "S2739015590"
IJDS     = "S2739402052"
HIJBS    = "S4210175251"
JBE      = "S2764747367"
STORE    = "S4306531081"
DAEDALUS = "S107749620"
NYRB     = "S122513169"
NYRB_ALT = "S4306476742"
PLATO    = "S2737990715"
JJRS     = "S120086578"
JCB      = "S107624032"
JCBS     = "S4306542695"
JPBS     = "S4306547155"
JOCBS    = "S2764611450"
PNAS     = "S125754415"
AO       = "S4210209688"
EB       = "S118212324"
EB_NS    = "S2764994964"
IBK      = "S2764402342"
EMSCAT   = "S4210198890"
IJBTC    = "S4210226626"
JKR      = "S2764709287"
JSS      = "S8401816"
SLJH     = "S4210213701"
AE       = "S144820813"
MINDFULNESS = "S47477353"
MOUSSONS = "S2736722918"
# Rejected Journals, don't fetch
ASIAN_STUDIES = "S114691300"
SSRN = "S4210172589"
IA = "S4377196541"

# from OA to OBU IDs
slugs = {
  ALT: "alt",
  ARIRIAB: "aririab",
  ARIRIAB_JP: "aririab",
  BSR: "bsr",
  JIABS: "jiabs",
  JGB: "jgb",
  JJRS: "jjrs",
  JPBS: "jpbs",
  JCB: "jcb",
  JCBS: "jcbs",
  JOCBS: "jocbs",
  IJDS: "ijds",
  HIJBS: "hijbs",
  JBE: "jbe",
  STORE: "store",
  DAEDALUS: "daedalus",
  NYRB: "nyrb",
  NYRB_ALT: "nyrb",
  PLATO: "plato",
  PNAS: "pnas",
  AE: "ae",
  AO: "ao",
  EB: "eb",
  EB_NS: "eb", # Just map the old and new series together
  IBK: "ibk",
  EMSCAT: "emscat",
  IJBTC: "ijbtc",
  JKR: "jkr",
  JSS: "jss",
  SLJH: "sljh",
  MINDFULNESS: "mindfulness",
  MOUSSONS: "moussons",
  ASIAN_STUDIES: '"The Journal of Asian Studies"',
}

issns = {
  "S4210189124": [
    "2051-5863"
  ],
  "S4306473384": [],
  "S4306544351": [],
  "S139284966": [
    "0265-2897",
    "1747-9681"
  ],
  "S2764843907": [],
  "S2739015590": [
    "1527-6457"
  ],
  "S120086578": [
    "0304-1042"
  ],
  "S4306547155": [],
  "S107624032": [
    "1463-9947",
    "1476-7953"
  ],
  "S4306542695": [],
  "S2764611450": [
    "2047-1076"
  ],
  "S2739402052": [
    "2196-8802"
  ],
  "S4210175251": [
    "2576-2923",
    "2576-2931"
  ],
  "S2764747367": [],
  "S4306531081": [
    "2323-5209"
  ],
  "S107749620": [
    "0011-5266",
    "1548-6192"
  ],
  "S122513169": [
    "0028-7504"
  ],
  "S4306476742": [],
  "S2737990715": [
    "1095-5054"
  ],
  "S125754415": [
    "0027-8424",
    "1091-6490"
  ],
  "S144820813": [
    "1882-6865"
  ],
  "S4210209688": [
    "0571-1371",
    "2328-1286"
  ],
  "S118212324": [
    "0012-8708"
  ],
  "S2764994964": [],
  "S2764402342": [
    "0019-4344",
    "1884-0051"
  ],
  "S4210198890": [
    "2101-0013",
    "2551-9603"
  ],
  "S4210226626": [
    "1598-7914"
  ],
  "S2764709287": [
    "2093-7288",
    "2167-2040"
  ],
  "S8401816": [],
  "S4210213701": [
    "0378-486X",
    "2279-3321"
  ],
  "S47477353": [
    "1868-8527",
    "1868-8535"
  ],
  "S2736722918": [
    "1620-3224",
    "2262-8363"
  ],
  "S114691300": [
    "0021-9118",
    "1752-0401"
  ],
  "S4210172589": [
    "1556-5068"
  ],
  "S4377196541": [],
}

if __name__ == "__main__":
  from openaleximporter import OPENALEX_CREDS
  import json
  import requests
  def get_issns_for_journal(oaid: str) -> list[str]:
    try:
      resp = requests.get(f"https://api.openalex.org/{oaid}?{OPENALEX_CREDS}")
      return resp.json()['issn'] or []
    except:
      print("FAILED TO GET ISSNs FOR "+oaid)
      return []
  issns = {}
  for oaid in slugs.keys():
    issns[oaid] = get_issns_for_journal(oaid)
  blob = "issns = " + json.dumps(issns, indent=2)
  print(blob)
