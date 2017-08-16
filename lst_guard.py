"""
Checks for changed section labels in recent changes, if any detected writes
revision details along with changed labels (as a list) in a file. This file
will be then read by lst_corrector to check and (if necessary) correct changed
lables in pages that transclude these sections.

Currently supported languages are: German, English, Spanish, Armenian, Portuguese.
"""

import json, requests
from sseclient import SSEClient as EventSource

def run(project = '', lang = ''):
    # Identify project which will be watched
    supported_projects = ['wikisource']
    supported_languages = ['de', 'en', 'es', 'hy', 'pt']
    if project is False:
        project = input('Enter project (eg.: "wikisource"): ').lower()
    assert (project in supported_projects), 'Not supported project'
    if lang is False:
        lang = input('Enter language code (eg. "de"): ').lower()
    assert (lang in supported_languages), 'Not supported language'

    domain = lang + '.' + project + '.org'
    url = 'https://' + domain + '/w/api.php'
    print('Watching recent changes in {}'.format(domain))

    # Start watching recent changes
    for event in EventSource('https://stream.wikimedia.org/v2/stream/recentchange'):
        if event.event == 'message':
            try:
                item = json.loads(event.data) # Create dict in json format with revision details
            except ValueError:
                pass
            else:
                # Pick edits in specified domain and in namespace 104 (i.e. "Page:")
                if (item['server_name'], item['type'], item['namespace']) == (domain, 'edit', 104):
                    print('New revision in page "{}". Checking...'.format(item['title']))
                    check_edit(item, url, lang)

def check_edit(item, url, lang):
    # See if there are changed labels in revision
    changed_labels = check_diff(item['revision'], url, lang)

    # If ther are changed labels write to file
    if len(changed_labels) == 0:
        print(' No changed labels: PASS')
    else:
        print(' {} changed label(s) detected...'.format(len(changed_labels)))
        print(' Saving to correct transclusions later.')
        data = {'title': item['title'], 'lang': lang, 'url': url, 'labels': changed_labels }
        with open('detected_pages.txt', 'a') as file:
            file.write(str(data) + '\n')

def check_diff(revision, url, lang):
    old_text, new_text = get_diff(revision, url)
    old_labels = get_labels(old_text, lang)
    new_labels = get_labels(new_text, lang)
    changed_labels = {}

    if len(old_labels) == len(new_labels): #If equal assume we have corresponding labels
        for old, new in zip(old_labels, new_labels):
            if old != new:
                changed_labels[old] = new
    return changed_labels

def get_labels(wikitext, lang):
    labels = []
    # Syntax of section labels
    syntax = {              'de': '<Abschnitt Anfang=',     #both english and german syntax are used
                            'en': '<section begin=',
                            'es': '<sección comienzo=',     #?, only English used
                            'hy': '<բաժին սկիզբ=',          #only English used
                            'pt': '<trecho começo=' }       #only English used
    for line in wikitext.splitlines():
        #Check for localized syntax
        if syntax[lang] in line:
            label = line.split(syntax[lang])[1].split('/>')[0] # Split to get label
            label = label.strip('" ') # Remove brackets and whitespace
            labels.append(label)
        #Check for English syntax
        elif syntax['en'] in line:
            label = line.split(syntax['en'])[1].split('/>')[0]
            label = label.strip('" ')
            labels.append(label)
    return labels

def get_diff(revision, url):
    parameters = {      'action': 'query',
                        'prop': 'revisions',
                        'rvprop': 'content',
                        'format': 'json',
                        'utf8': '',
                        'revids': str(revision['old']) + '|' + str(revision['new']) }
    resp = (requests.get(url, params = parameters))
    if resp.status_code != 200: #This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))

    js = json.loads(resp.content.decode('utf-8')) # Decode to make sure non-latin characters are displayed correctly
    assert ('badrevids' not in js['query'].keys()), 'Incorrect revision IDs'

    pid = list(js['query']['pages'].keys()) # Find page ID(s) in json, shouldn't be more than 1
    assert (len(pid) == 1), 'Revision IDs from different pages'

    pid = pid[0]
    diffs = js['query']['pages'][pid]['revisions']

    return diffs[0]['*'], diffs[1]['*'] #Two strings with each revision content (in wikisyntax)

if __name__ == '__main__':
    run('wikisource', 'hy')
