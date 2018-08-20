#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import requests
import time
import re
import redis
import logging
import sys
from sseclient import SSEClient as EventSource
from localizations import section_label

global redb, redb_params

logging.basicConfig(
            filename='logs/poller.log',
            level=logging.INFO,
            format='%(asctime)s:%(levelname)s:%(message)s')


def run(proj, langs, db_params):
    """
    Main routine. Reads the recent changes stream from EventSource (includes
    edits from all wikimedia projects), filters out edits in the specified
    project and langauge(s) and sends further through the pipline to check
    for modified section labels.

    Required arguments:
    - proj (string)             - the Wikimedia project to watch on
    - langs (list of strings)   - the language versions of project

    After each 100 edits, checks redis status, if stop signal is received will
    exit.
    """
    # Open Redis
    open_redis(db_params)
    set_redis_status('running')

    # Start watching recent changes
    logging.info('[RUN] Watching recent changes in {} ({})'.format(proj, \
        ', '.join(langs)))
    stream_url = 'https://stream.wikimedia.org/v2/stream/recentchange'
    stream_count = 0
    checked_count = 0
    for event in EventSource(stream_url):
        stream_count+=1
        if event.event == 'message':
            try:
                item = json.loads(event.data) # Create dict with edit details
            except ValueError:
                logging.warning('[RUN] Unable to parse event data. Skipping')
            else:
                # split server url to get language and project
                server = item['server_name'].split('.')
                # Filter out edits in specified project and language(s)
                if server[1] == proj and server[0] in langs and item['type'] \
                    == 'edit' and item['namespace'] == 104:
                    logging.info('[RUN] Checking new revision in page [{}] ' \
                        '({}).'.format(item['title'], server[0]))
                    check_edit(item)
                    checked_count += 1
                # Do checks every 100 edits
                if not (stream_count%100):
                    green_light = check_redis_status()
                    # Means stop signal received
                    if not green_light:
                        logging.info('[RUN] In total {} edits checked out of ' \
                        ' {}'.format(checked_count, stream_count))
                        set_redis_status('stopped')
                        logging.info('[RUN] Stop signal received. Stopping.')
                        sys.exit(0)
                # Log every 10000 edits
                if not (stream_count%10000):
                    logging.info('[RUN] So far {} edits checked out of {}' \
                        .format(checked_count, stream_count))


def open_redis(db_params):
    host, port, id = db_params
    global redb
    try:
        r = redis.StrictRedis(host=redb_host, port=redb_port, db=redb_id)
        r.client_list()
    except:
        logging.warning('[OPEN_REDIS] Unable to open Redis DB (host: {}, port:'\
        ' {}, db: {}). Terminating'.format(host, port, id))
        sys.exit(1)
    else:
        redb = r
        logging.info('[OPEN_REDIS] Redis DB running OK (host: {}, port: {}, ' \
        'db: {})'.format(host, port, id))


def set_redis_status(status):
    lock_redis()
    redb.set('poller_status', status)
    lock_redis(unlock=True)
    logger.info('[SET_REDIS_STATUS] Set status to {}'.format(status.upper()))


def check_redis_status():
    status = redb.get('poller_status')
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


def check_edit(item):
    """
    Parses the required parameters and psses data over to check_revision() which
    does the actual checking. If changed labels are detected calls write_data()
    to save edit data in Redis.

    Argument:
    item (dict) - should contain the following:
        revision - dict with revision IDS as {'old':int,'new':int}
        server_url - eg. https://es.wikipedia.org
        server_name - eg. es.wikipedia.org
        title - title of edited page
        lang - language of project (eg. 'en')
    """
    revids = item['revision']
    url = item['server_url'] + '/w/api.php'
    lang = item['server_name'].split('.')[0]

    # See if there are changed labels in revision (returns a dict)
    changed_labels = check_revision(revids, url, lang)

    # If there are any changed labels, write data to Redis
    if changed_labels:
        logger.info('[CHECK_EDIT] {} changed label(s) detected in []' \
            .format(len(changed_labels), item['title']))
        data = {    'title': item['title'],
                    'lang': lang,
                    'url': url,
                    'labels': changed_labels }
        write_data(data)


