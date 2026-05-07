(function () {
    function isBound(el, key) {
        if (!el) {
            return true;
        }
        if (el.dataset[key] === "1") {
            return true;
        }
        el.dataset[key] = "1";
        return false;
    }

    function initItemsSection(root) {
        var section = root.querySelector("[data-qb-items-section]");
        if (!section || isBound(section, "qbItemsBound")) {
            return;
        }

        function reindexRows() {
            section.querySelectorAll("[data-qb-item-row]").forEach(function (row, i) {
                var itemInput = row.querySelector("[data-qb-item-id]");
                var qtyInput = row.querySelector("[data-qb-qty]");
                if (itemInput) {
                    itemInput.name = "item_id_" + i;
                }
                if (qtyInput) {
                    qtyInput.name = "quantity_" + i;
                }
            });
        }

        var addBtn = section.querySelector("[data-qb-add-item]");
        var rows = section.querySelector("[data-qb-items-rows]");
        var tpl = section.querySelector("[data-qb-item-template]");
        if (!addBtn || !rows || !tpl) {
            return;
        }

        addBtn.addEventListener("click", function () {
            var clone = tpl.content.cloneNode(true);
            rows.appendChild(clone);
            reindexRows();
        });

        rows.addEventListener("click", function (e) {
            var btn = e.target.closest("[data-qb-remove-item]");
            if (!btn) {
                return;
            }
            var row = btn.closest("[data-qb-item-row]");
            if (row) {
                row.remove();
                reindexRows();
            }
        });
    }

    function initContactsSection(root) {
        var section = root.querySelector("[data-qb-contacts-section]");
        if (!section || isBound(section, "qbContactsBound")) {
            return;
        }

        function reindexRows() {
            section.querySelectorAll("[data-qb-contact-row]").forEach(function (row, i) {
                var contactInput = row.querySelector("[data-qb-contact-id]");
                var actionInput = row.querySelector("[data-qb-action]");
                var onceInput = row.querySelector("[data-qb-award-once]");
                if (contactInput) {
                    contactInput.name = "contact_id_" + i;
                }
                if (actionInput) {
                    actionInput.name = "action_" + i;
                }
                if (onceInput) {
                    onceInput.name = "award_once_" + i;
                }
            });
        }

        var addBtn = section.querySelector("[data-qb-add-contact]");
        var rows = section.querySelector("[data-qb-contacts-rows]");
        var tpl = section.querySelector("[data-qb-contact-template]");
        if (!addBtn || !rows || !tpl) {
            return;
        }

        addBtn.addEventListener("click", function () {
            var clone = tpl.content.cloneNode(true);
            rows.appendChild(clone);
            reindexRows();
        });

        rows.addEventListener("click", function (e) {
            var btn = e.target.closest("[data-qb-remove-contact]");
            if (!btn) {
                return;
            }
            var row = btn.closest("[data-qb-contact-row]");
            if (row) {
                row.remove();
                reindexRows();
            }
        });
    }

    function initRequirementsSection(root) {
        var section = root.querySelector("[data-qb-requirements-section]");
        if (!section || isBound(section, "qbRequirementsBound")) {
            return;
        }

        var groupsContainer = section.querySelector("[data-qb-req-groups]");
        var groupTpl = section.querySelector("[data-qb-req-group-template]");
        var rowTpl = section.querySelector("[data-qb-req-row-template]");
        var addGroupBtn = section.querySelector("[data-qb-add-group]");
        var form = section.querySelector("form");
        if (!groupsContainer || !groupTpl || !rowTpl || !addGroupBtn || !form) {
            return;
        }

        var typeAreaMap = {
            stat_gte: "stat",
            stat_lte: "stat",
            has_flag: "flag",
            missing_flag: "flag",
            quest_completed: "quest",
            quest_not_done: "quest",
            quest_ending: "quest",
            level_gte: "number",
            xp_gte: "number",
            has_item: "item",
            missing_item: "item",
            has_contact: "contact",
            missing_contact: "contact"
        };
        var allAreas = ["stat", "flag", "quest", "number", "item", "contact"];

        function updateParamVisibility(row, type) {
            allAreas.forEach(function (area) {
                var el = row.querySelector('[data-qb-param-area="' + area + '"]');
                if (el) {
                    el.style.display = "none";
                }
            });
            var targetArea = typeAreaMap[type];
            if (targetArea) {
                var target = row.querySelector('[data-qb-param-area="' + targetArea + '"]');
                if (target) {
                    target.style.display = (targetArea === "stat" || targetArea === "quest") ? "flex" : "block";
                }
            }
            var ending = row.querySelector("[data-qb-ending-type]");
            if (ending) {
                ending.style.display = (type === "quest_ending") ? "inline-block" : "none";
            }
        }

        function refreshSeparators() {
            groupsContainer.querySelectorAll("[data-qb-req-group]").forEach(function (group, i) {
                var sep = group.querySelector("[data-qb-and-sep]");
                if (sep) {
                    sep.style.display = i === 0 ? "none" : "block";
                }
            });
        }

        function cloneRow() {
            var clone = rowTpl.content.cloneNode(true);
            return clone.querySelector("[data-qb-req-row]");
        }

        function cloneGroup() {
            var clone = groupTpl.content.cloneNode(true);
            var group = clone.querySelector("[data-qb-req-group]");
            var firstRow = cloneRow();
            if (group && firstRow) {
                group.querySelector("[data-qb-req-rows]").appendChild(firstRow);
            }
            return group;
        }

        groupsContainer.addEventListener("change", function (e) {
            if (e.target.matches("[data-qb-req-type]")) {
                var row = e.target.closest("[data-qb-req-row]");
                if (row) {
                    updateParamVisibility(row, e.target.value);
                }
            }
        });

        groupsContainer.addEventListener("click", function (e) {
            var btn = e.target.closest("button");
            if (!btn) {
                return;
            }

            if (btn.matches("[data-qb-add-req]")) {
                var group = btn.closest("[data-qb-req-group]");
                if (group) {
                    group.querySelector("[data-qb-req-rows]").appendChild(cloneRow());
                }
            }

            if (btn.matches("[data-qb-remove-req]")) {
                var row = btn.closest("[data-qb-req-row]");
                if (row) {
                    row.remove();
                }
            }

            if (btn.matches("[data-qb-remove-group]")) {
                var groupToRemove = btn.closest("[data-qb-req-group]");
                if (groupToRemove) {
                    groupToRemove.remove();
                    refreshSeparators();
                }
            }
        });

        addGroupBtn.addEventListener("click", function () {
            var group = cloneGroup();
            if (group) {
                groupsContainer.appendChild(group);
                refreshSeparators();
            }
        });

        function buildParams() {
            var params = {};
            var groups = groupsContainer.querySelectorAll("[data-qb-req-group]");
            params.group_count = groups.length;

            groups.forEach(function (group, gi) {
                var logicEl = group.querySelector("[data-qb-req-logic]:checked");
                params["group_" + gi + "_logic"] = logicEl ? logicEl.value : "all";

                var rows = group.querySelectorAll("[data-qb-req-row]");
                params["group_" + gi + "_req_count"] = rows.length;

                rows.forEach(function (row, ri) {
                    var type = row.querySelector("[data-qb-req-type]").value;
                    params["group_" + gi + "_req_" + ri + "_type"] = type;

                    var param = "";
                    var param2 = "";
                    if (type === "stat_gte" || type === "stat_lte") {
                        var statName = (row.querySelector("[data-qb-stat-name]").value || "").trim();
                        var statVal = (row.querySelector("[data-qb-stat-value]").value || "0").trim();
                        param = statName + ":" + statVal;
                    } else if (type === "has_flag" || type === "missing_flag") {
                        param = (row.querySelector("[data-qb-flag-name]").value || "").trim();
                    } else if (type === "quest_completed" || type === "quest_not_done") {
                        param = (row.querySelector("[data-qb-quest-id]").value || "").trim();
                    } else if (type === "quest_ending") {
                        param = (row.querySelector("[data-qb-quest-id]").value || "").trim();
                        param2 = (row.querySelector("[data-qb-ending-type]").value || "").trim();
                    } else if (type === "level_gte" || type === "xp_gte") {
                        param = (row.querySelector("[data-qb-number-value]").value || "0").trim();
                    } else if (type === "has_item" || type === "missing_item") {
                        param = (row.querySelector("[data-qb-item-id]").value || "").trim();
                    } else if (type === "has_contact" || type === "missing_contact") {
                        param = (row.querySelector("[data-qb-contact-id]").value || "").trim();
                    }

                    params["group_" + gi + "_req_" + ri + "_param"] = param;
                    if (param2) {
                        params["group_" + gi + "_req_" + ri + "_param2"] = param2;
                    }
                });
            });

            return params;
        }

        section.buildReqParams = buildParams;

        form.addEventListener("htmx:configRequest", function (evt) {
            var extra = buildParams();
            var params = evt.detail.parameters;
            if (typeof params.set === "function") {
                Object.keys(extra).forEach(function (key) {
                    params.set(key, String(extra[key]));
                });
            } else {
                Object.assign(params, extra);
            }
        });
    }

    function initScenePanel(root) {
        var panel = root.querySelector("[data-qb-scene-panel]");
        if (!panel || isBound(panel, "qbScenePanelBound")) {
            return;
        }

        var sceneType = panel.querySelector("[data-qb-scene-type]");
        var rollSettings = panel.querySelector("[data-qb-roll-settings]");
        if (!sceneType || !rollSettings) {
            return;
        }

        function updateVisibility() {
            var type = sceneType.value;
            rollSettings.style.display = (type === "normal") ? "block" : "none";

            var combatSection = document.getElementById("combat-section");
            if (combatSection) {
                combatSection.style.display = (type === "combat") ? "block" : "none";
            }

            var endingTypeRow = panel.querySelector("[data-qb-ending-type-row]");
            if (endingTypeRow) {
                endingTypeRow.style.display = (type === "ending") ? "block" : "none";
            }
        }

        sceneType.addEventListener("change", updateVisibility);
        updateVisibility();
    }

    function initChoicePanel(root) {
        var panel = root.querySelector("[data-qb-choice-panel]");
        if (!panel || isBound(panel, "qbChoicePanelBound")) {
            return;
        }

        var routeDirect = panel.querySelector("[data-qb-route-direct]");
        var routeRoll = panel.querySelector("[data-qb-route-roll]");
        var sectionDirect = panel.querySelector("[data-qb-section-direct]");
        var sectionRoll = panel.querySelector("[data-qb-section-roll]");
        var failureFlavorRow = panel.querySelector("[data-qb-failure-flavor-row]");

        function updateSections() {
            if (routeRoll && routeRoll.checked) {
                if (sectionDirect) {
                    sectionDirect.style.display = "none";
                }
                if (sectionRoll) {
                    sectionRoll.style.display = "block";
                }
                if (failureFlavorRow) {
                    failureFlavorRow.style.display = "block";
                }
            } else {
                if (sectionDirect) {
                    sectionDirect.style.display = "block";
                }
                if (sectionRoll) {
                    sectionRoll.style.display = "none";
                }
                if (failureFlavorRow) {
                    failureFlavorRow.style.display = "none";
                }
            }
        }

        if (routeDirect) {
            routeDirect.addEventListener("change", updateSections);
        }
        if (routeRoll) {
            routeRoll.addEventListener("change", updateSections);
        }
        updateSections();

        var mainForm = panel.querySelector("form");
        if (mainForm) {
            mainForm.addEventListener("htmx:configRequest", function (evt) {
                var section = document.getElementById("requirements-section");
                if (!section || !section.buildReqParams) {
                    return;
                }
                var extra = section.buildReqParams();
                var params = evt.detail.parameters;
                if (typeof params.set === "function") {
                    Object.keys(extra).forEach(function (k) {
                        params.set(k, String(extra[k]));
                    });
                } else {
                    Object.assign(params, extra);
                }
            });
        }
    }

    function init(root) {
        var scope = root || document;
        initScenePanel(scope);
        initChoicePanel(scope);
        initItemsSection(scope);
        initContactsSection(scope);
        initRequirementsSection(scope);
    }

    window.qbQuestBuilderPanels = {
        init: init
    };
})();
