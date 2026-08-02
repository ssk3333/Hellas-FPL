(function () {
  "use strict";

  var toggle = document.querySelector(".nav-toggle");
  var nav = document.querySelector(".site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  var countdownEl = document.querySelector("[data-deadline]");
  if (countdownEl) {
    var deadline = new Date(countdownEl.getAttribute("data-deadline"));
    var render = function () {
      if (isNaN(deadline.getTime())) return;
      var diff = deadline.getTime() - Date.now();
      if (diff <= 0) {
        countdownEl.textContent = "Deadline has passed";
        return;
      }
      var totalMinutes = Math.floor(diff / 60000);
      var days = Math.floor(totalMinutes / 1440);
      var hours = Math.floor((totalMinutes % 1440) / 60);
      var minutes = totalMinutes % 60;
      var parts = [];
      if (days) parts.push(days + "d");
      parts.push(hours + "h", minutes + "m");
      countdownEl.textContent = parts.join(" ");
    };
    render();
    setInterval(render, 30000);
  }
})();
