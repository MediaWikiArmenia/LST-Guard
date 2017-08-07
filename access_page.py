import json, requests
from getpass import getpass

def get_pagecontent(page_id, url):
    parameters = {
                'action': 'query',
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

def edit_page(page_id, page_content, url):
    #see https://www.mediawiki.org/wiki/Manual:Bot_passwords
    username = ''
    password = ''
    session = requests.Session()

    # get login credentials from imput if necessary
    if username == '' or password == '':
        username = input('Bot username: ')
        password = getpass('Password: ')
    print(' logging in as {}...'.format(username))

    # get login token
    resp0 = session.get(url, params = {
                'action': 'query',
                'meta': 'tokens',
                'type': 'login',
                'format': 'json'})
    resp0.raise_for_status()

    # login
    resp1 = session.post(url, data = {
                'action': 'login',
                'format': 'json',
                'lgname': username,
                'lgpassword': password,
                'lgtoken': resp0.json()['query']['tokens']['logintoken']})
    if resp1.json()['login']['result'] != 'Success':
        raise RuntimeError(resp1.json()['login']['reason'])
    print('Login successful')

    # get edit token
    print(' getting edit token....')
    resp2 = session.get(url, params = {
                'action': 'query',
                'meta': 'tokens',
                'type': 'csrf',
                'format': 'json'})

    #edit page
    resp3 = session.post(url, data = {
                'action': 'edit',
                'pageid': page_id,
                'text': page_content,
                'summary': 'Բաժնի անվան ուղղում բոտի կողմից',
                'format': 'json',
                'utf8': '',
                'bot': 1,
                'token': resp2.json()['query']['tokens']['csrftoken']})
