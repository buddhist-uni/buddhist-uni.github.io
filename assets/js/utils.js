function getQueryVariable(variable) {
    var query = window.location.search.substring(1);
    var vars = query.split('&');

    for (var i = 0; i < vars.length; i++) {
      var pair = vars[i].split('=');

      if (pair[0] === variable) {
        return decodeURIComponent(pair[1].replace(/\+/g, '%20'));
      }
    }
}

function UpdateQueryString(key, value, url) {
    value = encodeURIComponent(value);
    if (!url) url = window.location.href;
    var re = new RegExp("([?&])" + key + "=.*?(&|#|$)(.*)", "gi"),
        hash;

    if (re.test(url)) {
        if (typeof value !== 'undefined' && value !== null) {
            return url.replace(re, '$1' + key + "=" + value + '$2$3');
        } 
        else {
            hash = url.split('#');
            url = hash[0].replace(re, '$1$3').replace(/(&|\?)$/, '');
            if (typeof hash[1] !== 'undefined' && hash[1] !== null) {
                url += '#' + hash[1];
            }
            return url;
        }
    }
    else {
        if (typeof value !== 'undefined' && value !== null) {
            var separator = url.indexOf('?') !== -1 ? '&' : '?';
            hash = url.split('#');
            url = hash[0] + separator + key + '=' + value;
            if (typeof hash[1] !== 'undefined' && hash[1] !== null) {
                url += '#' + hash[1];
            }
            return url;
        }
        else {
            return url;
        }
    }
}

var defaultComparer = function (a, b) { return (a > b); };
function locationOf(array, element, comparer, start, end) {
    if (array.length === 0)
        return 0;
    if (!comparer)
        comparer = defaultComparer;
    start = start || 0;
    if (end === null || end === undefined)
      end = array.length-1;
    var pivot = (start + end) >> 1;
    if (comparer(element, array[pivot])) {
        return (start==end)? pivot+1: locationOf(array, element, comparer, pivot+1, end);
    }
    if (start==end) return pivot;
    return locationOf(array, element, comparer, start, pivot);
 };

function sortedInsert(array, element) {
    array.splice(locationOf(array, element), 0, element);
    return array;
}
var utils = {
    'unaccented': function (str) { return str?str.normalize("NFD").replace(/[\u0300-\u036f]/g, ""):str; },
    'ascii': /^[ -~]+$/
};

function Ranges() {
    this.array = [];
}
Ranges.compareStart = function (a, b) { return a[0] > b[0]; };
Ranges.compareEnd = function (a, b) { return a[1] > b[1]; };
Ranges.prototype.dedupeAt = function(index) {
    if (index+1<this.array.length && this.array[index][1]+1>=this.array[index+1][0]) {
        this.array.splice(index, 2, [this.array[index][0], this.array[index+1][1]]);
    }
    if (index>0 && this.array[index-1][1]+1>=this.array[index][0]) {
        this.array.splice(index-1, 2, [this.array[index-1][0], this.array[index][1]]);
    }
};
Ranges.prototype.add = function(range) {
    var si = locationOf(this.array, range, Ranges.compareStart);
    var ei = locationOf(this.array, range, Ranges.compareEnd);
    if (si > ei) return;
    this.array.splice(si, ei-si, range);
    this.dedupeAt(si);
};

