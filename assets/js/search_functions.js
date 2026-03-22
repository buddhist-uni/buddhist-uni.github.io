// Parameters
var BMAX = 250; // Max blurb size in characters
var RMAX = 100; // Max number of results to display

function getPositions(result, field) {
    var positions = [];
    var md = result.matchData.metadata;
    for (var searchTerm in md) {
        var fieldResults = md[searchTerm][field];
        if (!fieldResults) continue;
        for (var p in fieldResults.position) sortedInsert(positions, fieldResults.position[p][0]);
    }
    return positions;
}

function resultMatched(result, fromfield) {
    let md = result.matchData.metadata;
    for (var st in md) {
        if (!md[st][fromfield]) continue;
        for (var mi in md[st][fromfield]['position']) return true;
    }
    return false;
}

function addMatchHighlights(result, blurb, fromfield, startindex, endindex) {
    var startindex = startindex || 0;
    var endindex = endindex || blurb.length;
    var ranges = new Ranges();
    let md = result.matchData.metadata;
    var i = 0; var j = 0;
    for (var searchTerm in md) {
        if (!md[searchTerm][fromfield]) continue;
        for (var mi in md[searchTerm][fromfield].position) {
            let m = md[searchTerm][fromfield].position[mi];
            i = m[0]; j = i+m[1];
            if (i < endindex && j > startindex) {
                ranges.add([(startindex>i?startindex:i)-startindex, j-startindex]);
            }
        }
    }
    i = ranges.array.length - 1;
    var ret = blurb;
    while (i >= 0) {
        ret = ret.substring(0,ranges.array[i][0]) +
            '<strong>' + ret.substring(ranges.array[i][0],ranges.array[i][1]) +
            '</strong>' + ret.substring(ranges.array[i][1], ret.length);
        i--;
    }
    return ret;
}

function getBlurbForResult(result, item, positions) {
    var titleMatch = false;
    let md = result.matchData.metadata;
    for (var searchTerm in md) {
        if (md[searchTerm]['title']) {
            titleMatch = true;
            break;
        }
    }
    if ((titleMatch || positions.length == 0) && item.description){
      var ret = item.description;
      if (item.description.length > BMAX)
        ret = item.description.substring(0, BMAX) + "...";
      return addMatchHighlights(result, ret, 'description');
    }
    // Calculate the best section of the content to blurb
    var best_i = -1;
    var best_n = 0;
    for (var i = 0; i < positions.length; i++) {
        var n = 1;
        var j = i+1;
        while (j < positions.length) {
            if (positions[j] > positions[i] + BMAX) break;
            n++; j++;
        }
        if (n > best_n) {
            best_n = n;
            best_i = i;
        }
    }
    i = positions[best_i];
    j = positions[best_i + best_n - 1];
    var m = (i+j)>>1;
    var startindex = m - (BMAX>>1);
    var pre = true;
    if (startindex <= 0){ startindex = 0; pre = false; }
    var endindex = startindex + BMAX;
    var ret = item.content.substring(startindex,endindex);
    ret = addMatchHighlights(result, ret, 'content', startindex, endindex);
    if (endindex >= item.content.length) return (pre?'...':'') + ret;
    return (pre?'...':'') + ret + "...";
}

function categoryName(c) {
    switch(c) {
        case 'av': return '<i class="fas fa-volume-up"></i> Recording';
        case 'articles': return '<i class="far fa-newspaper"></i> Article';
        case 'booklets': return '<i class="fas fa-book-open"></i> Book';
        case 'monographs': return '<i class="fas fa-book"></i> Book';
        case 'papers': return '<i class="far fa-file-powerpoint"></i> Paper';
        case 'essays': return '<i class="far fa-file-word"></i> Essay';
        case 'canon': return '<i class="fas fa-dharmachakra"></i> Canonical Work';
        case 'reference': return '<i class="fas fa-atlas"></i> Reference Work';
        case 'excerpts': return '<i class="fas fa-book-reader"></i> Excerpt';
    }
    return '<i class="far fa-file"></i> Library Item';
}

