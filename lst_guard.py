# !/usr/local/bin/python3
# -*- coding: utf-8 -*-

import json, requests, time, re, redis, atexit
from sseclient import SSEClient as EventSource
from configparser import ConfigParser
from localizations import section_label

# Load global variables from config file
global supported_projects, supported_languages, run_on_project, run_on_languages
config = ConfigParser()
config.readfp(open(r'config.ini'))
supported_projects = config.get('supported', 'projects').split()
supported_languages = config.get('supported', 'languages').split()
run_on_project = config.get('run on', 'project')
run_on_languages = config.get('run on', 'languages').split()


def run(proj='', langs=''):
    """
    Main Routine. Reads the recent changes stream EventSource (includes edits
    from all wikimedia projects), filters out edits in the specified project
    and langauge(s) and finally calls "check_edit()" to see if section labels
    were changed during edit. If so, "check_edit()" will store the edit details
    in Redis for lst_therapist to correct these labels in transclusions if
    necessary.

    The arguments proj and langs are respectively string and list. If empty,
    the global variables loaded from the config file will be used instead.
    """
    # Identify project which will be watched
    if not proj:
        proj = run_on_project
    assert (proj in supported_projects), 'Not supported project'
    if not langs:
        langs = run_on_languages
    assert (l in supported_languages for l in langs), 'Not supported language(s)'

    # Start watching recent changes
    print('Watching recent changes in {} ({})'.format(proj, ', '.join(langs)))
    for event in EventSource
        ('https://stream.wikimedia.org/v2/stream/recentchange'):
        if event.event == 'message':
            try:
                item = json.loads(event.data) # Create dict with edit details
            except ValueError:
                pass
            else:
                # split server url to get language and project
                server = item['server_name'].split('.')
                # Filter out edits in specified project and language(s)
                # TODO add namespace filter
                if (server[0] in langs and server[1] == proj and
                    item['type'] == 'edit'):
                    print('New revision in page "{}" ({}).\n Checking...'
                        .format(item['title'], server[0]))
                    check_edit(item)


def check_edit(item):
    """
    Passes data over to "check_revision()" (which does the actual checking).
    If changed labels are detected calls "write_data()" to save edit data in
    Redis.

    Expected argument is a dict with (at leas) the following values:
    revision - dict with revision IDS as {old:new}
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

    # Empty dict means no lables were changed
    if len(changed_labels) == 0:
        print(' No changed labels: PASS')
    # Pass data over to next function to write it in Redis
    else:
        print(' {} changed label(s) detected...'.format(len(changed_labels)))
        data = {    'title': item['title'],
                    'lang': lang,
                    'url': url,
                    'labels': changed_labels }
        write_data(data)

def write_data(new_item):
    """
    Writes new edit details into Redis. If Redis contains old data, new item is
    merged into it. Matching label names in old and new data are handled
    distinctly (see comments below).
    """
    r = redis.StrictRedis(host='localhost', port=7777, db=0)

    # Wait if Redis is locked
    if r.get('locked'): # Check if 'locked' variable exists
        while int(r.get('locked')): # Check if value is '1' (i.e. "true")
            time.sleep(0.02)
    r.set('locked', 1)

    # If Redis is not empty, first load older data
    all_data = []
    if not r.get('empty'):
        r.set('empty', 1) # Check if 'empty' variable exists
    if int(r.get('empty')) == 0: # Means not empty
        # We get a list of saved edits each as a dict. See also check_edit().
        all_data = json.loads(r.get('lstdata').decode('utf-8'))

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
    all_data.append(new_data)

    # Write merged data into Redis
    r.set('lstdata', json.dumps(all_data))
    r.set('empty', 0)
    r.set('locked', 0)
    print(' Saving to check transclusions later: DONE')


def check_revision(revids, url, lang):
    """
    A dumb function to find changed labels in an edited page.
    Compares the old and new versions of the page. Then compares the number of
    section labels in both, if equal, assumes those are labels of corresponding
    sections. Returns those labels that don't match.

    Returns empty dict if changed labels are not detected.
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
    Gets the new and old versions of an edited page (in wikisyntax).
    The argument revids is a dict with two int values:
    old - ID of the old version of the page
    new - ID of the new version
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
    from the localizations file.
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
        if en_label in line:
            label = re.search(r'<{}\s?=\s?"?(.*?)"?\s?/>'.format(en_label), line)
            if label:
                labels.append(label.groups()[0])
    return labels
