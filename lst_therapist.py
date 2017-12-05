# !/usr/local/bin/python3
# -*- coding: utf-8 -*-

import json, requests, time, redis, re
from getpass import getpass
from configparser import ConfigParser
from localizations import template, edit_summary

global stop_button, username, password
config = ConfigParser()
config.readfp(open(r'config.ini'))
username = config.get('credentials', 'username')
password = config.get('credentials', 'password')
stop_button = True # Bot will not edit actual pages if this is True


def run():
    """
    Main Routine.
    Wakes up every 5 minutes to read new data from Redis. If there is new data,
    will call check_saved_data() otherwise will sleep again.

    The variables read from Redis:
    locked - means others are editing data
    empty - means no data
    lstdata - the data, list with dicts

    empty and locked are strings, since Redis has no boolean types.
    """
    try:
        r = redis.StrictRedis(host='localhost', port=7777, db=0)
        check_credentials()
        while True:
            if r.get('locked'): # Check if 'locked' is set in Redis
                while int(r.get('locked')): # Wait if locked
                    time.sleep(0.01)
            if not r.get('empty'): # Make sure 'empty' is set in Redis
                r.set('empty', 1)
            if not int(r.get('empty')): # Continue if not empty
                r.set('locked', 1)
                data = json.loads(r.get('lstdata').decode('utf-8'))
                r.delete('lstdata')
                r.set('empty', 1)
                r.set('locked', 0)
                print('Checking saved labels...')
                check_saved_data(data)
                time.sleep(300)
            else:
                time.sleep(300)
    except(KeyboardInterrupt, SystemExit):
        #TODO exit gracefully
        raise


def check_saved_data(data):
    """
    Checks if transclusions of pages need to be corrected.
    Saved data must be a list of dicts, each corresponding to a wiki-page.
    If page has transclusions and they need to be updated (with new label names),
    calls edit_page() to edit transclusions and reports outcome in log.txt.

    Each dict must contain the following information about the wiki-page:
    url - the API url of the wiki project
    lang - language of the project
    title - title of the page
    labels - dict containing changed labels as {'old':'new'}.
    """
    for page in data:
        corrections = 0
        transclusions = get_transclusions(page['title'], page['url'])
        if not transclusions:
            print(' No transclusions of "{}": PASS'.format(page['title']))
        else:
            print(' Checking {} transclusion(s) of "{}"...'.format
                (len(transclusions), page['title']))
            for transclusion in transclusions:
                # Get source code of transcluding page
                page_content = get_pagecontent(page['url'], transclusion)
                if not page_content: # Means page not found
                    print(' Error. Page not found. PASS')
                else:
                # Update lables in content if necessary
                    page_content, corrected_labels = (fix_transclusion
                        (page_content, page['title'], page['labels'],
                        page['lang']))
                    if page_content: # Means labels were updated
                        set_status_on_wiki(page['url'], 'active')
                        edit_sum, labels_sum = (compose_summary
                            (corrected_labels, page['lang']))
                        summary = '{} {}'.format(edit_sum, labels_sum)
                        edit = edit_page(page['url'], transclusion,
                            page_content, summary)
                        if edit: # Means edit was succesful
                            print(' 1 transclusion corrected! DONE')
                            corrections += 1
                    else: # Means no edit necessary
                        print(' No corrections made. PASS')
        # Update log
        with open('log.txt', 'a') as file:
            page_url = page['url'].replace('w/api.php', 'wiki/')
            edit_sum,labels_sum = compose_summary(page['labels'], page['lang'])
            log = ('\n\n{}:\n\n{}\n{}{}\n{}\n{} transclusion(s) found\n{}'
                ' correction(s) made'.format(time.ctime(), page['title'],
                page_url, page['title'], labels_sum[1:-1],
                str(len(transclusions)), str(corrections)))
            file.write(log)


def set_status_on_wiki(url, status):
    """
    Updates bot status on bot subpage (in edited wiki project).
    Calls check_stopbutton() to update Stop button status.
    Will not edit if button is ON or status page is not created.
    """
    user = username.split('@')[0]
    page = 'User:' + user + '/status'
    button_exists = check_stopbutton(url, page)
    if button_exists and not stop_button:
        content = get_pagecontent(url, page)
        status_template = '{{User:' + user + '/status/' + status + '}}'
        already_set = False
        for line in content.splitlines():
            if status_template in line:
                already_set = True
        if not already_set:
            summary = 'Setting bot status to {}.'.format(status) #TODO:localize
            edit = edit_page(url, page, status_template, summary)
            if edit: # Means edit was succes
                print(summary)



def check_stopbutton(url, page):
    """
    Check user status page to see if user is allowed to edit.
    If the first line of the status page contains "stop", we consider this as
    "Stop button". This way wiki-users can immediately stop the bot if it's
    malfunctioning.
    Returns true if status page exists, otherwise false.
    """
    global stop_button
    print('Checking user stop button...')
    content = get_pagecontent(url, page)
    if not content: # Means page doesn't exist
        stop_button = False
        return False
    elif 'stop' in content.splitlines()[0].lower():
        print('stop button on')
        stop_button = True
    else:
        stop_button = False
    return True


