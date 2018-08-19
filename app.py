
import logging
import sys
from multiprocessing import Process
from configparser import ConfigParser
import lst_poller
import lst_repairer


"""
Expected arguments:
    Required:
        - config_fp
    Optional:
        - debug_mode_fp
"""
global langs, proj, config_fp, dbg_fp, m_name, rdb_host, rdb_port, rdb_id
config_fp = dbg_fp = None # initialize to avoid NameError
m_name = 'APP' # module name for logger

logging.basicConfig(
            filename='lst_guard.log',
            level=logging.INFO,
            format='%(asctime)s:%(levelname)s:%(message)s')


def run():
    set_args()
    load_config()
    logging.info('[{}] Checked argv and config: OKAY.'.format(m_name))
    Process(target=start_poller).start()
    Process(target=start_repairer).start()


def set_args():
    """
    Copies command line arguments to global variables.
    Accepted arguments:
        Required:
            argv[1] -   config file
        Optional:
            argv[2] -   debug mode file

    Will terminate if arguments are invalid.
    """
    global config_fp, dbg_fp
    # Allow only 1 or 2 arguments
    if len(sys.argv) == 2 or len(sys.argv) == 3:
        # first argument is config file
        config_fp = sys.argv[1]
        # second argument (optional) is debug mode file
        if len(sys.argv) == 3:
            dbg_fp = sys.argv[2]
    else:
        if len(sys.argv) < 2:
            logging.warning('[{}] Too few arguments [{}]. 2 or 3 expected.' \
            ' Terminating.'.format(m_name, ' '.join(sys.argv)))
        elif len(sys.argv) > 3:
            logging.warning('[{}] Too many arguments [{}]. 2 or 3 expected.' \
            ' Terminating.'.format(m_name, ' '.join(sys.argv)))
        sys.exit(2)


def start_poller():
    logging.info('[{}] Starting poller on [{}] ({})'.format(m_name, proj, \
        ', '.join(langs)))
    lst_poller.run(proj, langs, rdb_host, rdb_port, rdb_id)


def start_repairer():
    logging.info('[{}] Starting repairer in {} mode'.format \
        (m_name, 'DEBUG' if dbg_fp else 'normal'))
    lst_repairer.run(dbg_fp, rdb_host, rdb_port, rdb_id)


def load_config():
    """
    Load from config file:
        proj    -   project to run on service  (string)
        langs   -   list of languages to run on (list of strings)

    Additionally we check that both variables are in the list of supported
    projects and languages (also loaded from config file).

    Will terminate if options are invalid.
    """
    global langs, proj, rdb_host, rdb_port, rdb_id
    try:
        config = ConfigParser()
        config.read_file(open(config_fp))
    except:
        logging.warning('[{}] Unable to open config [{}]. Terminating'.format \
            (m_name, config_fp))
        sys.exit(1)
    else:
        # Try to load necessary data
        try:
            rdb_host = config.get('redis database', 'host')
            rdb_port = config.get('redis database', 'port')
            rdb_id = config.get('redis database', 'db')
            langs = config.get('run on', 'languages').split()
            proj = config.get('run on', 'project')
            supported_langs = config.get('supported', 'languages').split()
            supported_projs = config.get('supported', 'projects')
        except:
            logging.warning('[{}] Unable to load required data from config' \
                ' [{}]. Terminating'.format(m_name, config_fp))
            sys.exit(1)
        else:
        # Check if all selected languages are supported
            not_supported = []
            for lang in langs:
                if lang not in supported_langs:
                    not_supported.append(lang)
            # Both project and languages not supported
            if not_supported and proj not in supported_projs:
                logging.warning('[{}] Not supported language(s) {} and project' \
                    ' [{}]. Terminating'.format(m_name, not_supported, proj))
                sys.exit(1)
            # Languages not supported
            elif not_supported:
                logging.warning('[{}] Not supported language(s) {}. Terminating' \
                    .format(m_name, not_supported))
                sys.exit(1)
            # Project not supported
            elif proj not in supported_projs:
                logging.warning('[{}] Not supported project [{}]. Terminating' \
                    .format(m_name, proj))
                sys.exit(1)


if __name__ == '__main__':
    run()
