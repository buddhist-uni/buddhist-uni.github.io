#!/bin/python3

try:
  from lingua import LanguageDetectorBuilder, Language
except:
  print("pip install lingua-language-detector")
  exit(1)

LANGUAGES = [
  Language.ENGLISH,
  Language.CHINESE,
  Language.JAPANESE,
  Language.KOREAN,
  Language.VIETNAMESE,
  Language.THAI,
  Language.MONGOLIAN,
  Language.GERMAN,
  Language.FRENCH,
  Language.SPANISH,
  Language.ITALIAN,
  Language.RUSSIAN,
  Language.POLISH,
  Language.HINDI,
  Language.BENGALI,
  Language.TAMIL,
  Language.MARATHI,
]

LANGUAGE_DETECTOR = LanguageDetectorBuilder.from_languages(*LANGUAGES).build()
