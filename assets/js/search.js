(function () {
  const QMIN = 3;
  const CHECKTIME = 2500;
  var searchResults = document.getElementById('search-results');
  var loadingIndicator = document.getElementById('search-loading');
  var pendingui = null;

  const initialTitle = document.title;
  function setTitle(query) {
    if (!query) document.title = initialTitle;
    else document.title = query + " | " + initialTitle;
  }
  var stillLoading = document.getElementById('still-loading');
  var running = 0;
  var checkRunning = function () {
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
  
  const searchBox = document.getElementById('search-box');
  const filterDropdown = document.getElementById("search-filter");

  // Initialize search box and remember original value
  var originalSearchTerm = sanitizeQuery(getQueryVariable('q'));
  searchBox.setAttribute("value", originalSearchTerm);

  // Initialize filter dropdown and remember original value
  var originalFilterValue = sanitizeQuery(getQueryVariable('filter'));
  if (originalFilterValue !== null && originalFilterValue !== '') {
    filterDropdown.value = originalFilterValue;
  }

  setTitle(originalSearchTerm);

  window.history.replaceState({ "html": "", "q": originalSearchTerm, "filter": originalFilterValue }, "", window.location.href);

  var checker = setTimeout(checkRunning, CHECKTIME);

  function maybeRegisterNavigation() {
    if (this.q == sanitizeQuery(searchBox.value) && this.filterquery == sanitizeQuery(filterDropdown.value)) {
      clearTimeout(pendingui);
      var nuri = '?q=' + encodeURIComponent(this.q);
      if (this.filterquery !== null && this.filterquery !== '') {
        nuri += '&filter=' + encodeURIComponent(this.filterquery);
      }
      setTitle(this.q);
      if (this.q != originalSearchTerm || this.filterquery != originalFilterValue) {
        window.history.pushState(this, "", nuri);
        if (typeof ga != 'undefined') ga('send', 'pageview', { location: nuri });
        if (typeof gtag != 'undefined') gtag('event', 'search', { search_term: this.q });
        originalSearchTerm = this.q;
        originalFilterValue = this.filterquery;
      } else {
        window.history.replaceState(this, "", nuri);
      }
      pendingui = setTimeout(function () { searchForm.onsubmit = allow; }, CHECKTIME);
    }
  }
  function prevent(e) { searchBox.blur(); e.preventDefault(); }
  function allow(e) { return true; }
  function handle(e) {
    maybeRegisterNavigation.bind(this)();
    prevent(e);
  }
  var searchForm = document.getElementById('search');
  searchForm.onsubmit = prevent;

  try {
    window.search_worker = new Worker("/assets/js/search_index.js");
    function newQuery(e) {
      var q = searchBox.value;
      var filterValue = filterDropdown.value;
      var filterQuery = "";

      if (e.target === searchBox) {
        q = e.target.value;
      } else if (e.target === filterDropdown) {
        filterValue = e.target.value;
      }

      if (filterValue && filterValue !== "") {
        filterQuery = filterValue;
      }

      q = sanitizeQuery(q);
      if (!q) return;
      if (pendingui) {
        clearTimeout(pendingui);
        pendingui = null;
      }

      window.search_worker.postMessage({ 'q': q, 'filterquery': filterQuery, 'qt': performance.now() });
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
        originalSearchTerm = e.state.q;
        filterDropdown.value = e.state.filterquery ?? "";
        searchResults.innerHTML = e.state.html;
        setTitle(e.state.q);
        if (!e.state.html) {
          newQuery(e.state.q);
        }
      }
    };
    window.search_worker.onmessage = function (e) {
      running--;
      if (running == 0) {
        var perf = ((performance.now() - e.data.qt) / 1000).toFixed(2);
        if (perf == "0.00") perf = "&lt;0.01";
        searchResults.innerHTML = e.data.warninghtml + '<li style="margin-bottom:0;text-align:right;">' + e.data.count + ' results (' + perf + ' seconds)</li>' + e.data.html;
        loadingIndicator.style.display = 'none';
        stillLoading.style.display = 'none';
        searchResults.onclick = maybeRegisterNavigation.bind(e.data);
        if (document.activeElement === searchBox) {
          pendingui = setTimeout(maybeRegisterNavigation.bind(e.data), CHECKTIME);
          searchForm.onsubmit = handle.bind(e.data);
        } else {
          pendingui = setTimeout(maybeRegisterNavigation.bind(e.data), 1);
        }
      }
    }
    function displayError(e) {
      loadingIndicator.style.display = 'none';
      searchResults.innerHTML = "<li>Oops! " + e.message + "</li>";
    }
    window.search_worker.onerror = function (e) {
      running--;
      searchForm.onsubmit = allow;
      if (e.filename.endsWith("/lunr.min.js")) {
        // Bad query. Maybe still typing?
        e.preventDefault();
        clearTimeout(pendingui);
        pendingui = setTimeout(function () { if (!running) displayError(e); }, CHECKTIME);
      } else {
        // Unexpected error with my code
        displayError(e);
      }
    }
    if (originalSearchTerm) {
      const filterValue = sanitizeQuery(getQueryVariable('filter'));
      const filterQuery = filterValue ? ' ' + filterValue : '';
      window.search_worker.postMessage({ 'q': originalSearchTerm, 'filterquery': filterQuery, 'qt': performance.now() });
      running = 1;
    }
    
     else {
      loadingIndicator.style.display = 'none';
      stillLoading.style.display = 'none';
      searchResults.innerHTML = '<li class="instructions">To search, start typing in the box above!</li><li class="instructions">You can filter your results by adding <code>[+/-][field]:[value]</code>. For example, to find <a href="/search/?q=%2Bagama%20-author%3Aanalayo&filter=%2Bin%3Aarticles">an article about the Āgamas by someone <i>not</i> named "Analayo"</a>, use the <code>-author:analayo</code> filter. Or, to find <a href="/search/?q=%2Btranslator%3Abodhi&filter=%2Bin%3Acanon">suttas translated by Bhikkhu Bodhi</a>, you can use the <code>+translator:bodhi</code> filter. We currently support the fields: title, author, translator, and &quot;is&quot; (fiction, film, music, podcast, poetry).</li><li class="instructions"><strong>Search is fuzzy</strong> and may match some terms only vaguely similar to yours. It does <strong>not</strong> support &quot;exact phrases.&quot;</li>';
      window.history.replaceState({ "html": searchResults.innerHTML, "q": "", "filter": originalFilterValue }, "", window.location.href);
    }
    searchBox.addEventListener('input', newQuery);
    searchBox.addEventListener('propertychange', newQuery); // IE8
    filterDropdown.addEventListener('change', newQuery);
    setTimeout(searchBox.focus.bind(searchBox), 610);
  } catch (e) {
    console.error(e)
    loadingIndicator.style.display = 'none';
    searchResults.innerHTML = '<li class="instructions">Sorry, your browser doesn\'t seem to support this feature</li>' +
      '<li class="instructions"><a href="https://www.google.com/search?q=site%3buddhistuniversity.net+' + encodeURIComponent(originalSearchTerm) + '">Click here to try Google instead</a></li>';
  }
})();
