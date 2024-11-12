import os
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Page
import random
import time
import logging
from datetime import datetime
from app.core.config import config
from app.utils.playwright_helper import human_type

# Set up logging
logging.basicConfig(
    filename='script_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_and_print(message):
    """Logs and prints a message for tracking script progress."""
    print(message)
    logging.info(message)

def setup_download_folder():
    """Creates a timestamped download folder and returns its path for saving files."""
    download_dir = os.path.join(os.getcwd(), f"downloads_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(download_dir, exist_ok=True)
    log_and_print(f"Download folder created: {download_dir}")
    return download_dir

class UPSSelectors:
    LOGIN_USERNAME = [
        "input[type='text']", "#email", "//input[@id='email']", "//input[@name='userID']",
        "/html/body/div[1]/div[3]/div/div/div/div/div/main/div/div/div/form/div[2]/div[2]/div/div[1]/input",
        ".ups-form_input.ups-check.ups-active"
    ]
    LOGIN_PASSWORD = [
        "input[type='password']", "#pwd", "//input[@id='pwd']", "//input[@name='password']",
        "/html/body/div[1]/div[3]/div/div/div/div/div/main/div/div/div/form/div[2]/div[2]/div[2]/div[1]/input",
        ".ups-form_input.ups-has_showhide_icon"
    ]
    MY_INVOICES_LINK = [
        "#side-nav-link-my-invoices", "//a[@id='side-nav-link-my-invoices']",
        "/html/body/div[2]/div/div/div[1]/ul/li[2]/ul/a[2]",
        ".side-nav-icon-invoice.fa-custom.fa-file-alt", "a[href='/ups/billing/invoice']"
    ]
    NEXT_BUTTON = [
        ".paginate_button.next", "//a[@class='paginate_button next']",
        "/html/body/div[2]/div/main/div/div/div/div/div/div[4]/div[2]/div[3]/div[2]/div/a[2]",
        "//a[contains(@aria-label, 'Next Page')]"
    ]
    DOWNLOAD_BUTTON = [
        ".btn-download-invoices", "button[type='button']",
        "/html/body/div[2]/div/main/div/div/div/div/div/div[4]/div[2]/div[1]/div[2]/div/button[1]",
        "//button[contains(@class, 'btn-download-invoices')]"
    ]
    MODAL_CLOSE_BUTTON = [
        ".btn-primary", "button[data-test='button']",
        "/html/body/div[3]/div/div[2]/div/div/div[3]/button[1]",
        "//button[contains(text(), 'Close')]"
    ]
    DOWNLOAD_OPTION = [
        "#downloadOptionType_csv", "//input[@value='csv']",
        "/html/body/div[3]/div/div[2]/div/div/div[2]/div[2]/div[1]/div/fieldset/div[2]/div",
        ".form-check-input.form-control"
    ]
    CONFIRM_DOWNLOAD_BUTTON = [
        "#download-multiple-invoice-btn-download", "button[data-test='button']",
        "/html/body/div[3]/div/div[2]/div/div/div[3]/button[1]",
        "//button[contains(text(), 'Download')]"
    ]

async def wait_for_selector_with_retry(page: Page, selector: str, retries: int = 3, delay: float = 2.0):
    """Waits for a selector to appear, retrying if necessary."""
    for attempt in range(retries):
        try:
            await page.wait_for_selector(selector, timeout=delay * 1000)
            return True
        except PlaywrightTimeoutError:
            if attempt < retries - 1:
                log_and_print(f"Retrying... waiting for selector {selector}")
                await asyncio.sleep(delay)
            else:
                log_and_print(f"Failed to find selector {selector} after retries")
    return False

async def safe_find_and_click(page: Page, selectors, retries=3, delay=2.0):
    """Attempts to find and click an element using multiple selectors with retries."""
    for selector in selectors:
        for attempt in range(retries):
            try:
                if await wait_for_selector_with_retry(page, selector):
                    await page.click(selector)
                    log_and_print(f"Clicked element using selector: {selector}")
                    return True
            except Exception as e:
                log_and_print(f"Failed to click selector {selector} on attempt {attempt+1}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
    log_and_print("No valid selector found.")
    return False

async def click_all_checkboxes(page: Page, skip_first=False):
    """Clicks all checkboxes on the current page except the first one if skip_first is True."""
    checkboxes = page.locator("table tbody tr td input[type='checkbox']")
    count = await checkboxes.count()
    start = 1 if skip_first else 0
    for i in range(start, count):
        try:
            await checkboxes.nth(i).click()
            log_and_print(f"Clicked checkbox #{i+1}")
        except Exception as e:
            log_and_print(f"Failed to click checkbox #{i+1}: {e}")

async def download_and_validate(download, download_dir):
    """Validates the downloaded file by checking its presence and size."""
    file_path = os.path.join(download_dir, download.suggested_filename)
    await download.save_as(file_path)
    await asyncio.sleep(1)  # Ensure file write completion

    # File validation
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        log_and_print(f"Download validated: {file_path}")
        return file_path
    else:
        log_and_print(f"Download failed or file empty: {file_path}")
        return None

async def run_scraper(username: str, password: str) -> str:
    """Run the scraper using provided username and password with robust handling."""
    page_counter = 0
    download_dir = setup_download_folder()
    connection_url = f'wss://browser.zenrows.com?apikey={config.API_KEY}'

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(connection_url)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            page.on("download", lambda download: asyncio.create_task(download_and_validate(download, download_dir)))

            url = "https://www.ups.com/lasso/signin?client_id=rPfJLIzYqDE&scope=openid&response_type=code&redirect_uri=https%3A%2F%2Fbilling.ups.com%2Flogin%2Fcallback&nonce=ZUymyPQJVnxF1qqK5IasBcBl_huvcQSZ7hzD1gTo1P4&state=%2F"
            log_and_print(f"Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded")

            # Entering username
            if await wait_for_selector_with_retry(page, UPSSelectors.LOGIN_USERNAME[0]):
                await human_type(page, UPSSelectors.LOGIN_USERNAME[0], username)
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)

            # Entering password
            if await wait_for_selector_with_retry(page, UPSSelectors.LOGIN_PASSWORD[0]):
                await human_type(page, UPSSelectors.LOGIN_PASSWORD[0], password)
                await page.keyboard.press("Enter")
                await asyncio.sleep(5)

            # Navigate to My Invoices page
            if await safe_find_and_click(page, ["#main-nav-bar button", "//*[@id='main-nav-bar']/button"]):
                log_and_print("Clicked main navigation bar button.")
            if await safe_find_and_click(page, UPSSelectors.MY_INVOICES_LINK):
                log_and_print("Navigated to My Invoices page.")

            # Clicking the first checkbox
            checkbox_selector = "//*[@id='invoice-table_wrapper']/div[2]/div/table/tbody/tr[1]/td[2]"
            if await safe_find_and_click(page, [checkbox_selector]):
                log_and_print("Clicked on the first invoice checkbox.")
                screenshot_path = "after_first_checkbox_click.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                log_and_print(f"Screenshot saved to {screenshot_path}")

            # Close modal if appears
            await safe_find_and_click(page, UPSSelectors.MODAL_CLOSE_BUTTON)

            # Loop through each page and select checkboxes
            is_first_page = True
            while page_counter < config.MAX_PAGES:
                log_and_print(f"Processing page {page_counter + 1}.")
                
                await click_all_checkboxes(page, skip_first=is_first_page)
                is_first_page = False
                page_counter += 1

                # Move to next page
                if not await safe_find_and_click(page, UPSSelectors.NEXT_BUTTON):
                    log_and_print("No 'Next' button found. Reached the last page or limit.")
                    break
                
                await asyncio.sleep(random.uniform(1, 3))

            # Click download button and select download options
            if await safe_find_and_click(page, UPSSelectors.DOWNLOAD_BUTTON):
                log_and_print("Clicked download button.")
                
                await safe_find_and_click(page, UPSSelectors.DOWNLOAD_OPTION)
                await safe_find_and_click(page, UPSSelectors.CONFIRM_DOWNLOAD_BUTTON)

            final_screenshot_path = "final_state.png"
            await page.screenshot(path=final_screenshot_path, full_page=True)
            log_and_print(f"Final screenshot saved to {final_screenshot_path}")

        except PlaywrightTimeoutError as e:
            log_and_print(f"Timeout occurred: {e}")
        except Exception as e:
            log_and_print(f"An error occurred: {e}")
        finally:
            log_and_print("Closing the browser.")
            await browser.close()

    return download_dir
