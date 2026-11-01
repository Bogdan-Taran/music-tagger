#!/bin/bash
source "$(dirname -- "$0")/macos_setup.sh"
printf 'Запускаю MusicTagger…\n'
"$MAC_PYTHON" music_tagger.py
