(() => {
    const HOTEL_PATH_RE = /^\/Hotels-(g\d+)-.*\.html$/i;
    const RESTAURANT_PATH_RE = /^\/(?:FindRestaurants|Restaurants)(?:$|[\/\?\-])/i;
    const CRUISE_PATH_RE = /^\/Cruises-(g\d+)-(.+?)-Cruises(?:\.html|\/|$)/i;
    const FILTER_GROUP_DEFINITIONS = [
        {
            key: "popularFilters",
            headings: ["popular"],
            fieldPrefixes: [],
            dataAutomation: ["5starsF", "4stars&UpF"],
            ids: [],
            values: ["amenity:9167", "class:9572", "rating:4", "style:9650"],
            labels: ["Pets Allowed", "5 Star", "4+ Bubbles", "Luxury"],
        },
        {
            key: "deals",
            headings: ["deals"],
            fieldPrefixes: ["deal"],
            dataAutomation: ["freeCancellationF", "reserveNowF", "specialOffersF"],
            ids: [],
            values: ["1", "2", "3"],
            labels: ["Free cancellation", "Reserve now, pay later", "Properties with special offers"],
        },
        {
            key: "awards",
            headings: ["awards", "award", "travelers choice"],
            fieldPrefixes: ["award", "award"],
            dataAutomation: [],
            ids: [],
            values: ["BOTB", "TC"],
            labels: ["Best of the Best", "Travelers' Choice"],
        },
        {
            key: "propertyTypes",
            headings: ["property types", "property type"],
            fieldPrefixes: ["property", "type"],
            dataAutomation: ["hotelsF"],
            ids: [],
            values: ["21371", "21373", "9250", "9261"],
            labels: ["Hotels", "Specialty lodgings", "Condos", "Hostels"],
        },
        {
            key: "amenities",
            headings: ["amenities", "amenity"],
            fieldPrefixes: ["amenity"],
            dataAutomation: ["freeWifiF", "breakfastIncludedAmenF"],
            ids: ["amenity.9176", "amenity.9179", "amenity.6217", "amenity.9167"],
            values: ["9176", "9179", "6217", "9167", "amenity:9167"],
            labels: ["Free Wifi", "Breakfast included", "Pool", "Pets Allowed"],
        },
        {
            key: "neighborhoods",
            headings: ["neighborhoods", "neighborhood", "neighbourhood"],
            fieldPrefixes: [],
            dataAutomation: [],
            ids: [],
            values: ["15620622", "15620620", "15620543", "15620661"],
            labels: ["Deira", "Bur Dubai", "Al Barsha", "Naif"],
        },
        {
            key: "travelerRatings",
            headings: ["traveler rating", "traveler ratings", "rating"],
            fieldPrefixes: ["rating"],
            dataAutomation: ["4stars&UpF"],
            ids: [],
            values: ["20", "30", "40", "50", "rating:4"],
            labels: ["2+ Bubbles", "3+ Bubbles", "4+ Bubbles", "5 Bubbles"],
        },
        {
            key: "hotelClasses",
            headings: ["hotel class", "hotel classes", "stars", "star rating"],
            fieldPrefixes: ["class"],
            dataAutomation: ["5starsHotelClassF", "4starsHotelClassF", "5starsF"],
            ids: [],
            values: ["9572", "9566", "9568", "9569", "class:9572"],
            labels: ["5 Star", "4 Star", "3 Star", "2 Star"],
        },
        {
            key: "styles",
            headings: ["style", "styles", "great for"],
            fieldPrefixes: ["style"],
            dataAutomation: [],
            ids: [],
            values: ["5184", "9654", "9650", "6216", "style:9650"],
            labels: ["Budget", "Mid-range", "Luxury", "Family-friendly", "Business meetings", "Good for Couples"],
        },
        {
            key: "brands",
            headings: ["brands", "brand"],
            fieldPrefixes: ["brand"],
            dataAutomation: [],
            ids: ["brand.11779", "brand.9243", "brand.9611", "brand.12212"],
            values: ["11779", "9243", "9611", "12212"],
            labels: ["OYO", "Millennium", "Jumeirah", "B&B Hotels"],
        },
        {
            key: "establishmentTypes",
            headings: ["establishment type", "establishment types", "type"],
            fieldPrefixes: ["establishmentTypes"],
            dataAutomation: [],
            ids: [],
            values: [],
            labels: ["Restaurants", "Bakeries", "Quick Bites", "Hotels & Travel"],
        },
        {
            key: "mealTypes",
            headings: ["meal type", "meal types"],
            fieldPrefixes: ["mealTypes"],
            dataAutomation: [],
            ids: [],
            values: [],
            labels: ["Breakfast", "Brunch", "Lunch", "Dinner", "Dessert"],
        },
        {
            key: "cuisines",
            headings: ["cuisine", "cuisines"],
            fieldPrefixes: ["cuisines"],
            dataAutomation: [],
            ids: [],
            values: [],
            labels: ["Healthy", "Turkish", "American", "Italian", "French", "Japanese", "Chinese", "Indian"],
        },
        {
            key: "dishes",
            headings: ["dish", "dishes"],
            fieldPrefixes: ["dishes"],
            dataAutomation: [],
            ids: [],
            values: [],
            labels: ["Fried"],
        },
        {
            key: "diets",
            headings: ["dietary restriction", "dietary restrictions", "diet", "restriction"],
            fieldPrefixes: ["diets"],
            dataAutomation: [],
            ids: [],
            values: [],
            labels: ["Gluten free options", "Vegetarian options", "Vegan options"],
        },
        {
            key: "diningOptions",
            headings: ["features", "feature", "dining options"],
            fieldPrefixes: ["diningOptions"],
            dataAutomation: [],
            ids: [],
            values: [],
            labels: ["Wheelchair accessible"],
        },
        {
            key: "priceTypes",
            headings: ["price range", "price"],
            fieldPrefixes: ["price"],
            dataAutomation: [],
            ids: [],
            values: [],
            labels: [],
        },
    ];

    const FILTER_GROUP_KEYS = ["activeFilters", ...FILTER_GROUP_DEFINITIONS.map((definition) => definition.key)];
    const SELECTED_FILTER_BAR_SELECTOR = '[data-test-target="filter-bar"]';

    function cleanText(value) {
        if (!value) return "";
        return String(value).replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
    }

    function unique(values) {
        return [...new Set(values.filter(Boolean))];
    }

    function normalizeText(value) {
        return cleanText(value).toLowerCase();
    }

    function normalizeForMatch(value) {
        return cleanText(value)
            .toLowerCase()
            .replace(/[\u2018\u2019]/g, "'")
            .replace(/&/g, " and ")
            .replace(/[-_/]/g, " ")
            .replace(/[^a-z0-9:' ]+/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    function collectTexts(selectors) {
        const values = [];
        for (const selector of selectors) {
            for (const node of document.querySelectorAll(selector)) {
                const text = cleanText(
                    node.getAttribute && (
                        node.getAttribute("aria-label") ||
                        node.getAttribute("aria-labelledby") ||
                        node.getAttribute("title")
                    ) || node.innerText || node.textContent
                );
                if (text) {
                    values.push(text);
                }
            }
        }
        return unique(values);
    }

    function getDirectLabelText(label) {
        if (!label) return "";
        const clone = label.cloneNode(true);
        for (const removable of clone.querySelectorAll('input, svg, button, [aria-hidden="true"]')) {
            removable.remove();
        }
        return cleanText(clone.innerText || clone.textContent);
    }

    function sanitizeFilterText(value) {
        const text = cleanText(value)
            .replace(/^\s*remove\s+/i, "")
            .replace(/\s+filter\s*$/i, "")
            .replace(/\s+selected\s*$/i, "")
            .replace(/\bselected filter\b/gi, "")
            .replace(/\s+\(\d[\d,]*\)$/g, "")
            .replace(/\s+\d[\d,]*$/g, "")
            .trim();
        return cleanText(text);
    }

    function isLikelySiteNavText(value) {
        const text = cleanText(value).toLowerCase();
        if (!text) return false;
        const navTerms = ["hotels", "things to do", "restaurants", "cruises", "forums", "flights", "vacation rentals", "rentals"];
        let hitCount = 0;
        for (const term of navTerms) {
            if (text.includes(term)) hitCount += 1;
        }
        return hitCount >= 2;
    }

    function isMeaningfulFilterText(value) {
        const text = sanitizeFilterText(value);
        if (!text) return false;
        if (text.length > 80) return false;
        if (/^(show more|show all|filters?|sort|reset|learn more)$/i.test(text)) return false;
        if (isLikelySiteNavText(text)) return false;
        if (!/[a-z]/i.test(text)) return false;
        if (/^[a-z0-9_.:-]+$/i.test(text) && /\d/.test(text)) return false;
        return true;
    }

    function collectMeaningfulTexts(node) {
        if (!node) return [];
        const candidates = [];
        const pushCandidate = (value) => {
            const text = sanitizeFilterText(value);
            if (isMeaningfulFilterText(text)) {
                candidates.push(text);
            }
        };

        pushCandidate(node.getAttribute && node.getAttribute("aria-label"));
        pushCandidate(node.getAttribute && node.getAttribute("title"));
        pushCandidate(node.innerText || node.textContent);

        const descendants = node.querySelectorAll
            ? node.querySelectorAll('span, div, a, p, strong, b, [data-automation], [data-test-target], [role="button"]')
            : [];
        for (const descendant of descendants) {
            pushCandidate(descendant.getAttribute && descendant.getAttribute("aria-label"));
            pushCandidate(descendant.getAttribute && descendant.getAttribute("title"));
            pushCandidate(descendant.innerText || descendant.textContent);
        }

        return unique(candidates);
    }

    function extractFilterLabel(input, label) {
        const directLabelText = sanitizeFilterText(getDirectLabelText(label));
        if (isMeaningfulFilterText(directLabelText)) {
            return directLabelText;
        }

        const nearbyRoots = [
            label,
            input.parentElement,
            input.closest('[role="menuitemcheckbox"]'),
            input.closest('[role="checkbox"]'),
            input.closest("li"),
            input.closest("span"),
            input.closest("div"),
        ].filter(Boolean);

        for (const root of nearbyRoots) {
            for (const candidate of collectMeaningfulTexts(root)) {
                if (candidate !== sanitizeFilterText(input.value)) {
                    return candidate;
                }
            }
        }

        const inputAria = sanitizeFilterText(
            cleanText([
                input.getAttribute("aria-label"),
                input.getAttribute("title"),
                input.getAttribute("name"),
            ].filter(Boolean).join(" "))
        );
        return isMeaningfulFilterText(inputAria) ? inputAria : "";
    }

    function isInputChecked(input) {
        if (!input) return false;
        if (input.checked || input.getAttribute("checked") !== null || input.getAttribute("aria-checked") === "true") {
            return true;
        }

        const label = findGroupLabel(input);
        const wrapper = label || input.closest("span") || input.parentElement;
        const nearbyNodes = [
            input,
            label,
            wrapper,
            input.parentElement,
            input.closest('[role="menuitemcheckbox"]'),
            input.closest('[role="checkbox"]'),
            input.closest('[aria-checked]'),
            label && label.querySelector("span"),
            label && label.querySelector("div"),
            label && label.querySelector('[aria-checked]'),
            label && label.querySelector('[aria-selected]'),
            label && label.querySelector('[data-state]'),
        ].filter(Boolean);

        const classBlob = cleanText([
            ...nearbyNodes.map((node) => node.className),
            ...nearbyNodes.map((node) => node.getAttribute && node.getAttribute("data-state")),
            ...nearbyNodes.map((node) => node.getAttribute && node.getAttribute("aria-checked")),
            ...nearbyNodes.map((node) => node.getAttribute && node.getAttribute("aria-selected")),
            ...nearbyNodes.map((node) => node.getAttribute && node.getAttribute("aria-pressed")),
        ].filter(Boolean).join(" "));

        if (/\bchecked\b/i.test(classBlob) || /\bselected\b/i.test(classBlob) || /\bactive\b/i.test(classBlob)) {
            return true;
        }

        if (nearbyNodes.some((node) =>
            node.getAttribute && (
                node.getAttribute("aria-checked") === "true" ||
                node.getAttribute("aria-selected") === "true" ||
                node.getAttribute("aria-pressed") === "true" ||
                node.getAttribute("data-state") === "checked"
            )
        )) {
            return true;
        }

        const selectedDescendant = label && label.querySelector(
            '[aria-pressed="true"], [aria-selected="true"], [aria-checked="true"], [data-state="checked"]'
        );
        if (selectedDescendant) {
            return true;
        }

        return false;
    }

    function findGroupLabel(input) {
        const labelByFor = input.id ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`) : null;
        if (labelByFor) return labelByFor;
        return input.closest("label");
    }

    function getGroupHeading(node) {
        let current = node;
        const headingSelectors = [
            "h1",
            "h2",
            "h3",
            "h4",
            "legend",
            '[role="heading"]',
            '[data-automation*="filter"][data-automation*="title"]',
            '[data-test-target*="filter"][data-test-target*="title"]',
        ];

        for (let i = 0; current && i < 8; i += 1) {
            for (const selector of headingSelectors) {
                const heading = current.querySelector && current.querySelector(selector);
                if (heading) {
                    const headingText = cleanText(heading.innerText || heading.textContent);
                    if (headingText) {
                        return headingText;
                    }
                }
            }
            current = current.parentElement;
        }
        return "";
    }

    function createEmptyGroupedFilters() {
        const grouped = { activeFilters: [] };
        for (const key of FILTER_GROUP_KEYS) {
            if (key !== "activeFilters") {
                grouped[key] = [];
            }
        }
        return grouped;
    }

    function buildFilterContext({ text, heading = "", value = "", id = "", name = "", source = "" }) {
        return {
            text: cleanText(text),
            heading: cleanText(heading),
            value: cleanText(value),
            id: cleanText(id),
            name: cleanText(name),
            source: cleanText(source),
        };
    }

    function compileFilterDefinitions() {
        return FILTER_GROUP_DEFINITIONS.map((definition) => ({
            key: definition.key,
            headings: (definition.headings || []).map(normalizeForMatch),
            fieldPrefixes: (definition.fieldPrefixes || []).map(normalizeText),
            dataAutomation: (definition.dataAutomation || []).map(normalizeText),
            ids: (definition.ids || []).map(normalizeText),
            values: (definition.values || []).map(normalizeText),
            labels: (definition.labels || []).map(normalizeForMatch),
        }));
    }

    const COMPILED_FILTER_GROUP_DEFINITIONS = compileFilterDefinitions();

    function contextTokens(context) {
        return {
            heading: normalizeForMatch(context.heading),
            text: normalizeForMatch(context.text),
            value: normalizeText(context.value),
            id: normalizeText(context.id),
            name: normalizeText(context.name),
            source: normalizeText(context.source),
        };
    }

    function classifyFilterGroups(context) {
        const matches = [];

        if (!cleanText(context.text)) {
            return matches;
        }

        const tokens = contextTokens(context);

        for (const definition of COMPILED_FILTER_GROUP_DEFINITIONS) {
            const matchesHeading = definition.headings.some((heading) => tokens.heading.includes(heading));
            const matchesPrefix = definition.fieldPrefixes.some((prefix) =>
                [tokens.value, tokens.id, tokens.name].some((field) => field === prefix || field.startsWith(`${prefix}.`) || field.startsWith(`${prefix}:`))
            );
            const matchesHook = definition.dataAutomation.some((hook) => tokens.source.includes(hook));
            const matchesId = definition.ids.includes(tokens.id);
            const matchesValue = definition.values.includes(tokens.value);
            const matchesLabel = definition.labels.some((label) => tokens.text.includes(label));

            if (matchesHeading || matchesPrefix || matchesHook || matchesId || matchesValue || matchesLabel) {
                matches.push(definition.key);
            }
        }

        return unique(matches);
    }

    function addFilterToGroups(grouped, context) {
        const text = sanitizeFilterText(context.text);
        if (!text) return;

        grouped.activeFilters.push(text);
        for (const groupKey of classifyFilterGroups(context)) {
            if (groupKey !== "activeFilters" && grouped[groupKey]) {
                grouped[groupKey].push(text);
            }
        }
    }

    function finalizeGroupedFilters(grouped) {
        const normalized = {};
        for (const key of FILTER_GROUP_KEYS) {
            const values = unique(grouped[key] || []);
            normalized[key] = key === "activeFilters" ? values : (values.length ? values : 0);
        }
        return normalized;
    }

    function collectCheckedFilterGroups() {
        const grouped = createEmptyGroupedFilters();
        const candidateSelectors = [
            'input[type="checkbox"]',
            'input[type="radio"]',
            '[role="checkbox"]',
            '[role="radio"]',
            '[aria-selected="true"]',
            '[aria-checked="true"]',
            '[data-state="checked"]',
        ];
        const nodes = new Set();

        for (const selector of candidateSelectors) {
            for (const node of document.querySelectorAll(selector)) {
                nodes.add(node);
            }
        }

        for (const node of nodes) {
            if (!isInputChecked(node)) continue;

            const input = node.tagName && node.tagName.toLowerCase() === "input"
                ? node
                : node.querySelector('input[type="checkbox"], input[type="radio"]');

            const value = cleanText(input ? input.value : "");
            let label = input ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`) : null;
            if (!label) label = findGroupLabel(node);
            const labelText = extractFilterLabel(input || node, label);
            const heading = getGroupHeading(node);
            const candidateText = labelText;
            if (!candidateText) continue;

            addFilterToGroups(grouped, buildFilterContext({
                text: candidateText,
                heading,
                value,
                id: input?.id || "",
                name: input?.name || "",
                source: cleanText([
                    node.getAttribute && node.getAttribute("aria-label"),
                    node.getAttribute && node.getAttribute("data-automation"),
                    node.className,
                    label && label.className,
                ].filter(Boolean).join(" ")),
            }));
        }

        return grouped;
    }

    function collectSelectedFilterPills() {
        const selectors = [
            `${SELECTED_FILTER_BAR_SELECTOR} button`,
            `${SELECTED_FILTER_BAR_SELECTOR} [role="button"]`,
            `${SELECTED_FILTER_BAR_SELECTOR} ._T button`,
            'button[data-automation="filter-pill-active"]',
            '[data-automation*="filter-pill"]',
            '[data-automation*="chip"][aria-pressed="true"]',
            '[data-automation*="chip"][aria-selected="true"]',
            '[aria-label*="selected filter" i]',
            '[class*="filter"][class*="active"]',
            '[class*="chip"][class*="active"]',
        ];

        const values = [];
        for (const selector of selectors) {
            for (const node of document.querySelectorAll(selector)) {
                const candidates = [
                    sanitizeFilterText(node.innerText || node.textContent),
                    ...collectMeaningfulTexts(node),
                    sanitizeFilterText(node.getAttribute && node.getAttribute("aria-label")),
                    sanitizeFilterText(node.getAttribute && node.getAttribute("title")),
                ];

                for (const candidate of candidates) {
                    if (!isMeaningfulFilterText(candidate)) continue;
                    if (/^show more$/i.test(candidate)) continue;
                    if (/^filters?$/i.test(candidate)) continue;
                    values.push(candidate);
                    break;
                }
            }
        }

        return unique(values);
    }

    function collectSelectedFilterBarValues() {
        const bar = document.querySelector(SELECTED_FILTER_BAR_SELECTOR);
        if (!bar) return [];

        const values = [];
        for (const button of bar.querySelectorAll("button")) {
            const descendantTexts = [];
            for (const node of button.querySelectorAll(".AWdfh, .ZpvBJ, .fQXsQ, span, div")) {
                descendantTexts.push(sanitizeFilterText(node.innerText || node.textContent));
            }
            const candidates = [
                ...descendantTexts,
                sanitizeFilterText(button.innerText || button.textContent),
                ...collectMeaningfulTexts(button),
            ];

            for (const candidate of candidates) {
                if (!isMeaningfulFilterText(candidate)) continue;
                if (/^(previous|next)$/i.test(candidate)) continue;
                values.push(candidate);
                break;
            }
        }

        return unique(values);
    }

    function collectActionBarValues() {
        const bar = document.querySelector('div[data-automation="actionBar"]');
        if (!bar) return [];

        const values = [];
        for (const node of bar.querySelectorAll('button, span')) {
            const text = sanitizeFilterText(node.textContent || node.innerText);
            if (!text) continue;
            if (/^sort\b/i.test(text)) continue;
            if (/^clear all filters$/i.test(text)) continue;
            if (isLikelySiteNavText(text)) continue;
            values.push(text);
        }
        return unique(values);
    }

    function mergeSelectedPillsIntoGroups(grouped, pills) {
        for (const pill of pills) {
            addFilterToGroups(grouped, buildFilterContext({
                text: pill,
                source: "selected pill",
            }));
        }
        return grouped;
    }

    function parseNumber(value) {
        if (value == null) return null;
        const match = String(value).match(/-?\d+(?:[.,]\d+)?/);
        if (!match) return null;
        return parseFloat(match[0].replace(/,/g, ""));
    }

    function getText(selector) {
        const node = document.querySelector(selector);
        return node ? cleanText(node.textContent || node.innerText) : "";
    }

    function getMetaContent(names) {
        const keys = Array.isArray(names) ? names : [names];
        for (const key of keys) {
            const selector = key.startsWith("og:")
                ? `meta[property="${key}"]`
                : `meta[itemprop="${key}"],meta[name="${key}"]`;
            const node = document.querySelector(selector);
            if (node && node.content) {
                return cleanText(node.content);
            }
        }
        return null;
    }

    function extractTitleHotelName() {
        const title = cleanText(document.title);
        if (!title) {
            return null;
        }
        const match = title.match(/^(.+?)\s*[-–•]\s*Tripadvisor$/i);
        const candidate = match ? match[1].trim() : title;
        if (/^Hotels? in\b/i.test(candidate)) {
            return null;
        }
        return candidate || null;
    }

    function extractCitySlugFromTitle() {
        const title = cleanText(document.title);
        if (!title) {
            return null;
        }
        const match = title.match(/(?:Hotels|Restaurants|Attractions) in\s+(.+?)(?:\s*[-–•]\s*Tripadvisor|$)/i);
        if (!match) {
            return null;
        }
        return cleanText(match[1]).replace(/[,.:]+/g, "").replace(/\s+/g, "_");
    }

    function extractCitySlugFromRestaurantPath(url) {
        const match = url.pathname.match(/^\/Restaurants-(?:g\d+)-(.*?)(?:\.html|\/|$)/i);
        if (!match) {
            return null;
        }
        const rawTokens = match[1].split("-").filter(Boolean);
        const cityTokens = rawTokens.filter(
            (token) => !/^z[a-z0-9_]+(?:\.[a-z0-9_]+)?$/i.test(token) && !/^a_[a-z0-9_.]+$/i.test(token)
        );
        if (!cityTokens.length) {
            return null;
        }
        return cityTokens.join("_");
    }

    function extractCitySlugFromTourismNavHeader() {
        const navText = cleanText(
            document.querySelector('[data-automation="navHeader_Tourism"] a')?.textContent ||
            document.querySelector('[data-automation="navHeader_Tourism"]')?.textContent ||
            ""
        );
        const match = navText.match(/(?:Restaurants in|Hotels in|Attractions in)\s+(.+)/i);
        const cityText = match ? match[1] : navText;
        return cityText ? cleanText(cityText).replace(/[,.:]+/g, "").replace(/\s+/g, "_") : null;
    }

    function parseDateValue(buttonSelector) {
        const button = document.querySelector(buttonSelector);
        if (!button) {
            return { raw: null, iso: null };
        }

        const ariaLabel = cleanText(button.getAttribute("aria-label"));
        const innerText = cleanText(button.innerText || button.textContent);
        const combined = [ariaLabel, innerText].filter(Boolean).join(" ");

        const fullDateMatch = combined.match(
            /\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b/i
        );
        if (fullDateMatch) {
            const raw = cleanText(fullDateMatch[0]);
            const parsed = new Date(raw);
            return {
                raw,
                iso: Number.isNaN(parsed.getTime()) ? null : parsed.toISOString().slice(0, 10),
            };
        }

        const compactMatch = combined.match(/\b[A-Z][a-z]{2},\s*[A-Z][a-z]{2}\s+\d{1,2}\b/);
        return {
            raw: compactMatch ? cleanText(compactMatch[0]) : (combined || null),
            iso: null,
        };
    }

    function collectActiveFilters() {
        const selectors = [
            'button[data-automation="filter-pill-active"]',
            'button[aria-pressed="true"]',
            'button[aria-selected="true"]',
            '[data-automation*="filter"] button[aria-pressed="true"]',
            '[data-automation*="filter"] button[aria-selected="true"]',
            '[data-automation*="filter-pill"]',
            '[data-automation*="chip"][aria-pressed="true"]',
            '[data-automation*="chip"][aria-selected="true"]',
            '[data-test-target*="filter"] button[aria-pressed="true"]',
            '[data-test-target*="filter"] button[aria-selected="true"]',
            '[class*="filter"][class*="active"]',
            '[class*="filter"][class*="selected"]',
        ];

        const texts = collectSelectedFilterPills();

        return unique(texts.filter((text) => {
            if (/^sort\b/i.test(text)) return false;
            if (/^filters?$/i.test(text)) return false;
            if (/^show map$/i.test(text)) return false;
            if (/^\d+\s+properties$/i.test(text)) return false;
            return true;
        }));
    }

    function getSortOrder() {
        const candidates = [
            getText('div[data-automation="sort"] button div.biGQs'),
            getText('div[data-automation="sort"] button'),
            getText('div.lOvTR button span.biGQs._P.ezezH'),
            getText('div[role="listbox"] [aria-selected="true"]'),
        ].filter(Boolean);
        const raw = candidates[0] || "";
        return raw.replace(/^sort by:\s*/i, "").trim() || null;
    }

    function getPriceRangeState() {
        const result = {
            display: getText('div[data-automation="pRange"] div.biGQs._P.ZNjnF') || null,
            min: null,
            max: null,
            minInput: null,
            maxInput: null,
            displayType: null,
        };

        const minSlider = document.querySelector('div[role="slider"][aria-label="Minimum price"]');
        const maxSlider = document.querySelector('div[role="slider"][aria-label="Maximum price"]');
        if (minSlider) result.min = parseNumber(minSlider.getAttribute("aria-valuenow"));
        if (maxSlider) result.max = parseNumber(maxSlider.getAttribute("aria-valuenow"));

        const rangeInputs = document.querySelectorAll("input.krvDH");
        if (rangeInputs[0]) {
            result.minInput = parseNumber(rangeInputs[0].value || rangeInputs[0].getAttribute("value"));
            if (result.min == null) {
                result.min = result.minInput;
            }
        }
        if (rangeInputs[1]) {
            result.maxInput = parseNumber(rangeInputs[1].value || rangeInputs[1].getAttribute("value"));
            if (result.max == null) {
                result.max = result.maxInput;
            }
        }

        const selectedDisplay = document.querySelector(
            'div[data-automation="pRange"] input[type="radio"]:checked, div[data-automation="pRange"] [role="radio"][aria-checked="true"]'
        );
        if (selectedDisplay) {
            const label = selectedDisplay.closest("label");
            result.displayType = cleanText(
                (label && (label.innerText || label.textContent)) ||
                selectedDisplay.getAttribute("aria-label") ||
                selectedDisplay.getAttribute("value")
            ) || null;
        }

        return result;
    }

    function getDistanceState() {
        const maxDistanceSlider = document.querySelector('div[role="slider"][aria-label="Maximum distance"]');
        const selectedLandmark = document.querySelector('input[id^="distance-"]:checked, [role="radio"][id^="distance-"][aria-checked="true"]');
        const selectedPills = collectSelectedFilterBarValues();
        const distancePill = selectedPills.find((text) => /\b(?:mi|km)\s+from\b/i.test(text)) || null;
        return {
            maxDistance: maxDistanceSlider
                ? cleanText(maxDistanceSlider.getAttribute("aria-valuenow"))
                : (distancePill && cleanText(distancePill.match(/^[^a-zA-Z]*([\d.]+\s*(?:mi|km))/i)?.[1])) || null,
            landmark: selectedLandmark
                ? cleanText(
                    (findGroupLabel(selectedLandmark) && getDirectLabelText(findGroupLabel(selectedLandmark))) ||
                    selectedLandmark.getAttribute("aria-label") ||
                    selectedLandmark.getAttribute("value")
                )
                : (distancePill && cleanText(distancePill.replace(/^[^a-zA-Z]*[\d.]+\s*(?:mi|km)\s+from\s+/i, ""))) || null,
        };
    }

    function emptyCruiseFilterGroups() {
        return {
            deals: [],
            departingFrom: [],
            cruiseLengths: [],
            cruiseLines: [],
            cruiseStyles: [],
            ships: [],
            cabinTypes: [],
            ports: [],
        };
    }

    function getCruiseDateSelection() {
        const trigger = document.querySelector("div.btiUA._S");
        const currentMonth = document.querySelector("div.btiUA._S span.mHCeW.H4");
        return {
            triggerPresent: Boolean(trigger),
            currentMonth: cleanText(currentMonth?.textContent || "") || null,
        };
    }

    function getCruiseSortOrder() {
        const container = document.querySelector("div.DYAfS");
        const trigger = document.querySelector("div.jvgKF.B1.Z.S4") || container?.querySelector("div.jvgKF");
        const currentValue = document.querySelector("div.jvgKF span") || trigger?.querySelector("span");
        return cleanText(currentValue?.textContent || trigger?.textContent || "") || null;
    }

    function getCruiseActionBarState() {
        const actionBar = document.querySelector("div#filtersDiv ul.pKGCB");
        const state = {
            all: [],
            byGroup: {
                deals: [],
                cruiseLines: [],
                ships: [],
            },
        };
        if (!actionBar) {
            return state;
        }

        const collectPillTexts = (selector) => unique(
            [...actionBar.querySelectorAll(selector)]
                .map((node) => sanitizeFilterText(node.textContent || node.getAttribute("aria-label") || ""))
                .filter(Boolean)
        );

        state.all = collectPillTexts("li.oSjvu");
        state.byGroup.deals = collectPillTexts('li[data-automation="filter-selection-li-deals"]');
        state.byGroup.cruiseLines = collectPillTexts('li[data-automation="filter-selection-li-cruiseLines"]');
        state.byGroup.ships = collectPillTexts('li[data-automation="filter-selection-li-ships"]');
        return state;
    }

    function collectCruiseFilterGroups() {
        const groups = emptyCruiseFilterGroups();
        const headingMap = {
            "deal type": "deals",
            "departing from": "departingFrom",
            "cruise length": "cruiseLengths",
            "cruise line": "cruiseLines",
            "cruise style": "cruiseStyles",
            "ship": "ships",
            "cabin type": "cabinTypes",
            "port": "ports",
        };

        for (const group of document.querySelectorAll("div.QClzD")) {
            const heading = cleanText(group.querySelector("div.MDRRl")?.textContent || "");
            const key = headingMap[heading.toLowerCase()];
            if (!key) continue;

            const content = group.querySelector("div.content.tSmPf") || group;
            const selectedValues = [];
            for (const label of content.querySelectorAll("label")) {
                const forId = label.getAttribute("for");
                const input = label.querySelector('input[type="checkbox"], input[type="radio"]')
                    || (forId ? document.getElementById(forId) : null);
                const optionRoot = label.closest('[role="checkbox"], [role="radio"], li, div') || label;
                const checked = isInputChecked(input || optionRoot);
                if (!checked) continue;
                const text = sanitizeFilterText(getDirectLabelText(label) || optionRoot.textContent || "");
                if (text) {
                    selectedValues.push(text);
                }
            }
            groups[key] = unique(selectedValues);
        }

        return groups;
    }

    function mergeCruiseSelections(groups, actionBarState) {
        groups.deals = unique([...(groups.deals || []), ...(actionBarState.byGroup.deals || [])]);
        groups.cruiseLines = unique([...(groups.cruiseLines || []), ...(actionBarState.byGroup.cruiseLines || [])]);
        groups.ships = unique([...(groups.ships || []), ...(actionBarState.byGroup.ships || [])]);
        return groups;
    }

    function parseIntegerParam(searchParams, keys) {
        for (const key of keys) {
            const value = searchParams.get(key);
            if (!value) continue;
            const parsed = parseInt(value, 10);
            if (!Number.isNaN(parsed)) {
                return parsed;
            }
        }
        return null;
    }

    function parseOccupancyState() {
        const primaryButton = document.querySelector('button[data-automation="roomsandguests"], button[data-automation="enterGuests"], [data-automation="enterGuests"] button');
        if (primaryButton) {
            const aria = cleanText(primaryButton.getAttribute("aria-label"));
            const roomMatch = aria.match(/selected number of rooms is\s+(\d+)/i);
            const guestMatch = aria.match(/selected number of guests is\s+(\d+)/i);
            if (roomMatch || guestMatch) {
                return {
                    guests: guestMatch ? parseInt(guestMatch[1], 10) : null,
                    rooms: roomMatch ? parseInt(roomMatch[1], 10) : null,
                };
            }
        }

        const selectors = [
            'button[data-automation="roomsandguests"]',
            'button[data-automation="roomsandguests"] *',
            'button[data-automation="enterGuests"]',
            'button[data-automation="enterGuests"] *',
            '[data-automation="enterGuests"] button',
            '[data-automation="enterGuests"] button *',
            'button[data-automation*="guest"]',
            'button[data-automation*="room"]',
            'button[data-automation*="adult"]',
            'button[aria-label*="guest" i]',
            'button[aria-label*="adult" i]',
            'button[aria-label*="room" i]',
            '[data-automation*="occupancy"]',
            '[data-automation*="occupancy"] *',
            '[data-automation*="traveler"]',
            '[data-automation*="traveler"] *',
            '[data-automation*="guest"] *',
            '[data-automation*="room"] *',
            '[data-automation*="adult"] *',
            '[data-test-target*="guest"]',
            '[data-test-target*="room"]',
        ];

        const candidates = collectTexts(selectors);

        let guests = null;
        let rooms = null;
        for (const text of candidates) {
            const roomMatch = text.match(/\b(\d+)\s+rooms?\b/i);
            if (roomMatch && rooms == null) {
                rooms = parseInt(roomMatch[1], 10);
            }

            const adultsMatch = text.match(/\b(\d+)\s+adults?\b/i);
            if (adultsMatch && guests == null) {
                guests = parseInt(adultsMatch[1], 10);
            }

            const guestsMatch = text.match(/\b(\d+)\s+guests?\b/i);
            if (guestsMatch && guests == null) {
                guests = parseInt(guestsMatch[1], 10);
            }

            if (guests != null && rooms != null) {
                break;
            }
        }

        if (guests == null || rooms == null) {
            const pageText = document.body ? cleanText(document.body.innerText || document.body.textContent) : "";

            const combinedMatch = pageText.match(/\b(\d+)\s+(?:guests?|adults?)\b[\s\S]{0,40}?\b(\d+)\s+rooms?\b/i);
            if (combinedMatch) {
                if (guests == null) guests = parseInt(combinedMatch[1], 10);
                if (rooms == null) rooms = parseInt(combinedMatch[2], 10);
            }

            const reversedMatch = pageText.match(/\b(\d+)\s+rooms?\b[\s\S]{0,40}?\b(\d+)\s+(?:guests?|adults?)\b/i);
            if (reversedMatch) {
                if (rooms == null) rooms = parseInt(reversedMatch[1], 10);
                if (guests == null) guests = parseInt(reversedMatch[2], 10);
            }
        }

        return { guests, rooms };
    }

    function parseLdJsonBlocks() {
        const blocks = [];
        for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
                const parsed = JSON.parse(script.textContent);
                if (Array.isArray(parsed)) {
                    blocks.push(...parsed);
                } else if (parsed && Array.isArray(parsed["@graph"])) {
                    blocks.push(...parsed["@graph"]);
                } else if (parsed) {
                    blocks.push(parsed);
                }
            } catch (_) {
                // Ignore malformed LD+JSON blocks.
            }
        }
        return blocks;
    }

    function flattenLdJsonItem(item) {
        if (!item || typeof item !== "object") return null;
        if (item.item && typeof item.item === "object") return item.item;
        return item;
    }

    function findHotelLikeItem(items) {
        for (const item of items) {
            const candidate = flattenLdJsonItem(item);
            const type = candidate && candidate["@type"];
            const types = Array.isArray(type) ? type : [type];
            if (types.some((entry) => typeof entry === "string" && /hotel|lodgingbusiness/i.test(entry))) {
                return candidate;
            }
            if (
                candidate &&
                cleanText(candidate.name) &&
                (candidate.offers || candidate.aggregateRating)
            ) {
                return candidate;
            }
        }
        return null;
    }

    function extractLdJsonHotelState() {
        const items = parseLdJsonBlocks();
        const hotel = findHotelLikeItem(items);
        if (!hotel) {
            return {
                hotelName: extractTitleHotelName(),
                price: parseNumber(getMetaContent(["price", "lowPrice"])),
                rating: parseNumber(getMetaContent(["ratingValue", "og:rating"])),
                source: "dom_only",
            };
        }

        const offers = Array.isArray(hotel.offers) ? hotel.offers[0] : hotel.offers;
        const aggregateRating = hotel.aggregateRating || {};

        return {
            hotelName: cleanText(hotel.name) || extractTitleHotelName(),
            price: parseNumber(
                offers &&
                (offers.price || offers.lowPrice ||
                    (offers.priceSpecification && offers.priceSpecification.price))
            ),
            rating: parseNumber(aggregateRating.ratingValue) || parseNumber(getMetaContent(["ratingValue", "og:rating"])),
            source: "ld+json",
        };
    }

    function extractCitySlugFromPath(url) {
        const match = url.pathname.match(/^\/Hotels-(g\d+)-(.+?)-Hotels(?:\.html|\/|$)/i);
        if (!match) {
            return null;
        }

        const rawTokens = match[2].split("-").filter(Boolean);
        const cityTokens = rawTokens.filter(
            (token) => !/^z[a-z0-9_]+(?:\.[a-z0-9_]+)?$/i.test(token) && !/^a_[a-z0-9_.]+$/i.test(token)
        );
        return cityTokens.length ? cityTokens.join("_") : null;
    }

    function extractCruiseLocationSlugFromPath(url) {
        const match = url.pathname.match(CRUISE_PATH_RE);
        if (!match) {
            return null;
        }

        const rawTokens = match[2].split("-").filter(Boolean);
        const locationTokens = rawTokens.filter(
            (token) => !/^z[a-z0-9_]+(?:\.[a-z0-9_]+)?$/i.test(token) && !/^a_[a-z0-9_.]+$/i.test(token)
        );
        return locationTokens.length ? locationTokens.join("_") : null;
    }

    function getUrlState() {
        const url = new URL(window.location.href);
        const hotelMatch = url.pathname.match(HOTEL_PATH_RE);
        const restaurantMatch = url.pathname.match(RESTAURANT_PATH_RE);
        const cruiseMatch = url.pathname.match(CRUISE_PATH_RE);
        const occupancy = parseOccupancyState();
        const pageText = document.body ? cleanText(document.body.innerText || document.body.textContent).toLowerCase() : "";
        const antiBotStatus =
            pageText.includes("access is temporarily restricted") ||
                pageText.includes("unusual activity") ||
                pageText.includes("your request looks automated") ||
                pageText.includes("verification required") ||
                pageText.includes("please verify your browser") ||
                pageText.includes("are you a robot") ||
                document.querySelector('[name*="captcha" i], iframe[src*="captcha" i], [id*="captcha" i]') ?
                "blocked_access_restricted" :
                "clear";

        return {
            url: url.href,
            pageType: hotelMatch ? "hotel_results" : restaurantMatch ? "restaurant_results" : cruiseMatch ? "cruise_results" : "other",
            antiBotStatus,
            geographicId: hotelMatch ? hotelMatch[1].toLowerCase() : cruiseMatch ? cruiseMatch[1].toLowerCase() : null,
            citySlug:
                extractCitySlugFromPath(url) ||
                extractCruiseLocationSlugFromPath(url) ||
                extractCitySlugFromRestaurantPath(url) ||
                extractCitySlugFromTitle() ||
                extractCitySlugFromTourismNavHeader(),
            guests: occupancy.guests ?? parseIntegerParam(url.searchParams, ["adults", "adult", "guests", "guest", "partySize", "party"]),
            rooms: occupancy.rooms ?? parseIntegerParam(url.searchParams, ["rooms", "room", "numRooms", "roomCount"]),
            urlDate: url.searchParams.get("date") || url.searchParams.get("checkIn") || null,
            urlTime: url.searchParams.get("time") || url.searchParams.get("reservationTime") || null,
        };
    }

    const checkIn = parseDateValue('button[data-automation="checkin"], button[data-automation="enterDate"], [data-automation="enterDate"] button');
    const checkOut = parseDateValue('button[data-automation="checkout"]');
    const reservationTime = parseDateValue('button[data-automation="enterTime"], [data-automation="enterTime"] button');
    const selectedFilterBarValues = collectSelectedFilterBarValues();
    const groupedFilters = finalizeGroupedFilters(mergeSelectedPillsIntoGroups(
        collectCheckedFilterGroups(),
        [...collectSelectedFilterPills(), ...selectedFilterBarValues],
    ));
    const urlState = getUrlState();
    const cruiseActionBarState = getCruiseActionBarState();
    const cruiseDateSelection = getCruiseDateSelection();
    const cruiseGroups = mergeCruiseSelections(collectCruiseFilterGroups(), cruiseActionBarState);
    const cruiseActiveFilters = unique([
        ...cruiseActionBarState.all,
        ...(cruiseGroups.deals || []),
        ...(cruiseGroups.departingFrom || []),
        ...(cruiseGroups.cruiseLengths || []),
        ...(cruiseGroups.cruiseLines || []),
        ...(cruiseGroups.cruiseStyles || []),
        ...(cruiseGroups.ships || []),
        ...(cruiseGroups.cabinTypes || []),
        ...(cruiseGroups.ports || []),
    ]);
    const defaultActiveFilters = unique([
        ...collectActionBarValues(),
        ...selectedFilterBarValues,
        ...collectActiveFilters(),
        ...groupedFilters.activeFilters,
    ]);
    const activeFilters = urlState.pageType === "cruise_results" ? cruiseActiveFilters : defaultActiveFilters;

    return {
        ...urlState,
        ...extractLdJsonHotelState(),
        checkIn: checkIn.iso || checkIn.raw,
        checkOut: checkOut.iso || checkOut.raw,
        departureMonth: cruiseDateSelection.currentMonth,
        reservationTime: reservationTime.raw,
        activeFilters,
        selectedFilterBarValues: urlState.pageType === "cruise_results" ? cruiseActionBarState.all : selectedFilterBarValues,
        brands: groupedFilters.brands,
        amenities: groupedFilters.amenities,
        styles: groupedFilters.styles,
        deals: urlState.pageType === "cruise_results" ? (cruiseGroups.deals.length ? cruiseGroups.deals : 0) : groupedFilters.deals,
        awards: groupedFilters.awards,
        propertyTypes: groupedFilters.propertyTypes,
        neighborhoods: groupedFilters.neighborhoods,
        travelerRatings: groupedFilters.travelerRatings,
        hotelClasses: groupedFilters.hotelClasses,
        popularFilters: groupedFilters.popularFilters,
        cruiseLines: cruiseGroups.cruiseLines.length ? cruiseGroups.cruiseLines : 0,
        departingFrom: cruiseGroups.departingFrom.length ? cruiseGroups.departingFrom : 0,
        cruiseLengths: cruiseGroups.cruiseLengths.length ? cruiseGroups.cruiseLengths : 0,
        cruiseStyles: cruiseGroups.cruiseStyles.length ? cruiseGroups.cruiseStyles : 0,
        ships: cruiseGroups.ships.length ? cruiseGroups.ships : 0,
        cabinTypes: cruiseGroups.cabinTypes.length ? cruiseGroups.cabinTypes : 0,
        ports: cruiseGroups.ports.length ? cruiseGroups.ports : 0,
        establishmentTypes: groupedFilters.establishmentTypes,
        mealTypes: groupedFilters.mealTypes,
        cuisines: groupedFilters.cuisines,
        dishes: groupedFilters.dishes,
        diets: groupedFilters.diets,
        diningOptions: groupedFilters.diningOptions,
        priceTypes: groupedFilters.priceTypes,
        selectedFiltersByGroup: {
            popularFilters: groupedFilters.popularFilters,
            deals: groupedFilters.deals,
            propertyTypes: groupedFilters.propertyTypes,
            amenities: groupedFilters.amenities,
            awards: groupedFilters.awards,
            neighborhoods: groupedFilters.neighborhoods,
            travelerRatings: groupedFilters.travelerRatings,
            hotelClasses: groupedFilters.hotelClasses,
            styles: groupedFilters.styles,
            brands: groupedFilters.brands,
            cruiseLines: cruiseGroups.cruiseLines.length ? cruiseGroups.cruiseLines : 0,
            departingFrom: cruiseGroups.departingFrom.length ? cruiseGroups.departingFrom : 0,
            cruiseLengths: cruiseGroups.cruiseLengths.length ? cruiseGroups.cruiseLengths : 0,
            cruiseStyles: cruiseGroups.cruiseStyles.length ? cruiseGroups.cruiseStyles : 0,
            ships: cruiseGroups.ships.length ? cruiseGroups.ships : 0,
            cabinTypes: cruiseGroups.cabinTypes.length ? cruiseGroups.cabinTypes : 0,
            ports: cruiseGroups.ports.length ? cruiseGroups.ports : 0,
            establishmentTypes: groupedFilters.establishmentTypes,
            mealTypes: groupedFilters.mealTypes,
            cuisines: groupedFilters.cuisines,
            dishes: groupedFilters.dishes,
            diets: groupedFilters.diets,
            diningOptions: groupedFilters.diningOptions,
            priceTypes: groupedFilters.priceTypes,
        },
        priceRange: getPriceRangeState(),
        distanceFrom: getDistanceState(),
        sortOrder: urlState.pageType === "cruise_results" ? getCruiseSortOrder() : getSortOrder(),
    };
})();
