# !/usr/local/bin/python3
# -*- coding: utf-8 -*-

import json
import requests
import time
import redis
import re
import logging
import sys
from configparser import ConfigParser
from localizations import template, edit_summary

global proc_name, stop_button, user, pssw, redb, debug_mode, debug_fp
debug_fp = 'debug_edits.html'
proc_name = 'worker'
stop_button = True  # While true bot will not edit any pages

logger = logging.getLogger('worker')
_h = logging.FileHandler('logs/worker.log')
_h.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
logger.addHandler(_h)
logger.setLevel(logging.INFO)
logger.propagate = False

#TODO extend sleaping time to avoid edit conflict

def main(db_params, debug=False, username=None, password=None):
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
    # Check if we run in dubug mode
    global debug_mode, user, pssw
    if debug:
        debug_mode = True
        user = None
        pssw = None
    else:
        debug_mode = False
        user = username
        pssw = password
    # Open Redis
    global redb
    redb = open_redis(db_params)
    set_redis_status('running')

    logger.info('[MAIN] Starting worker in {} mode'.format('DEBUG' if \
        debug_mode else 'NORMAL'))

    while True:
        # See if there is new data:
        if not redb.get('empty'):
            # Make sure 'empty' is set in Redis
            lock_redis()
            redb.set('empty', 1)
            lock_redis(unlock=True)
        elif not int(redb.get('empty')):
            # Means not empty, so continue
            data = json.loads(redb.get('lstdata').decode('utf-8'))
            lock_redis()
            redb.delete('lstdata')
            redb.set('empty', 1)
            lock_redis(unlock=True)
            logger.info('[MAIN] Loaded new data from Redis DB. Checking labels.')
            check_saved_data(data)
        # Sleep 5 minutes and in between check redis status
        for i in range(10): #TODO set 100
            time.sleep(3)
            green_light = check_redis_status()
            if not green_light:
                # Means stop signal received
                logger.info('[MAIN] Stop signal received. Stopping.')
                # TODO before exiting check redis data again?
                set_redis_status('stopped')
                sys.exit(0)


def open_redis(db_params):
    host, port, id = db_params
    try:
        r = redis.StrictRedis(host, port, id)
        r.client_list()
    except:
        logger.warning('[OPEN_REDIS] Unable to open Redis DB (host: {}, port:'\
        ' {}, db: {}). Terminating'.format(host, port, id))
        sys.exit(1)
    else:
        logger.info('[OPEN_REDIS] Redis DB running OK (host: {}, port: {}, ' \
        'db: {})'.format(host, port, id))
        return r


def set_redis_status(status):
    lock_redis()
    redb.set('{}_status'.format(proc_name), status)
    lock_redis(unlock=True)
    logger.info('[SET REDIS STATUS] Set status to {}'.format(status.upper()))


def check_redis_status():
    status = redb.get('{}_status'.format(proc_name)).decode('utf-8')
    return False if status == 'stopping' else True


def lock_redis(unlock=False):
    if unlock:
        redb.set('locked', 0)
    else:
        # Check if locked is set
        if not redb.get('locked'):
            redb.set('locked', 0 if unlock else 1)
        elif int(redb.get('locked')):
            logger.info('[LOCK_REDIS] Waiting 10s for Redb to unlock')
            waited = 0
            while (int(redb.get('locked'))):
                sleep(0.01)
                waited += 1
                if waited > 10000: # we waited 100s
                    logger.warning('[LOCK_REDIS] Unable to lock Redb. ' \
                    'Terminating.')
                    sys.exit(1)
            logger.info('[LOCK_REDIS] Unlocked after {}s'.format(waited/100))
        redb.set('locked', 1)


