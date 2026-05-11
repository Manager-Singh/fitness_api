(function () {
  "use strict";

  var MIN_TEXTAREA_PX = 88; /* ~3 lines at 15px */

  function parseInitial(scriptEl) {
    if (!scriptEl || !scriptEl.textContent) {
      return [];
    }
    try {
      var data = JSON.parse(scriptEl.textContent);
      return Array.isArray(data) ? data : [];
    } catch (e) {
      return [];
    }
  }

  function growTextarea(ta) {
    ta.style.height = "auto";
    ta.style.height = Math.max(MIN_TEXTAREA_PX, ta.scrollHeight) + "px";
  }

  function syncHidden(container) {
    var hid = document.getElementById(container.dataset.fieldId);
    if (!hid) {
      return;
    }
    var inputs = container.querySelectorAll("textarea.instruction-step-input");
    var steps = [];
    inputs.forEach(function (inp) {
      var v = inp.value.trim();
      if (v.length) {
        steps.push(v);
      }
    });
    hid.value = JSON.stringify(steps);
  }

  function renumber(container) {
    var rows = container.querySelectorAll(".instruction-step-row");
    rows.forEach(function (row, i) {
      var lab = row.querySelector(".instruction-step-num");
      if (lab) {
        lab.textContent = "Step " + (i + 1) + ": ";
      }
    });
  }

  function addRow(container, value, doFocus) {
    var rows = container.querySelector(".instruction-steps-rows");
    var wrap = document.createElement("div");
    wrap.className = "instruction-step-row";

    var header = document.createElement("div");
    header.className = "instruction-step-header";
    var num = document.createElement("span");
    num.className = "instruction-step-num";
    var rm = document.createElement("button");
    rm.type = "button";
    rm.className = "button instruction-step-remove";
    rm.textContent =
      container.getAttribute("data-remove-label") || "Remove";
    header.appendChild(num);
    header.appendChild(rm);

    var inp = document.createElement("textarea");
    inp.className = "vLargeTextField instruction-step-input";
    inp.setAttribute("rows", "4");
    inp.setAttribute("spellcheck", "true");
    inp.setAttribute("maxlength", "2000");
    inp.setAttribute("autocomplete", "off");
    inp.setAttribute(
      "placeholder",
      "e.g. title / dosage on step 1, then numbered cues…"
    );
    inp.value = value || "";

    wrap.appendChild(header);
    wrap.appendChild(inp);
    rows.appendChild(wrap);
    renumber(container);
    growTextarea(inp);

    rm.addEventListener("click", function () {
      wrap.remove();
      renumber(container);
      syncHidden(container);
      var left = container.querySelectorAll(".instruction-step-row");
      if (left.length === 0) {
        addRow(container, "", false);
        syncHidden(container);
      }
    });

    inp.addEventListener("input", function () {
      growTextarea(inp);
      syncHidden(container);
    });

    if (doFocus) {
      setTimeout(function () {
        inp.focus();
      }, 0);
    }
  }

  function initContainer(container) {
    var id = container.dataset.fieldId;
    var seed = document.getElementById(id + "_seed");
    var steps = parseInitial(seed);
    if (steps.length === 0) {
      addRow(container, "", false);
    } else {
      steps.forEach(function (s) {
        addRow(container, s, false);
      });
    }
    syncHidden(container);
    var addBtn = container.querySelector(".instruction-steps-add");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        addRow(container, "", true);
        syncHidden(container);
      });
    }
    var form = container.closest("form");
    if (form) {
      form.addEventListener("submit", function () {
        syncHidden(container);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".instruction-steps-array").forEach(initContainer);
  });
})();
