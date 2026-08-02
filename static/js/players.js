(function () {
  "use strict";

  var dataEl = document.getElementById("players-data");
  var table = document.getElementById("players-table");
  if (!dataEl || !table) return;

  var players = JSON.parse(dataEl.textContent);
  var tbody = table.querySelector("tbody");
  var positionFilter = document.getElementById("filter-position");
  var clubFilter = document.getElementById("filter-club");
  var priceMin = document.getElementById("filter-price-min");
  var priceMax = document.getElementById("filter-price-max");
  var ownMin = document.getElementById("filter-ownership-min");
  var countEl = document.getElementById("players-count");

  var sortKey = "total_points";
  var sortDir = "desc";

  function populateClubs() {
    var clubs = Array.prototype.slice.call(
      new Set(players.map(function (p) { return p.team; }))
    ).sort();
    clubs.forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      clubFilter.appendChild(opt);
    });
  }

  function applyFilters() {
    var pos = positionFilter.value;
    var club = clubFilter.value;
    var pMin = parseFloat(priceMin.value);
    var pMax = parseFloat(priceMax.value);
    var oMin = parseFloat(ownMin.value);
    pMin = isNaN(pMin) ? 0 : pMin;
    pMax = isNaN(pMax) ? Infinity : pMax;
    oMin = isNaN(oMin) ? 0 : oMin;

    var filtered = players.filter(function (p) {
      if (pos && p.position !== pos) return false;
      if (club && p.team !== club) return false;
      if (p.cost_m < pMin || p.cost_m > pMax) return false;
      if (p.ownership_pct < oMin) return false;
      return true;
    });

    filtered.sort(function (a, b) {
      var av = a[sortKey];
      var bv = b[sortKey];
      if (typeof av === "string") {
        av = av.toLowerCase();
        bv = bv.toLowerCase();
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });

    render(filtered);
  }

  function render(list) {
    tbody.innerHTML = "";
    var frag = document.createDocumentFragment();
    list.forEach(function (p) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + p.name + (p.flagged ? ' <span class="badge badge-claret">FLAG</span>' : "") + "</td>" +
        "<td>" + p.team + "</td>" +
        "<td>" + p.position + "</td>" +
        '<td class="num">£' + p.cost_m.toFixed(1) + "m</td>" +
        '<td class="num">' + p.total_points + "</td>" +
        '<td class="num">' + p.form.toFixed(1) + "</td>" +
        '<td class="num">' + p.ownership_pct.toFixed(1) + "%</td>" +
        '<td class="num">' + p.points_per_million.toFixed(2) + "</td>";
      frag.appendChild(tr);
    });
    tbody.appendChild(frag);
    if (countEl) countEl.textContent = list.length + " of " + players.length + " players";
  }

  function wireSortHeaders() {
    var headers = table.querySelectorAll("th[data-sort]");
    headers.forEach(function (th) {
      th.setAttribute("tabindex", "0");
      th.setAttribute("role", "button");
      var activate = function () {
        var key = th.getAttribute("data-sort");
        if (sortKey === key) {
          sortDir = sortDir === "asc" ? "desc" : "asc";
        } else {
          sortKey = key;
          sortDir = "desc";
        }
        headers.forEach(function (other) { other.classList.remove("sorted-asc", "sorted-desc"); });
        th.classList.add(sortDir === "asc" ? "sorted-asc" : "sorted-desc");
        applyFilters();
      };
      th.addEventListener("click", activate);
      th.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });
    });
  }

  [positionFilter, clubFilter, priceMin, priceMax, ownMin].forEach(function (el) {
    if (el) el.addEventListener("input", applyFilters);
  });

  populateClubs();
  wireSortHeaders();
  applyFilters();
})();
