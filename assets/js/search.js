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
    if (!q) return '';
    var ret = utils.unaccented(q.replaceAll('"', ''));
    if (ret.length < QMIN) return '';
    return ret;
  }

  var initialSearchTerm = sanitizeQuery(getQueryVariable('q'));
  setTitle(initialSearchTerm);
  var searchBox = document.getElementById('search-box');
  searchBox.setAttribute("value", initialSearchTerm);

  setTimeout(checkRunning, CHECKTIME);
  function prevent(e) { e.preventDefault(); }
  function allow(e) { return true; }
  var searchForm = document.getElementById('search');
  searchForm.onsubmit = prevent;

  try {
      window.search_worker = new Worker("/assets/js/search_index.js");
      window.onpopstate = function (e) {
        if (e.state) {
            searchBox.blur();
            searchBox.value = e.state.q;
            initialSearchTerm = e.state.q;
            searchResults.innerHTML = e.state.html;
            setTitle(e.state.q);
        }
      };
      function maybeRegisterNavigation() {
        if (!running && this.q == searchBox.value && this.q != initialSearchTerm) {
            var nuri = UpdateQueryString('q', this.q);
            setTitle(this.q);
            window.history.pushState(this, "", nuri);
        }
      }
      window.search_worker.onmessage = function(e) {
        running--;
        if (running == 0) {
            searchResults.innerHTML = e.data;
            var query = searchBox.value;
            loadingIndicator.style.display = 'none';
            stillLoading.style.display = 'none';
            var data = {"html": e.data, "q": query};
            setTimeout(maybeRegisterNavigation.bind(data), 1000);
            setTimeout(function(){ searchForm.onsubmit = allow; }, CHECKTIME);
            if (typeof ga != 'undefined' && searchBox.value != initialSearchTerm) {
                ga('send', 'pageview', {location: nuri});
            }
        }
      }
      window.search_worker.onerror = function(e) {
        loadingIndicator.style.display = 'none';
        searchResults.innerHTML = "<li>Oops! " + e.message + "</li>";
        running = -1;
        searchForm.onsubmit = allow;
      }
      if (initialSearchTerm) {
        console.log("Running initial search: " + initialSearchTerm);
        window.search_worker.postMessage(initialSearchTerm);
        running = 1;
      } else {
        loadingIndicator.style.display = 'none';
        stillLoading.style.display = 'none';
        searchResults.innerHTML = "<li>To search, start typing in the box above!</li>";
        window.history.replaceState({"html": searchResults.innerHTML, "q": ""}, "", "/search/");
      }
      function newQuery(e) {
        var q = sanitizeQuery(e.target.value);
        if (!q) return;
        if (!running) {
            loadingIndicator.style.display = 'block';
            setTimeout(checkRunning, CHECKTIME);
            searchForm.onsubmit = prevent;
        }
        running++;
        window.search_worker.postMessage(q);
      }
      searchBox.addEventListener('input', newQuery);
      searchBox.addEventListener('propertychange', newQuery); // IE8
  } catch (e) {
    loadingIndicator.style.display = 'none';
    searchResults.innerHTML = "<li>Sorry, your browser doesn't seem to support this feature</li>" +
        '<li><a href="https://www.google.com/search?q=site%3Abuddhist-uni.github.io+' + encodeURIComponent(initialSearchTerm) + '">Click here to try Google instead</a></li>';
  }
})();
