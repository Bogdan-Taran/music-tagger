#!/bin/bash
# Shared setup; sourced by the two .command launchers.
set -e
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

fail() {
    printf '\n%s\n' "$1"
    if [ -t 0 ]; then read -r -p 'Нажмите Enter, чтобы закрыть окно…' unused_reply; fi
    exit 1
}
trap 'fail "Не удалось завершить операцию. Подробности ошибки указаны выше."' ERR

check_python() {
    [ -x "$1" ] && "$1" -c 'import sys, tkinter; assert sys.version_info >= (3, 11); assert tkinter.TkVersion >= 8.6' >/dev/null 2>&1
}

if ! check_python "$PWD/.venv-macos/bin/python"; then
    chosen_python=''
    # Finder has a minimal PATH. Prefer the python.org installation with bundled Tk.
    for candidate in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.{14,13,12,11}/bin/python3 \
        /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 || true)"; do
        if check_python "$candidate"; then
            chosen_python="$candidate"
            break
        fi
    done
    if [ -z "$chosen_python" ]; then
        fail 'Нужен Python 3.11 или новее с Tk 8.6+. Установите macOS installer с https://www.python.org/downloads/macos/ и снова откройте этот файл. Системный Python от Apple не подходит.'
    fi
    "$chosen_python" -m venv .venv-macos
fi
MAC_PYTHON="$PWD/.venv-macos/bin/python"
if ! "$MAC_PYTHON" -c 'import mutagen, PIL, PIL.ImageTk' >/dev/null 2>&1; then
    printf 'Устанавливаю библиотеки (при первом запуске нужен интернет)…\n'
    "$MAC_PYTHON" -m pip install -r requirements.txt
fi
