<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Bote_Boas_Vindas2.png/206px-Bote_Boas_Vindas2.png" align="right" width="103px" height="120"/>

# LST-Guard

[![lst guard](https://img.shields.io/badge/lst%20guard-mediawiki%20bot-ff69b4.svg?style=flat-square)](https://github.com/MediaWikiArmenia/LST-Guard)

> Mediawiki bot to fix broken transclusions. Easily adaptable to similar tasks.

LST-Guard watches recent changes in Wikimedia projects and catches edits that may result in broken links in other pages. More specifically, it catches changes in section labels and corrects them in pages that ([transclude](https://en.wikipedia.org/wiki/Transclusion)) these sections. This program is intended to be both easily usable and easily adaptable. The current version supports 3 Wikimedia projects and 5 languages. The current version supports 3 Wikimedia projects and 5 languages (see under Supported Languages).

The software consists of two main modules: `lst_guard` constantly watches recent changes in a Wikimedia project, detects changed section labels and stores them for the second module. LST-Guard watches only one project (eg. Wikisource), but it can watch multiple languages simultaneously. The second module, `lst_therapist`, will be only active if there are any labels stored and will check this with 5 minutes interval. For any changed section label, it will go through all pages that transclude them and will - if necessary - correct them. Both modules are called into life by `app.py`.

This repository contains:

1. [config file](config.ini) - defines what project and languages to run on, as well as user credentials to edit the Wikimedia project
2. [app.py](app.py) - runs `lst_guard` and `lst_therapist`, command line arguments will override config file
3. [lst_guard](lst_guard.py) detects changed section labels and stores them
4. [lst_therapist](badge) checks stored labels and corrects transclusions
5. [requirements](requirements.txt) - dependencies necessary to run this program


## Table of Contents

- [Background](#background)
  - [Behavior](#behavior)
- [Supported projects and languages](#supported-projects-and-languages)
- [Install](#install)
- [Usage](#usage)
	- [Config file](#config-file)
  - [Log](#log)
- [Maintainers](#maintainers)
- [Further development](#further-development)
- [Contribute](#contribute)
- [License](#license)

## Background

([see MediaWiki for more info](https://www.mediawiki.org/wiki/Extension:Labeled_Section_Transclusion]))
