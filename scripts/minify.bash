#!/bin/bash

[[ -z "$BUILD_DIR" ]] && { echo "\$BUILD_DIR is unassigned" ; exit 1; }

if [[ "$BUILD_DIR" =~ [[:space:]] ]]; then
    echo "\$BUILD_DIR cannot contain whitespace."
    exit 1
fi

shopt -s globstar

echo "Removing unused CSS Rules..."
npx purgecss -v --content "$BUILD_DIR/**/*.html" "$BUILD_DIR/assets/js/*.js" --css $BUILD_DIR/assets/css/main.css -o $BUILD_DIR/assets/css/purged-main.css
test -s $BUILD_DIR/assets/css/purged-main.css

echo "Minifying CSS..."
npx cleancss --batch --batch-suffix '' -O2 \
    $BUILD_DIR/assets/css/purged-main.css \
    $BUILD_DIR/assets/css/content-perma.css \
    $BUILD_DIR/assets/css/course.css \
    $BUILD_DIR/assets/css/courselist.css \
    $BUILD_DIR/assets/css/frontpage.css \
    $BUILD_DIR/assets/css/search.css \
    $BUILD_DIR/assets/css/tagindex.css

# Don't minify HTML for now because minhtml is too buggy and html-minifier is too slow
# if [ ! -f "$HOME/minhtml" ]; then
#     echo "Installing HTML Minifier..."
#     wget --no-verbose https://github.com/wilsonzlin/minify-html/releases/download/v0.15.0/minhtml-0.15.0-x86_64-unknown-linux-gnu --output-document="$HOME/minhtml"
#     chmod a+x $HOME/minhtml
# fi

# echo "Minifying HTML..."
# HTML_COUNT=$($HOME/minhtml --minify-js --minify-css $BUILD_DIR/**/*.html | wc -l)
# echo "  minified $HTML_COUNT html files"

echo "Minifying Search JS..."
npx uglify-js $BUILD_DIR/assets/js/search_index.js -o $BUILD_DIR/assets/js/search_index.min.js -c -m
mv $BUILD_DIR/assets/js/search_index.min.js $BUILD_DIR/assets/js/search_index.js
# The other js files are too small to need minification

echo "Done!"
