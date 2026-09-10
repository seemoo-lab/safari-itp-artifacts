let donationPayload = null;

// Drag & Drop Setup
const dropZone = document.getElementById('drop-zone');
const reviewSection = document.getElementById('review-section');
const jsonPreview = document.getElementById('json-preview');

// Visual feedback for dragging
['dragenter', 'dragover'].forEach(e => {
     dropZone.addEventListener(e, (ev) => {
        ev.preventDefault();
        dropZone.classList.add('hover');
    });
  });

['dragleave', 'drop'].forEach(e => {
    dropZone.addEventListener(e, (ev) => {
        ev.preventDefault();
        dropZone.classList.remove('hover');
    });
});

async function queryMetadata(db) {

    const metadata = {};
    
    // Get number of operation days
    const operationDays = db.exec("SELECT COUNT(*) FROM OperatingDates");
    metadata.operationDays = operationDays[0].values[0][0];

    // Get number of observed domains (before filtering)
    const observedDomainCount = db.exec("SELECT COUNT(domainID) FROM ObservedDomains");
    metadata.observedDomainCountBeforeFiltering = observedDomainCount[0].values[0][0];

    // Number of prevalent domains
    const prevalentDomainCount = db.exec("SELECT COUNT(domainID) FROM ObservedDomains WHERE isPrevalent = 1");
    metadata.prevalentDomainCountBeforeFiltering = prevalentDomainCount[0].values[0][0];

    // Number of very prevalent domains
    const veryPrevalentDomainCount = db.exec("SELECT COUNT(domainID) FROM ObservedDomains WHERE isVeryPrevalent = 1");
    metadata.veryPrevalentDomainCountBeforeFiltering = veryPrevalentDomainCount[0].values[0][0];

    // Number of domains with user interaction
    const userInteractionDomainCount = db.exec("SELECT COUNT(domainID) FROM ObservedDomains WHERE hadUserInteraction = 1");
    metadata.userInteractionDomainCountBeforeFiltering = userInteractionDomainCount[0].values[0][0];

    return metadata;
}

async function queryDomains(db) {

    // Fetch all prevalent domains
    const prevalentDomains = db.exec("SELECT domainID, registrableDomain, lastSeen, hadUserInteraction, mostRecentUserInteractionTime, isPrevalent, isVeryPrevalent, dataRecordsRemoved, timesAccessedAsFirstPartyDueToUserInteraction, timesAccessedAsFirstPartyDueToStorageAccessAPI, isScheduledForAllButCookieDataRemoval FROM ObservedDomains");

    // Transform to hashmap with domainID as key
    let prevalentDomainMap = {};
    if (prevalentDomains.length > 0) {
        for (const row of prevalentDomains[0].values) {
            prevalentDomainMap[row[0]] = {
                registrableDomain: row[1],
                lastSeen: row[2],
                hadUserInteraction: row[3],
                mostRecentUserInteractionTime: parseInt(row[4]),
                isPrevalent: row[5],
                isVeryPrevalent: row[6],
                dataRecordsRemoved: row[7],
                timesAccessedAsFirstPartyDueToUserInteraction: row[8],
                timesAccessedAsFirstPartyDueToStorageAccessAPI: row[9],
                isScheduledForAllButCookieDataRemoval: row[10],
            };
        }
    }

    return prevalentDomainMap;
}

async function filterNonWhitelistedDomains(domainMap) {
    const whitelist = await fetchWhitelist();
    const whitelistSet = new Set(whitelist);

    // remove all non-whitelisted domains
    for (const domainID in domainMap) {
        const domain = domainMap[domainID].registrableDomain;
        if (!whitelistSet.has(domain)) {
            delete domainMap[domainID];
        }
    }

    // Right now, we just remove domain UUIDs from extensions
    // for (const domainID in domainMap) {
    //     const domain = domainMap[domainID].registrableDomain;
    //     if (domain.length === 36 && /^[A-F0-9\-]+$/.test(domain)) {
    //         delete domainMap[domainID];
    //     }
    // }

    return domainMap;
}

