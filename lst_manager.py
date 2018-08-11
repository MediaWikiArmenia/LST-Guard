# !/usr/local/bin/python3

import redis, subprocess
from sys import argv
from configparser import ConfigParser
from time import sleep

"""
Manage LST-Guard processes: start, stop, restart or get status.
Also checks if the Redis database is accessible. And verifies
the Config file before (re)starting LST-Guard.
"""

global redb, redb_host, redb_port, redb_id, proc_arg, config_fp
redb_host = 'localhost'
redb_port = 7777
redb_id = 0
proc_arg = ['nohup', 'python3', 'app.py', '&']
config_fp = r'config.ini'


def run():
    # Check command line option
    # Print usage and exit if not valid
    run_option = {  '-start':start_lstg,
                    '-stop':stop_lstg,
                    '-restart':restart_lstg,
                    '-status':get_status,
                    '-redis':check_redis,
                    '-help':print_usage
                    }
    if not len(argv)>1 or argv[1] not in run_option.keys():
        print_usage()
        exit()
    # Option is ok, continue
    open_redis()
    if len(argv)>2:
        run_option[argv[1]](argv[2])
    else:
        run_option[argv[1]]()


def open_redis():
    global redb
    try:
        redb = redis.StrictRedis(host=redb_host, port=redb_port, db=redb_id)
    except:
        print('Error: Unable to open Redis DB (host: {}, port: {}, db: {}).' \
            'Exiting'.format(redb_host, redb_port, redb_id))
        exit()
    else:
        print('Check: Redis DB running OK (host: {}, port: {}, db: {})'.format \
            (redb_host, redb_port, redb_id))


def lock_redis(unlock=False):
    if unlock:
        redb.set('locked', 0)
    else:
        # Check if locked is set
        if not redb.get('locked'):
            redb.set('locked', 0 if unlock else 1)
        elif int(redb.get('locked')):
            print('Waiting for Redb to unlock...', end=' ', flush=True)
            waited = 0.0
            while (int(redb.get('locked'))):
                sleep(0.01)
                waited += 0.01
                if waited > 10:
                    print('\nError: Unable to lock Redb, terminating.' \
                    'Check variable "locked".')
                    exit()
            print('OK')
        sleep(2)
        redb.set('locked', 0 if unlock else 1)


def check_redis(data=None):
    if data:
        if redb.get(data):
            print('Content of "{}":\t"{}"'.format(data, redb.get(data).decode('utf-8')))
        else:
            print('Data "{}" is not set (empty).'.format(data))
    else:
        if redb.keys():
            print('The following data are set:\n\t{}'.format('\n\t'.join \
                ([k.decode('utf-8') for k in redb.keys()])))
        else:
            print('No data are set in Redis database.')


def start_lstg():
    check_config()
    print('Flushing Redis database.')
    redb.flushdb()
    subprocess.Popen(proc_arg, stdin=subprocess.PIPE, stdout=subprocess.PIPE, \
        stderr=subprocess.PIPE )
    lock_redis()
    redb.set('poller_status', 'starting')
    redb.set('repairer_status', 'starting')
    lock_redis(unlock=True)
    print('Starting LST-guard: lst_poller & lst_repairer initiated.')


def restart_lstg():
    stop_lstg()
    print('Waiting for processes to stop. This might take 5-10 seconds...')
    still_running = True
    while(still_running):
        sleep(2)
        if redb.get('poller_status').decode('utf-8') == 'stopped' \
            and redb.get('repairer_status').decode('utf-8') == 'stopped':
            still_running = False
    print('All processes stopped. Preparing to restart service.')
    start_lstg()


def stop_lstg():
    lock_redis()
    redb.set('poller_status', 'stopping')
    redb.set('repairer_status', 'stopping')
    lock_redis(unlock=True)
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
    Calls app.py to start the service (lst_poller and lst_repairer) and uses
    Redis to send stop message to these processes.

    REQUIREMENTS:
        To start service, a Redis-server must be running and a valid config file
        available.

    ARGUMENTS:
        Required (one of):
            -status            Show status of service (see details below)
            -start             Start service
            -stop              Stop service, processes will finilize and stop
            -restart           Restart service, processes will finilize and restart
            -redis             Show is Redis-server is running and available data
            -help              Print this message
        Optional:
            -redis data        Print content of data

    STATUS:
            'Not started'      Service has not been started
            'Starting'         app.py is called to start service
            'Running'          Processes are running
            'Stopping'         Stop signal send to processes
            'Processes'        Processes finilized and exited successfully

    EXAMPLES:
        Start Lst-guard:
        ./lst_manager -start
    """
    )

if __name__ == '__main__':
    run()
