
# LST-Guard

LST-Guard watches recent changes in Wikimedia projects and catches edits that may result in broken links in other pages. More specifically, it catches changes in section labels and corrects them in pages that ([transclude](https://en.wikipedia.org/wiki/Transclusion)) these sections. We tried to make this software easily usable and easily adaptable.

## Table of Contents

- [Files](#files)
- [Background](#background)
  - [Behavior](#behavior)
- [Supported projects and languages](#supported-projects-and-languages)
- [Install](#install)
- [Usage](#usage)
	- [Config file](#config-file)
  - [Log](#log)
- [Further development](#further-development)
- [Contribute](#contribute)
- [License](#license)

## Files

This repository contains:

1. [config file](config.ini) - contains project and languages to run on, as well as user credentials to edit the Wikimedia project
2. [app.py](app.py) - runs `lst_guard` and `lst_therapist` simultaneously
3. [lst_guard](lst_guard.py) detects changed section labels and stores them
4. [lst_therapist](badge) checks stored labels and corrects transclusions if necessary
5. [requirements](requirements.txt) - dependencies necessary to run this program

## Background
LST-Guard consists of two modules: `lst_guard` constantly watches recent changes in a Wikimedia project, detects changed section labels and stores them to be checked later. LST-Guard runs on one project (eg. Wikisource) at a time, but it can watch multiple languages.

The second module, `lst_therapist`, runs only on intervals (5 minutes by default) and sleeps for the rest of the time. If there are any changed label stored, it will go through all pages that transclude them and will - if necessary - replace old labels with new labels.

Both modules are called into life by `app.py`.

### Example
* in a Wikisource page the section label `s1` has [been changed](https://en.wikisource.org/w/index.php?title=Page:EB1911_-_Volume_15.djvu/536&diff=7006224&oldid=6576545) to `Jordan, Dorothea`.
* the article where this section was transcluded [lost its content](https://en.wikisource.org/w/index.php?title=1911_Encyclop%C3%A6dia_Britannica/Jordan,_Wilhelm&oldid=6576548)
* `lst_guard` detected the change in label name in the original page
* `lst_therapist` [corrected](https://en.wikisource.org/w/index.php?title=1911_Encyclop%C3%A6dia_Britannica/Jordan,_Wilhelm&diff=next&oldid=6576548) the label in the transcluding article

### Behavior
Every time a page is edited, `lst_guard` compares the old and new versions and subtracts section labels with the following syntax (including localizations and minor syntactic variations):

```html
<section begin="Some Label" />
```
When the number of section labels in the old and new versions are the same, it will assume that these correspond to each other.

When it comes to correcting these labels in transclusions, `lst_therapist` has to recognize three different syntaxes (again: including localizations and minor syntactic variations):

HTML syntax:
```html
<pages index="Original Page" fromsection="Some Label", tosection= "Some Label"/>
```
Mediawiki syntax:
```
{{#lst:Original Page|Some Label}}
```
Template:
```
{{page|Original Page|num=Page number|section=Some Label}}
```

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

## Install
To use LST-Guard, you need Python3 or higher. You also need Redis-server. If you run a Linux machine, run this command to install Redis:
```sh
$ apt-get install redis-server
```

Then install all Python dependencies with PIP:
```sh
$ pip3 install -r requirements.txt
```

### Usage
Before you run LST-Guard, you have to start Redis-server (& will run it in the background):
```sh
$ redis-server --port 7777 &
```

Then you can start LST-Guard:
```sh
$ python3 app.py
```
You can also add command line arguments but it is probably much easier to use the config file instead. Command line arguments may contain 1 project and 1 or more languages, eg.:

```sh
$ python3 app.py wikisource en es de
```

This will run LST-Guard on the English, Spanish and German Wikisources.

### Config file

The `config.ini` file contains the types of data. The fist, `[run on]` contains the project and the language(s) that LST-Guard will watch when run. If you run the program with command line arguments they will override the data in the config file.

The second section, `[supported on]`, contains the projects and languages that are currently supported. Don't change them unless you know what you are doing.

Lastly, `[credentials]` is the place to add the login data of your Wikimedia bot account. Note, that these have to be obtained from [Special:BotPasswords](https://www.mediawiki.org/wiki/Manual:Bot_passwords).

### Log
A simple `log.txt` is maintained with minimal data about detected changed labels and corrections. The log file of the testing version of the bot can be found here: ([http://185.203.116.239/publ/lst_guard/log.txt](http://185.203.116.239/publ/lst_guard/log.txt)).
## Further development
Next stage is to expand `lst_guard` with some basic NLP to be sure that corresponding labels are correctly identified (as mentioned, current versions assumes that if the number of labels in old and new versions is the same, then they must be corresponding labels).

Secondly we want to add languages, especially languages that have many article transclusions in Wikisource.

## Contribute
Help us with adding new languages. Test the code and find bugs.

## License
