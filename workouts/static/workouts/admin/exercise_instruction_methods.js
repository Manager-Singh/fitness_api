(function () {
  "use strict";

  var MIN_TEXTAREA_PX = 76;

  function parseInitial(scriptEl) {
    if (!scriptEl || !scriptEl.textContent) return [];
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
    if (!hid) return;

    var methods = [];
    container.querySelectorAll(".instruction-method").forEach(function (methodEl) {
      var titleEl = methodEl.querySelector("input.instruction-method-title");
      var title = titleEl ? String(titleEl.value || "").trim() : "";
      var steps = [];
      methodEl
        .querySelectorAll("textarea.instruction-method-step")
        .forEach(function (ta) {
          var v = String(ta.value || "").trim();
          if (v.length) steps.push(v);
        });
      if (title.length || steps.length) {
        methods.push({ title: title, steps: steps });
      }
    });
    hid.value = JSON.stringify(methods);
  }

  function addStep(methodEl, value, doFocus) {
    var stepsEl = methodEl.querySelector(".instruction-method-steps");
    var row = document.createElement("div");
    row.className = "instruction-method-step-row";

    var ta = document.createElement("textarea");
    ta.className = "vLargeTextField instruction-method-step";
    ta.setAttribute("rows", "3");
    ta.setAttribute("maxlength", "2000");
    ta.setAttribute("autocomplete", "off");
    ta.setAttribute("spellcheck", "true");
    ta.setAttribute("placeholder", "#1. ...");
    ta.value = value || "";

    var rm = document.createElement("button");
    rm.type = "button";
    rm.className = "button instruction-method-step-remove";
    rm.textContent = "Remove";

    row.appendChild(ta);
    row.appendChild(rm);
    stepsEl.appendChild(row);
    growTextarea(ta);

    rm.addEventListener("click", function () {
      row.remove();
      if (methodEl.querySelectorAll(".instruction-method-step-row").length === 0) {
        addStep(methodEl, "", false);
      }
      syncHidden(methodEl.closest(".instruction-methods"));
    });

    ta.addEventListener("input", function () {
      growTextarea(ta);
      syncHidden(methodEl.closest(".instruction-methods"));
    });

    if (doFocus) {
      setTimeout(function () {
        ta.focus();
      }, 0);
    }
  }

  function addMethod(container, methodData, doFocusTitle) {
    var list = container.querySelector(".instruction-methods-list");
    var methodEl = document.createElement("div");
    methodEl.className = "instruction-method";

    var header = document.createElement("div");
    header.className = "instruction-method-header";

    var title = document.createElement("input");
    title.type = "text";
    title.className = "vTextField instruction-method-title";
    title.setAttribute("maxlength", "200");
    title.setAttribute("autocomplete", "off");
    title.setAttribute("placeholder", "Method title (e.g. Method A — Pull-up bar)");
    title.value = (methodData && methodData.title) || "";

    var rmMethod = document.createElement("button");
    rmMethod.type = "button";
    rmMethod.className = "button instruction-method-remove";
    rmMethod.textContent = "Remove method";

    header.appendChild(title);
    header.appendChild(rmMethod);

    var steps = document.createElement("div");
    steps.className = "instruction-method-steps";

    var footer = document.createElement("div");
    footer.className = "instruction-method-footer";

    var addStepBtn = document.createElement("button");
    addStepBtn.type = "button";
    addStepBtn.className = "button instruction-method-add-step";
    addStepBtn.textContent = "Add step";

    footer.appendChild(addStepBtn);

    methodEl.appendChild(header);
    methodEl.appendChild(steps);
    methodEl.appendChild(footer);
    list.appendChild(methodEl);

    var stepList = (methodData && methodData.steps) || [];
    if (Array.isArray(stepList) && stepList.length) {
      stepList.forEach(function (s) {
        addStep(methodEl, s, false);
      });
    } else {
      addStep(methodEl, "", false);
    }

    title.addEventListener("input", function () {
      syncHidden(container);
    });

    addStepBtn.addEventListener("click", function () {
      addStep(methodEl, "", true);
      syncHidden(container);
    });

    rmMethod.addEventListener("click", function () {
      methodEl.remove();
      if (container.querySelectorAll(".instruction-method").length === 0) {
        addMethod(container, { title: "", steps: [""] }, false);
      }
      syncHidden(container);
    });

    syncHidden(container);
    if (doFocusTitle) {
      setTimeout(function () {
        title.focus();
      }, 0);
    }
  }

  function initContainer(container) {
    var id = container.dataset.fieldId;
    var seed = document.getElementById(id + "_seed");
    var methods = parseInitial(seed);
    if (!methods.length) {
      addMethod(container, { title: "", steps: [""] }, false);
    } else {
      methods.forEach(function (m) {
        addMethod(container, m, false);
      });
    }

    var addMethodBtn = container.querySelector(".instruction-method-add");
    if (addMethodBtn) {
      addMethodBtn.addEventListener("click", function () {
        addMethod(container, { title: "", steps: [""] }, true);
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
    document.querySelectorAll(".instruction-methods").forEach(initContainer);
  });
})();

