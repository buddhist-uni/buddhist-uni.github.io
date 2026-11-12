// Parameters
var BMAX = 250; // Max blurb size in characters
var RMAX = 100; // Max number of results to display
var joinedTitles = []

function normalizeSuttaTitles (obj) {
  var joinedTitleDatabase = []

  for (var i in obj){
    const item = obj[i];
    if (!item || item.type !== "content" || item.category !== "canon") continue;
    const title = item.title || "";
      const titleJoin = title.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/^\s*(?:DN|MN|SN|AN|KN|LAL|DA|MA|SA|EA|SNP|DHP|ITI|THAG|THIG|UD|NIDD|CV|BV|AP|JA|PV|VV|KP|PTS)\s*\d+(?:\.\d+)?\s*[:.-]?\s*/i, "").replace(/\s*[:\-–]\s*.*$/, "").toLowerCase().replace(/[^a-z0-9]/g, "");
      const removedTheOnJoin = titleJoin.replace(/^\s*(?:the)\s*/i, "");
      if(removedTheOnJoin.includes('sutta') || removedTheOnJoin.includes('sutra') || removedTheOnJoin.includes('gatha')) {
        joinedTitleDatabase.push({
          ref: i,
          title: removedTheOnJoin,
          matchData: { metadata: {} }
      });
    }
  }
  return joinedTitleDatabase;
}

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
      return applyErrorStyle('<li>No results found</li>', false);
    }
}

function findOneWordSuttaTitleMatches(query, joinedTitles) {
  var tokenResults = [];
  const normalizedQuery = query.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
  for (var i in joinedTitles){
    const item = joinedTitles[i]
    if(item.title === normalizedQuery){
      tokenResults.push({
        ref: item.ref,
        score: 1,
        matchData: { metadata: {} }
      });
    }
  }
  return tokenResults;
}

// The number of suttas in each book (or in each chapter of the book) that
// SuttaCentral references are matched against. Derived from the citation
// rules in https://discourse.suttacentral.net/t/25616/7 and checked against
// SuttaCentral's API.
var SC_SUTTA_COUNTS = {
  dn: 34, mn: 152, dhp: 423, iti: 112,
  an: [627, 479, 352, 783, 1152, 649, 1124, 627, 432, 746, 1151],
  sn: [81, 30, 25, 25, 10, 15, 22, 12, 14, 12, 25, 213, 11, 39, 20, 13, 43, 22, 21, 12, 12, 159, 46, 96, 10, 10, 10, 10,
       50, 46, 112, 57, 55, 55, 248, 31, 34, 16, 16, 11, 10, 13, 44, 11, 180, 184, 104, 178, 54, 108, 86, 24, 54, 20, 74, 131],
  snp: [12, 14, 12, 16, 19],
  thag: [120, 49, 16, 12, 12, 14, 5, 3, 1, 7, 1, 2, 1, 2, 2, 10, 3, 1, 1, 1, 1],
  thig: [18, 10, 8, 1, 12, 8, 3, 1, 1, 1, 1, 1, 5, 1, 1, 1],
  ud: [10, 10, 10, 10, 10, 10, 10, 10]
};
var SC_BOOK_ABBREVIATIONS = {
  dn: 'DN', mn: 'MN', sn: 'SN', an: 'AN', dhp: 'Dhp', iti: 'Iti',
  snp: 'Snp', thag: 'Thag', thig: 'Thig', ud: 'Ud'
};

// Returns the SuttaCentral id (e.g. "mn4" or "an10.5") if the query is a
// reference to a single sutta that exists, otherwise null.
function suttaCentralUid(query) {
  var m = query.trim().toLowerCase().match(/^(dn|mn|sn|an|dhp|iti|snp|thag|thig|ud)\s*(\d+)(?:[.:](\d+))?$/);
  if (!m) return null;
  var counts = SC_SUTTA_COUNTS[m[1]];
  var first = parseInt(m[2], 10);
  var second = m[3] === undefined ? null : parseInt(m[3], 10);
  if (typeof counts === 'number') {
    if (second !== null || first < 1 || first > counts) return null;
    return m[1] + first;
  }
  if (second === null || first < 1 || first > counts.length || second < 1 || second > counts[first - 1]) return null;
  return m[1] + first + '.' + second;
}

// Splits a SuttaCentral id into its book and number, e.g. "an10.5" -> ["an", "10.5"]
function splitSuttaCentralUid(uid) {
  var book = uid.match(/^[a-z]+/)[0];
  return [book, uid.substring(book.length)];
}

function displaySuttaCentralResult(uid) {
  var parts = splitSuttaCentralUid(uid);
  var title = SC_BOOK_ABBREVIATIONS[parts[0]] + ' ' + parts[1];
  return '<li><h3><a href="https://suttacentral.net/' + uid + '">' + title + ' on SuttaCentral</a></h3>' +
    '<span class="Counter">' + categoryName('canon') + '</span>' +
    '<p>Nothing in the library matched this reference, but you can read the sutta on SuttaCentral.</p></li>';
}

function applyErrorStyle(message, isWarning) {
  if (isWarning){
    const css = '<div style="display: flex; justify-content: flex-start; align-items: center;">';
    const icon = '<i class="fa-solid fa-triangle-exclamation" style="color: rgb(207, 182, 45) !important; margin-right: 15px; margin-left: 5px"></i>'
    return css + icon + " " + '<div style="margin-top: 22px;">' + message + "</div>" + "</div>";
  } else {
    const css = '<div style="display: flex; justify-content: flex-start; align-items: center;">';
    const icon = '<i class="fa-regular fa-circle-question" style="color: rgb(21, 125, 194) !important; margin-right: 15px; margin-left: 5px"></i>'
    return css + icon + " " + '<div style="margin-top: 22px;">' + message + "</div>" + "</div>";
  }
}

function handleSearchMessage(data, searchFn) {
  var results = [];
  var warning = "";
  var words = data.q.trim().split(" ");

  for (var i = 0; i < words.length; i++) {
    const s = words[i].trim();
    if (!s.startsWith("+") && !s.startsWith("-") && s.length > 1 && lunr.stopWordFilter(s)) {
      words[i] = "+" + s;
    } else {
      words[i] = s;
    }
  }
  var query = words.join(' ').trim();
  var suttaUid = suttaCentralUid(data.q);
  if (suttaUid) {
    // Look for that exact sutta, rather than for anything in the same book
    var suttaParts = splitSuttaCentralUid(suttaUid);
    query = '+' + suttaParts[0] + ' +' + suttaParts[1];
  }
  try {
    results = searchFn(query);
    if (!results.length && !suttaUid){
      warning = "<li><strong>No results</strong> found matching all of your terms. Results found matching <em>any</em> term:</li>";
      results = searchFn(data.q.trim());
    }
  } catch (err) {
    if (err.message.indexOf("unrecognised field") >= 0 && query.indexOf(":") >= 0) {
      results = searchFn(data.q.replaceAll(":"," "));
    } else { throw err; }
  }
  if (!results.length && !suttaUid){
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
  finalResults = results.length ? results : findOneWordSuttaTitleMatches(data.q.trim(), joinedTitles);
  var html = displaySearchResults(finalResults);
  var count = finalResults ? finalResults.length : 0;
  if (!count && suttaUid) {
    warning = "";
    html = displaySuttaCentralResult(suttaUid);
    count = 1;
  }
  return {
    "warninghtml": warning ? applyErrorStyle(warning, true) : warning,
    "html": html,
    "count": count,
    "q": data.q,
    "filterquery": data.filterquery,
    "qt": data.qt
  };
}
