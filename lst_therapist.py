import json, requests

def get_transclusions(title, url):
    parameters = {'action': 'query', 'prop': 'transcludedin', 'titles': title,
        'format': 'json', 'utf8': '', 'tinamespace': '*'} #TODO change ns to 0
    resp = (requests.get(url, params = parameters))

    js = json.loads(resp.content.decode('utf-8'))
    #print('TRANSCLUDEDIN:', js)
    pid = str(js['query']['pages'].keys())[12:-3]   #TODO: throw keyerror when js = {'batchcomplete': '', 'warnings': {'main': {'*': 'Unrecognized parameter: pageid.'}}}
    transclusions = js['query']['pages'][pid]
    if 'transcludedin' in transclusions.keys():
        return [item['pageid'] for item in transclusions['transcludedin']]
    return [] #return empty list if no transclusions

def check_transclusion(page_content, changed_sections):
    page_content = page_content.splitlines()
    edit = False

    # If old section name found replace with new section name
    for line in page_content:
        if '<pages index=' in line: #TODO make sure template includes page!!
            index = page_content.index(line)
            for section in changed_sections.keys():
                if section in line:
                    edit = True
                    line = line.replace(section, changed_sections[section])
                    page_content[index] = line
    page_content = '\n'.join(page_content)

    if edit == True:
        return page_content
    return '' # Return empty string if no edit in page necessary
