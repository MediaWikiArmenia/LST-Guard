#TODO: resolve all pid variable issues

import json, requests
from sseclient import SSEClient as EventSource

def watch_rc(project = 'hy.wikisource.org'):
    url = 'https://stream.wikimedia.org/v2/stream/recentchange'
    print('Watching recent changes in {}'.format(project))
    for event in EventSource(url):
        if event.event == 'message':
            try:
                item = json.loads(event.data) #creates dict in json format
            except ValueError:
                pass
            else:
                if project in item['server_name']:
                    if 'revision' in item.keys():# and item['namespace'] == 104:    #TODO: when actually running add ns 104!
                        print('New revision in page "{}" (id: {}). Checking...'.format(item['title'], item['id']))
                        get_revisions(item['revision'], item['title'])

def get_revisions(revision, title):
    parameters = {'action': 'query', 'prop': 'revisions', 'rvprop': 'content',
        'format': 'json', 'utf8': '', 'revids': str(revision['old']) + '|' + str(revision['new']) }
    resp = (requests.get('https://hy.wikisource.org/w/api.php', params = parameters))
    if resp.status_code != 200: #This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))

    js = json.loads(resp.content.decode('utf-8')) #decode to make sure armenian characters are displayed correctly
    pid = str(js['query']['pages'].keys())[12:-3]
    diffs = js['query']['pages'][pid]['revisions']
    if len(diffs) == 2: #Make sure we have 2 revisions TODO: resolve this in watch_rc (item['type'] == 'edit')
        old = diffs[0]['*']
        new = diffs[1]['*']
        check_diff(old, new, title)
    else: #This means we have only 1 revision, i.e. new page is created, rather than edited
        print(' New page: PASS')

def check_diff(old, new, title):
    # Parsing changed section names from diff
    changed_sections = {}
    old, new = old.splitlines(), new.splitlines()
    for a, b in zip(old, new):
        if '<section begin=' in b and a != b:
            a, b = a.split('"')[1], b.split('"')[1]
            changed_sections[a] = b

    # Generating a list of transclusions of the edited page
    if len(changed_sections) > 0:
        print(' {} changed section name(s) detected: {}'.format(len(changed_sections), changed_sections))
        transclusions = get_transclusions(title)
        print(' Checking transclusions... {} found.'.format(len(transclusions)))
        # Checking if changed section names occur in transclusions
        if len(transclusions) > 0:
            for item in transclusions:
                check_transclusion(item, changed_sections)
        else:
            print(' No transclusions: PASS')
    else:
        print(' Everything OK: PASS')

def get_transclusions(title):
    parameters = {'action': 'query', 'prop': 'transcludedin', 'titles': title,
        'format': 'json', 'utf8': '', 'tinamespace': '*'} #TODO change ns to 0
    resp = (requests.get('https://hy.wikisource.org/w/api.php', params = parameters))

    js = json.loads(resp.content.decode('utf-8'))
    #print('TRANSCLUDEDIN:', js)
    pid = str(js['query']['pages'].keys())[12:-3]   #TODO: Will throw keyerror when js = {'batchcomplete': '', 'warnings': {'main': {'*': 'Unrecognized parameter: pageid.'}}}
    transclusions = js['query']['pages'][pid]
    if 'transcludedin' in transclusions.keys():
        return [item['pageid'] for item in transclusions['transcludedin']]
    return [] #return empty list if no transclusions

def check_transclusion(page_id, changed_sections):
    page_content = get_pagecontent(page_id).splitlines()
    edit = False
    #print(page_content)
    for line in page_content:
        if '<pages index=' in line:
            index = page_content.index(line)
            for section in changed_sections.keys():
                if section in line:
                    edit = True
                    line = line.replace(section, changed_sections[section])
                    page_content[index] = line
    page_content = '\n'.join(page_content)

    if edit == True:
        edit_page(page_id, page_content)
        print(' 1 transclusion corrected! DONE')
    else:
        print(' No corrections made. PASS')

def get_pagecontent(page_id):
    parameters = {'action': 'query', 'prop': 'revisions', 'rvprop': 'content',
        'format': 'json', 'utf8': '', 'pageids': page_id }
    resp = (requests.get('https://hy.wikisource.org/w/api.php', params = parameters))
    if resp.status_code != 200:
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    js = json.loads(resp.content.decode('utf-8'))
    #print(js)
    pid = str(js['query']['pages'].keys())[12:-3]
    return js['query']['pages'][pid]['revisions'][0]['*']

def edit_page(page_id, page_content):
    # get token to edit
    print(' getting edit token....')
    parameters = {'action': 'query', 'meta': 'tokens', 'type': 'csrf',
        'format': 'json'}
    resp = (requests.get('https://hy.wikisource.org/w/api.php', params = parameters))
    if resp.status_code != 200: #This means something went wrong
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    js = json.loads(resp.content.decode('utf-8'))
    edittoken = js['query']['tokens']['csrftoken']
    del js
    del resp

    #edit page
    editdetails = {'action': 'edit', 'pageid': page_id, 'text': page_content,
        'summary': 'Բաժնի անվան ուղղում բոտի կողմից', 'format': 'json', 'utf8': '', 'token': edittoken}
    resp = (requests.post('https://hy.wikisource.org/w/api.php', data = editdetails))
    if resp.status_code != 200: #This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    js = json.loads(resp.content.decode('utf-8'))
    #print(js)

if __name__ == '__main__':
    watch_rc()

# search for:
# <pages index="Հայկական Սովետական Հանրագիտարան (Soviet Armenian Encyclopedia) 6.djvu" from=161 to=161 fromsection="Հայզենբերգ" tosection="Հայզենբերգ"/>
# {{Էջ|Հայկական Համառոտ Հանրագիտարան․ Հ տառով հոդվածները.djvu/2|բաժին=Հագուստ|համ=34}}
