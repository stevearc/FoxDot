#!/bin/bash

trim() {
    local files="$1"
    # Trim whitespace at end of line
    echo "$files" | xargs sed -i -e 's/[[:blank:]]\+$//'
    # Delete blank lines at end of file
    echo "$files" | xargs sed -i -e :a -e '/^\n*$/{$d;N;ba' -e '}'
}

main() {
    local files=$(find FoxDot -name gen -prune -o \
        \( -name "*.py" -or -name "*.scd" \) \
        -type f -print)

    trim "$files"
}

main "$@"
