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
STORE    = "S4210200836"
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
}