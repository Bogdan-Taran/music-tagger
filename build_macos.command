#!/bin/bash
source "$(dirname -- "$0")/macos_setup.sh"
printf 'Собираю приложение для этого Mac…\n'
"$MAC_PYTHON" -m pip install 'pyinstaller>=6.11,<7'
export PYINSTALLER_CONFIG_DIR="$PWD/.build-cache"
"$MAC_PYTHON" -m PyInstaller --noconfirm --clean --onedir --windowed \
    --name MusicTagger --osx-bundle-identifier local.musictagger.app \
    --distpath dist-macos --workpath build-macos music_tagger.py
printf '\nГотово: %s/dist-macos/MusicTagger.app\nМожно перенести MusicTagger.app в папку «Программы».\n' "$PWD"
open -R "$PWD/dist-macos/MusicTagger.app"