async function enrichDomainData(db, domainMap) {
    const domains = {};

    // Bulk Fetch Data into Lookup Maps
    // Helper to transform SQL results into a Map: ID -> Array of Related IDs
    const buildLookup = (query) => {
        const map = new Map();
        const result = db.exec(query);
        if (result.length > 0 && result[0].values) {
            for (const row of result[0].values) {
                const key = row[0];   // The ID we will look up (e.g., subresourceDomainID)
                const value = row[1]; // The data we want (e.g., topFrameDomainID)
                
                if (!map.has(key)) map.set(key, []);
                map.get(key).push(value);
            }
        }
        return map;
    };

    // Subresource Under Top Frame
    const subresourceUnderMap = buildLookup("SELECT DISTINCT subresourceDomainID, topFrameDomainID FROM SubresourceUnderTopFrameDomains");

    // Subframe Under Top Frame
    const subframeUnderMap = buildLookup("SELECT DISTINCT subframeDomainID, topFrameDomainID FROM SubframeUnderTopFrameDomains");

    // Third Party Scripts
    const thirdPartyScriptsMap = buildLookup("SELECT DISTINCT subresourceDomainID, topFrameDomainID FROM TopFrameLoadedThirdPartyScripts");

    // Storage Access
    const storageAccessMap = buildLookup("SELECT DISTINCT domainID, topLevelDomainID FROM StorageAccessUnderTopFrameDomains");

    // Redirects (Special Case: One table, two directions)
    const redirectsToMeMap = new Map();   // Key: Target, Value: Source
    const redirectsFromMeMap = new Map(); // Key: Source, Value: Target
    
    const redirectsResult = db.exec("SELECT DISTINCT fromDomainID, subresourceDomainID FROM SubresourceUniqueRedirectsFrom");
    if (redirectsResult.length > 0 && redirectsResult[0].values) {
        for (const row of redirectsResult[0].values) {
            const fromID = row[0];
            const toID = row[1];

            // "Redirects To Me": I am 'toID', I want 'fromID'
            if (!redirectsToMeMap.has(toID)) redirectsToMeMap.set(toID, []);
            redirectsToMeMap.get(toID).push(fromID);

            // "Redirects From Me": I am 'fromID', I want 'toID'
            if (!redirectsFromMeMap.has(fromID)) redirectsFromMeMap.set(fromID, []);
            redirectsFromMeMap.get(fromID).push(toID);
        }
    }
    
    // Helper to resolve a list of IDs to their Registrable Domain strings
    const resolveDomains = (ids) => {
        if (!ids) return [];
        return ids
            .map(id => domainMap[id]?.registrableDomain)
            .filter(Boolean); // Remove null/undefined if ID is missing from domainMap
    };

    // Iterate through domainMap once, performing O(1) lookups for the data
    for (const domainIDStr in domainMap) {
        // Ensure ID types match (DB usually returns numbers, object keys are strings)
        const domainID = Number(domainIDStr); 
        const originalData = domainMap[domainIDStr];

        domains[originalData.registrableDomain] = {
            ...originalData,
            observedAsSubresourceUnder: resolveDomains(subresourceUnderMap.get(domainID)),
            observedAsSubframeUnder: resolveDomains(subframeUnderMap.get(domainID)),
            observedAsThirdPartyScriptUnder: resolveDomains(thirdPartyScriptsMap.get(domainID)),
            subresourceUniqueRedirectsToMe: resolveDomains(redirectsToMeMap.get(domainID)),
            subresourceUniqueRedirectsFromMe: resolveDomains(redirectsFromMeMap.get(domainID)),
            storageAccessUnder: resolveDomains(storageAccessMap.get(domainID)),
        };
    }

    return domains;
}

