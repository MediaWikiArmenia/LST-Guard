import json, requests

# HTML syntax of section labels
section_label = {       'de': '<Abschnitt Anfang=',     #both english and german syntax used
                        'en': '<section begin=',
                        'es': '<sección comienzo=',     #?, only English used
                        'hy': '<բաժին սկիզբ=',          #only English used
                        'pt': '<trecho começo=' }       #only English used

# HTML transclusion syntax (used by all languages)
html_labels = ['<pages index=', 'fromsection=', 'tosection']

# Mediawiki transclusion syntax
mediawiki_labels = ['#lst:', '#lstx:']

# Localized template name and parmeter(s) for section name
transclusion_labels = {
                        'de': [],
                        'en': ['Page', 'section', 'section-x'],
                        'es': ['Inclusión', 'sección', 'section', 'section-x'],
                        'hy': ['Էջ', 'բաժին', 'բաժին-x'],
                        'pt': ['Página', 'seção']   }


def run(lang = 'hy', project = 'wikisource'):
    global supported_langs
    assert (lang in supported_langs), 'Not supported language'

    domain = lang + '.' + project + '.org'
    url = 'https://' + domain + '/w/api.php'
    print('Watching recent changes in {}'.format(domain))

    for event in EventSource('https://stream.wikimedia.org/v2/stream/recentchange'):
        if event.event == 'message':
            try:
                item = json.loads(event.data) #create dict in json format
            except ValueError:
                pass
            else:
                # Pick edits in specified domain and in namespace 104 ("Page:")
                # If you are testing remove the namespace conditional to test on a sandboxe page
                if (item['server_name'], item['type'], item['namespace']) == (domain, 'edit', 104):
                    print('New revision in page "{}". Checking...'.format(item['title']))
                    check_revision(item, url, lang)

def check_revision(item, url, lang):
    # See if there are changed section names in revision
    changed_sections = get_revisions(item['revision'], url)

    # Ckeck changed section names in transclusions if there are any
    if len(changed_sections) == 0:
        print(' No changed section names: PASS')
    else:
        print(' {} changed section name(s) detected...'.format(len(changed_sections)))
        transclusions = get_transclusions(item['title'], url)
        print(' Checking transclusions... {} found.'.format(len(transclusions)))

        # Correct section names in transclusions if necessary
        if len(transclusions) == 0:
            print(' No transclusions: PASS')
        else:
            for transclusion in transclusions:
                # Get source code of transcluding page
                page_content = get_pagecontent(transclusion, url)
                # Updates section names if necessary, otherwise retruns empty string
                page_content = check_transclusion(page_content, changed_sections)
                if page_content == '':
                    print(' No corrections made. PASS')
                else:
                    edit_page(transclusion, page_content, url, lang) #TODO: return something to indicate edit was successful/fail
                    print(' 1 transclusion corrected! DONE')

def get_revisions(revision, url):

    parameters = {'action': 'query', 'prop': 'revisions', 'rvprop': 'content',
        'format': 'json', 'utf8': '', 'revids': str(revision['old']) + '|' + str(revision['new']) }
    resp = (requests.get(url, params = parameters))
    if resp.status_code != 200: #This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))

    js = json.loads(resp.content.decode('utf-8')) #Decode to make sure non-latin characters are displayed correctly
    assert ('badrevids' not in js['query'].keys()), 'Incorrect revision IDs'

    pid = list(js['query']['pages'].keys()) #Find page ID(s) in json, shouldn't be more than 1
    assert (len(pid) == 1), 'Revision IDs from different pages'

    pid = pid[0]
    diffs = js['query']['pages'][pid]['revisions']
    old, new = diffs[0]['*'], diffs[1]['*'] #Two strings with each revision content (in wikisyntax)
    return check_diff(old, new)

def check_diff(old, new):
    changed_sections = {}
    old, new = old.splitlines(), new.splitlines()
    for a, b in zip(old, new):
        if '<section begin=' in b and a != b: #TODO: adapt to syntax variations / irregularities
            a, b = a.split('"')[1], b.split('"')[1]
            changed_sections[a] = b
    return changed_sections
