import json
from sseclient import SSEClient as EventSource

from diff_parser import get_revisions
from check_transclusions import get_transclusions, check_transclusion
from access_page import get_pagecontent, edit_page

def run(lang = 'hy', project = 'wikisource'):
    supported_langs = ['hy'] # en, de, es will be added soon
    assert (lang in supported_langs), 'Not supported language'

    domain = lang + '.' + project + '.org'
    url = 'https://' + domain + '/w/api.php'
    print('Watching recent changes in {}'.format(domain))

    for event in EventSource('https://stream.wikimedia.org/v2/stream/recentchange'):
        if event.event == 'message':
            try:
                item = json.loads(event.data) #create dict in json format
            except ValueError:
                pass
            # Consider only edits in specified project/lang and in namespace 104 (Page:***)
            else:
                if (item['server_name'], item['type'], item['namespace']) == (domain, 'edit', 104):
                # IF YOU ARE TESTING, REMOVE THE NAMESPACE CONDITIONAL AND TEST ON USER SUBPAGES AND SANDBOXES
                    print('New revision in page "{}". Checking...'.format(item['title']))
                    check_revision(item, url)

def check_revision(item, url):
    # See if there are changed section names in revision
    changed_sections = get_revisions(item['revision'], url)

    # Go ahead and handle changed section names, if any
    if len(changed_sections) == 0:
        print(' No changed section names: PASS')
    else:
        print(' {} changed section name(s) detected...'.format(len(changed_sections)))
        transclusions = get_transclusions(item['title'], url)
        print(' Checking transclusions... {} found.'.format(len(transclusions)))

        # Handle transclusions, if any
        if len(transclusions) == 0:
            print(' No transclusions: PASS')
        else:
            for transclusion in transclusions:
                page_content = get_pagecontent(transclusion, url)
                page_content = check_transclusion(page_content, changed_sections)
                if page_content == '':
                    print(' No corrections made. PASS')
                else:
                    edit_page(transclusion, page_content, url)
                    print(' 1 transclusion corrected! DONE')

if __name__ == '__main__':
    run()
