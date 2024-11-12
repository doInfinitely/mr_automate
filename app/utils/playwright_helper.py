from playwright.sync_api import sync_playwright
import random
import time

def human_type(page, selector, text):
    for char in text:
        page.type(selector, char, delay=random.randint(100, 200))
        time.sleep(random.uniform(0.05, 0.15))

def safe_wait_for_selector(page, selector, timeout=30000, retries=3):
    for attempt in range(retries):
        try:
            page.wait_for_selector(selector, timeout=timeout)
            return True
        except TimeoutError:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return False

def safe_click(page, selector, retries=3):
    for attempt in range(retries):
        try:
            page.click(selector)
            return True
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return False
