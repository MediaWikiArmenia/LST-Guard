"""
WORK IN PROGRESS, THIS IS STILL A DRAFT.
This class will read the html code of the recent changes from any MediaWiki API
(eg. https://en.wikipedia.org/w/api.php?action=feedrecentchanges&days=30),
and produce a machine-readable data: a list of dictionaries with the
revisioned text as strings.
"""

class HtmlParser:
    def __init__(self):
        self.trcontents = []
        self.recentchanges = ''
        f = open('sandbox_.html', 'r')
        for line in f:
            self.recentchanges += line
        f.close()

    def run(self):
        # split all <tr> tags into elements in a list
        table_tr = self.tr_split(self.recentchanges)
        print(table_tr)
        # split all <tr> tags into dictionaries in a list
        table_td = []
        for tr in table_tr:
            table_td.append(self.td_split(tr))
            del tr
        print(table_td)

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
    diffs = DiffTokenizer()
    diffs.run()