def check_revision(revids, url, lang):
    """
    Compares the old and new versions of the page. Then compares the number of
    section labels in both, if equal, assumes those labels correspond to each
    other.

    Arguments:
        revids  - Dict with revision ids (two items: 'old' and 'new', both int)
        url     - API reference point
        lang    - Language of the project

    Returns:
        Dict with modified labels: old label as key, new label as value. (Dict
        is empty if are no modified labels were found.)
    """
    old_text, new_text = get_diff(revids, url)
    old_labels = get_labels(old_text, lang)
    new_labels = get_labels(new_text, lang)

    changed_labels = {}

    if len(old_labels) == len(new_labels): # Compare number of lables
        for old, new in zip(old_labels, new_labels):
            if old != new:
                changed_labels[old] = new
    return changed_labels


def get_diff(revids, url):
    """
    Gets the page content before and after the revision (in wikisyntax).

    Arguments:
        revids  - Dict with revision ids (two items: 'old' and 'new', both int)
        url     - API reference point

    Returns: Tuple of two strings

    """
    resp = (requests.get(url, params = {
                        'action': 'query',
                        'prop': 'revisions',
                        'rvprop': 'content',
                        'format': 'json',
                        'utf8': '',
                        'revids': str(revids['old']) + '|' + str(revids['new'])
                        }))
    if resp.status_code != 200: # Means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))

    # Decode to make sure non-latin characters are displayed correctly
    js = json.loads(resp.content.decode('utf-8'))
    assert ('badrevids' not in js['query'].keys()), 'Incorrect revision IDs'

    # Find page id(s) in json, shouldn't be more than 1
    pageid = list(js['query']['pages'].keys())
    assert (len(pageid) == 1), 'Revision IDs from different pages'
    pageid = pageid[0]
    diffs = js['query']['pages'][pageid]['revisions']

    return diffs[0]['*'], diffs[1]['*']


def get_labels(wikitext, lang):
    """
    Retrieve section labels from a wiki-page. The label syntax is obtained
    from the localizations file. Checks for both, localized and English syntax.
    """
    labels = []
    en_label = section_label['en']  # English syntax
    loc_label = section_label[lang] # Localized syntax

    for line in wikitext.splitlines():
        # Check localized syntax of labels
        if loc_label and loc_label in line:
            # Some regex to deal with irregularietes (brackets, whitespace)
            label = re.search(r'<{}\s?=\s?"?(.*?)"?\s?/>'.format(loc_label), line)
            if label:
                labels.append(label.groups()[0])
        # Check English syntax of labels (since most wikis use English syntax)
        elif en_label in line: # TODO was initialy if, doublecheck
            label = re.search(r'<{}\s?=\s?"?(.*?)"?\s?/>'.format(en_label), line)
            if label:
                labels.append(label.groups()[0])
    return labels


def write_data(new_item):
    """
    Writes new edit details into Redis. If Redis contains old data, new item is
    merged into it. Matching label names in old and new data are handled
    distinctly (see comments below).
    """

    lock_redis()
    # If Redis is not empty, first load older data
    all_data = []
    if not redb.get('empty'): # Make sure 'empty' variable exists
        redb.set('empty', 1)
    elif int(redb.get('empty')) == 0: # Means not empty
        # We get a list of saved edits each as a dict. See also check_edit().
        all_data = json.loads(redb.get('lstdata').decode('utf-8'))

    # Merge new data into old data. For identical lables do further checks
    if len(all_data) > 0:
        for old_item in all_data:
            # Look for identical labels in new and old item
            # oldl, newl = old and new labels in old item
            for oldl, newl in zip(list(old_item['labels'].keys()),
                list(old_item['labels'].values())):
                if newl in new_item['labels'].keys():
                    # Means same label is changed twice
                    if oldl == new_item['labels'][newl]:
                    # Case 1: label changed back (reverted), eg. a->b, b->a.
                    # We remove old label pair, but keep the new one (b->a)
                    # Because it mights still happen that transclusions are
                    # manually updated to b and we need to revert it back to a.
                        old_item['labels'].pop(oldl)
                    else:
                    # Case 2: label changed to something else, eg. a->b, b->c.
                    # We update old label pair so that a->b becomes a->c.
                    # So every transclusion with a or b will be updated to c.
                        old_item['labels'][oldl] = new_item['labels'][newl]
            # If no more label pairs remove old item
            if len(old_item['labels']) == 0:
                all_data.pop(all_data.index(old_item))
    # Finally merge the two lists
    all_data.append(new_item)

    # Write merged data into Redis
    redb.set('lstdata', json.dumps(all_data))
    redb.set('empty', 0)
    lock_redis(unlock=True)
    logging.info('[WRITE_DATA] Saved data in Redb')
