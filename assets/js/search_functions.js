// Parameters
var BMAX = 250; // Max blurb size in characters
var RMAX = 100; // Max number of results to display

const suttaFinder = '<a href="https://name.readingfaithfully.org/" class="btn" target="_blank">Sutta Finder</a>'

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
      return '<li>No results found</li>';
    }
}

function handleSearchMessage(data, searchFn) {
  var results = [];
  var warning = "";

  /* Dylan's edit - the search queries are complex, but here in this function we are certainly testing
      user input against our database info. My theory, is first do a oneword check against database titles
      joined in one word, if matched show results and if not then go back to our usual methods. 

      I had AI confirm against all lunr search scripts, that this is the best place to test this theory, and the AI
      has implemented this fixed based on the context of our .js scripts. 
  */
  var oneWordQuery = data.q.trim();
  if (oneWordQuery && oneWordQuery.indexOf(" ") === -1) {
    try {
      results = searchFn(oneWordQuery);
    } catch (_) {
      results = [];
    }
    if (!results.length && typeof store !== "undefined" && store) {
      var normalizedToken = utils.unaccented(oneWordQuery).toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
      if (normalizedToken) {
        var matchedRefs = [];
        for (var ref in store) {
          var rawTitle = store[ref] && store[ref].title ? store[ref].title : "";
          var titleText = Array.isArray(rawTitle) ? rawTitle.join("") : String(rawTitle);
          var joinedTitle = utils.unaccented(titleText).toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");

          // after joining title, use regex to take away leading nikaya index tokens so we don't get -> an944pannavimuttasuttafreedbywisdom
          // and take away any words/characters after sutta
          var normalizedJoinedTitle = joinedTitle
            .replace(/^(dn|mn|sn|an|snp)\d+(\d+)?/i, "")
            .replace(/(sutta).*/i, "$1");

          // here I check for sutta in the string.
          const hasSuttaOneWord = /\bsutta\b/i.test(normalizedJoinedTitle);
          if(hasSuttaOneWord){
            warning = "<li>We have detected the use of sutta. If you don't find what you are looking for - put spaces between the pali words or use sutta finder whilst we improve our searching features</li>" + "<li>" + suttaFinder + "</li>"
          }
          if (joinedTitle === normalizedToken || normalizedJoinedTitle === normalizedToken) {
            matchedRefs.push(ref);
          }
        }
        if (matchedRefs.length) {
          results = matchedRefs.map(function(matchedRef) {
            return { ref: matchedRef, score: 1, matchData: { metadata: {} } };
          });
        }
      }
    }
    if (results.length) {
      if (data.filterquery && data.filterquery !== "") {
        var earlyFilteredResults = searchFn(data.filterquery);
        results = results.filter(function(result) {
          return earlyFilteredResults.some(function(filteredResult) {
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
  }

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
