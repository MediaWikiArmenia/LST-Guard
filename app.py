import lst_poller, lst_therapist
import logging
from sys import argv
from multiprocessing import Process

logging.basicConfig(filename='logs_lst.txt',
                    level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')
global lang, proj, DEBUG_MODE
DEBUG_MODE = True

def set_args():
    assert len(argv) <= 11, 'Too many arguments given' # max 11 args, i.e. max 9 languages
    global lang, proj
    if len(argv) > 2:
        proj, lang = argv[1], argv[2:]
    else:
        proj = proj, lang = '', []

def start_poller():
    lst_poller.run(proj, lang)

def start_therapist():
    lst_therapist.run()

def run():
    set_args()
    Process(target=start_poller).start()
    Process(target=start_therapist).start()

if __name__ == '__main__':
    run()