def check_saved_data(data):
    """
    Checks if the pages in input have transclusions and if labels in those
    transclusions need to be corrected.

    Input:
        data - list of dicts with the following items:
            url     - API of the project
            lang    - language of the project
            title   - title of the page
            labels  - dict with changed labels (key: old, value: new)

    If page has transclusions and labels need to be updated, calls edit_page()
    or edit_debug_mode() if we are in debug mode.
    """
    for page in data:
        edits = 0
        transclusions = get_transclusions(page['title'], page['url'])
        if not transclusions:
            logger.info('[CHECK SAVED DATA] No transclusions in [{}]. Pass.' \
                .format(page['title']))
        else:
            logger.info('[CHECK SAVED DATA] Found {} transclusions for [{}].' \
                ' Checking...'.format(len(transclusions), page['title']))
            for transclusion in transclusions:
                # Get source code of transcluding page
                tr_content = get_pagecontent(page['url'], transclusion[0])
                if tr_content:
                    # Update lables in content if necessary
                    new_content, corrected_labels = fix_transclusion(tr_content, \
                        page['title'],page['labels'],page['lang'])
                    if new_content:
                        # Means labels need to be updated
                        edit_sum,labels_sum = compose_summary(corrected_labels,\
                            page['lang'])
                        summary = '{} {}'.format(edit_sum, labels_sum)
                        # TODO having both edit_sum and summary is a bit confusing
                        if debug_mode:
                            edited = edit_debug_mode(transclusion[1], page, \
                                labels_sum)
                            if edited:
                                edits += 1
                        else:
                            edited = edit_page(page['url'], transclusion[0], \
                                new_content, summary)
                            if edited:
                                edits += 1
                    else:
                        # Means no edit necessary
                        logger.info('[CHECK SAVED DATA] No edit necessary in' \
                            ' [{}]. Skipping'.format(transclusion[1]))
        # Update log for current page
        if edits:
            logger.info('[CHECK SAVED DATA] Done checking [{}]. In total {} ' \
            'corrections were made in {} transclusions.'.format(page['title'], \
            edits,len(transclusions)))
        else:
            logger.info('[CHECK SAVED DATA] Done checking [{}] with {} ' \
                'transclusion(s). No corrections are necessary'.format \
                (page['title'], len(transclusions)))
    # Update log for current sessions
    logger.info('[CHECK SAVED DATA] Ending session. Checked transclusions of' \
        ' {} pages.'.format(len(data)))


def edit_debug_mode(transclusion, page, labels_sum):
    # Define data to write in file
    write_data = []
    # Timestamp
    write_data.append('\n\n<br/><br/>{}\n'.format(time.ctime()))
    # Url of the project
    base_url = page['url'].split('/')[2]
    write_data.append('<b>{}</b>\n'.format(base_url))
    # Page with changed labels
    original_page_url = 'https://{}/wiki/{}'.format(base_url,page['title'])
    write_data.append('Original page: <a href="{}">{}</a>\n'.format \
        (original_page_url,page['title']))
    # Page that should be edited
    target_page_url = 'https://{}/wiki/{}'.format(base_url,transclusion)
    write_data.append('Page to edit: <a href="{}">{}</a>\n'.format \
        (target_page_url,transclusion))
    # Labels to be updated
    write_data.append(labels_sum)
    try:
        with open(debug_fp, 'a') as f:
            f.write('<br />'.join(write_data))
    except:
        logger.warning('[EDIT DEBUG MODE] Failed to edit debug_mode file '\
            '[{}]'.format(debug_fp))
        return False
    else:
        return True


def set_status_on_wiki(url, status):
    """
    Updates bot status on bot subpage (in edited wiki project).
    Calls check_stopbutton() to update Stop button status.
    Will not edit if button is ON or status page is not created.
    """
    if not debug_mode:
        usr = user.split('@')[0]
        page = 'User:' + usr + '/status'
        button_exists = check_stopbutton(url, page)
        if button_exists and not stop_button:
            content = get_pagecontent(url, page)
            status_template = '{{User:' + usr + '/status/' + status + '}}'
            already_set = False
            #TODO make sure template page exists and localize
            if content:
                for line in content.splitlines():
                    if status_template in line:
                        already_set = True
            if not already_set:
                #TODO localize summary
                summary = 'Setting bot status to {}.'.format(status)
                edit = edit_page(url, page, status_template, summary, force=True)
                if edit: # Means edit was succes
                    logger.info('[SET STATUS ON WIKI] Set bot status to {} ' \
                        'in subpage [{}]'.format(status.upper(), page))


