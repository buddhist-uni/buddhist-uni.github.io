(function() {
  const QMIN = 3;
  const CHECKTIME = 3000;
  var searchResults = document.getElementById('search-results');
  var loadingIndicator = document.getElementById('search-loading');
  loadingIndicator.style.display = 'block';
  searchResults.innerHTML = '';

  const initialTitle = document.title;
  function setTitle(query) {
    if (!query) document.title = initialTitle;
    else document.title = query + " | " + initialTitle;
  }
  var stillLoading = document.getElementById('still-loading');
  var running = 0;
  var checkRunning = function(){
    if (running > 0) {
        stillLoading.style.display = 'block';
    }
  };
  function sanitizeQuery(q) {
    if (!q || typeof q == 'undefined') return '';
    var ret = utils.unaccented(q.replace(/[^\P{P}:-]+/ug, ''));
    if (ret.length < QMIN) return '';
    return ret;
  }

  var initialSearchTerm = sanitizeQuery(getQueryVariable('q'));
  setTitle(initialSearchTerm);
  var searchBox = document.getElementById('search-box');
  searchBox.setAttribute("value", initialSearchTerm);
  window.history.replaceState({"html": "", "q": initialSearchTerm}, "", window.location.href);

  var checker = setTimeout(checkRunning, CHECKTIME);
  function prevent(e) { e.preventDefault(); }
  function allow(e) { return true; }
  var searchForm = document.getElementById('search');
  searchForm.onsubmit = prevent;

  try {
      window.search_worker = new Worker("/assets/js/search_index.js");
      var pendingui = null;
      function newQuery(e) {
        var q = e;
        if (e.target) q = e.target.value;
        q = sanitizeQuery(q);
        if (!q) return;
        if (pendingui){ clearTimeout(pendingui); pendingui = null; }
        window.search_worker.postMessage(q);
        clearTimeout(checker);
        checker = setTimeout(checkRunning, CHECKTIME);
        loadingIndicator.style.display = 'block';
        searchForm.onsubmit = prevent;
        running++;
      }
      window.onpopstate = function (e) {
        if (e.state) {
            searchBox.blur();
            searchBox.value = e.state.q;
            initialSearchTerm = e.state.q;
            searchResults.innerHTML = e.state.html;
            setTitle(e.state.q);
            if (!e.state.html) {
                newQuery(e.state.q);
            }
        }
      };
      function maybeRegisterNavigation() {
        if (!running && this.q == sanitizeQuery(searchBox.value)) {
          var nuri = UpdateQueryString('q', this.q);
          setTitle(this.q);
          if (this.q != initialSearchTerm) {
            window.history.pushState(this, "", nuri);
            if (typeof ga != 'undefined') ga('send', 'pageview', {location: nuri});
            initialSearchTerm = this.q;
          } else {
            window.history.replaceState(this, "", nuri);
          }
          pendingui = setTimeout(function(){ searchForm.onsubmit = allow; }, 2000);
        }
      }
      window.search_worker.onmessage = function(e) {
        running--;
        if (running == 0) {
            searchResults.innerHTML = e.data.html;
            loadingIndicator.style.display = 'none';
            stillLoading.style.display = 'none';
            pendingui = setTimeout(maybeRegisterNavigation.bind(e.data), 1100);
        }
      }
      function displayError(e) {
        loadingIndicator.style.display = 'none';
        searchResults.innerHTML = "<li>Oops! " + e.message + "</li>";
      }
      window.search_worker.onerror = function(e) {
        running--;
        searchForm.onsubmit = allow;
        if (e.filename.endsWith("/lunr.min.js")) {
            // Bad query. Maybe still typing?
            e.preventDefault();
            pendingui = setTimeout(function(){ if (!running) displayError(e); }, 2000);
        } else {
            // Unexpected error with my code
            displayError(e);
        }
      }
      if (initialSearchTerm) {
        window.search_worker.postMessage(initialSearchTerm);
        running = 1;
      } else {
        loadingIndicator.style.display = 'none';
        stillLoading.style.display = 'none';
        searchResults.innerHTML = "<li>To search, start typing in the box above!</li>";
        window.history.replaceState({"html": searchResults.innerHTML, "q": ""}, "", "/search/");
      }
      searchBox.addEventListener('input', newQuery);
      searchBox.addEventListener('propertychange', newQuery); // IE8
  } catch (e) {
    loadingIndicator.style.display = 'none';
    searchResults.innerHTML = "<li>Sorry, your browser doesn't seem to support this feature</li>" +
        '<li><a href="https://www.google.com/search?q=site%3www.buddhistuniversity.net+' + encodeURIComponent(initialSearchTerm) + '">Click here to try Google instead</a></li>';
  }
})();
