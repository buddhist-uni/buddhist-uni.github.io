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
  const seriesr = /^\/publishers\/([a-z-]+)$/;
  const journalr = /^\/journals\/([a-z-]+)$/;
  const contentr = /^\/content\/([a-z]+)\/([a-z0-9_-]+)$/;
  const courser = /^\/courses\/([a-z_-]+)[\/]?([a-z0-9_-]*)$/;
  const publisherr = /^\/publishers\/([a-z-]+)$/;
  const blogr = /^\/blog\/20[2-7][0-9]\/[01][0-9]\/[0-3][0-9]\/[a-z_-]+$/;
  const authorr = /^\/authors\/([a-z-]+)$/;
  const lp = d.createElement('a');
  function whenceContent(referrer,r,l,m){
    lp.href=referrer;l=d.location;
    r=(referrer&&lp.host==l.host)?lp.pathname:'';
    if (r == '/search/') return "Search Results";
    if (r == '/library/highlights') return "Highlights";
    if (r == '/content/random/') return "Randomizer";
    if (r == '/exclusive/') return "Exclusive Content";
    l = l.pathname;
    m = l.match(tagr) || r.match(tagr);
    if(m) return "Tag Page: "+m[1];
    m = l.match(courser) || r.match(courser);
    if(m) return "Course: "+m[1];
    m = l.match(blogr) || r.match(blogr);
    if(m) return "Blog Post";
    m = r.match(/^\/content\/([a-z]+)\/$/);
    if(m) return "Master "+m[1]+" List";
    m = r.match(contentr);
    if(m) return "Related Content";
    m = l.match(publisherr) || r.match(publisherr);
    if(m) return "Publisher Page";
    m = l.match(authorr) || r.match(authorr);
    if(m) return "Author Page";
    m = l.match(seriesr) || r.match(seriesr);
    if(m) return "Series Page";
    m = l.match(journalr) || r.match(journalr);
    if(m) return "Journal Page";
    if(l.match(contentr)) l = "Content Page";
    if (!referrer) return 'Direct → '+l;
    if (lp.host!=d.location.host) return lp.hostname+" → "+l;
    return l==r?r:r+" → "+l;
  }
  function linkInfo(link,l,p,gp,m){
    l=d.location.pathname;p=link.parentElement;gp=p.parentElement;
    m=l.match(publisherr);
    if(m) return p.tagName=='H3'?['publishers',m[1],'html']:['Generic Links',m[1]];
    m=l.match(seriesr);
    if(m) return [p.tagName=='H3'?'series':'Generic Links',m[1]];
    m=l.match(journalr);
    if(m) return p.tagName=='H3'?['journals',m[1],'html']:['Generic Links',m[1]];
    if(l=='/courses/'){
      if(p.className=='courselink') return ['courses', 'external_courses'];
      if(link.className=='f3') return ['courses', 'mit_courses', 'html'];
      return ['Generic Links','courses'];
    }
    if(gp.className=='social-media-list') return ['marketing', 'social_media_links'];
    if(gp.className=='contact-list') return ['marketing', 'contact_links'];
    if(gp.tagName=='UL' && l=='/sources/')
      return [
        link.closest('div').getAttribute('data-link-type'),
        link.getAttribute('data-slug') || link.text,
        'html'
      ];
    m=l.match(courser)||l.match(tagr)||l.match(authorr);
    if(m) return ['Generic Links',m[1]];
    return ['Generic Links', l];
  }
  function inferLinkType(link){
    if (link.host.includes('youtu')) return 'YouTube (link)';
    switch (link.pathname.slice(-4)) {
      case '.htm': return 'html';
      case 'html': return 'html';
      case '.mp3': return 'mp3';
      case '.pdf': return 'pdf';
    }
    return 'Unknown/HTML';
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
  this.sendEvent=function(oid,name,value,categories,thost){
    if (localStorage.getItem(oid+":click")) return; else localStorage.setItem(oid+":click",1);
    gtag('event','purchase',{
      transaction_id: "T_"+cyrb53(this.getUID()+":"+oid),
      value: value,
      items: [{
        item_id: oid,
        item_name: name,
        price: value,
        item_category: window.WEBSITE_SECTION+' '+categories[0], 
        item_category2: categories[1], 
        item_category3: categories[2], 
        item_category4: categories[3], 
        item_category5: categories[4], 
        item_list_name: whenceContent(d.referrer),
        item_brand: thost
      }]
    });
  };
  this.handleEvent=function(e){this.handleClick(e.target.closest('a'));};
  this.handleClick=function(link){if(!link) return;
   var value = link.getAttribute('ga-event-value')*1;
   if(link.host != d.location.host || value > 0) {
    var cid = link.getAttribute('data-content-path');
    var oid = cid || link.href;
    value ||= 0.15;
    var categories=null,name=null;
    if(cid){
      var category = link.getAttribute('data-content-subcat');
      if (category) category = link.getAttribute('data-content-category')+'/'+category;
      else category = link.getAttribute('data-content-category');
      categories = [
        'content',
        category,
        link.getAttribute('data-content-course'),
        link.getAttribute('data-content-authors'),
        link.getAttribute('data-content-link-ext')
      ];
      name = link.getAttribute('data-content-title');
    }else{
      categories=linkInfo(link);
      categories.splice(2,0,link.getAttribute('data-content-authors')||'(unknown)');
      categories.unshift('link');
      name = link.text;
    }
    thost = link.host || link.pathname;
    categories[4] ||= inferLinkType(link);
    this.sendEvent(oid,name,value,categories,thost);
  }};
  d.addEventListener("click", this, {useCapture: true});
  d.addEventListener("contextmenu", this, {useCapture: true, passive: true});
}
const buggytrack = new BuggyTracker(document);
