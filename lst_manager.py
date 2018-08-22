#!/usr/bin/env python3

import redis
import subprocess
import sys
from time import sleep
from configparser import ConfigParser

global redb, redb_host, redb_port, redb_id, proc_args, config_fp, debug_mode_fp
config_fp = 'config.ini'
debug_mode_fp = 'debug_edits.html'
debug_mode = False
proc_args = ['nohup', 'python3', 'dumb.py', config_fp, '&']


__doc__ = """
LST-Guard manager: start, restart, stop or status the service.

Calls app.py to start the service (lst_poller and lst_worker) and uses
Redis to send stop signals, get status or check data.

REQUIREMENTS:
    To start the service, a Redis-server must be running and a valid config
    file available.

ARGUMENTS:
    Required (one of):
        -status            Show status of service (see details below)
        -start             Start service
        -stop              Stop service, processes will finilize and stop
        -restart           Restart service, processes will finilize and restart
        -redis             Show is Redis-server is running and available data
        -help              Print this message

    Optional:
    with -start/-restart:
        -d --debug         Start in dubug mode, no edits will be made,
                           instead edits will be stored in "{}"
    with -redis:
        variable           Print content of "variable" in Redis db

STATUS:
        'Not started'      Service has not been started
        'Starting'         Signal sent to app.py to start service
        'Running'          Process is running
        'Stopping'         Stop signal send to processes
        'Stopped'          Processes finilized and exited successfully

EXAMPLES:
    Start Lst-guard:
    ./lst_manager -start
""".format(debug_mode_fp)

# TODO add option to export Redis

def run():
    global debug_mode
    # Check command line option
    # Print usage and exit if not valid
    run_option = {  '-start':start_lstg,
                    '-stop':stop_lstg,
                    '-restart':restart_lstg,
                    '-status':get_status,
                    '-redis':check_redis
                    }
    # Exit if arguments are invalid
    check_argv(run_option.keys())
    # Option/arguments are ok, continue
    print('\n## LST-Guard Manager ##\n')
    # Check config file and Redis db
    open_redis()
    # Run the requested option
    if len(sys.argv)==2:
        run_option[sys.argv[1]]()
    else:
        run_option[sys.argv[1]](sys.argv[2])


def check_argv(options):
    if len(sys.argv)<2 or len(sys.argv)>3 or sys.argv[1]=='-help':
        print(__doc__)
        sys.exit(2)
    elif sys.argv[1] not in options:
        print('Unrecognized option "{}". Use "-help" for help'.format(sys.argv[1]))
        sys.exit(2)
    elif sys.argv[1] in ('-start','-restart') and len(sys.argv)==3 and sys.argv[2] not in ('--debug','-d'):
        print('Unrecognized argument "{}". Use "-help" for help'.format(sys.argv[2]))
        sys.exit(2)
    elif sys.argv[1] in ('-stop','-status','-help') and len(sys.argv)==3:
        print('Unrecognized argument "{}". Use "-help" for help'.format(sys.argv[2]))
        sys.exit(2)


def open_redis():
    global redb, redb_host, redb_port, redb_id
    redb_host, redb_port, redb_id = check_config()
    try:
        redb = redis.StrictRedis(host=redb_host, port=redb_port, db=redb_id)
        redb.client_list()
    except:
        print('Error: Unable to open Redis DB (host: {}, port: {}, db: {}).' \
            .format(redb_host, redb_port, redb_id))
        print('Is redis-server running or wrong parameters?')
        sys.exit(1)
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
            waited = 0
            while (int(redb.get('locked'))):
                sleep(0.01)
                waited += 1
                if waited > 1000: # we waited 10s
                    print('\nError: Unable to lock Redb. Terminating.' \
                    'Check variable "locked".')
                    sys.exit(1)
            print('OK')
        redb.set('locked', 1)


def check_redis(data=None):
    if data:
        if redb.get(data):
            print('Content of "{}":\t"{}"'.format(data, redb.get(data).decode('utf-8')))
        else:
            print('Variable "{}" is not set.'.format(data))
    else:
        if redb.keys():
            print('The following variables have values:\n \'{}\''.format \
                ('\'\n \''.join([k.decode('utf-8') for k in redb.keys()])))
        else:
            print('No variables in Redis database.')


