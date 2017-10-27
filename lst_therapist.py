# !/usr/local/bin/python3
# -*- coding: utf-8 -*-

import json, requests, time, redis
from getpass import getpass
from configparser import ConfigParser
from localizations import template, edit_summary

global stop_button, username, password
config = ConfigParser()
config.readfp(open(r'config.ini'))
username = config.get('credentials', 'username')
password = config.get('credentials', 'password')
stop_button = 'On' # Don't start editing without checking stop button

def run():
    r = redis.StrictRedis(host='localhost', port=7777, db=0)
    while True:
        if r.get('locked'): # Make sure 'locked' is set in Redis
            while int(r.get('locked')): # Wait if 'locked' is true
                time.sleep(0.01)
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
        set_status_on_wiki(item['url'], 'active')
        transclusions = get_transclusions(item['title'], item['url'])
        if len(transclusions) == 0:
            print(' No transclusions of "{}": PASS'.format(item['title']))
        else:
            for transclusion in transclusions:
                print(' Checking 1 transclusion of "{}"...'.format(item['title']))
                # Get source code of transcluding page
                page_content = get_pagecontent(item['url'], transclusion)
                # Updates section names if necessary, otherwise retruns empty string
                page_content, corrected_labels = fix_transclusion(page_content, item['title'], item['labels'], item['lang'])
                if page_content == '':
                    print(' No corrections made. PASS')
                else:
                    summary = compose_edit_summary(corrected_labels, item['lang'])
                    edit_page(item['url'], transclusion, page_content, summary) #TODO: Return something to indicate edit was success/fail
                    corrections += 1
                    print(' 1 transclusion corrected! DONE')
        with open('log.txt', 'a') as file:
            file.write(item['lang'] + '\n' + item['title'] + '\n' + str(len(transclusions)) + ' transclusions' + '\n' + str(corrections) + ' corrections' + '\n\n')
        time.sleep(120)
        set_status_on_wiki(item['url'], 'standby')

def set_status_on_wiki(url, status):
    user = username.split('@')[0]
    button_exists = check_stopbutton(url, user)
    if button_exists and stop_button == 'Off':
        page = 'User:' + user + '/status'
        content = get_pagecontent(url, page)
        status_template = '{{User:' + user + '/status/' + status + '}}'
        already_set = False
        for line in content.splitlines():
            if status_template in line:
                already_set = True
        if not already_set:
            summary = 'Setting bot status' # For now only used for English wikisource
            edit_page(url, page, status_template, summary)

def check_stopbutton(url, username): # Returns true/false if button page exists or not
    global stop_button
    page = 'User:' + username + '/status'
    content = get_pagecontent(url, page)
    if not content: # Means page doesn't exist
        stop_button = 'Off'
        return False
    elif 'stop' in content.splitlines()[0].lower():
        stop_button = 'On'
    else:
        stop_button = 'Off'
    return True

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
    page_content = page_content.splitlines()
    corrected_labels = {}
    edit = False
    title = clean_title(title) # Get rid of namespace or subpage

    for line in page_content:
        if title in line:
            index = page_content.index(line) #Remember location of each line

            # Case 1: HTML syntax for transclusion
            if line.startswith('<pages index'):
                for label in labels.keys():
                    if label in line:
                        pattern = r'(<pages index\s?=\s?"?{}"?\s.*?fromsection\s?=\s?"?)({}|.*)("?\s?tosection\s?=\s?"?)({}|.*)("?\s?/>.*$)'.format(title, label, label)
                        match = re.match(pattern, line)
                        if match:
                            line = re.sub(r'([from|to]section\s?=\s?"?){}'.format(label), r'\1{}'.format(labels[label]), line, count=2)
                            page_content[index] = line
                            corrected_labels[label] = labels[label]
                            edit = True
                            del match

            # Case 2: Mediawiki syntax
            if line.startswith('{{#lst:') or line.startswith('{{#lstx'):
                for label in labels.keys():
                    if label in line:
                        pattern = r'({{#lstx?:)(\w+:)?({})(/\d*)?([|]{})(}})'.format(title, label)
                        match = re.search(pattern, line)
                        if match:
                            line = re.sub(pattern, r'\1\2\3\4|{}\6'.format(labels[label]), line)
                            page_content[index] = line
                            corrected_labels[label] = labels[label]
                            edit = True
                            del match

            # Case 3: template used for transclusion
            if template[lang] and line.lower().startswith(template[lang][0]):
                for label in labels.keys():
                    if label in line:
                        pattern = r'({}{})(/\d*)?(.*?)([|])(\w+)(\s?=\s?)({})(.*?}}$)'.format(template[lang][1], title, label)
                        match = re.match(pattern, line)
                        if match and match.group(5) in template[lang][2:]:
                            line = re.sub(pattern, r'\1\2\3\4\5\6{}\8'.format(labels[label]), line)
                            page_content[index] = line
                            corrected_labels[label] = labels[label]
                            edit = True
                            del match

    page_content = '\n'.join(page_content)
    if edit == True:
        return page_content, corrected_labels
    return '', '' # Return two empty strings if no edit in page necessary

