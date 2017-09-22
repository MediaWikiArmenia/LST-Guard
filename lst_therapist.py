"""
Checks transclusions of pages in the file "detected_pages.txt". Fixes transclusions
if they are broken (i.e. replaces old section labels with new ones). Cleans file
after each check (every 5 minutes).
"""
import json, requests, time, redis
from getpass import getpass
from configparser import ConfigParser
from localizations import transclusion_template, edit_summary

def run():
    r = redis.StrictRedis(host='localhost', port=7777, db=0)
    while True:
        if r.get('locked'): # Make sure 'locked' is set in Redis
            while int(r.get('locked')): # Wait if 'locked' is true
                time.sleep(0.02)
        if not r.get('empty'): # Make sure 'empty' is set in Redis
            r.set('empty', 1)
        if not int(r.get('empty')):
            r.set('locked', 1)
            data = json.loads(r.get('lstdata').decode('utf-8')) # We will get a list with dicts
            r.delete('lstdata')
            r.set('empty', 1)
            r.set('locked', 0)
            print('Checking saved labels...')
            # Check each item and update transclusions if necessary
            check_saved_data(data)
            time.sleep(300)
        else:
            time.sleep(300)

def check_saved_data(data):
    for item in data:
        corrections = 0
        transclusions = get_transclusions(item['title'], item['url'])
        if len(transclusions) == 0:
            print(' No transclusions of "{}": PASS'.format(item['title']))
        else:
            for transclusion in transclusions:
                print(' Checking 1 transclusion of "{}"...'.format(item['title']))
                # Get source code of transcluding page
                page_content = get_pagecontent(transclusion, item['url'])
                # Updates section names if necessary, otherwise retruns empty string
                page_content, fixed_labels = fix_transclusion(page_content, item['title'], item['labels'], item['lang'])
                if page_content == '':
                    print(' No corrections made. PASS')
                else:
                    edit_page(transclusion, page_content, item['url'], item['lang'], fixed_labels) #TODO: Return something to indicate edit was success/fail
                    corrections += 1
                    print(' 1 transclusion corrected! DONE')
        with open('log.txt', 'a') as file:
            file.write(item['lang'] + '\n' + item['title'] + '\n' + str(len(transclusions)) + ' transclusions' + '\n' + str(corrections) + ' corrections' + '\n\n')

def get_transclusions(title, url):
    parameters = {  'action': 'query',
                    'prop': 'transcludedin',
                    'titles': title,
                    'format': 'json',
                    'utf8': '',
                    'tinamespace': '*'} #TODO change ns to 0?
    resp = (requests.get(url, params = parameters))

    js = json.loads(resp.content.decode('utf-8'))
    pid = [p for p in js['query']['pages'].keys()][0]   #TODO: throw keyerror when js = {'batchcomplete': '', 'warnings': {'main': {'*': 'Unrecognized parameter: pageid.'}}}
    transclusions = js['query']['pages'][pid]
    if 'transcludedin' in transclusions.keys():
        return [item['pageid'] for item in transclusions['transcludedin']]
    return [] # Return empty list if no transclusions

def fix_transclusion(page_content, title, labels, lang):

    # HTML transclusion syntax (used by all languages)
    html_transclusion = ['<pages index=', 'fromsection=', 'tosection=']
    # Mediawiki transclusion syntax
    mediawiki_transclusion = ['#lst:', '#lstx:']

    page_content = page_content.splitlines()
    fixed_labels = {}
    edit = False
    # Clean title if necessary
    title = clean_title(title)
    # If old section name found replace with new section name
    for line in page_content:
        if title in line:
            index = page_content.index(line)
            # Case 1: html syntax is used for transclusion
            if html_transclusion[0] in line:
                for label in labels.keys():
                    if label in line: #TODO: deal label as a seperate word
                        fixed_labels[label] = labels[label]
                        edit = True
                        line = line.replace(label, labels[label])
                        page_content[index] = line
            # Case 2: mediawiki syntax is used for transclusion
            if mediawiki_transclusion[0] in line or mediawiki_transclusion[1] in line:
                for label in labels.keys():
                    label = '|' + label + '}}'
                    newlabel = '|' + labels[label] + '}}'
                    if label in line:
                        fixed_labels[label] = newlabel
                        edit = True
                        line = line.replace(label, new_label)
                        page_content[index] = line
            # Case 3: template is used for transclusion
            template = '{{' + transclusion_template[lang][0] + '|'
            if template in line:
                for label in labels.keys():
                    label = '=' + label + '}}' #TODO: deal with cases when section isn't last parameter!
                    newlabel = '=' + labels[label] + '}}'
                    if label in line:
                        fixed_labels[label] = newlabel
                        edit = True
                        line = line.replace(label, new_label)
                        page_content[index] = line
    page_content = '\n'.join(page_content)
    if edit == True:
        return page_content, fixed_labels
    return '', '' # Return empty string if no edit in page necessary

def clean_title(title):
    if '.djvu/' in title:
        title = title.split('.djvu/')[0] + '.djvu'
    if ':' in title:
        title = title.split(':')[1]
    return title

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

def edit_page(page_id, page_content, url, lang, labels):
    # Load credentials from config file
    config = ConfigParser()
    config.readfp(open(r'config.ini'))
    username = config.get('credentials', 'username')
    password = config.get('credentials', 'password')

    # Ask for user login/password if necessary
    if not username or not password:
        username = input('Bot username: ')
        password = getpass('Password: ')
    print(' logging in as {}...'.format(username))

    session = requests.Session()
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
    assert (resp1.json()['login']['result'] == 'Success'), 'Failed to log in'
    print('Login successful')

    # Request edit token
    print(' getting edit token....')
    resp2 = session.get(url, params = {
                'action': 'query',
                'meta': 'tokens',
                'type': 'csrf',
                'format': 'json'})
    #TODO: assert token successful

    # Edit page
    changes = []
    for old, new in zip(labels.keys(), labels.values()):
        changes.append(old + '→' + new)
    summary = edit_summary[lang] + ' (' + ', '.join(changes) + ')'
    resp3 = session.post(url, data = {
                'action': 'edit',
                'pageid': page_id,
                'text': page_content,
                'summary': summary,
                'format': 'json',
                'utf8': '',
                'bot': 1,
                'token': resp2.json()['query']['tokens']['csrftoken']})
    #TODO: assert edit successful

if __name__ == '__main__':
    run()
