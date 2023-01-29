const cyrb53 = function(str) {
  // A simple string->integer hash function
  // https://stackoverflow.com/a/52171480
  let h1 = 0xdeadbeef ^ 0xabcd0123,
    h2 = 0x41c6ce57 ^ 0xabcd0123;
  for (let i = 0, ch; i < str.length; i++) {
    ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return 4294967296 * (2097151 & h2) + (h1 >>> 0);
};
const BuggyTracker = function (d) {
  const tagr = /^\/tags\/([a-z-]+)[\/]?$/;
  const courser = /^\/courses\/([a-z_-]+)[\/]?([a-z0-9_-]*)$/;
  const blogr = /^\/blog\/20[2-7][0-9]\/[01][0-9]\/[0-3][0-9]\/[a-z_-]+$/;
  const lp = d.createElement('a');
  function whenceContent(referrer,r,l,m){
    lp.href=referrer;l=d.location;
    if (lp.host!=l.host) return null;
    if (referrer) r=lp.pathname; else r='';
    if (r == '/search/') return "Search Results";
    if (r == '/library/highlights') return "Highlights";
    if (r == '/content/random/') return "Randomizer";
    if (r == '/exclusive/') return "Exclusive Content";
    l = l.pathname; m = l.match(tagr) || r.match(tagr);
    if(m) return "Tag Page: "+m[1];
    m = l.match(courser) || r.match(courser);
    if(m) return "Course: "+m[1];
    m = l.match(blogr) || r.match(blogr);
    if(m) return "Blog Post";
    m = r.match(/^\/content\/([a-z]+)\/$/);
    if(m) return "Master "+m[1]+" List";
    m = r.match(/^\/content\/([a-z]+)\/([a-z0-9_-]+)$/);
    if(m) return "Related Content";
    m = r.match(/^\/publishers\/([a-z-]+)$/);
    if(m) return "Publisher Page";
    m = r.match(/^\/authors\/([a-z-]+)$/);
    if(m) return "Author Page";
    m = r.match(/^\/series\/([a-z-]+)$/);
    if(m) return "Series Page";
    m = r.match(/^\/journals\/([a-z-]+)$/);
    if(m) return "Journal Page";
    return null;
  }
  function linkType(link,l,gp){
    l=d.location.pathname; gp=link.parentElement.parentElement;
    if(link.parentElement.className=='courselink' && l=='/courses/') return 'External Course';
    if(link.className=='f3' && l=='/courses/') return 'MIT Course';
    if(gp.className=='social-media-list') return 'Social Media Link';
    if(gp.tagName=='UL' && l=='/sources/') return 'Sources Page Link';
    return 'Link';
  }
  function getGAUID(){
    try{return d.cookie.match(/_ga=(.+?);/)[1].split('.').slice(-2).join(".");}
    catch(e){return null;}
  }
  this.getUID=function(){if(!this._uid){
    this._uid = localStorage.getItem("uid") || getGAUID();
    if(!this._uid){this._uid=Math.random()*10000000;localStorage.setItem("uid", this._uid);}
    } return this._uid;
  };
  this.sendEvent=function(oid,value,list,category){gtag('event','purchase',{
    transaction_id: "T_"+cyrb53(this.getUID()+":"+oid),
    value: value,
    items: [{
      item_id: oid, price: value, item_category: category, item_list_name: list, item_brand: window.WEBSITE_SECTION
    }]
  });};
  this.handleEvent=function(e,link){link=e.target.closest('a');if(link && link.host != d.location.host) {
    var cid = link.getAttribute('data-content-path');
    var oid = cid || link.href;
    var value = link.getAttribute('ga-event-value')*1 || 0.15;
    if (localStorage.getItem(oid+":click")) value=0; else localStorage.setItem(oid+":click",1);
    var list=null,category=null;
    if(cid){
      list=whenceContent(d.referrer);
      category='Content';
    }else{
      category=linkType(link);
    }
    if(value) this.sendEvent(oid,value,list,category);
  }};
  d.addEventListener("click", this, {useCapture: true});
  d.addEventListener("contextmenu", this, {useCapture: true, passive: true});
}
const buggytrack = new BuggyTracker(document);
