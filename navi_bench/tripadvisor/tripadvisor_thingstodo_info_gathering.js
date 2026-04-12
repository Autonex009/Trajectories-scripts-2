(() => {
    const normalizeText = (value) => (value || "").replace(/\s+/g, " ").trim();

    const url = window.location.href;
    const pathname = window.location.pathname;
    const loweredPageText = normalizeText(document.body?.innerText || "").toLowerCase();
    const isThingsToDoPath = /\/(Attractions|Activities)-/i.test(pathname);
    const hasResults = document.querySelectorAll('div[data-automation="LeftRailMain"] div[data-automation="cardWrapper"]').length > 0;
    const hasActionBar = Boolean(document.querySelector('div[data-automation="actionBar"]'));

    const blockSignatures = [
        "access is temporarily restricted",
        "unusual activity",
        "are you a robot",
        "please verify your browser",
        "unusual traffic",
        "access denied",
        "captcha",
        "verification required",
    ];

    const antiBotStatus = blockSignatures.some((text) => loweredPageText.includes(text))
        ? "blocked_access_restricted"
        : "clear";

    const collectTexts = (nodes) => {
        const values = [];
        for (const node of nodes) {
            const text = normalizeText(node.textContent || node.innerText || "");
            if (text) values.push(text);
        }
        return [...new Set(values)];
    };

    const getActionBarValues = () => {
        const actionBar = document.querySelector('div[data-automation="actionBar"]');
        if (!actionBar) return [];
        const values = [];
        for (const button of actionBar.querySelectorAll("button")) {
            const text = normalizeText(button.textContent || "");
            if (!text) continue;
            if (/^sort\b/i.test(text)) continue;
            if (/^clear all filters$/i.test(text)) continue;
            values.push(text);
        }
        return [...new Set(values)];
    };

    const actionBarValues = getActionBarValues();

    const elementLooksChecked = (element) => {
        if (!element) return false;
        const ariaChecked = element.getAttribute?.("aria-checked");
        const ariaSelected = element.getAttribute?.("aria-selected");
        const dataState = element.getAttribute?.("data-state");
        return ariaChecked === "true" || ariaSelected === "true" || dataState === "checked";
    };

    const textAppearsInActionBar = (text) => {
        const normalized = normalizeText(text).toLowerCase();
        if (!normalized) return false;
        return actionBarValues.some((value) => normalizeText(value).toLowerCase().includes(normalized));
    };

    const getLabeledCheckedOptions = (selector) => {
        const labels = document.querySelectorAll(selector);
        const selected = [];
        for (const label of labels) {
            const forId = label.getAttribute("for");
            const input = (
                label.querySelector('input[type="checkbox"], input[type="radio"]')
                || (forId ? document.getElementById(forId) : null)
            );
            const optionRoot = label.closest('[role="checkbox"], [role="radio"], li, div, section') || label;
            const text = normalizeText(label.textContent || optionRoot.textContent || "");
            const checked = Boolean(input?.checked)
                || elementLooksChecked(input)
                || elementLooksChecked(label)
                || elementLooksChecked(optionRoot)
                || textAppearsInActionBar(text);
            if (!checked) continue;
            if (text) selected.push(text);
        }
        return [...new Set(selected)];
    };

    const getCheckedInputLabels = (inputSelector) => {
        const selected = [];
        const inputs = document.querySelectorAll(inputSelector);
        for (const input of inputs) {
            const id = input.getAttribute("id") || "";
            const label = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`) : null;
            const labelText = normalizeText(label?.textContent || "");
            if (labelText) selected.push(labelText);
        }
        return [...new Set(selected)];
    };

    const getSectionRootByHeading = (headingPattern) => {
        const headings = [...document.querySelectorAll("h2, h3, h4, div, span")];
        for (const node of headings) {
            const text = normalizeText(node.textContent || "");
            if (!headingPattern.test(text)) continue;
            const section = node.closest("section, div[role='group'], div");
            if (section) return section;
        }
        return null;
    };

    const getTravelerRatings = () => {
        const section = getSectionRootByHeading(/^travell?er rating/i);
        const selected = [];

        if (section) {
            const candidates = section.querySelectorAll('label, [role="checkbox"], [role="radio"], button');
            for (const node of candidates) {
                const titleText = normalizeText(node.querySelector("svg title")?.textContent || "");
                const text = normalizeText(node.textContent || "");
                const combined = normalizeText([text, titleText].filter(Boolean).join(" "));
                const valueText = combined || titleText || text;
                if (!valueText) continue;
                const input = node.querySelector('input[type="checkbox"], input[type="radio"]')
                    || (node.getAttribute('for') ? document.getElementById(node.getAttribute('for')) : null);
                const checked = Boolean(input?.checked)
                    || input?.getAttribute('aria-checked') === 'true'
                    || elementLooksChecked(node)
                    || textAppearsInActionBar(valueText);
                if (checked) {
                    selected.push(valueText);
                }
            }
        }

        for (const value of actionBarValues) {
            if (/travell?er rating|bubbles|of 5/i.test(value)) {
                selected.push(value);
            }
        }

        return [...new Set(selected)];
    };

    const getSelectedTreeNode = (containerSelector) => {
        const container = document.querySelector(containerSelector);
        if (!container) return null;
        const selectedNode = container.querySelector(
            "button.Dgygn, button[aria-selected='true'], button[aria-checked='true'], [role='treeitem'][aria-selected='true'], [role='treeitem'][aria-checked='true']"
        );
        if (selectedNode) {
            return normalizeText(selectedNode.textContent || "") || null;
        }

        for (const node of container.querySelectorAll("div.XDHza, li, button, a")) {
            const text = normalizeText(node.textContent || "");
            if (!text) continue;
            if (
                node.classList?.contains("Dgygn")
                || node.querySelector?.(".Dgygn")
                || elementLooksChecked(node)
                || textAppearsInActionBar(text)
            ) {
                return text;
            }
        }

        return null;
    };

    const getDateRange = () => {
        const button = document.querySelector('button[aria-haspopup="dialog"]');
        if (!button) return { label: null, ariaLabel: null };
        return {
            label: normalizeText(button.textContent || "") || null,
            ariaLabel: normalizeText(button.getAttribute("aria-label") || "") || null,
        };
    };

    const normalizeSortLabel = (value) => {
        const text = normalizeText(value || "");
        if (!text) return "";
        const cleaned = text
            .replace(/^sorted\s+by\s+/i, "")
            .replace(/^sort\s+by\s+/i, "")
            .replace(/^sort\s+/i, "")
            .trim();
        const normalized = cleaned
            .replace(/\btraveller\b/gi, "Traveler")
            .replace(/\bfavourites\b/gi, "Favorites")
            .trim();
        if (/traveler\s+ranking/i.test(normalized)) return "Traveler favorites";
        return normalized;
    };

    const decodeSortToken = (token) => {
        const raw = normalizeText(token || "");
        if (!raw) return "";

        const decoded = raw
            .replace(/__5f__/gi, " ")
            .replace(/_/g, " ")
            .trim();

        if (!decoded) return "";

        const lower = decoded.toLowerCase();
        if (lower === "featured") return "Featured";
        return decoded.replace(/\b\w/g, (char) => char.toUpperCase());
    };

    const getSortOrder = () => {
        const sortButton = document.querySelector(
            '#sort-filter-menu button[aria-haspopup="listbox"], ' +
            '[data-automation="sort-filter-menu"] button[aria-haspopup="listbox"], ' +
            '[data-automation="SortingListButton"] button[aria-haspopup="listbox"]'
        );

        const sortAriaLabel = normalizeSortLabel(sortButton?.getAttribute("aria-label") || "");
        if (sortAriaLabel) return sortAriaLabel;

        const sortButtonText = normalizeSortLabel(sortButton?.textContent || "");
        if (sortButtonText) {
            return sortButtonText;
        }

        const selectedOption = document.querySelector('[role="listbox"] [role="option"][aria-selected="true"] .PqcNG')
            || document.querySelector('[role="listbox"] [role="option"][aria-selected="true"] span.biGQs')
            || document.querySelector('[role="listbox"] [role="option"][aria-selected="true"]');
        const selectedText = normalizeSortLabel(selectedOption?.textContent || "");
        if (selectedText) return selectedText;

        const sortToken = pathname.match(/a_sort\.([A-Z0-9_]+)-/i)?.[1] || "";
        const decodedToken = decodeSortToken(sortToken);
        if (decodedToken) return decodedToken;

        const buttons = document.querySelectorAll('div[data-automation="actionBar"] button');
        for (const button of buttons) {
            const buttonText = normalizeText(button.textContent || "");
            if (!/sort/i.test(buttonText)) continue;
            const label = normalizeSortLabel(button.querySelector("span.biGQs")?.textContent || buttonText);
            return label || null;
        }
        return null;
    };

    const getSearchRefreshState = () => {
        const el = document.querySelector('[data-automation="search_in_progress_message"]');
        if (!el) return { present: false, visible: false, text: null };
        const style = window.getComputedStyle(el);
        const visible = style.display !== "none" && style.visibility !== "hidden" && normalizeText(el.textContent || "") !== "";
        return {
            present: true,
            visible,
            text: normalizeText(el.textContent || "") || null,
        };
    };

    const getPriceSliders = () => {
        const sliders = [...document.querySelectorAll('div#price_filter_contents div[role="slider"]')];
        const values = {};
        for (const slider of sliders) {
            const label = normalizeText(slider.getAttribute("aria-label") || "");
            const value = slider.getAttribute("aria-valuenow");
            if (label && value) values[label] = value;
        }
        return values;
    };

    const resultCards = [...document.querySelectorAll('div[data-automation="LeftRailMain"] div[data-automation="cardWrapper"]')]
        .slice(0, 10)
        .map((card) => {
            const saveButton = [...card.querySelectorAll('[data-automation^="trips-save-button-item-"]')][0];
            const saveAutomation = saveButton?.getAttribute("data-automation") || "";
            const idMatch = saveAutomation.match(/trips-save-button-item-(\d+)/);
            const titleNode = card.querySelector("h3.biGQs div.ATCbm") || card.querySelector("h3");
            let title = normalizeText(titleNode?.textContent || "");
            title = title.replace(/^\d+\.\s*/, "");
            return {
                listingId: idMatch ? idMatch[1] : null,
                title: title || null,
                bubbleRating: normalizeText(card.querySelector('svg[data-automation="bubbleRatingImage"] title')?.textContent || "") || null,
                reviewCount: normalizeText(card.querySelector('div[data-automation="bubbleReviewCount"]')?.textContent || "") || null,
                price: normalizeText(card.querySelector('div[data-automation="cardPrice"]')?.textContent || "") || null,
                offerTags: collectTexts((card.querySelector('div[data-automation="cardSpecialOfferTags"]') || card).querySelectorAll('*')),
            };
        });

    const geographicId = pathname.match(/-g(\d+)/i)?.[1] || null;
    const citySlugMatch = pathname.match(/\/(?:Attractions|Activities)-g\d+-(?:.*-)?([A-Za-z][A-Za-z0-9_]+)\.html/i);
    const citySlug = citySlugMatch?.[1] || null;
    const cityName = normalizeText(
        document.querySelector('[data-automation="navHeader_Tourism"] a')?.textContent
        || document.querySelector('[data-automation="navHeader_Tourism"]')?.textContent
        || ""
    ) || null;

    const groups = {
        languages: getLabeledCheckedOptions('label[for^="main_language_"]'),
        uniqueExperiences: getLabeledCheckedOptions('label[for^="main_themes_"]'),
        timeOfDay: getLabeledCheckedOptions('label[for^="main_timeOfDay_"]'),
        duration: getLabeledCheckedOptions('label[for^="main_duration_"]'),
        accessibility: getLabeledCheckedOptions('label[for^="main_accessibilityTag_"]'),
        awards: getLabeledCheckedOptions('label[for^="main_awardCategories_"]'),
        neighborhoods: [
            ...getLabeledCheckedOptions('label[for^="main_neighborhood_"]'),
            ...getCheckedInputLabels('input[id^="main_neighborhood_"]:checked'),
        ],
        destinationGeo: [
            ...getLabeledCheckedOptions('label[for^="main_destinationGeo_"]'),
            ...getCheckedInputLabels('input[id^="main_destinationGeo_"]:checked'),
        ],
        anyTag: [
            ...getLabeledCheckedOptions('label[for^="main_anyTag_"]'),
            ...getCheckedInputLabels('input[id^="main_anyTag_"]:checked'),
        ],
        typeLevel3: getLabeledCheckedOptions('div#type_filter_contents label[for^="main_type_"]'),
        travelerRatings: getTravelerRatings(),
    };

    const activeFilters = [...new Set([
        ...actionBarValues,
        ...Object.values(groups).flat(),
        getSelectedTreeNode('div[data-filter-name="navbar"]') || "",
        getSelectedTreeNode('div[data-filter-name="category"]') || "",
        getSelectedTreeNode('div[data-filter-name="type"]') || "",
    ].filter(Boolean))];

    return {
        url,
        pageType: isThingsToDoPath && (hasResults || hasActionBar) ? "things_to_do_results" : "other",
        antiBotStatus,
        geographicId,
        citySlug,
        cityName,
        actionBarValues,
        activeFilters,
        selectedFiltersByGroup: groups,
        sortOrder: getSortOrder(),
        dateRange: getDateRange(),
        refreshState: getSearchRefreshState(),
        tierSelections: {
            navbar: getSelectedTreeNode('div[data-filter-name="navbar"]'),
            category: getSelectedTreeNode('div[data-filter-name="category"]'),
            type: getSelectedTreeNode('div[data-filter-name="type"]'),
        },
        priceSlider: getPriceSliders(),
        resultsCount: document.querySelectorAll('div[data-automation="LeftRailMain"] div[data-automation="cardWrapper"]').length,
        resultsSample: resultCards,
    };
})();
