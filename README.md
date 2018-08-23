
# LST-Guard

LST-Guard watches recent changes in Wikimedia projects and catches edits that may cause broken links in ([transclusion](https://en.wikipedia.org/wiki/Transclusion)) pages. This is done by one process (`lst_poller`) catching and saving all changed section labels and the second process (`lst_worker`) checking if those result in broken transclusions and if so, updating the section labels in pages where they are transcluded.

## Table of Contents

- [Files](#files)
- [Architecture](#architecture)
  - [Behavior](#behavior)
  - [Example](#example)
- [Supported languages](#supported-languages)
- [Usage](#usage)
- [Install requirements](#install-requirements)
	- [Starting](#starting)
	- [Managing & monitoring](#managing-&-monitoring)
	- [Run in debug-mode](#run-in-debug-mode)
	- [Config file](#config-file)
  - [Logging](#logging)
- [Further development](#further-development)
- [Contribute](#contribute)
- [License](#license)

## Files

This repository contains:

1. [config.ini](config.ini) - contains options for running the program, as well credentials of as a Wikimedia user (bot) to edit pages. (See details below.)
2. [lst_manager.py](lest_manager.py) - manage and monitor the program.
3. [app.py](app.py) - runs `lst_poller` and `lst_worker` in the background.
4. [lst_poller.py](lst_poller.py) - detects changed section labels and stores them in Redis.
5. [lst_worker.py](lst_worker.py) - checks stored labels and corrects transclusions if necessary.
6. [localizations.py](localizations.py) - syntax details and other language-specific data used to extract label names.
7. [requirements.txt](requirements.txt) - list of dependencies necessary to run this program.

## Architecture

LST-Guard consists of two background processes: `lst_poller` constantly watches recent changes in a Wikimedia project reading the _[EventStreams](https://wikitech.wikimedia.org/wiki/EventStreams)_ feed, detects changed section labels and stores them to be checked later. It filters out edits in `project` (usually Wikisource), in `languages` (defined in `config.ini`) and in [namespace](https://en.wikisource.org/wiki/Help:Namespaces) `104` (_Pages:_). Consequently it checks if section labels have been changed in these edits. If yes, old and new labels, page and edit info is stored in the Redis database.

The second process, `lst_worker`, runs only on intervals (5 minutes by default). If there is new data in Redis, it checks if any sections of the edited page is transcluded in other _content_ pages (namespace `1`) and if they are not updated manually, it will replace old labels with new labels.

Both modules are called into life by `app.py`. It is preferable not to execute this module directly, but to use `lst_manager.py` instead.

### Behavior

Every time a page is edited, `lst_poller` compares the old and new revision texts of the article and extracts section labels assuming the following syntax is used (including localizations and minor syntactic variations, see `localizations.py`):

```html
<section begin="Some Label" />
```
When the number of section labels in the old and new versions are the same, it will assume that they correspond to each other.

When it comes to correcting these labels in transclusions, `lst_worker` has to recognize three different syntaxes (again: including localizations and minor syntactic variations):

1. HTML syntax:
```html
<pages index="Original Page" fromsection="Section Label", tosection= "Section Label"/>
```

2. Mediawiki syntax:
```
{{#lst:Original Page|Section Label}}
```

3. Template:
```
{{page|Original Page|num=Page number|section=Section Label}}
```

### Example

Here is an example when editing sectoin labels causes a broken transclusion and how it is handled by LST-Guard:

1. in a Wikisource page the section label `s1` has [is changed](https://en.wikisource.org/w/index.php?title=Page:EB1911_-_Volume_15.djvu/536&diff=7006224&oldid=6576545) to `Jordan, Dorothea` by an editor.
2. the article where this section was transcluded [lost its content](https://en.wikisource.org/w/index.php?title=1911_Encyclop%C3%A6dia_Britannica/Jordan,_Wilhelm&oldid=6576548)
3. `lst_poller` detects the change in label name in the original page
4. `lst_worker` [corrects](https://en.wikisource.org/w/index.php?title=1911_Encyclop%C3%A6dia_Britannica/Jordan,_Wilhelm&diff=next&oldid=6576548) the label in the transcluding article

## Supported languages

The current version supports 9 languages:
* English
* German
* Spanish
* Armenian
* Portuguese
* French
* Italian
* Polish
* Russian

## Usage

### Install requirements

To use LST-Guard, Python3 is required. `redis-server` must also be installed. For a Debian/Ubunti machine, install it with this command:
```sh
$ apt-get install redis-server
```
or use your preferred package manager.

Furthermore, the Python libraries `redis`, `configparser`, `sseclient`
and `requests` are required. Install all of them with PIP:

```sh
$ pip3 install -r requirements.txt
```

Finally we use `nohup` to run LST-Guard in background, this program is present in most Linux machines.

### Starting

Before starting LST-Guard, a redis-server should be running. This can be done with this command (note that `&` will run it in the background):

```sh
$ redis-server --port 7777 &
```

Start LST-Guard using `lst_manager`:

```sh
$ ./lst_manager.py -start
```

If everything is okay, your terminal should print this:

```sh
$ ./lst_manager.py -start
Check: Redis DB running OK (host: localhost, port: 7777, db: 0)
Check: config file [config.ini]: Success.
Flushing Redis database.
Starting LST-guard: lst_poller & lst_worker initiated.
$
```

### Managing & monitoring

The status of the processes can be queried with the following command
```sh
$ python3 lst_manager.py -status
```

An example output could be:

```sh
LST-Guard processes:
lst_poller:	  RUNNING
lst_worker:	RUNNING

```

Run `lst_manager` without any options to see its full functionality: you can check the status of the two processes, restart or stop them, check the redis-database and export its contents.

### Run in debug-mode

#TODO


### Config file

The `config.ini` file contains the types of data:

1. `[run on]` - contains the project and the language(s) that LST-Guard will watch when running.

2. `[supported on]` - contains the projects and languages that are supported. Change this section only with great precaution and on your own risk.

3. `[credentials]` - should contain the username and password of your Wikimedia bot account. Note, that these have to be obtained from [Special:BotPasswords](https://www.mediawiki.org/wiki/Manual:Bot_passwords).

4. `[redis database]` - contains `hostname`, `port` and `db` number of the redis database.

### Logging

<s>[log.txt](http://185.203.116.239/publ/lst_poller/log.txt) is the main log and contains all detected changed labels and corrections.
[stdout.txt](http://185.203.116.239/publ/lst_poller/stdout.txt) is where the terminal output of the last/current run is dumped and contains all pages that were checked by the bot.</s>

Will be updated

## Further development
Next stage is to expand `lst_poller` with some basic NLP to be sure that corresponding labels are correctly identified (as mentioned, current versions assumes that if the number of labels in old and new versions is the same, then they must be corresponding labels).

<s>Secondly we want to add languages, especially languages that have many transclusions in Wikisource.</s> Done

## Contribute
Help us with adding new languages. Test the code and find bugs.

## License
We will define the license of LST-Guard soon. Meanwhile feel free to use, share, copy and modify it however you want as it is free software.
