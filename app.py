import lst_guard, lst_therapist
import logging
from sys import argv
from multiprocessing import Process

logging.basicConfig(filename='logs_lst.txt',
                    level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')
global lang, proj

def run():
    set_args()
    guard = Process(target=start_guard)
    guard.start()
    therapist = Process(target=start_therapist)
    therapist.start()

def set_args():
    assert len(argv) <= 11, 'Too many arguments given' # max 11 args, i.e. max 9 languages
    global lang, proj
    if len(argv) > 2:
        proj, lang = argv[1], argv[2:]
    else:
        proj = proj, lang = '', []

def start_guard():
    lst_guard.run(proj, lang)

def start_therapist():
    lst_therapist.run()

if __name__ == '__main__':
    run()