async function queryTopFrameUniqueRedirects(db) {
    const topFrameUniqueRedirects = {};

    // Use LEFT JOINs to fetch main data and checks (SSS/Decorations) in a single pass.
    // We check for existence (IS NOT NULL) to determine the boolean flags.
    const query = `
        SELECT 
            FromDomain.registrableDomain, 
            ToDomain.registrableDomain, 
            T2.sourceDomainID, 
            T3.fromDomainID
        FROM TopFrameUniqueRedirectsTo AS T1
        LEFT JOIN TopFrameUniqueRedirectsToSinceSameSiteStrictEnforcement AS T2
            ON T1.sourceDomainID = T2.sourceDomainID 
            AND T1.toDomainID = T2.toDomainID
        LEFT JOIN TopFrameLinkDecorationsFrom AS T3
            ON T1.sourceDomainID = T3.fromDomainID 
            AND T1.toDomainID = T3.toDomainID
        JOIN ObservedDomains AS FromDomain 
            ON T1.sourceDomainID = FromDomain.domainID
        JOIN ObservedDomains AS ToDomain 
            ON T1.toDomainID = ToDomain.domainID
    `;

    const result = db.exec(query);

    if (result.length > 0) {
        // Iterate once through the combined result set
        for (const row of result[0].values) {
            const fromDomain = row[0];
            const toDomain = row[1];
            // If the ID from the LEFT JOIN is not null, the record exists in that table
            const isSinceSSS = row[2] !== null; 
            const hasDeco = row[3] !== null;

            if (!topFrameUniqueRedirects[fromDomain]) {
                topFrameUniqueRedirects[fromDomain] = [];
            }
            
            // Add the redirect entry
            topFrameUniqueRedirects[fromDomain].push({
                toDomain: toDomain,
                sinceSameSiteStrictEnforcement: isSinceSSS,
                hasLinkDecorations: hasDeco
            });
        }
    }

    return topFrameUniqueRedirects;
}

async function filterUserRemovedDomains(donationPayload, domainsToKeep) {

    const keepSet = new Set(domainsToKeep);

    // domains filtering
    const referenceFields = [
        "observedAsSubresourceUnder",
        "observedAsSubframeUnder",
        "observedAsThirdPartyScriptUnder",
        "subresourceUniqueRedirectsToMe",
        "subresourceUniqueRedirectsFromMe",
        "storageAccessUnder"
    ];

    const filteredDomains = {};

    // Iterate over the existing domains
    if (donationPayload.domains) {
        for (const domainName in donationPayload.domains) {
            
            // Primary Check: Should this domain exist at all?
            if (keepSet.has(domainName)) {
                const originalData = donationPayload.domains[domainName];
                
                // Shallow copy to modify arrays safely
                const cleanedData = { ...originalData };

                // Secondary Check: Filter the internal relationship arrays
                for (const field of referenceFields) {
                    if (Array.isArray(cleanedData[field])) {
                        cleanedData[field] = cleanedData[field].filter(relatedDomain => 
                            keepSet.has(relatedDomain)
                        );
                    }
                }
                filteredDomains[domainName] = cleanedData;
            }
        }
        donationPayload.domains = filteredDomains;
    }

    // TopFrameUniqueRedirects filtering
    if (donationPayload.topFrameUniqueRedirects) {
        const filteredRedirects = {};

        for (const sourceDomain in donationPayload.topFrameUniqueRedirects) {
            // Check if the Source Domain is allowed
            if (keepSet.has(sourceDomain)) {
                
                // Filter the targets: 'toDomain' must also be allowed
                const originalArray = donationPayload.topFrameUniqueRedirects[sourceDomain];
                const validEntries = originalArray.filter(entry => 
                    keepSet.has(entry.toDomain)
                );

                // Only add to result if there are valid redirects left
                // (This preserves the sparse nature of the redirects object)
                if (validEntries.length > 0) {
                    filteredRedirects[sourceDomain] = validEntries;
                }
            }
        }
        donationPayload.topFrameUniqueRedirects = filteredRedirects;
    }

    return donationPayload;
}
window.filterUserRemovedDomains = filterUserRemovedDomains;