def clean_title(title):
    # Remove namespace
    if ':' in title:
        title = re.sub(r'^(\w+:)(\S.*)$', r'\2', title, count=1)
    # Remove subpage number
    if '.djvu/' in title or '.pdf/' in title:
        title = re.sub(r'(^.*\.)(djvu|pdf)(/\d+$)', r'\1\2', title, count=1)
    return title

def get_pagecontent(url, page):
    parameters = {  'action': 'query',
                    'prop': 'revisions',
                    'rvprop': 'content',
                    'format': 'json',
                    'utf8': '' }
    if type(page) == int:
        parameters['pageids'] = page
    else:
        parameters['titles'] = page
    resp = (requests.get(url, params = parameters))
    if resp.status_code != 200:
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    pid = [p for p in resp.json()['query']['pages'].keys()][0]
    if pid == '-1':
        return ''
    content = resp.json()['query']['pages'][pid]['revisions'][0]['*']
    return content

def check_credentials():
    # Ask for user login/password if necessary
    if not username or not password:
        username = input('Bot username: ')
        password = getpass('Password: ')

def edit_page(url, page, page_content, summary):
    if stop_button == 'On':
        print('Stop button ON: Aborting all edits')
        return None
    print(' logging in as {}...'.format(username))
    session = requests.Session()

    # Request login token
    params = {  'action': 'query',
                'meta': 'tokens',
                'type': 'login',
                'format': 'json' }
    resp = session.get(url, params = params)
    resp.raise_for_status()
    assert 'tokens' in resp.json()['query'], 'Failed to get login token'

    # Login
    logindata = {'action': 'login',
                'format': 'json',
                'lgname': username,
                'lgpassword': password,
                'lgtoken': resp.json()['query']['tokens']['logintoken'] }
    resp = session.post(url, data = logindata)
    resp.raise_for_status()
    assert resp.json()['login']['result'] == 'Success', 'Failed to log in'

    # Request edit token
    print(' getting edit token....')
    params['type'] = 'csrf'
    resp = session.get(url, params = params)
    resp.raise_for_status()
    assert 'tokens' in resp.json()['query'], 'Failed to get edit token'

    # Edit page
    editdata = {'action': 'edit',
                'text': page_content,
                'summary': summary,
                'format': 'json',
                'utf8': '', 'bot': 1,
                'token': resp.json()['query']['tokens']['csrftoken'] }
    if type(page) == int:
        editdata['pageid'] = page
    else:
        editdata['title'] = page
    resp = session.post(url, data = editdata)
    resp.raise_for_status()
    assert resp.json()['edit']['result'] == 'Success', 'Failed to edit page'

def compose_edit_summary(labels, lang):
    changes = []
    for old, new in zip(labels.keys(), labels.values()):
        changes.append(old + '→' + new)
    return edit_summary[lang] + ' (' + ', '.join(changes) + ')'
