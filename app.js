(function () {
  "use strict";
  var LISTS = window.BOOK_LISTS || [];
  var LIST_KEY = "books.list.v1";
  var saved = null;
  try { saved = localStorage.getItem(LIST_KEY); } catch (e) { saved = null; }
  var fromUrl = new URLSearchParams(location.search).get("list");
  var DATA = LISTS.filter(function (l) { return l.slug === (fromUrl || saved); })[0] || LISTS[0] || { books: [], title: "", updated: "" };
  var EMPTY = { millie: { status: "pending" }, ridi: { status: "pending" }, crema: { status: "pending" }, yes24: { status: "pending" } };
  var KEY = "books.overrides.v1";

  // 화면에 보이는 서점 5칸. 리디는 셀렉트(구독)와 단권 구매를 나눠 보여준다.
  var STORES = [
    { id: "millie", name: "밀리의서재", short: "밀리" },
    { id: "ridiSelect", name: "리디셀렉트", short: "리디셀렉트" },
    { id: "crema", name: "크레마클럽", short: "크레마" },
    { id: "ridiBuy", name: "리디 단권", short: "리디 단권" },
    { id: "yes24", name: "YES24 eBook", short: "YES24" }
  ];

  var overrides = {};
  try { overrides = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { overrides = {}; }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(overrides)); } catch (e) { /* 저장 불가 환경 */ } }

  function isPending(book) { return !book.stores; }
  function base(book, sid) {
    var s = book.stores || EMPTY;
    if (sid === "ridiSelect") return { on: s.ridi.status === "select", src: s.ridi, url: s.ridi.url };
    if (sid === "ridiBuy") return { on: s.ridi.status === "select" || s.ridi.status === "buy", src: s.ridi, url: s.ridi.url };
    return { on: s[sid].status === "yes", partial: s[sid].status === "partial", src: s[sid], url: s[sid].url };
  }
  function isOn(book, sid) {
    var o = overrides[book.id];
    return o && sid in o ? o[sid] : base(book, sid).on;
  }
  function isMine(book, sid) { var o = overrides[book.id]; return !!o && sid in o; }

  function sourceLabel(book, sid) {
    var b = base(book, sid), src = b.src;
    if (isMine(book, sid)) return { text: "직접 수정함", warn: true };
    if (sid === "yes24") {
      if (src.source === "api") {
        var t = "YES24 API 확인" + (src.matched ? " · “" + src.matched + "”" : "");
        var sheetYes = /YES24 가능/.test(src.sheet || "");
        return sheetYes !== b.on ? { text: t + " · 시트와 다름", warn: true } : { text: t };
      }
      if (src.source === "crema") return { text: "크레마클럽 상품으로 확인" };
      return { text: "시트 기준 · 미검증" + (b.partial ? " (일부/구판)" : ""), warn: true };
    }
    var sheetOn = /가능/.test(src.sheet || "");
    var text = "자동 확인" + (src.matched ? " · “" + src.matched + "”" : "");
    if (sid !== "ridiBuy" && sheetOn !== b.on) return { text: text + " · 시트와 다름", warn: true };
    return { text: text };
  }

  function krRating(book) {
    if (isPending(book)) return 0;
    var c = book.stores.crema, r = book.stores.ridi;
    var y = book.stores.yes24;
    if (y.rating) return y.rating;                // YES24 10점 만점
    if (c.rating) return c.rating;
    if (r.rating && r.count) return r.rating * 2; // 리디 5점 만점 → 10점 환산
    return 0;
  }
  function screenItems(book) { return (book.screen && book.screen.items) || []; }
  function screenLabel(i) {
    return (i.kind === "movie" ? "영화" : "드라마") + " " + (i.year || "공개 미정") + (i.source === "tmdb" ? " (추정)" : "");
  }
  function storeCount(book) { return STORES.filter(function (s) { return isOn(book, s.id); }).length; }

  var state = { q: "", stores: {}, cat: "", sort: "sheet", open: {}, author: "", view: "books", screen: false };
  var $ = function (id) { return document.getElementById(id); };
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  var norm = function (x) { return (x || "").toLowerCase().replace(/[^0-9a-z가-힣]/g, ""); };
  var fmt = function (n) { return Number(n).toLocaleString("ko-KR"); };

  function visible() {
    var q = state.q.trim().toLowerCase();
    var need = STORES.filter(function (s) { return state.stores[s.id]; });
    var rows = DATA.books.filter(function (b) {
      if (state.author && b.author !== state.author) return false;
      if (state.screen && !screenItems(b).length) return false;
      if (q && (b.title + " " + b.original + " " + b.author + " " + ((b.korean || {}).title || "")).toLowerCase().indexOf(q) < 0) return false;
      if (state.cat === "번역본" ? ["confirmed", "likely"].indexOf((b.korean || {}).verdict) < 0 : state.cat && b.category !== state.cat) return false;
      return need.every(function (s) { return isOn(b, s.id); });
    });
    var by = {
      gr: function (b) { return b.goodreads ? b.goodreads.rating : 0; },
      kr: krRating,
      stores: storeCount
    }[state.sort];
    if (by) rows = rows.slice().sort(function (a, b) { return by(b) - by(a); });
    return rows;
  }

  function renderChips() {
    var box = $("storeChips");
    box.textContent = "";
    STORES.forEach(function (s) {
      var n = DATA.books.filter(function (b) { return isOn(b, s.id); }).length;
      var c = el("button", "chip", s.short);
      c.type = "button";
      c.setAttribute("aria-pressed", String(!!state.stores[s.id]));
      c.appendChild(el("b", null, n));
      c.onclick = function () { state.stores[s.id] = !state.stores[s.id]; render(); };
      box.appendChild(c);
    });
    var sc = el("button", "chip", "영상화");
    sc.type = "button";
    sc.setAttribute("aria-pressed", String(state.screen));
    sc.appendChild(el("b", null, DATA.books.filter(function (b) { return screenItems(b).length; }).length));
    sc.onclick = function () { state.screen = !state.screen; render(); };
    box.appendChild(sc);
    var cats = ["", "번역본"];
    DATA.books.forEach(function (b) { if (cats.indexOf(b.category) < 0) cats.push(b.category); });
    var cb = $("catChips");
    cb.textContent = "";
    cats.forEach(function (c) {
      var n = el("button", "chip", c || "전체");
      n.type = "button";
      n.setAttribute("aria-pressed", String(state.cat === c));
      n.onclick = function () { state.cat = c; render(); };
      cb.appendChild(n);
    });
  }

  function ratingsRow(book) {
    if (isPending(book)) return null;
    var row = el("div", "ratings"), g = book.goodreads, r = book.stores.ridi, c = book.stores.crema, m = book.stores.millie;
    function add(label, score, max, count, unit) {
      var s = el("span");
      s.appendChild(document.createTextNode(label + " "));
      s.appendChild(el("b", null, "★ " + score));
      s.appendChild(el("small", null, "/" + max + " · " + fmt(count) + unit));
      row.appendChild(s);
    }
    if (g) add("Goodreads", g.rating.toFixed(2), 5, g.count, "명");
    var y = book.stores.yes24;
    if (c.rating) add("YES24", c.rating.toFixed(1), 10, c.reviews, "리뷰");
    else if (y.rating) {
      var ys = el("span");
      ys.appendChild(document.createTextNode("YES24 "));
      ys.appendChild(el("b", null, "★ " + Number(y.rating).toFixed(1)));
      ys.appendChild(el("small", null, "/10"));
      row.appendChild(ys);
    }
    if (r.rating && r.count) add("리디", Number(r.rating).toFixed(1), 5, r.count, "명");
    if (m.reviews) { var s = el("span"); s.appendChild(el("small", null, "밀리 리뷰 " + fmt(m.reviews))); row.appendChild(s); }
    return row.childNodes.length ? row : null;
  }

  function card(book) {
    var art = el("article", "book");
    var open = !!state.open[book.id];
    var head = el("div", "head");
    head.setAttribute("role", "button");
    head.tabIndex = 0;
    head.setAttribute("aria-expanded", String(open));
    head.onkeydown = function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); head.click(); } };
    var topRow = el("div", "toprow");
    if (book.cover) {
      var img = el("img", "cover");
      img.src = book.cover; img.alt = ""; img.loading = "lazy"; img.referrerPolicy = "no-referrer";
      img.onerror = function () { img.remove(); };
      topRow.appendChild(img);
    }
    var info = el("div", "info");
    info.appendChild(el("div", "cat", book.category));
    var t = el("h2", "title", book.title);
    var kv = (book.korean || {}).verdict;
    if (kv === "none") t.appendChild(el("span", "badge", "국내판 없음"));
    else if (kv === "likely") t.appendChild(el("span", "badge", "국내판 유력"));
    else if (kv === "unknown") t.appendChild(el("span", "badge", "국내판 확인 불가"));
    info.appendChild(t);
    var meta = el("div", "meta");
    var ab = el("button", "author", book.author);
    ab.type = "button";
    ab.setAttribute("aria-label", book.author + " 작가의 책 모아 보기");
    ab.onclick = function (e) { e.stopPropagation(); pickAuthor(book.author); };
    ab.onkeydown = function (e) { e.stopPropagation(); };
    meta.appendChild(ab);
    meta.appendChild(document.createTextNode(" · " + book.original));
    info.appendChild(meta);
    var kt = (book.korean || {}).title;
    if (kt && norm(kt).indexOf(norm(book.title.split("(")[0].split("/")[0])) < 0) {
      info.appendChild(el("div", "ktitle", "국내 제목: " + kt));
    }
    var rr = ratingsRow(book);
    if (rr) info.appendChild(rr);
    topRow.appendChild(info);
    head.appendChild(topRow);
    var rv = book.review;
    head.appendChild(el("p", "review", rv ? rv.text : book.summary));
    if (rv) {
      var n = rv.sources || {}, parts = [];
      if (n.goodreads) parts.push("Goodreads " + n.goodreads);
      if (n.ridi) parts.push("리디 " + n.ridi);
      if (n.yes24) parts.push("YES24 " + n.yes24);
      head.appendChild(el("p", "src", "독자 리뷰 요약 · " + parts.join(" · ") + "건"));
    } else {
      head.appendChild(el("p", "src", "추천 포인트 (독자 리뷰 요약 전)"));
    }
    var dots = el("div", "dots");
    if (isPending(book)) dots.appendChild(el("span", "dot wait", "국내 정보 조회 중…"));
    else STORES.forEach(function (s) {
      dots.appendChild(el("span", "dot " + (isOn(book, s.id) ? "on" : "off"), s.short));
    });
    var si = screenItems(book);
    if (si.length) {
      var watch = [];
      si.forEach(function (i) { (i.watch || []).forEach(function (w) { if (watch.indexOf(w) < 0 && !/with Ads/.test(w)) watch.push(w); }); });
      dots.appendChild(el("span", "dot screen", "영상화 " + si.map(function (i) { return (i.kind === "movie" ? "영화" : "드라마") + " " + (i.year || "예정"); }).slice(0, 2).join(" · ")
        + (si.length > 2 ? " 외 " + (si.length - 2) : "") + (watch.length ? " ▸ " + watch.slice(0, 2).join(", ") : "")));
    }
    var pp0 = !isPending(book) && book.stores.yes24.paper;
    if (pp0) dots.appendChild(el("span", "dot paper", "종이책 " + pp0.status));
    head.appendChild(dots);
    head.onclick = function () { state.open[book.id] = !open; render(); };
    art.appendChild(head);
    if (!open) return art;
    if (isPending(book)) {
      var pb = el("div", "body");
      if (book.awards) pb.appendChild(el("p", "aw", book.awards));
      pb.appendChild(el("p", "aw", "국내판·서점 입점 정보를 조회하는 중입니다. 잠시 뒤 새로고침하면 채워집니다."));
      art.appendChild(pb);
      return art;
    }

    var body = el("div", "body");
    if (book.review) {
      var r = book.review;
      if (r.pros && r.pros.length) body.appendChild(el("p", "pc", "＋ " + r.pros.join(" · ")));
      if (r.cons && r.cons.length) body.appendChild(el("p", "pc", "－ " + r.cons.join(" · ")));
      if (r.domestic) body.appendChild(el("p", "aw", "국내 독자: " + r.domestic));
      body.appendChild(el("p", "aw", "추천 포인트: " + book.summary));
    }
    var k = book.korean;
    if (k && k.title) {
      body.appendChild(el("p", "aw", "국내판: 『" + k.title + "』" + (k.publisher ? " · " + k.publisher : "") + (k.date ? " " + k.date : "")
        + " · " + (k.verdict === "confirmed" ? "확정 ✅" : "유력 ⚠️") + " (" + k.how + ")"));
    } else if (k) {
      body.appendChild(el("p", "aw", k.verdict === "unknown" ? "국내판: 확인 불가 (조회 실패)"
        : k.verdict === "likely" ? "국내판: 유력 ⚠️ (서점 제목 일치)" : "국내판: YES24에서 찾지 못함"));
    }
    if (book.awards) body.appendChild(el("p", "aw", book.awards));
    if (book.note) body.appendChild(el("p", "aw", "비고: " + book.note));
    if (book.goodreads) {
      var gp = el("p", "aw");
      var a = el("a", null, "Goodreads에서 해외 리뷰 보기 ↗");
      a.href = book.goodreads.url; a.target = "_blank"; a.rel = "noopener";
      gp.appendChild(a);
      body.appendChild(gp);
    }
    if (si.length) {
      var sl = el("ul", "screens");
      si.forEach(function (i) {
        var li = el("li"), a = el("a", null, i.title + " — " + screenLabel(i) + " ↗");
        a.href = i.url; a.target = "_blank"; a.rel = "noopener";
        li.appendChild(a);
        var w = (i.watch || []).filter(function (x) { return !/with Ads/.test(x); });
        if (w.length) li.appendChild(el("span", "ott", "국내 OTT: " + w.join(", ")));
        sl.appendChild(li);
      });
      body.appendChild(el("p", "aw", "영상화 작품"));
      body.appendChild(sl);
    }
    var ul = el("ul", "stores");
    STORES.forEach(function (s) {
      var li = el("li"), on = isOn(book, s.id), lab = sourceLabel(book, s.id);
      var name = el("span", "sname", s.name);
      name.appendChild(el("span", "ssrc" + (lab.warn ? " warn" : ""), lab.text));
      li.appendChild(name);
      var sw = el("button", "sw" + (isMine(book, s.id) ? " mine" : ""), on ? "입점" : "미입점");
      sw.type = "button";
      sw.setAttribute("role", "switch");
      sw.setAttribute("aria-checked", String(on));
      sw.setAttribute("aria-label", s.name + " 입점 여부");
      sw.onclick = function () {
        var o = overrides[book.id] || (overrides[book.id] = {});
        var next = !on;
        if (next === base(book, s.id).on) delete o[s.id]; else o[s.id] = next;
        if (!Object.keys(o).length) delete overrides[book.id];
        save(); render();
      };
      li.appendChild(sw);
      var go = el("a", "go", "↗");
      go.href = base(book, s.id).url; go.target = "_blank"; go.rel = "noopener";
      go.setAttribute("aria-label", s.name + "에서 열기");
      li.appendChild(go);
      ul.appendChild(li);
    });
    body.appendChild(ul);
    var pp = book.stores.yes24.paper;
    if (pp) {
      var pl = el("p", "aw");
      var pa = el("a", null, "YES24 종이책: " + pp.status + " · “" + pp.matched + "” ↗");
      pa.href = pp.url; pa.target = "_blank"; pa.rel = "noopener";
      pl.appendChild(pa);
      body.appendChild(pl);
    }
    if (overrides[book.id]) {
      var u = el("button", "undo", "이 책의 토글을 자동 확인 값으로 되돌리기");
      u.type = "button";
      u.onclick = function () { delete overrides[book.id]; save(); render(); };
      body.appendChild(u);
    }
    art.appendChild(body);
    return art;
  }

  function pickAuthor(name) {
    state.author = name; state.view = "books";
    render();
    window.scrollTo(0, 0);
  }

  function authorIndex() {
    var map = {}, q = state.q.trim().toLowerCase();
    DATA.books.forEach(function (b) { (map[b.author] = map[b.author] || []).push(b); });
    var names = Object.keys(map).filter(function (n) {
      return !q || (n + " " + map[n].map(function (b) { return b.title + b.original; }).join(" ")).toLowerCase().indexOf(q) >= 0;
    }).sort(function (a, b) { return a.localeCompare(b, "ko"); });
    var ul = el("ul", "authors");
    names.forEach(function (n) {
      var li = el("li"), btn = el("button", "arow");
      btn.type = "button";
      btn.appendChild(el("span", "aname", n));
      btn.appendChild(el("span", "acount", map[n].length + "권"));
      btn.appendChild(el("span", "atitles", map[n].map(function (b) { return b.title; }).join(" · ")));
      btn.onclick = function () { pickAuthor(n); };
      li.appendChild(btn);
      ul.appendChild(li);
    });
    return { node: ul, count: names.length };
  }

  function render() {
    renderChips();
    var list = $("list");
    list.textContent = "";
    ["books", "authors"].forEach(function (v) { $("tab-" + v).setAttribute("aria-selected", String(state.view === v)); });
    document.body.dataset.view = state.view;
    var af = $("authorFilter");
    af.hidden = !state.author || state.view !== "books";
    af.textContent = state.author ? "작가: " + state.author + "  ✕" : "";
    if (state.view === "authors") {
      var ai = authorIndex();
      list.appendChild(ai.node);
      $("count").textContent = "작가 " + ai.count + "명";
      $("resetAll").hidden = !Object.keys(overrides).length;
      return;
    }
    var rows = visible();
    rows.forEach(function (b) { list.appendChild(card(b)); });
    if (!rows.length) list.appendChild(el("p", "empty", "조건에 맞는 책이 없습니다."));
    $("count").textContent = rows.length + "권 / 전체 " + DATA.books.length + "권";
    var mine = Object.keys(overrides).length;
    $("resetAll").hidden = !mine;
  }

  var waiting = DATA.books.filter(isPending).length;
  $("sub").textContent = (DATA.subtitle ? DATA.subtitle + " · " : "") + DATA.books.length + "권 · 확인일 " + DATA.updated
    + (waiting ? " · " + waiting + "권 조회 중" : "");
  var sel = $("listSel");
  LISTS.forEach(function (l) {
    var o = el("option", null, l.title + " (" + l.books.length + ")");
    o.value = l.slug; o.selected = l === DATA;
    sel.appendChild(o);
  });
  sel.hidden = LISTS.length < 2;
  sel.onchange = function () {
    try { localStorage.setItem(LIST_KEY, sel.value); } catch (e) { /* 저장 불가 환경 */ }
    location.search = "?list=" + encodeURIComponent(sel.value);
  };
  $("legend").textContent = "입점 여부는 밀리의서재·리디·크레마클럽 검색과 YES24 Open API로 확인한 값입니다. ↗ 로 서점에서 직접 확인한 뒤 토글로 고칠 수 있고, 수정은 이 기기에만 저장됩니다. 리뷰 요약은 Goodreads·리디·YES24에서 수집한 독자 리뷰를 요약한 것입니다. 영상화 정보는 위키데이터와 TMDB 기준이며, OTT 제공처는 TMDB(JustWatch 제공)의 국내 정보입니다.";
  $("tab-books").onclick = function () { state.view = "books"; render(); };
  $("tab-authors").onclick = function () { state.view = "authors"; render(); };
  $("authorFilter").onclick = function () { state.author = ""; render(); };
  $("q").oninput = function (e) { state.q = e.target.value; render(); };
  $("sort").onchange = function (e) { state.sort = e.target.value; render(); };
  $("resetAll").onclick = function () {
    if (confirm("직접 바꾼 토글을 모두 자동 확인 값으로 되돌릴까요?")) { overrides = {}; save(); render(); }
  };
  render();
})();
