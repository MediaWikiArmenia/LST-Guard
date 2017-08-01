
def get_transclusions(title):
    parameters = {'action': 'query', 'prop': 'transcludedin', 'titles': title,
        'format': 'json', 'utf8': '', 'tinamespace': '*'} #TODO change ns to 0
    resp = (requests.get('https://hy.wikisource.org/w/api.php', params = parameters))

    js = json.loads(resp.content.decode('utf-8'))
    #print('TRANSCLUDEDIN:', js)
    pid = str(js['query']['pages'].keys())[12:-3]   #TODO: throw keyerror when js = {'batchcomplete': '', 'warnings': {'main': {'*': 'Unrecognized parameter: pageid.'}}}
    transclusions = js['query']['pages'][pid]
    if 'transcludedin' in transclusions.keys():
        return [item['pageid'] for item in transclusions['transcludedin']]
    return [] #return empty list if no transclusions

def check_transclusion(page_id, changed_sections):
    #GET_PAGECONTENT
    #EDIT_PAGE
    page_content = get_pagecontent(page_id).splitlines()
    edit = False
    #print(page_content)
    for line in page_content:
        if '<pages index=' in line:
            index = page_content.index(line)
            for section in changed_sections.keys():
                if section in line:
                    edit = True
                    line = line.replace(section, changed_sections[section])
                    page_content[index] = line
    page_content = '\n'.join(page_content)

    if edit == True:
        edit_page(page_id, page_content)
        print(' 1 transclusion corrected! DONE')
    else:
        print(' No corrections made. PASS')
