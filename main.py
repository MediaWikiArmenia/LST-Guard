#TODO: resolve all pid variable issues

import json, requests
from sseclient import SSEClient as EventSource

def run(project = 'wikisource', lang = 'hy'):
    domain = lang + '.' + project + '.org'
    print(domain)
    url = 'https://stream.wikimedia.org/v2/stream/recentchange'
    print('Watching recent changes in {}'.format(domain))
    for event in EventSource(url):
        if event.event == 'message':
            try:
                item = json.loads(event.data) #creates dict in json format
            except ValueError:
                pass
            else:
                if domain in item['server_name']:
                    if 'revision' in item.keys():# and item['namespace'] == 104:    #TODO: when actually running add ns 104!
                        print('New revision in page "{1}" (id: {2}, {3}). Checking...'.format(item['title'], item['id'], item['server_name']))
                        #get_revisions(item['revision'], item['title'])


if __name__ == '__main__':
    run()

# search for:
# <pages index="Հայկական Սովետական Հանրագիտարան (Soviet Armenian Encyclopedia) 6.djvu" from=161 to=161 fromsection="Հայզենբերգ" tosection="Հայզենբերգ"/>
# {{Էջ|Հայկական Համառոտ Հանրագիտարան․ Հ տառով հոդվածները.djvu/2|բաժին=Հագուստ|համ=34}}
