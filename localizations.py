 # Syntax of section labeling
   section_label = {
    'de': '<Abschnitt Anfang=',     #both English and German syntaxes are used
    'en': '<section begin=',
    'es': '<sección comienzo=',     #?, only English used
    'fr': '',                       #only English used
    'hy': '<բաժին սկիզբ=',          #only English used
    'pt': '<trecho começo=' }       #only English used

# Localized template name and parmeter(s) for section name (depraced in some wikis)
transclusion_template = {
    'de': ['Seite', 'Abschnitt'], # not used
    'en': ['Page', 'section', 'section-x'],
    'es': ['Inclusión', 'sección', 'section', 'section-x'],
    'fr': [],
    'hy': ['Էջ', 'բաժին', 'բաժին-x'],
    'pt': ['Página', 'seção']   }

edit_summary = {
    'en': 'Bot: fix broken section transclusion',
    'es': 'Bot: arreglo de los nombres de sección de la transclusión',
    'de': 'Bot: Korrigiere Abschnittsnamen von Einbindung',

    'hy': 'Բոտ․ ներառված բաժնի անվան ուղղում',
    'pt': 'bot: corrigir nomes de seção' }
