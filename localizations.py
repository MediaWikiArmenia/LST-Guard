#TODO: check is empty values will cause error

# Syntax of section labeling
   section_label = {
    'de': '<Abschnitt Anfang=',     #both English and German syntaxes are used
    'en': '<section begin=',
    'es': '<sección comienzo=',     #?, only English used
    'fr': '',                       #no localization
    'hy': '<բաժին սկիզբ=',          #only English used
    'it': '',
    'pl': '',                       #no localization
    'pt': '<trecho começo=',        #only English used
    'ru': ''                        #no localization
    }

# Localized template name and parmeter(s) for section name (depraced in some wikis)
transclusion_template = {
    'de': ['Seite', 'Abschnitt'],   # not used
    'en': ['Page', 'section', 'section-x'],
    'es': ['Inclusión', 'sección', 'section', 'section-x'],
    'fr': ['Page', 'section', 'section-x'],
    'hy': ['Էջ', 'բաժին', 'բաժին-x'],
    'it': ['Pagina', 'section']
    'pl': [],                       # no template
    'pt': ['Página', 'seção'],
    'ru': ['Страница', 'section', 'section-x'] # Redirected 'Page' is also used
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