def check_stopbutton(url, page):
    """
    Check user status page to see if user is allowed to edit.
    If first line of the status page contains "stop", stop_button is ON.
    This allows off-line control over the bot. If stop_botton is ON no edits
    will be made.

    Updates global stop_button.
    Returns True if status page exists, otherwise False.
    """
    global stop_button
    content = get_pagecontent(url, page)
    # Page doesn't exist
    if not content:
        stop_button = False
        return False
    # Page exists and stop botton is ON
    elif 'stop' in content.splitlines()[0].lower():
        stop_button = True
    # Stop botton is OFF
    else:
        stop_button = False
    return True


def get_transclusions(title, url):
    """
    Checks if page has transclusions. Returns a list of tuples if so, otherwise
    None. Tuple is pair of page-id and title.
    """
    parameters = {  'action': 'query',
                    'prop': 'transcludedin',
                    'titles': title,
                    'format': 'json',
                    'utf8': '',
                    'tinamespace': '*'} #TODO change ns to 0?
    try:
        resp = (requests.get(url, params = parameters))
        js = json.loads(resp.content.decode('utf-8'))
        pid = [p for p in js['query']['pages'].keys()][0]
        transclusions = js['query']['pages'][pid]
    except:
        logger.warning('[GET TRANSCLUSIONS] Unable to get transcusions of ' \
            '[{}]. Unexpected or no reply from API [{}]'.format(title,url))
        return None
    else:
        if 'transcludedin' in transclusions.keys():
            return [(page['pageid'],page['title']) for page in \
                transclusions['transcludedin']]
        return None


