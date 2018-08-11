# !/usr/local/bin/python3

# TODO check if importing module also imports imported libs

import redis, subprocess
from sys import argv
from configparser import ConfigParser
from time import sleep


global redb, proc_arg, config_fp
proc_arg = ['nohup', 'python3', 'app.py', '&']
config_fp = r'config.ini'


def run():
    open_redis()
    run_option = {  '-start':start_lstg,
                    '-stop':stop_lstg,
                    '-restart':restart_lstg,
                    '-status':get_status
                    }
    if len(argv)!=2 or argv[1] not in run_option.keys():
        print_usage()
        exit()
    run_option[argv[1]]()


def open_redis():
    global redb
    try:
        redb = redis.StrictRedis(host='localhost', port=7777, db=0)
    except:
        print('Error: Unable to open Redis DB. Exiting')
    else:
        print('Check: Redis DB running (port: 7777, db: 0)')


def start_lstg():
    check_config()
    redb.flushdb()
    subprocess.Popen(proc_arg, stdin=subprocess.PIPE, stdout=subprocess.PIPE, \
        stderr=subprocess.PIPE )
    redb.set('poller_status', 'starting')
    redb.set('repairer_status', 'starting')
    print('Starting LST-guard: lst_poller & lst_repairer initiated')


def restart_lstg():
    stop_lstg()
    print('Waiting for processes to stop. This might take 5-10 seconds...')
    still_running = True
    while(still_running):
        sleep(2)
        if redb.get('poller_status').decode('utf-8') == 'stopped' \
            and redb.get('repairer_status').decode('utf-8') == 'stopped':
            still_running = False
    start_lstg()


def stop_lstg():
    redb.set('poller_status', 'stopping')
    redb.set('repairer_status', 'stopping')
    print('Stopping LST-guard: message sent to lst_poller & lst_repairer.')


def get_status():
    poller = 'Not started' if not redb.get('poller_status') \
        else redb.get('poller_status').decode('utf-8')
    repairer = 'Not started' if not redb.get('repairer_status') \
        else redb.get('repairer_status').decode('utf-8')
    print('\nLST-Guard processes:\nlst_poller:\t{}\nlst_repairer:\t{}\n\n' \
    'Note: After sending stop signal it might take 5-10s for the processes ' \
    'to finlize, cleanup and exit.'.format(poller.upper(),repairer.upper()))


def check_config():
    missing_fields = {}
    required_fields = { 'run on':       ['project', 'languages'],
                        'supported':    ['projects', 'languages'],
                        'credentials':  ['username', 'password']
                        }
    config = ConfigParser()
    try:
        config.read_file(open(config_fp))
    except:
        print('Error: config file [{}] not found. Exiting.'.format(config_fp))
        exit()
    else:
        for section in required_fields.keys():
            if section not in config.sections():
                missing_fields[section] = None
            else:
                for option in required_fields[section]:
                    if option not in config.options(section) or not config.get(section, option):
                        missing_fields[section] = missing_fields.get(section,[]) + [option]
        if missing_fields:
            print('Error: missing or empty fields in [config.ini]:')
            for section in missing_fields.keys():
                if not missing_fields[section]:
                    print('  [{}] section missing'.format(section))
                else:
                    print('  missing or empty in section [{}]: {}'.format(section, ', '.join(missing_fields[section])))
            print('Exiting')
            exit()
        else:
            print('Check: config file [{}]: Success.'.format(config_fp))


def print_usage():
    print("""

    LST-Guard manager: start, restart, stop or status the service.

    ARGUMENTS:
        Required (one of):
            -status            Show status of service
            -start             Start service
            -stop              Stop service, processes will finilize and stop
            -restart           Restart service, processes will finilize and restart

    EXAMPLES:
        Start Lst-guard:
        ./lst_manager -start
    """
    )

if __name__ == '__main__':
    run()
