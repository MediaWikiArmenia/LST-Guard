"""
WORK IN PROGRESS, THIS IS STILL A DRAFT.
This class will read the html code of the recent changes from any MediaWiki API
(eg. https://en.wikipedia.org/w/api.php?action=feedrecentchanges&days=30),
and produce a machine-readable data: a list of dictionaries with the
revisioned text as strings.
"""

import re

class HtmlParser:
    def __init__(self):
        self.recentchanges = ''
        f = open('sandbox6.txt', 'r') #This is just for play, final version should get data from api
        self.recentchanges = f.readline()
        print(self.recentchanges)
        f.close()

    def run(self):
        print('works!')
        table = self.item_split(self.recentchanges)
        print(type(table))
        print(table)
        for item in table:
            print('item in table')
            self.all_split(item)

        """
        # split all <tr> tags into elements in a list
        table_tr = self.tr_split(self.recentchanges)
        print(table_tr)
        # split all <tr> tags into dictionaries in a list
        table_td = []
        for tr in table_tr:
            table_td.append(self.td_split(tr))
            del tr
        print(table_td)
        """
        return

    def all_split(self, content):
        print('all print!')
        item = {}
        # should return dict:
        # {'title': xx, 'link': xx, 'date': xx, 'user': xx, 'comment': xx, 'diffs': {'old': [xx], 'new': [xx]]}
        table = content.split('<link>')
        item['title'] = table[0].split('<title>')[1].split('</title>')[0]
        table = table[1].split('</link>')
        item['link'] = table[0]
        table = table[1].split('<description>')[1].split('</description>')
        item['comment'], item['diffs'] = self.parse_diffs(table[0])
        table = table[1].split('<pubDate>')[1].split('</pubDate>')
        item['date'] = table[0]
        table = table[1].split('<dc:creator>')[1].split('</dc:creator>')
        item['user'] = table [0]
        print(item)
        return

    def parse_diffs(self, content):
        comment, table = content.split('</p>', 1)
        print(table)
        return self.clean_tags(comment), 'DIFF'

    def clean_tags(self, content):
        cleantext = re.sub('<.*?>', '', content)
        cleantext = re.sub('\\\\x..', '', cleantext)
        return cleantext

    def item_split(self, content):
        table = content #.split['<item>']
        table2 = table.split('<item>')[1:]
        return table2

    def td_split(self, content):
        tr = []
        startcopy = False
        opentag = False
        tag = ''
        openingtag = ''
        tagcontent = ''
        classcontent = ''

        for char in content:
            if startcopy:
                tagcontent += char
            if char == '<':
                opentag = True
            if opentag:
                tag += char
            if char == '>':
                opentag = False
                if tag == '</td>':
                    classcontent = self.get_classvalue(openingtag)
                    startcopy = False
                    td = {}
                    td['class'] = classcontent
                    td['content'] = tagcontent[:-5]
                    tr.append(td)
                    del td
                    tagcontent = ''
                    openingtag = ''
                elif tag[:3] == '<td':
                    tagcontent = ''
                    startcopy = True
                    if tag == '<td>':
                        openingtag = ''
                    else:
                        openingtag = tag
                tag = ''
        return tr

    def get_classvalue(self, td):
        # gets the value of the tag class (eg. class="empty-diff")
        if 'class' in td:
            return td.split('class=', 1)[1][1:-2]
        return ''

    def tr_split(self, content):

        opentag = False
        startcopy = False
        tag = ''
        tagcontent = ''
        result = []

        for char in content:
            if startcopy:
                tagcontent += char
            if char == '<':
                opentag = True
            if opentag:
                tag += char
            if char == '>':
                opentag = False
                if tag == '<tr>':
                    startcopy = True
                elif tag == '</tr>':
                    startcopy = False
                    result.append(tagcontent[0:-5])
                    tagcontent = ''
                tag = ''
        return result

if __name__ == "__main__":
    diffs = HtmlParser()
    diffs.run()