def start_lstg(option=False):
    print('Flushing Redis database.')
    redb.flushdb()
    if option in ('--debug','-d'):
        proc_args.insert(4, debug_mode_fp)
    subprocess.Popen(proc_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, \
        stderr=subprocess.PIPE )
    lock_redis()
    redb.set('poller_status', 'starting')
    redb.set('worker_status', 'starting')
    lock_redis(unlock=True)
    print('Starting LST-guard: lst_poller & lst_worker initiated.')
    if debug_mode:
        print('Note: lst_worker runs in debug mode, edits will be saved in:' \
            ' [{}].'.format(debug_mode_fp))


def restart_lstg(debug_mode=False):
    stop_lstg()
    print('Waiting for processes to stop. This might take 5-20 seconds...')
    still_running = True
    while(still_running):
        sleep(2)
        if redb.get('poller_status').decode('utf-8') == 'stopped' \
            and redb.get('worker_status').decode('utf-8') == 'stopped':
            still_running = False
    print('All processes stopped. Preparing to restart service.')
    start_lstg(debug_mode)


def stop_lstg():
    lock_redis()
    redb.set('poller_status', 'stopping')
    redb.set('worker_status', 'stopping')
    lock_redis(unlock=True)
    print('Stopping LST-guard: signal sent to lst_poller & lst_worker.')


def get_status():
    poller = 'Not started' if not redb.get('poller_status') \
        else redb.get('poller_status').decode('utf-8')
    worker = 'Not started' if not redb.get('worker_status') \
        else redb.get('worker_status').decode('utf-8')
    print('\nProcesses:\tStatus:\nlst_poller\t{}\nlst_worker\t{}\n'.format \
        (poller.upper(),worker.upper()))
    if worker == 'running debug mode':
        print('Note: lst_worker runs in debug mode, edits are saved in [{}].' \
            .format(debug_mode_fp))


def check_config():
    # TODO, if debug mode don't require usr/psw
    """
    Validate config.ini and return Redis db details that we need.
    """
    missing_fields = {}
    required_fields = { 'run on':           ['project', 'languages'],
                        'supported':        ['projects', 'languages'],
                        'credentials':      ['username', 'password'],
                        'redis database':   ['host', 'port', 'db']
                        }
    config = ConfigParser()
    # Only require credentials for start/restart and not debug mode
    require_credentials = False
    if sys.argv[1] in ('-start','-restart') and not ('-d' in sys.argv \
        or '--debug' in sys.argv):
        require_credentials = True
        print('require_credentials')
    # Try to read config file
    try:
        config.read_file(open(config_fp))
    except:
        print('Error: config file [{}] not found. Exiting.'.format(config_fp))
        sys.exit(1)
    else:
        for section in required_fields.keys():
            if not config.has_section(section):
                # Entire section is missing
                missing_fields[section] = None
            else:
                # Section is there: check is all parameters are present
                for param in required_fields[section]:
                    # Check that parameter label and value are both present
                    # Eg. "password = " without the actual password itself will
                    # be noted as missing parameter
                    if not config.has_option(section, param) or not \
                        config.get(section, param, fallback=False):
                        missing_fields[section] = missing_fields.get(section,[]) + [param]
        # Print warnings
        if missing_fields:
            print(missing_fields)
            if not require_credentials and list(missing_fields.keys()) == ['credentials']:
                print('Warning: credentials missing from config (not required for this operation).')
            else:
                print('Error: missing or empty fields in [config.ini]:')
                for section in missing_fields.keys():
                    # Only print if missing section is critical
                    if require_credentials or section!='credentials':
                        # Means empty section
                        if not missing_fields[section]:
                            print('  Missing section: [{}]'.format(section))
                        # Some parameters are missing
                        else:
                            print('  Missing in section [{}]: {}'.format(section, \
                            ', '.join(missing_fields[section])))
                print('Exiting')
                sys.exit(1)

        print('Check: config file [{}]: OK.'.format(config_fp))
        return (config.get('redis database', 'host'), \
                config.get('redis database', 'port'), \
                config.get('redis database', 'db'))


if __name__ == '__main__':
    run()
