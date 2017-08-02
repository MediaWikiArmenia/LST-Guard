import json, requests

def get_revisions(revision, domain):
    url = 'https://' + domain + '/w/api.php'
    parameters = {'action': 'query', 'prop': 'revisions', 'rvprop': 'content',
        'format': 'json', 'utf8': '', 'revids': str(revision['old']) + '|' + str(revision['new']) }
    resp = (requests.get(url, params = parameters))
    if resp.status_code != 200: #This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))

    js = json.loads(resp.content.decode('utf-8')) #Decode to make sure non-latin characters are displayed correctly
    assert ('badrevids' not in js['query'].keys()), 'Incorrect revision IDs'

    pid = list(js['query']['pages'].keys()) #Find page ID(s) in json, shouldn't be more than 1
    assert (len(pid) == 1), 'Revision IDs from different pages'

    pid = pid[0]
    diffs = js['query']['pages'][pid]['revisions']
    old, new = diffs[0]['*'], diffs[1]['*'] #Two strings with each revision content (in wikisyntax)
    return check_diff(old, new)

def check_diff(old, new):
    changed_sections = {}
    old, new = old.splitlines(), new.splitlines()
    for a, b in zip(old, new):
        if '<section begin=' in b and a != b: #TODO: addapt to syntax variations / irregularities
            a, b = a.split('"')[1], b.split('"')[1]
            changed_sections[a] = b
    return changed_sections
