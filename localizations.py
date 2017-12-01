# !/usr/local/bin/python3
# -*- coding: utf-8 -*-

# Syntax of section labeling
section_label = {
    'de': 'Abschnitt Anfang',     #both English and German syntaxes used
    'en': 'section begin',
    'es': '',                       #no localization? (<sección comienzo=?)
    'fr': '',                       #no localization
    'hy': 'բաժին սկիզբ',          #only English used
    'it': '',
    'pl': '',                       #no localization
    'pt': 'trecho começo',        #only English used
    'ru': ''                        #no localization
    }

# Localized template syntax (depraced in some wikis)
template = {
    'de': ['{{seite|', '{{[Ss]eite[|]', 'Abschnitt'],   # not used
    'en': ['{{page|', '{{[Pp]age[|]', 'section', 'section-x'],
    'es': ['{{inclusión|', '{{[Ii]nclusión[|]', 'sección', 'section', 'section-x'],
    'fr': ['{{page|', '{{[Pp]age[|]', 'section', 'section-x'],
    'hy': ['{{էջ|', '{{[Էէ]ջ[|]', 'բաժին', 'բաժին-x'],
    'it': ['{{pagina|', '{{[Pp]agina[|]', 'section'],
    'pl': [],                       # no template
    'pt': ['{{página|', '{{[Pp]ágina[|]', 'seção'],
    'ru': ['{{страница|', '{{[Сс]траница[|]', 'section', 'section-x'] # Redirected 'Page' is also used
    }

edit_summary = {
    'en': 'Bot: fix broken section transclusion',
    'es': 'Bot: arreglo de los nombres de sección de la transclusión',
    'de': 'Bot: Korrigiere Abschnittsnamen von Einbindung',
    'fr': 'Bot: répare transclusion de la section',
    'hy': 'Բոտ․ ներառված բաժնի անվան ուղղում',
    'it': 'Bot: corretto trasclusione',
    'pl': 'Bot poprawia dołączanie',
    'pt': 'bot: corrigir nomes de seção',
    'ru': 'Бот исправил сломанное включение'
    }
