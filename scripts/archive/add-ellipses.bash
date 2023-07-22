#!/bin/bash
# Auto-generated bash version of the py script by ChatGPT (for AWK educational purposes)

function modify_markdown() {
    local file_path="$1"
    local tmp_file=$(mktemp)

    local modification_needed=false

    awk '
        BEGIN { previous_line_empty = 0; }
        /^[[:space:]]*$/ { previous_line_empty = 1; print; next; }
        previous_line_empty && /^> [a-z]/ && !/.*  $/ { modification_needed = 1; print "> … " substr($0, 3); previous_line_empty = 0; next; }
        { print; previous_line_empty = 0; }
    ' "$file_path" > "$tmp_file"

    if $modification_needed; then
        mv "$tmp_file" "$file_path"
        echo "Modified: $file_path"
    else
        rm "$tmp_file"
        echo "No changes needed: $file_path"
    fi
}

function process_all_markdown_files() {
    local root_dir="./" # Replace this with the root directory of your Git repository
    local markdown_files=( $(find "$root_dir" -type f -name "*.md") )

    local total_files=${#markdown_files[@]}
    echo "Total Markdown files found: $total_files"

    for ((idx=0; idx<$total_files; idx++)); do
        local file_path="${markdown_files[idx]}"
        echo "Processing file $((idx+1))/$total_files: $file_path"
        modify_markdown "$file_path"
    done
}

process_all_markdown_files
echo "Markdown modification complete!"
