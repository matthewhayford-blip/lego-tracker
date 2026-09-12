/* Hover/tap tooltip for the modelled-value chart on set pages.
   Every point on the line (not just the labelled 5yr/10yr ones) gets an
   invisible, larger hit-target circle (.chart-pt, drawn in set.html) that
   carries data-value / data-pct / data-label attributes. This file shows a
   small tooltip positioned over whichever point is hovered, focused, or
   tapped -- no server-side or per-page logic, just the shared behaviour. */
(function () {
  "use strict";

  function buildTooltipContent(tooltip, pt) {
    tooltip.textContent = "";

    var value = pt.getAttribute("data-value") || "";
    var pct = pt.getAttribute("data-pct") || "";
    var label = pt.getAttribute("data-label") || "";

    if (value) {
      var b = document.createElement("b");
      b.textContent = value;
      tooltip.appendChild(b);
    }
    if (pct) {
      var pctEl = document.createElement("span");
      pctEl.className = "tt-pct";
      if (pct.charAt(0) === "+") pctEl.className += " good";
      else if (pct.charAt(0) === "-") pctEl.className += " bad";
      pctEl.textContent = pct;
      tooltip.appendChild(pctEl);
    }
    if (label) {
      var labelEl = document.createElement("span");
      labelEl.className = "tt-label";
      labelEl.textContent = label;
      tooltip.appendChild(labelEl);
    }
  }

  function initChart(card) {
    var tooltip = card.querySelector(".chart-tooltip");
    var pts = card.querySelectorAll(".chart-pt");
    if (!tooltip || !pts.length) return;

    function clearActive() {
      for (var i = 0; i < pts.length; i++) pts[i].classList.remove("is-active");
      card.classList.remove("declutter-hl", "declutter-ep");
    }

    function showFor(pt) {
      buildTooltipContent(tooltip, pt);
      tooltip.hidden = false;

      var ptRect = pt.getBoundingClientRect();
      var cardRect = card.getBoundingClientRect();
      var x = ptRect.left + ptRect.width / 2 - cardRect.left;
      var y = ptRect.top - cardRect.top;

      tooltip.style.left = x + "px";
      tooltip.style.top = y + "px";

      // Keep the tooltip inside the card horizontally. It's centred on the
      // point by default, but the RRP-today point (left edge) and the 10yr
      // endpoint (right edge) sit close enough to the card's side that a
      // centred box would otherwise run past the edge.
      var margin = 8;
      var ttRect = tooltip.getBoundingClientRect();
      var halfWidth = ttRect.width / 2;
      var minX = halfWidth + margin;
      var maxX = cardRect.width - halfWidth - margin;
      if (maxX < minX) { minX = maxX = cardRect.width / 2; }
      if (x < minX) x = minX;
      else if (x > maxX) x = maxX;
      tooltip.style.left = x + "px";

      clearActive();
      pt.classList.add("is-active");
      // the 5yr/10yr points already show a permanent price/return label on
      // the chart itself -- hide that one while its tooltip is open so the
      // two don't overlap (see data-declutter on those two .chart-pt only)
      var declutter = pt.getAttribute("data-declutter");
      if (declutter) card.classList.add("declutter-" + declutter);
    }

    function hide() {
      tooltip.hidden = true;
      clearActive();
    }

    for (var i = 0; i < pts.length; i++) {
      (function (pt) {
        pt.addEventListener("mouseenter", function () { showFor(pt); });
        pt.addEventListener("mouseleave", hide);
        pt.addEventListener("focus", function () { showFor(pt); });
        pt.addEventListener("blur", hide);
        pt.addEventListener("click", function (e) {
          e.stopPropagation();
          if (pt.classList.contains("is-active")) hide();
          else showFor(pt);
        });
      })(pts[i]);
    }

    document.addEventListener("click", function (e) {
      if (!card.contains(e.target)) hide();
    });
  }

  var cards = document.querySelectorAll(".chart-card");
  for (var i = 0; i < cards.length; i++) initChart(cards[i]);
})();