async function processDbFile(file) {
    
    try {

        const SQL = await initSqlJs({
            locateFile: file => `dist/sqljs/${file}`
        });

        // Read file into db
        const arrayBuffer = await file.arrayBuffer();
        const db = new SQL.Database(new Uint8Array(arrayBuffer));

        // Extract data from database
        const metadata = await queryMetadata(db);

        // Collect prevalent domains
        let domainMap = await queryDomains(db);

        // Filter out non-whitelisted domains
        const filteredDomainMap = await filterNonWhitelistedDomains(domainMap);

        // Collect subresource and subframe, and third-party script, subresource redirect observations, storage access for each prevalent domain
        const domains = await enrichDomainData(db, filteredDomainMap);
        
        // TopFrameUniqueRedirectsTo, TopFrameUniqueRedirectsToSinceSameSiteStrictEnforcement, and TopFrameLinkDecorationsFrom
        const topFrameUniqueRedirects = await queryTopFrameUniqueRedirects(db);

        // from each data[key], remove the registrableDomain value key (redundant)
        for (const domain in domains) {
            delete domains[domain].registrableDomain;
        }

        // order domains by isPrevalent, registrableDomain
        const orderedDomains = Object.fromEntries(
            Object.entries(domains).sort((a, b) => {
                // First by isPrevalent (true first)
                if (b[1].isPrevalent !== a[1].isPrevalent) {
                    return b[1].isPrevalent - a[1].isPrevalent;
                }
                // Then by registrableDomain alphabetically
                return a[0].localeCompare(b[0]);
            })
        );

        // Prepare payload
        donationPayload = {
            processedAt: Date.parse(new Date()),
            metadata: metadata,
            domains: orderedDomains,
            topFrameUniqueRedirects: topFrameUniqueRedirects
        };

        // Close the database
        db.close();

        return donationPayload;
        
    } catch (error) {
        console.error("Error processing DB file:", error);
        return null;
    }
}

async function fetchWhitelist() {
    try {
        let api_url = 'data/whitelist.txt';
        const urlParams = new URLSearchParams(window.location.search);
        const accessKey = urlParams.get('k');
        if (accessKey) {
            api_url += `?k=${encodeURIComponent(accessKey)}`;
        }
        const res = await fetch(api_url);
        if (res.ok) {
            const whitelist = await res.text();
            const items = whitelist.split('\n').map(line => line.trim()).filter(line => line.length > 0);
            return items;
        } else {
            console.error("Failed to fetch whitelist:", res.statusText);
            return [];
        }
    } catch (error) {
        console.error("Error fetching whitelist:", error);
        return [];
    }
}

// File processing
dropZone.addEventListener('drop', async (e) => {
    const file = e.dataTransfer.files[0];
    if (!file) return;

    // Language detection
    const currentLang = document.getElementById('btn-de').classList.contains('active') ? 'de' : 'en';

    // Check filename
    if (file.name !== 'observations.db') {
        dropZone.innerHTML = dictionary[currentLang].invalid_file;
        setTimeout(() => {
            dropZone.innerHTML = `<h4 class="mb-3" data-i18n="drag_drop_file_here">${dictionary[currentLang].drag_drop_file_here}</h4><p class="text-muted small" data-i18n="file_processing_info">${dictionary[currentLang].file_processing_info}</p>`;
        }, 3000);
        return;
    }

    // Check file size
    const MAX_SIZE = 2 * 1024 * 1024; // 2MB in bytes
    if (file.size > MAX_SIZE) { 
        dropZone.innerHTML = dictionary[currentLang].file_too_large;
        setTimeout(() => {
            dropZone.innerHTML = `<h4 class="mb-3" data-i18n="drag_drop_file_here">${dictionary[currentLang].drag_drop_file_here}</h4><p class="text-muted small" data-i18n="file_processing_info">${dictionary[currentLang].file_processing_info}</p>`;
        }, 3000);
        return;
    }

    // Check for SQLite magic header
    const header = await file.slice(0, 16).text();
    if (header !== 'SQLite format 3\u0000') {
        dropZone.innerHTML = dictionary[currentLang].not_valid_sqlite;
        setTimeout(() => {
            dropZone.innerHTML = `<h4 class="mb-3" data-i18n="drag_drop_file_here">${dictionary[currentLang].drag_drop_file_here}</h4><p class="text-muted small" data-i18n="file_processing_info">${dictionary[currentLang].file_processing_info}</p>`;
        }, 3000);
        return;
    }

    // Process the file
    dropZone.innerHTML = `<div class="spinner-border text-primary" role="status"></div><p class="mt-2">${dictionary[currentLang].processing}</p>`;

    let donationPayload = await processDbFile(file);
    if (donationPayload) {

        // File processed successfully
        window.domainManager.load(Object.keys(donationPayload.domains));
        window.domainManager.sort();
        window.donationPayload = donationPayload;

        reviewSection.classList.remove('d-none');
        dropZone.innerHTML = dictionary[currentLang].file_processed;

        // Hide drop zone after a delay with smooth transition
        setTimeout(() => {
            dropZone.style.transition = 'opacity 0.5s ease-out';
            dropZone.style.opacity = '0';
            setTimeout(() => {
                dropZone.classList.add('d-none');
            }, 250);
        }, 250);

    }else {
        dropZone.innerHTML = dictionary[currentLang].something_went_wrong;
    }
    
}); // End of drop event listener

