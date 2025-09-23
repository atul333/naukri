import asyncio
from main import NaukriJobScraper

async def test_scraper():
    # Create scraper instance with test credentials
    scraper = NaukriJobScraper('test_token', 'test_channel')
    
    # Run the scraper
    print("Starting job scraping test...")
    jobs = await scraper.scrape_jobs()
    
    # Print results
    print(f"Found {len(jobs)} jobs")
    
    # Print details of first few jobs
    for i, job in enumerate(jobs[:3]):
        print(f"\nJob {i+1}:")
        print(f"Title: {job['title']}")
        print(f"Company: {job['company']}")
        print(f"Location: {job['location']}")
        print(f"Posted Date: {job['posted_date']}")
        print(f"Apply Link: {job['apply_link']}")

if __name__ == "__main__":
    asyncio.run(test_scraper())