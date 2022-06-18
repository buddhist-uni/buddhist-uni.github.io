importScripts("search-index.js");

// Parameters
var BMAX = 250; // Max blurb size in characters
var RMAX = 100;

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
    for (var i in positions) {
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
        case 'essays': return '<i class="far fa-sticky-note fa-rotate-270"></i> Essay';
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
        case 'tags': type = '<i class="fas fa-box-open"></i> Bibliography'; break;
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
    return ret + '<p>' + blurb + '</p></li>';
}

function displaySearchResults(results) {
    if (results.length) {
      var ret = '';
      for (var i in results) {
        if (i > RMAX) break;
        ret += displaySearchResult(results[i], store[results[i].ref]);
      }
      return ret;
    } else {
      return '<li>No results found</li>';
    }
}

self.onmessage = function(e) {
    var results = [];
    try {
      results = idx.search(e.data.q);
    } catch (err) {
      if (err.message.indexOf("unrecognised field") >= 0 && e.data.q.indexOf(":") >= 0) {
        results = idx.search(e.data.q.replaceAll(":",""));
      } else { throw err; }
    }
    if (!results.length){
      var words = e.data.q.split(" ");
      if (words.find(function(w){ return w.length <= 2; }) == undefined)
        results = idx.search(words.join("~1 ") + "~1");
    }
    self.postMessage({
      "html": displaySearchResults(results),
      "count": results ? results.length : 0,
      "q": e.data.q,
      "qt": e.data.qt
    });
}