// Send report to server
document.getElementById('btn-donate').addEventListener('click', async () => {
    if (!window.donationPayload) return;

    // Language detection
    const currentLang = document.getElementById('btn-de').classList.contains('active') ? 'de' : 'en';


    // Check if privacy policy and terms are accepted
    // privacy-policy-checkbox and consent-checkbox
    const privacyPolicyAccepted = document.getElementById('privacy-policy-checkbox').checked;
    const consentGiven = document.getElementById('consent-checkbox').checked;
    if (!privacyPolicyAccepted || !consentGiven) {
        alert(dictionary[currentLang].accept_terms);
        return;
    }

    const btn = document.getElementById('btn-donate');
    btn.disabled = true;
    btn.innerText = dictionary[currentLang].uploading;

    // Research context questions
    const usesAdBlocker = document.querySelector('input[name="q_adblock"]:checked')?.value;
    const adBlockerText = document.getElementById('adblock_name')?.value || '';

    const safariUsageFrequency = document.querySelector('input[name="q_safari_freq"]:checked')?.value;
    const platform = document.getElementById('platform-select')?.value;

    const searchEngine = document.getElementById('search-engine-select')?.value;
    
    // Filter out domains the user chose to remove
    const domainsToKeep = window.domainManager.get();
    const payload = await filterUserRemovedDomains(window.donationPayload, domainsToKeep);

    const finalPayload = {
        ...payload, 
        questions: {
            usesAdBlocker: usesAdBlocker,
            adBlockerText: adBlockerText,
            safariUsageFrequency: safariUsageFrequency,
            platform: platform,
            searchEngine: searchEngine
        }
    };

    try {
        // Read the key from URL
        let api_url = 'donate';
        const urlParams = new URLSearchParams(window.location.search);
        const accessKey = urlParams.get('k');
        if (accessKey) {
            api_url += `?k=${encodeURIComponent(accessKey)}`;
        }

        // Send to server
        const res = await fetch(api_url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(finalPayload)
        });

        if (res.ok) {
            // Success, extract donation ID and redirect
            const resData = await res.json();
            const fileId = resData.data?.id || null;
            sessionStorage.setItem('donationId', fileId);

            // Redirect to thank you page
            const thankYouUrl = 'thankyou?lang=' + currentLang + (accessKey && accessKey !== 'null' ? `&k=${encodeURIComponent(accessKey)}` : '');
            window.location.href = thankYouUrl;
        } else {
            alert("Server error: " + res.statusText);
            btn.disabled = false;
        }
    } catch (err) {
        alert("Network error: " + err.message);
        btn.disabled = false;
    }
}); // End of donate button listener
