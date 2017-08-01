
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
