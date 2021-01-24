(function() {
  var QMIN = 3;
  var searchResults = document.getElementById('search-results');
  searchResults.innerHTML = '<li><h3 style="text-align: center"><i class="fas fa-circle-notch fa-spin"></i></h3></li>';
  function sanitizeQuery(q) {
    if (!q) return '';
    var ret = utils.unaccented(q.replaceAll('"', ''));
    if (ret.length < QMIN) return '';
    return ret;
  }

  var running = 0;
  var initialSearchTerm = sanitizeQuery(getQueryVariable('q'));
  var searchBox = document.getElementById('search-box');
  searchBox.setAttribute("value", initialSearchTerm);

  setTimeout(function(){
    if (running > 0) {
        searchResults.innerHTML += '<li style="text-align: center">Still loading...</li>';
    }
  }, 3000);
  try {
      window.search_worker = new Worker("/assets/js/search_index.js");
      window.onpopstate = function (e) {
        if (e.state) {
            searchBox.setAttribute("value", e.state.q);
            searchResults.innerHTML = e.state.html;
        }
      };
      window.search_worker.onmessage = function(e) {
        running--;
        if (running == 0) {
            searchResults.innerHTML = e.data;
            var nuri = UpdateQueryString('q', searchBox.value);
            window.history.pushState(
                {"html":e.data, "q":searchBox.value},
                "",
                nuri
            );
            if (ga && searchBox.value != initialSearchTerm) {
                ga('send', 'pageview', {location: nuri});
            }
        }
      }
      window.search_worker.onerror = function(e) {
        searchResults.innerHTML = "<li>Oops! " + e.message + "</li>";
        running = -1;
      }
      if (initialSearchTerm) {
        window.search_worker.postMessage(initialSearchTerm);
        running = 1;
      } else {
        searchResults.innerHTML = "<li>To search, start typing in the box above!</li>";
      }
      function newQuery(e) {
        var q = sanitizeQuery(e.target.value);
        if (!q) return;
        running++;
        window.search_worker.postMessage(q);
      }
      searchBox.addEventListener('input', newQuery);
      searchBox.addEventListener('propertychange', newQuery); // IE8
  } catch (e) {
    searchResults.innerHTML = "<li>Sorry, your browser doesn't seem to support this feature</li>" +
        '<li><a href="https://www.google.com/search?q=site%3Abuddhist-uni.github.io+' + encodeURIComponent(initialSearchTerm) + '">Click here to try Google instead</a></li>';
  }
})();