function displaySearchResult(result, item) {
    var positions = getPositions(result, 'content');
    var blurb = getBlurbForResult(result, item, positions);
    var type = null;
    switch (item.type) {
        case 'courses': type = '<i class="fas fa-chalkboard"></i> Course'; break;
        case 'content': type = categoryName(item.category); break;
        case 'posts': type = '<i class="fas fa-rss"></i> Blog Post'; break;
        case 'journals': type = '<i class="fas fa-newspaper"></i> Journal'; break;
        case 'authors': type = '<i class="far fa-address-book"></i> Author'; break;
        case 'publishers': type = '<i class="far fa-building"></i> Publisher'; break;
        case 'tags': type = '<i class="fas fa-tag"></i> Bibliography'; break;
        case 'series': type = '<i class="fas fa-list-ol"></i> Series'; break;
    }
    var ret = '<li><h3><a href="' + item.url + '">' + addMatchHighlights(result, item.title, 'title') + '</a></h3>';
    if (type) ret += '<span class="Counter">' + type + '</span>';
    var lc = 0;
    for (var i in item.authors) {
        ret += '<span class="Label ml-1">' +
            addMatchHighlights(result, item.authors[i], 'author', lc, lc + item.authors[i].length) +
            '</span>';
        lc += 2 + item.authors[i].length;
    }
    if (resultMatched(result, 'translator')) ret += '<span class="Label ml-1">Translator: ' +
        addMatchHighlights(result, item.translator, 'translator') +
        '</span>';
    if (resultMatched(result, 'tag')) {
        lc = 0;
        for (var i in item.tags) {
            if (!item.tags[i]) continue;
            let t = '<span class="Label ml-1 text-capitalize"><i class="fas fa-tag"></i> ' +
                addMatchHighlights(result, item.tags[i].replace('-',' '), 'tag', lc, lc + item.tags[i].length) + '</span>';
            if (t.includes('<strong>')) ret += t;
            lc += 1 + item.tags[i].length;
        }
    }
    if (resultMatched(result, 'format')) {
        lc = 0;
        for (var i in item.formats) {
            if (!item.formats[i]) continue;
            let t = '<span class="Label ml-1"><i class="fas fa-file-arrow-down"></i> ' +
                addMatchHighlights(result, item.formats[i], 'format', lc, lc + item.formats[i].length) + '</span>';
            if (t.includes('<strong>')) ret += t;
            lc += 2 + item.formats[i].length;
        }
    }
    return ret + '<p>' + blurb + '</p></li>';
}

function displaySearchResults(results) {
    if (results.length) {
      var ret = '';
      for (var i in results) {
        if (i >= RMAX) break;
        ret += displaySearchResult(results[i], store[results[i].ref]);
      }
      return ret;
    } else {
      //Dylan's failsafe no result feature - check search.scss for css edits
      return '<div class="sutta-finder"><li>No results found</li><li>We may not have every sutta available and we recommend using sutta finder.</li><li>Click the button below - (opens in new tab)<li><a href="https://name.readingfaithfully.org/" class="btn" target="_blank">Sutta Finder!</a></li></div><div class="sutta-finder"><li>Or if you would like to use <strong>Sutta Central</strong></li><li>Click the button below - (opens in new tab)<li><a href="https://suttacentral.net/?lang=en" class="btn" target="_blank">Sutta Central!</a></li></div>';
    }
}

/* #region Handle Search */
function handleSearchMessage(data, searchFn) {
  var results = [];
  var warning = "";

  // Dylan's edit - remove quotes?
  // /["']/g is a JavaScript regular expression literal - g = global flag (match all occurrences, not just the first)
  var preWordsParse = data.q.replace(/["']/g, "");

  // Normalize leading nikaya index, e.g. "MN6" -> "MN 6"
  // I wrote out some for loops and char checks but AI suggested regex when I had him check my code.
  // Regex seems straight forward you just need to research it as I still need to. I would have preferred manually doing it so I can practice my ability
  preWordsParse = preWordsParse.replace(/^(\s*)(MN|SN|SNP|AN|DN)\s*(\d+)/i, function(_, leadingSpace, nikaya, number) {
    return leadingSpace + nikaya.toUpperCase() + " " + number;
  });

  // Back to the original functionality
  var words = preWordsParse.trim().split(" ");
  for (var i = 0; i < words.length; i++) {
    const s = words[i].trim();
    if (!s.startsWith("+") && !s.startsWith("-") && s.length > 1 && lunr.stopWordFilter(s)) {
      words[i] = "+" + s;
    } else {
      words[i] = s;
    }
  }
  var query = words.join(' ').trim();
  try {
    results = searchFn(query);
    if (!results.length){
      warning = "<li><strong>No results</strong> found matching all of your terms. Results found matching <em>any</em> term:</li>";
      results = searchFn(data.q.trim());
    }
  } catch (err) {
    if (err.message.indexOf("unrecognised field") >= 0 && query.indexOf(":") >= 0) {
      results = searchFn(data.q.replaceAll(":"," "));
    } else { throw err; }
  }
  if (!results.length){
    words = data.q.trim().split(" ");
    if (words.find(function(w){ return w.length <= 2; }) == undefined) {
      results = searchFn(words.join("~1 ") + "~1");
      if (results.length)
        warning = "<li><strong>No results</strong> found for your query. Perhaps you meant:</li>";
      else
        warning = "";
    } else {
      warning = "";
    }
  }
  if (data.filterquery && data.filterquery !== "") {
    var filteredResults = searchFn(data.filterquery);
    results = results.filter(function(result) {
      return filteredResults.some(function(filteredResult) {
        return filteredResult.ref === result.ref;
      });
    });
  }
  return {
    "warninghtml": warning,
    "html": displaySearchResults(results),
    "count": results ? results.length : 0,
    "q": data.q,
    "filterquery": data.filterquery,
    "qt": data.qt
  };
}
