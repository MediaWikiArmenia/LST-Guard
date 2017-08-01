
def get_revisions(revision, title):
    #USED METHODS: CHECK_DIFF
    parameters = {'action': 'query', 'prop': 'revisions', 'rvprop': 'content',
        'format': 'json', 'utf8': '', 'revids': str(revision['old']) + '|' + str(revision['new']) }
    resp = (requests.get('https://hy.wikisource.org/w/api.php', params = parameters))
    if resp.status_code != 200: #This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))

    js = json.loads(resp.content.decode('utf-8')) #decode to make sure armenian characters are displayed correctly
    pid = str(js['query']['pages'].keys())[12:-3]
    diffs = js['query']['pages'][pid]['revisions']
    if len(diffs) == 2: #Make sure we have 2 revisions TODO: resolve this in watch_rc (item['type'] == 'edit')
        old = diffs[0]['*']
        new = diffs[1]['*']
        check_diff(old, new, title)
    else: #This means we have only 1 revision, i.e. new page is created, rather than edited
        print(' New page: PASS')

def check_diff(old, new, title):
    #GET_TRANSCLUSIONS
    #CHECK_TRANSCLUSION
    # Parsing changed section names from diff
    changed_sections = {}
    old, new = old.splitlines(), new.splitlines()
    for a, b in zip(old, new):
        if '<section begin=' in b and a != b:
            a, b = a.split('"')[1], b.split('"')[1]
            changed_sections[a] = b

    # Generating a list of transclusions of the edited page
    if len(changed_sections) > 0:
        print(' {} changed section name(s) detected: {}'.format(len(changed_sections), changed_sections))
        transclusions = get_transclusions(title)
        print(' Checking transclusions... {} found.'.format(len(transclusions)))
        # Checking if changed section names occur in transclusions
        if len(transclusions) > 0:
            for item in transclusions:
                check_transclusion(item, changed_sections)
        else:
            print(' No transclusions: PASS')
    else:
        print(' Everything OK: PASS')
