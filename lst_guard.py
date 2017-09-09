"""
Checks for changed section labels in recent changes, if any detected writes
revision details along with changed labels (as a list) in a file. This file
will be then read by lst_corrector to check and (if necessary) correct changed
lables in pages that transclude these sections.

Currently supported languages are: German, English, Spanish, Armenian, Portuguese.
"""
import json, requests, time, re, redis
from sseclient import SSEClient as EventSource

# Supported projects and languages
global projects, languages
projects = ['wikisource', 'wikipedia', 'wiktionary']
languages = ['de', 'en', 'es', 'hy', 'pt']

def run(proj, langs): # Arguments are respectively string and list

    # Identify project which will be watched
    if not proj:
        proj = input('Enter project (eg.: "wikisource"): ').lower()
    assert (proj in projects), 'Not supported project'
    if not langs:
        langs = input('Enter language code(s) (eg. "de"): ').lower()
    assert (l in languages for l in langs), 'Not supported language(s)'

    # Start watching recent changes
    print('Watching recent changes in {} ({})'.format(proj, ', '.join(langs)))
    for event in EventSource('https://stream.wikimedia.org/v2/stream/recentchange'):
        if event.event == 'message':
            try:
                item = json.loads(event.data) # Create dict in json format with revision details
            except ValueError:
                pass
            else:
                server = item['server_name'].split('.')
                #TODO add namespace filter
                if server[0] in langs and server[1] == proj and item['type'] == 'edit':
                    print('New revision in page "{}" ({}).\n Checking...'.format(item['title'], server[0]))
                    check_edit(item)

def check_edit(item):
    revids = item['revision']   #revision ids
    url = item['server_url'] + '/w/api.php'
    lang = item['server_name'].split('.')[0]

    # See if there are changed labels in revision (returns a dict)
    changed_labels = check_revision(revids, url, lang)

    # If ther are changed labels write to file
    if len(changed_labels) == 0:
        print(' No changed labels: PASS')
    else:
        print(' {} changed label(s) detected...'.format(len(changed_labels)))
        data = {'title': item['title'], 'lang': lang, 'url': url, 'labels': changed_labels }
        write_data(data)

def write_data(new_data):
    r = redis.StrictRedis(host='localhost', port=7777, db=0)
    while(r.get('locked') == 'True'): #Because redis stores this as a string
        time.sleep(0.02)
    r.set('locked', True)

    # Load older data if necessary
    if(r.get('lstdata')):
        all_data = json.loads(r.get('lstdata').decode('utf-8'))
    else:
        all_data = []

    # Check for identical lables
    if len(all_data) > 0:
        for old_data in all_data:
            for oldl, newl in zip(list(old_data['labels'].keys()), list(old_data['labels'].values())):
                if newl in new_data['labels'].keys():
                    if oldl == new_data['labels'][newl]: # This means label is changed back (reverted)
                        old_data['labels'].pop(oldl)
                    else: # This means label is changed to something else
                        old_data['labels'][oldl] = new_data['labels'][newl]

    all_data.append(new_data)
    r.set('lstdata', json.dumps(all_data))
    r.set('empty', False)
    r.set('locked', False)
    print(' Saving to check transclusions later: DONE')

def check_revision(revids, url, lang):
    old_text, new_text = get_diff(revids, url)
    old_labels = get_labels(old_text, lang)
    new_labels = get_labels(new_text, lang)
    changed_labels = {}

    if len(old_labels) == len(new_labels): #If equal assume we have corresponding labels
        for old, new in zip(old_labels, new_labels):
            if old != new:
                changed_labels[old] = new
    return changed_labels # Returns empty dict if nothing is detected

def get_diff(revids, url):
    resp = (requests.get(url, params = {
                        'action': 'query',
                        'prop': 'revisions',
                        'rvprop': 'content',
                        'format': 'json',
                        'utf8': '',
                        'revids': str(revids['old']) + '|' + str(revids['new'])
                        }))
    if resp.status_code != 200: #This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))

    js = json.loads(resp.content.decode('utf-8')) # Decode to make sure non-latin characters are displayed correctly
    assert ('badrevids' not in js['query'].keys()), 'Incorrect revision IDs'

    pageid = list(js['query']['pages'].keys()) # Find page id(s) in json, shouldn't be more than 1
    assert (len(pageid) == 1), 'Revision IDs from different pages'
    pageid = pageid[0]
    diffs = js['query']['pages'][pageid]['revisions']

    return diffs[0]['*'], diffs[1]['*'] # Two strings with revision content (in wikisyntax)

def get_labels(wikitext, lang):
    labels = []
    # Syntax of section labels
    syntax = {              'de': '<Abschnitt Anfang=',     #both english and german syntaxes are used
                            'en': '<section begin=',
                            'es': '<sección comienzo=',     #?, only English used
                            'hy': '<բաժին սկիզբ=',          #only English used
                            'pt': '<trecho começo=' }       #only English used
    for line in wikitext.splitlines():
        #Check localized and English syntax labeling
        if syntax[lang] in line or syntax['en'] in line:
            # Some regex to deal with syntactic irregularietes (brackets, whitespace)
            label = re.search(r'[{}{}]\s?=\s?"?(.*?)"?\s?/>'.format(syntax['en'], syntax[lang]), line)
            if label:
                labels.append(label.groups()[0])
    return labels
