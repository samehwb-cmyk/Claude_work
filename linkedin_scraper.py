import json
from playwright.sync_api import sync_playwright

SEARCH_MATRIX = {
    "Search 1 - Technical Project Manager": "https://www.linkedin.com/jobs/search/?keywords=Technical+Project+Manager+IT&f_WT=2&f_TPR=r86400",
    "Search 2 - Technical Program Manager": "https://www.linkedin.com/jobs/search/?keywords=Technical+Program+Manager&f_WT=2&f_TPR=r86400",
    "Search 3 - IT Program Manager": "https://www.linkedin.com/jobs/search/?keywords=IT+Program+Manager&f_WT=2&f_TPR=r86400",
    "Search 4 - IT Service Delivery Manager": "https://www.linkedin.com/jobs/search/?keywords=IT+Service+Delivery+Manager&f_WT=2&f_TPR=r86400",
    "Search 5 - Senior IT Project Manager PA": "https://www.linkedin.com/jobs/search/?keywords=Senior+IT+Project+Manager&location=Pennsylvania&f_TPR=r86400",
    "Search 6 - Infrastructure Project Manager": "https://www.linkedin.com/jobs/search/?keywords=Infrastructure+Project+Manager&f_WT=2&f_TPR=r86400",
    "Search 7 - ITSM Manager": "https://www.linkedin.com/jobs/search/?keywords=ITSM+Manager+IT+Service+Management&f_WT=2&f_TPR=r86400",
    "Search 8 - PMO Manager": "https://www.linkedin.com/jobs/search/?keywords=PMO+Manager+IT&f_WT=2&f_TPR=r86400",
    "Search 9 - VA/NoVA Federal Contractor Sweep": "https://www.linkedin.com/jobs/search/?keywords=IT+Program+Manager+OR+Technical+Project+Manager&location=Virginia&f_TPR=r604800"
}

def extract_jobs():
    extracted_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = context.new_page()

        for search_name, url in SEARCH_MATRIX.items():
            print(f"Scraping {search_name}...")
            try:
                page.goto(url, timeout=30000)
                page.wait_for_timeout(3000)

                # Collect job elements
                jobs = page.query_selector_all("ul.jobs-search__results-list > li, div.job-card-container")
                for job in jobs[:15]:  # Process top matching entries per search
                    title_elem = job.query_selector(".base-search-card__title, .job-card-list__title")
                    company_elem = job.query_selector(".base-search-card__subtitle, .job-card-container__primary-description")
                    location_elem = job.query_selector(".job-search-card__location, .job-card-container__metadata-item")
                    link_elem = job.query_selector("a.base-card__full-link, a.job-card-list__title")

                    if title_elem and link_elem:
                        extracted_data.append({
                            "title": title_elem.inner_text().strip(),
                            "company": company_elem.inner_text().strip() if company_elem else "N/A",
                            "location": location_elem.inner_text().strip() if location_elem else "N/A",
                            "link": link_elem.get_attribute("href").split("?")[0],
                            "search_source": search_name
                        })
            except Exception as e:
                print(f"Error fetching {search_name}: {e}")

        browser.close()

    # Deduplicate extracted jobs by link
    unique_jobs = {}
    for item in extracted_data:
        link = item["link"]
        if link not in unique_jobs:
            unique_jobs[link] = item
        else:
            unique_jobs[link]["search_source"] += f", {item['search_source']}"

    return list(unique_jobs.values())

if __name__ == "__main__":
    jobs_list = extract_jobs()
    with open("raw_extracted_jobs.json", "w", encoding="utf-8") as f:
        json.dump(jobs_list, f, indent=2)
    print(f"Extracted {len(jobs_list)} unique jobs.")