def fix_transclusion(page_content, title, labels, lang):
    """
    Checks if transclusion contains old labels and updates them in provided
    page content. Three transclusion styles are checked consecutively, although
    only the first is widely used in wiki projects.

    Regex is used to make sure that labels are corrected only where necessary
    (the page can for example transclude more than one pages).

    Input:
        page_content    - content of transcluding page
        title           - title of transcluded page
        changed labels  - labels that were changed in transcluded page
        lang            - language of project

    Returns:
        Tuple         - if updates were made, tuple contains:
            string    - updated page content
            dict      - updated labels (key: old, value: new)
        Both values will be None if no changes are necessary.
    """
    page_content = page_content.splitlines()
    title = clean_title(title) # Remove subpage and namespace from title
    corrected_labels = {}
    edited = False

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
                            edited = True
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
                            edited = True
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
                            edited = True
                            del match

    page_content = '\n'.join(page_content)
    if edited:
        return page_content, corrected_labels
    return None, None


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

    Input:
        url     - API of the project
        page    - Can be either title (string) or ID (int).

    Returns a single string if page exists, otherwise None.
    """
    parameters = {  'action': 'query',
                    'prop': 'revisions',
                    'rvprop': 'content',
                    'format': 'json',
                    'utf8': '' }

    # Is 'page' title or page id?
    if type(page) is int:
        parameters['pageids'] = page
    elif type(page) is str:
        parameters['titles'] = page
    else:
        logger.warning('[GET PAGECONTENT] Argument [{}] has invalid type ' \
            '[{}]. Expected int or str'.format(page,type(page)))
        return None

    try:
        resp = requests.get(url, params = parameters)
        js = json.loads(resp.content.decode('utf-8'))
    except:
        logger.warning('[GET PAGECONTENT] Unable to get content of [{}]. ' \
            'Unexpected or no reply from API [{}].'.format(page,url,))
    else:
        pid = [p for p in js['query']['pages'].keys()][0]
        if 'revisions' in js['query']['pages'][pid].keys():
            return js['query']['pages'][pid]['revisions'][0]['*']
        else:
            logger.warning('[GET PAGECONTENT] Unable to get content of [{}].' \
                ' API response: [{}]'.format(page,js['query']['pages'][pid]))
            return None


def edit_page(url, page, page_content, summary, force=False):
    """
    Edit wiki-page using provided credentials.

    Input:
        url             - API of the project
        page            - can be either title (string) or ID (int).
        page_content    - string
        summary         - string, edit summary

    Returns:
        True            - if edit was success
        False           - edit didn't succeed
    """
    if not force:
        set_status_on_wiki(url, 'active')
        if stop_button:
            base_url = url.split('/')[2]
            logger.info('[EDIT PAGE] Stop button is ON. No edits will be made '\
                'until it is turned OFF again.'.format(base_url))
            return False

    # Continue in normal mode
    logger.info('[EDIT PAGE] Preparing to edit page [{}] through API [{}]' \
        .format(page,url))
    session = requests.Session()

    # Step 1: Request login token
    logger.info('[EDIT PAGE] Logging in as [{}] in [{}]'.format(user, url))
    params = {  'action': 'query',
                'meta': 'tokens',
                'type': 'login',
                'format': 'json' }
    try:
        resp = session.get(url, params = params).json()
    except:
        logger.warning('[EDIT PAGE] Unable to get login token. Unexpected ' \
            'or no API response: {}'.format(resp if resp else 'None'))
        return False
    else:
        if not resp['query'] or not 'tokens' in resp['query']:
            logger.warning('[EDIT PAGE] Login token request rejected. API ' \
            'response: [{}]'.format(resp if resp else 'None'))
            return False
        login_token = resp['query']['tokens']['logintoken']
        del resp

    # Step 2: Login
    logindata = {'action': 'login',
                'format': 'json',
                'lgname': user,
                'lgpassword': pssw,
                'lgtoken': login_token }
    try:
        resp = session.post(url, data = logindata).json()
    except:
        logger.warning('[EDIT PAGE] Unable to login to project. Unexpected ' \
            'or no API response: {}'.format(resp if resp else 'None'))
        return False
    else:
        if not resp['login'] or resp['login']['result'] != 'Success':
            logger.warning('[EDIT PAGE] Log-in request rejected. API ' \
            'response: [{}]'.format(resp if resp else 'None'))
            return False
        del resp

    # Step 3: Request edit token
    logger.info('[EDIT PAGE] Getting edit token....')
    params['type'] = 'csrf'
    try:
        resp = session.get(url, params = params).json()
    except:
        logger.warning('[EDIT PAGE] Unable to get edit token. Unexpected or' \
            ' no API response: {}'.format(resp if resp else 'None'))
        return False
    else:
        if not resp or not 'tokens' in resp['query']:
            logger.warning('[EDIT PAGE] Edit token request rejected. API ' \
                'response: [{}]'.format(resp if resp else 'None'))
            return False
        edit_token = resp['query']['tokens']['csrftoken']
        del resp

    # Step 4: Edit page
    editdata = {'action': 'edit',
                'text': page_content,
                'summary': summary,
                'format': 'json',
                'utf8': '',
                'bot': 1,
                'token': edit_token }
    if type(page) is int:
        editdata['pageid'] = page
    elif type(page) is str:
        editdata['title'] = page
    else:
        logger.warning('[EDIT PAGE] Argument [{}] has invalid type [{}]. ' \
            'Expected int or str. Aborting edit.'.format(page,type(page)))
        return False

    try:
        resp = session.post(url, data = editdata).json()
        result = resp['edit']['result']
    except:
        logger.warning('[EDIT PAGE] Edit request rejected. API response: [{}]'\
            .format(resp if resp else 'None'))
        return False
    else:
        if result == 'Success':
            logger.info('[EDIT PAGE] Page [{}] edited successfully.'.format(page))
            return True
        else:
            logger.warning('[EDIT PAGE] Edit of page [{}] failed. API ' \
                'response: [{}]'.format(page, resp if resp else 'None'))
            return False


def compose_summary(labels, lang):
    """
    Generates summary in local language with the labels that were changed.

    Returns tuple of two strings: edit_summary and changed labels
    """
    changes = []
    for old, new in zip(labels.keys(), labels.values()):
        changes.append(old + '→' + new)
    labels_summary = '({})'.format(', '.join(changes))
    return edit_summary[lang], labels_summary
