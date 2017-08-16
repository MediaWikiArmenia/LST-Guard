import json, requests, time
from getpass import getpass

def run():
    while True:
        time.sleep(180) # 3 minutes between each check
        print('Checking saved transclusions...')
        with open('detected_pages.txt', 'r+') as file:
            try:
                data = file.readlines()
            finally:
                file.close()
        if len(data) != 0:
            for item in data:
                transclusions = get_transclusions(item['title'], item['url'])
                if len(transclusions) == 0:
                    print(' No transclusions of "{}": PASS'.format(item['title']))
                else:
                    for tr in transclusions:
                        print(' Checking transclusions of "{}"...'.format(item['title'])')
                        # Get source code of transcluding page
                        page_content = get_pagecontent(tr, item['url'])
                        # Updates section names if necessary, otherwise retruns empty string
                        page_content = check_transclusion(page_content, changed_sections)
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
    return [] #return empty list if no transclusions

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

def check_transclusion(page_content, changed_sections):
    page_content = page_content.splitlines()
    edit = False

    # If old section name found replace with new section name
    for line in page_content:
        if '<pages index=' in line: #TODO make sure template includes page!!
            index = page_content.index(line)
            for section in changed_sections.keys():
                if section in line:
                    edit = True
                    line = line.replace(section, changed_sections[section])
                    page_content[index] = line
    page_content = '\n'.join(page_content)

    if edit == True:
        return page_content
    return '' # Return empty string if no edit in page necessary

def edit_page(page_id, page_content, url, lang):
    #see https://www.mediawiki.org/wiki/Manual:Bot_passwords
    username = ''
    password = ''
    session = requests.Session()

    summaries = {   'en': 'Bot: fix broken section transclusion',
                    'es': 'Bot: arreglo de los nombres de sección de la transclusión',
                    'de': 'Bot: Korrigiere Abschnittsnamen von Einbindung'
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
    global summaries
    resp3 = session.post(url, data = {
                'action': 'edit',
                'pageid': page_id,
                'text': page_content,
                'summary': summaries[lang],
                'format': 'json',
                'utf8': '',
                'bot': 1,
                'token': resp2.json()['query']['tokens']['csrftoken']})