def get_transclusions(title, url):
    """
    Checks if page has transclusions. If yes, return their page IDs.
    """
    parameters = {  'action': 'query',
                    'prop': 'transcludedin',
                    'titles': title,
                    'format': 'json',
                    'utf8': '',
                    'tinamespace': '*'} #TODO change ns to 0?
    resp = (requests.get(url, params = parameters))

    js = json.loads(resp.content.decode('utf-8'))
    #TODO: throw keyerror when: js = {'batchcomplete': '',
        #'warnings': {'main': {'*': 'Unrecognized parameter: pageid.'}}}
    pid = [p for p in js['query']['pages'].keys()][0]
    transclusions = js['query']['pages'][pid]
    if 'transcludedin' in transclusions.keys():
        return [page['pageid'] for page in transclusions['transcludedin']]
    return None # Means no transclusions


def fix_transclusion(page_content, title, labels, lang):
    """
    Checks if transclusion contains old label names and updates them.
    Three transclusion styles are checked consecutively, although only the
    first is widely used in wiki projects.

    Regex is used to make sure that labels are corrected only where necessary
    (the page can for example transclude more than one pages).

    Returns updated page content and a the labels that were corrected as two
    values (string and dict).
    """
    page_content = page_content.splitlines()
    title = clean_title(title) # Remove subpage and namespace from title
    corrected_labels = {}
    edit = False

    for line in page_content:
        if title in line:
            index = page_content.index(line) # Remember index of each line

            # Case 1: HTML syntax for transclusion
            if line.startswith('<pages index'):
                for label in labels.keys():
                    if label in line:
                        # Check if transclusion template uses old label
                        pattern = (r'(<pages index\s?=\s?"?{}"?\s.*?fromsection'
                            '\s?=\s?"?)({}|.*)("?\s?tosection\s?=\s?"?)({}|.*)'
                            '("?\s?/>)'.format(re.escape(title), label, label))
                        match = re.search(pattern, line)
                        if match:
                            # Replace old label(s) with new label
                            line = (re.sub(r'([from|to]section\s?=\s?"?){}'
                                .format(label), r'\1{}'.format(labels[label]),
                                line, count=2))
                            page_content[index] = line
                            corrected_labels[label] = labels[label]
                            edit = True
                            del match

            # Case 2: Mediawiki syntax
            if line.startswith('{{#lst:') or line.startswith('{{#lstx'):
                for label in labels.keys():
                    if label in line:
                        pattern = (r'({{#lstx?:)(\w+:)?({})(/\d*)?([|]{})(}})'
                            .format(title, label))
                        match = re.search(pattern, line)
                        if match:
                            line = re.sub(pattern, r'\1\2\3\4|{}\6'.format
                                (labels[label]), line)
                            page_content[index] = line
                            corrected_labels[label] = labels[label]
                            edit = True
                            del match

            # Case 3: template used for transclusion
            if template[lang] and line.lower().startswith(template[lang][0]):
                for label in labels.keys():
                    if label in line:
                        pattern = (r'({}{})(/\d*)?(.*?)([|])(\w+)(\s?=\s?)({})'
                            '(.*?}}$)'.format(template[lang][1], title, label))
                        match = re.match(pattern, line)
                        if match and match.group(5) in template[lang][2:]:
                            line = (re.sub(pattern, r'\1\2\3\4\5\6{}\8'.format
                                (labels[label]), line))
                            page_content[index] = line
                            corrected_labels[label] = labels[label]
                            edit = True
                            del match

    page_content = '\n'.join(page_content)
    if edit == True:
        return page_content, corrected_labels
    return None, None # Means no edit in page necessary


def clean_title(title):
    """
    Removes namespace and subpages from title.
    (Transclusion templates use titles without those).
    """
    if ':' in title: # Means there is namespace
        title = re.sub(r'^(\w+:)(\S.*)$', r'\2', title, count=1)
    if '.djvu/' in title or '.pdf/' in title: # Means there is subpage
        title = re.sub(r'(^.*\.)(djvu|pdf)(/\d+$)', r'\1\2', title, count=1)
    return title


def get_pagecontent(url, page):
    """
    Retrieves page content with an API request to Wikimedia server.
    Page can be either page title (string) or page ID (int).
    """
    parameters = {  'action': 'query',
                    'prop': 'revisions',
                    'rvprop': 'content',
                    'format': 'json',
                    'utf8': '' }

    # Check to see if 'page' is title or pageid
    if type(page) == int:
        parameters['pageids'] = page
    else:
        parameters['titles'] = page

    resp = (requests.get(url, params = parameters))
    if resp.status_code != 200:
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    pid = [p for p in resp.json()['query']['pages'].keys()][0]
    if pid == '-1': # Means page not found
        return None
    content = resp.json()['query']['pages'][pid]['revisions'][0]['*']
    return content

def check_credentials():
    """
    Check if user credentials are imported from config file.
    If not ask for input.
    """
    global username, password
    # Ask for user login/password if necessary
    if not username or not password:
        username = input('Bot username: ')
        password = getpass('Password: ')


def edit_page(url, page, page_content, summary):
    """
    Login and edit wiki-page with API request.
    Returns true if edit was success, otherwise false.
    """
    if stop_button:
        print('Stop button ON: Aborting all edits')
        return False
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
    result = resp.json()['edit']['result']
    assert result == 'Success', 'Failed to edit page'
    if result == 'Success':
        return True
    return False


def compose_summary(labels, lang):
    """
    Generates summary in local language with the labels that were changed.
    """
    changes = []
    for old, new in zip(labels.keys(), labels.values()):
        changes.append(old + '→' + new)
    labels_summary = '({})'.format(', '.join(changes))
    return edit_summary[lang], labels_summary
