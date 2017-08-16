"""
Checks transclusions of pages in the file "detected_pages.txt". Fixes transclusions
if they are broken (i.e. replaces old section labels with new ones). Cleans file
after each check (every 3 minutes).
"""

import json, requests, time
from getpass import getpass

def run():
    while True:
        time.sleep(180) # Sleep 3m between each check
        data = []
        print('Checking saved transclusions...')
        with open('detected_pages.txt', 'r+') as file:
            try:
                for line in file:
                    item = json.loads(line)
                    data.append(item)
            finally:
                file.truncate(0) # Clean file
                file.close()
        if len(data) != 0:
            for item in data:
                transclusions = get_transclusions(item['title'], item['url'])
                if len(transclusions) == 0:
                    print(' No transclusions of "{}": PASS'.format(item['title']))
                else:
                    for tr in transclusions:
                        print(' Checking transclusions of "{}"...'.format(item['title']))
                        # Get source code of transcluding page
                        page_content = get_pagecontent(tr, item['url'])
                        # Updates section names if necessary, otherwise retruns empty string
                        page_content = fix_transclusion(page_content, item['title'], item['labels'], item['lang'])
                        if page_content == '':
                            print(' No corrections made. PASS')
                        else:
                            edit_page(tr, page_content, item['url'], item['lang']) #TODO: return something to indicate edit was successful/fail?
                            print(' 1 transclusion corrected! DONE')

def get_transclusions(title, url):
    parameters = {  'action': 'query',
                    'prop': 'transcludedin',
                    'titles': title,
                    'format': 'json',
                    'utf8': '',
                    'tinamespace': '*'} #TODO change ns to 0?
    resp = (requests.get(url, params = parameters))

    js = json.loads(resp.content.decode('utf-8'))
    pid = str(js['query']['pages'].keys())[12:-3]   #TODO: throw keyerror when js = {'batchcomplete': '', 'warnings': {'main': {'*': 'Unrecognized parameter: pageid.'}}}
    transclusions = js['query']['pages'][pid]
    if 'transcludedin' in transclusions.keys():
        return [item['pageid'] for item in transclusions['transcludedin']]
    return [] # Return empty list if no transclusions

def fix_transclusion(page_content, title, labels, lang):
    # HTML transclusion syntax (used by all languages)
    html = ['<pages index=', 'fromsection=', 'tosection=']
    # Mediawiki transclusion syntax
    mediawiki = ['#lst:', '#lstx:']
    # Localized template name and parmeter(s) for section name
    templates = {           'de': ['Seite', 'Abschnitt'], # not used
                            'en': ['Page', 'section', 'section-x'],
                            'es': ['Inclusión', 'sección', 'section', 'section-x'],
                            'hy': ['Էջ', 'բաժին', 'բաժին-x'],
                            'pt': ['Página', 'seção']   }

    page_content = page_content.splitlines()
    edit = False

    # If old section name found replace with new section name
    for line in page_content:
        if title in line:
            index = page_content.index(line)
            template = '{{' + templates[lang][0] + '|'
            # Case 1: html syntax is used for transclusion
            if html[0] in line:
                for label in labels.keys():
                    if label in line: #TODO: deal label as a seperate word
                        edit = True
                        line = line.replace(label, labels[label])
                        page_content[index] = line
            # Case 2: mediawiki syntax is used for transclusion
            elif mediawiki[0] in line or mediawiki[1] in line:
                for label in labels.keys():
                    label = '|' + label + '}}'
                    newlabel = '|' + labels[label] + '}}'
                    if label in line:
                        edit = True
                        line = line.replace(label, new_label)
                        page_content[index] = line
            # Case 3: template is used for transclusion
            elif template in line:
                for label in labels.keys():
                    label = '=' + label + '}}' #TODO: deal with cases when section isn't last parameter!
                    newlabel = '=' + labels[label] + '}}'
                    if label in line:
                        edit = True
                        line = line.replace(label, new_label)
                        page_content[index] = line
    page_content = '\n'.join(page_content)
    if edit == True:
        return page_content
    return '' # Return empty string if no edit in page necessary

def get_pagecontent(page_id, url):
    parameters = {  'action': 'query',
                    'prop': 'revisions',
                    'rvprop': 'content',
                    'format': 'json',
                    'utf8': '',
                    'pageids': page_id }

    resp = (requests.get(url, params = parameters))

    if resp.status_code != 200:
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    js = json.loads(resp.content.decode('utf-8'))
    pid = str(js['query']['pages'].keys())[12:-3]
    return js['query']['pages'][pid]['revisions'][0]['*']

def edit_page(page_id, page_content, url, lang):
    #see https://www.mediawiki.org/wiki/Manual:Bot_passwords
    username = ''
    password = ''
    session = requests.Session()

    summaries = {   'en': 'Bot: fix broken section transclusion',
                    'es': 'Bot: arreglo de los nombres de sección de la transclusión',
                    'de': 'Bot: Korrigiere Abschnittsnamen von Einbindung',
                    'hy': 'Բոտ․ ներառված բաժնի անվան ուղղում',
                    'pt': 'bot: corrigir nomes de seção' }

    # Ask for user login/password if necessary
    if username == '' or password == '':
        username = input('Bot username: ')
        password = getpass('Password: ')
    print(' logging in as {}...'.format(username))

    # Request login token
    resp0 = session.get(url, params = {
                'action': 'query',
                'meta': 'tokens',
                'type': 'login',
                'format': 'json'})
    resp0.raise_for_status()
    # Login
    resp1 = session.post(url, data = {
                'action': 'login',
                'format': 'json',
                'lgname': username,
                'lgpassword': password,
                'lgtoken': resp0.json()['query']['tokens']['logintoken']})
    if resp1.json()['login']['result'] != 'Success':
        raise RuntimeError(resp1.json()['login']['reason'])
    print('Login successful')
    # Request edit token
    print(' getting edit token....')
    resp2 = session.get(url, params = {
                'action': 'query',
                'meta': 'tokens',
                'type': 'csrf',
                'format': 'json'})
    # Edit page
    resp3 = session.post(url, data = {
                'action': 'edit',
                'pageid': page_id,
                'text': page_content,
                'summary': summaries[lang],
                'format': 'json',
                'utf8': '',
                'bot': 1,
                'token': resp2.json()['query']['tokens']['csrftoken']})

if __name__ == '__main__':
    run()
