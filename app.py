import json
from sseclient import SSEClient as EventSource

from diff_parser import get_revisions
from check_transclusions import get_transclusions, check_transclusion
from access_page import get_pagecontent, edit_page


if __name__ == '__main__':
    run()
