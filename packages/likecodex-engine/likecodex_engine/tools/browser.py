"""Browser automation tools for the agent.

Provides web page opening, screenshot capture, element clicking, form filling,
structured data extraction, and console log capture.

All tools use the browser__ prefix to avoid naming conflicts.
Playwright is the primary backend; selenium/selenium-wire serves as fallback.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import tempfile
import time
from typing import Any

# ---------------------------------------------------------------------------
# Tool registry for conditional registration
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {}


def tool(
    name: str,
    description: str,
    read_only: bool = True,
    parameters: dict | None = None,
) -> Any:
    """Decorator to register a browser tool."""

    def decorator(func: Any) -> Any:
        TOOL_DEFINITIONS[name] = {
            "name": name,
            "description": description,
            "read_only": read_only,
            "handler": func,
            "parameters": parameters or {"type": "object", "properties": {}},
        }
        return func

    return decorator


# ---------------------------------------------------------------------------
# User-Agent rotation
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    # Chrome 120+ on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox 121 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Edge 120 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


def _random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------


async def _launch_playwright(headless: bool = True) -> tuple[Any, Any, bool]:
    """Launch a Playwright browser. Returns (browser, context, success_flag)."""
    try:
        from playwright.async_api import async_playwright

        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=_random_user_agent(),
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        return browser, context, True
    except ImportError:
        return None, None, False
    except Exception as exc:
        return None, None, False


async def _launch_playwright_with_url(
    url: str,
    wait_selector: str | None = None,
    timeout: int = 30000,
    headless: bool = True,
    width: int = 1280,
    height: int = 720,
) -> str:
    """Open a URL with Playwright and return structured result as JSON string."""
    try:
        from playwright.async_api import async_playwright, TimeoutError as PwTimeout
    except ImportError:
        return json.dumps({"error": "Playwright is not installed. Run `pip install playwright` and `playwright install`."})

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                user_agent=_random_user_agent(),
                viewport={"width": width, "height": height},
                ignore_https_errors=True,
            )
            page = await context.new_page()

            try:
                await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            except PwTimeout:
                pass
            except Exception as exc:
                await browser.close()
                return json.dumps({"error": f"Failed to navigate to URL: {exc}"})

            # Wait for optional selector
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=min(timeout, 10000))
                except (PwTimeout, Exception):
                    pass

            # Small extra wait for dynamic content
            await asyncio.sleep(0.5)

            # Save screenshot
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            screenshot_path = tmp.name
            tmp.close()
            try:
                await page.screenshot(path=screenshot_path, full_page=False)
            except Exception:
                screenshot_path = ""

            # Gather page data
            title = await page.title()
            current_url = page.url
            try:
                text_content = await page.evaluate("() => document.body?.innerText || ''")
                text_content = text_content.strip()[:50000]  # limit to 50k chars
            except Exception:
                text_content = ""

            result: dict[str, Any] = {
                "title": title,
                "url": current_url,
                "content_length": len(text_content),
                "content_preview": text_content[:2000],
            }

            if screenshot_path and os.path.isfile(screenshot_path):
                result["screenshot_path"] = os.path.abspath(screenshot_path)
                result["screenshot_size_bytes"] = os.path.getsize(screenshot_path)

            await browser.close()
            return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"error": f"Playwright error: {exc}"})


async def _selenium_open(
    url: str,
    timeout: int = 30000,
    width: int = 1280,
    height: int = 720,
) -> str:
    """Fallback: open URL with selenium."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        return json.dumps(
            {"error": "Selenium is not installed. Run `pip install selenium selenium-wire`."}
        )

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument(f"user-agent={_random_user_agent()}")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:
        return json.dumps({"error": f"Failed to start Chrome driver: {exc}"})

    try:
        driver.set_page_load_timeout(timeout / 1000)
        driver.get(url)

        # Save screenshot
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        screenshot_path = tmp.name
        tmp.close()
        try:
            driver.save_screenshot(screenshot_path)
        except Exception:
            screenshot_path = ""

        title = driver.title
        current_url = driver.current_url
        try:
            text_content = driver.find_element("tag name", "body").text[:50000]
        except Exception:
            text_content = ""

        result: dict[str, Any] = {
            "title": title,
            "url": current_url,
            "content_length": len(text_content),
            "content_preview": text_content[:2000],
        }

        if screenshot_path and os.path.isfile(screenshot_path):
            result["screenshot_path"] = os.path.abspath(screenshot_path)
            result["screenshot_size_bytes"] = os.path.getsize(screenshot_path)

        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"error": f"Selenium error: {exc}"})
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ===================================================================
# 1. browser__open — 打开URL并返回页面内容
# ===================================================================


@tool(
    name="browser__open",
    description=(
        "Open a URL in a headless browser and return the page title, URL, text content, "
        "and a screenshot. Supports optional CSS selector to wait for specific elements. "
        "Uses Playwright (primary) or Selenium (fallback)."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to open",
            },
            "wait_selector": {
                "type": "string",
                "description": "Optional CSS selector to wait for before returning",
            },
            "timeout": {
                "type": "integer",
                "description": "Page load timeout in milliseconds",
                "default": 30000,
            },
        },
        "required": ["url"],
    },
)
async def browser__open(
    url: str,
    wait_selector: str | None = None,
    timeout: int = 30000,
) -> str:
    """Open a URL and return page content with screenshot."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Try Playwright first
    result = await _launch_playwright_with_url(url, wait_selector, timeout)
    parsed = json.loads(result)
    if "error" not in parsed:
        return result

    # Fallback to Selenium
    return await _selenium_open(url, timeout)


# ===================================================================
# 2. browser__screenshot — 浏览器截图
# ===================================================================


@tool(
    name="browser__screenshot",
    description=(
        "Open a URL in a headless browser and capture a screenshot. "
        "Supports full-page capture and configurable viewport size."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to screenshot",
            },
            "full_page": {
                "type": "boolean",
                "description": "Whether to capture the full scrollable page",
                "default": False,
            },
            "width": {
                "type": "integer",
                "description": "Viewport width in pixels",
                "default": 1280,
            },
            "height": {
                "type": "integer",
                "description": "Viewport height in pixels",
                "default": 720,
            },
        },
        "required": ["url"],
    },
)
async def browser__screenshot(
    url: str,
    full_page: bool = False,
    width: int = 1280,
    height: int = 720,
) -> str:
    """Open a URL and capture a screenshot."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Try Playwright first
    try:
        from playwright.async_api import async_playwright, TimeoutError as PwTimeout
    except ImportError:
        pass
    else:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=_random_user_agent(),
                    viewport={"width": width, "height": height},
                    ignore_https_errors=True,
                )
                page = await context.new_page()
                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                except PwTimeout:
                    pass
                except Exception as exc:
                    await browser.close()
                    return json.dumps({"error": f"Failed to navigate: {exc}"})

                await asyncio.sleep(1)

                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                screenshot_path = tmp.name
                tmp.close()
                await page.screenshot(path=screenshot_path, full_page=full_page)

                page_title = await page.title()
                await browser.close()

                return json.dumps(
                    {
                        "file_path": os.path.abspath(screenshot_path),
                        "file_size_bytes": os.path.getsize(screenshot_path),
                        "format": "PNG",
                        "title": page_title,
                        "url": url,
                        "full_page": full_page,
                        "viewport": {"width": width, "height": height},
                    },
                    ensure_ascii=False,
                )
        except Exception as exc:
            return json.dumps({"error": f"Playwright screenshot error: {exc}"})

    # Fallback: Selenium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        return json.dumps(
            {
                "error": (
                    "Playwright and Selenium are both unavailable. "
                    "Run `pip install playwright selenium` and `playwright install`."
                )
            }
        )

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument(f"user-agent={_random_user_agent()}")
    options.add_argument("--ignore-certificate-errors")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:
        return json.dumps({"error": f"Failed to start Chrome driver: {exc}"})

    try:
        driver.set_page_load_timeout(30)
        driver.get(url)

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        screenshot_path = tmp.name
        tmp.close()

        if full_page:
            # Try to capture full page with selenium
            original_height = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(width, original_height)
            driver.save_screenshot(screenshot_path)
            driver.set_window_size(width, height)
        else:
            driver.save_screenshot(screenshot_path)

        result = {
            "file_path": os.path.abspath(screenshot_path),
            "file_size_bytes": os.path.getsize(screenshot_path),
            "format": "PNG",
            "title": driver.title,
            "url": url,
            "full_page": full_page,
            "viewport": {"width": width, "height": height},
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"Selenium screenshot error: {exc}"})
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ===================================================================
# 3. browser__click — 点击页面元素
# ===================================================================


@tool(
    name="browser__click",
    description=(
        "Open a URL, click on a page element identified by CSS selector, "
        "wait for navigation/updates, and return the resulting page state."
    ),
    read_only=False,
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to open",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector of the element to click",
            },
            "wait_after": {
                "type": "integer",
                "description": "Milliseconds to wait after clicking",
                "default": 1000,
            },
        },
        "required": ["url", "selector"],
    },
)
async def browser__click(
    url: str,
    selector: str,
    wait_after: int = 1000,
) -> str:
    """Open a URL, click an element, and return the resulting page state."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Try Playwright first
    try:
        from playwright.async_api import async_playwright, TimeoutError as PwTimeout
    except ImportError:
        pass
    else:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    user_agent=_random_user_agent(),
                    viewport={"width": 1280, "height": 720},
                    ignore_https_errors=True,
                )
                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                except PwTimeout:
                    pass
                except Exception as exc:
                    await browser.close()
                    return json.dumps({"error": f"Failed to navigate: {exc}"})

                # Wait for selector to be visible
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    await page.click(selector)
                except Exception as exc:
                    await browser.close()
                    return json.dumps({"error": f"Failed to click '{selector}': {exc}"})

                # Wait for any resulting navigation/updates
                if wait_after > 0:
                    await asyncio.sleep(wait_after / 1000)

                # Save screenshot
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                screenshot_path = tmp.name
                tmp.close()
                try:
                    await page.screenshot(path=screenshot_path, full_page=False)
                except Exception:
                    screenshot_path = ""

                title = await page.title()
                current_url = page.url
                try:
                    text_content = await page.evaluate("() => document.body?.innerText || ''")
                    text_content = text_content.strip()[:20000]
                except Exception:
                    text_content = ""

                result: dict[str, Any] = {
                    "title": title,
                    "url": current_url,
                    "content_length": len(text_content),
                    "content_preview": text_content[:2000],
                    "clicked_selector": selector,
                }
                if screenshot_path and os.path.isfile(screenshot_path):
                    result["screenshot_path"] = os.path.abspath(screenshot_path)

                await browser.close()
                return json.dumps(result, ensure_ascii=False)

        except Exception as exc:
            return json.dumps({"error": f"Playwright click error: {exc}"})

    # Fallback: Selenium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        return json.dumps(
            {
                "error": (
                    "Playwright and Selenium are both unavailable. "
                    "Run `pip install playwright selenium`."
                )
            }
        )

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"user-agent={_random_user_agent()}")
    options.add_argument("--ignore-certificate-errors")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:
        return json.dumps({"error": f"Failed to start Chrome driver: {exc}"})

    try:
        driver.set_page_load_timeout(30)
        driver.get(url)

        try:
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.click()
        except Exception as exc:
            return json.dumps({"error": f"Failed to click '{selector}': {exc}"})

        if wait_after > 0:
            time.sleep(wait_after / 1000)

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        screenshot_path = tmp.name
        tmp.close()
        try:
            driver.save_screenshot(screenshot_path)
        except Exception:
            screenshot_path = ""

        result = {
            "title": driver.title,
            "url": driver.current_url,
            "content_preview": (
                driver.find_element("tag name", "body").text[:2000]
                if driver.find_elements("tag name", "body")
                else ""
            ),
            "clicked_selector": selector,
        }
        if screenshot_path and os.path.isfile(screenshot_path):
            result["screenshot_path"] = os.path.abspath(screenshot_path)

        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"error": f"Selenium click error: {exc}"})
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ===================================================================
# 4. browser__fill — 填写表单
# ===================================================================


@tool(
    name="browser__fill",
    description=(
        "Open a URL and fill a text input/textarea identified by CSS selector "
        "with the specified value. Returns the resulting page state."
    ),
    read_only=False,
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to open",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector of the input element",
            },
            "value": {
                "type": "string",
                "description": "Text value to fill into the input",
            },
        },
        "required": ["url", "selector", "value"],
    },
)
async def browser__fill(
    url: str,
    selector: str,
    value: str,
) -> str:
    """Open a URL and fill a form field with the specified value."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Try Playwright first
    try:
        from playwright.async_api import async_playwright, TimeoutError as PwTimeout
    except ImportError:
        pass
    else:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    user_agent=_random_user_agent(),
                    viewport={"width": 1280, "height": 720},
                    ignore_https_errors=True,
                )
                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                except PwTimeout:
                    pass
                except Exception as exc:
                    await browser.close()
                    return json.dumps({"error": f"Failed to navigate: {exc}"})

                # Wait for selector
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    await page.fill(selector, value)
                except Exception as exc:
                    await browser.close()
                    return json.dumps({"error": f"Failed to fill '{selector}': {exc}"})

                await asyncio.sleep(0.5)

                # Save screenshot
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                screenshot_path = tmp.name
                tmp.close()
                try:
                    await page.screenshot(path=screenshot_path, full_page=False)
                except Exception:
                    screenshot_path = ""

                result: dict[str, Any] = {
                    "title": await page.title(),
                    "url": page.url,
                    "filled_selector": selector,
                    "filled_value_length": len(value),
                }
                if screenshot_path and os.path.isfile(screenshot_path):
                    result["screenshot_path"] = os.path.abspath(screenshot_path)

                await browser.close()
                return json.dumps(result, ensure_ascii=False)

        except Exception as exc:
            return json.dumps({"error": f"Playwright fill error: {exc}"})

    # Fallback: Selenium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        return json.dumps(
            {
                "error": (
                    "Playwright and Selenium are both unavailable. "
                    "Run `pip install playwright selenium`."
                )
            }
        )

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"user-agent={_random_user_agent()}")
    options.add_argument("--ignore-certificate-errors")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:
        return json.dumps({"error": f"Failed to start Chrome driver: {exc}"})

    try:
        driver.set_page_load_timeout(30)
        driver.get(url)

        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            element.clear()
            element.send_keys(value)
        except Exception as exc:
            return json.dumps({"error": f"Failed to fill '{selector}': {exc}"})

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        screenshot_path = tmp.name
        tmp.close()
        try:
            driver.save_screenshot(screenshot_path)
        except Exception:
            screenshot_path = ""

        result = {
            "title": driver.title,
            "url": driver.current_url,
            "filled_selector": selector,
            "filled_value_length": len(value),
        }
        if screenshot_path and os.path.isfile(screenshot_path):
            result["screenshot_path"] = os.path.abspath(screenshot_path)

        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"Selenium fill error: {exc}"})
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ===================================================================
# 5. browser__extract — 提取页面结构化数据
# ===================================================================


@tool(
    name="browser__extract",
    description=(
        "Open a URL and extract structured data from the page: "
        "links (href + text), images (src + alt), and/or full text content. "
        "Returns the data as structured JSON."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to extract data from",
            },
            "extract_links": {
                "type": "boolean",
                "description": "Whether to extract all links from the page",
                "default": True,
            },
            "extract_images": {
                "type": "boolean",
                "description": "Whether to extract all image sources from the page",
                "default": False,
            },
            "extract_text": {
                "type": "boolean",
                "description": "Whether to extract text content from the page",
                "default": True,
            },
        },
        "required": ["url"],
    },
)
async def browser__extract(
    url: str,
    extract_links: bool = True,
    extract_images: bool = False,
    extract_text: bool = True,
) -> str:
    """Open a URL and extract structured data (links, images, text)."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Try Playwright first
    try:
        from playwright.async_api import async_playwright, TimeoutError as PwTimeout
    except ImportError:
        pass
    else:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    user_agent=_random_user_agent(),
                    viewport={"width": 1280, "height": 720},
                    ignore_https_errors=True,
                )
                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                except PwTimeout:
                    pass
                except Exception as exc:
                    await browser.close()
                    return json.dumps({"error": f"Failed to navigate: {exc}"})

                await asyncio.sleep(0.5)

                result: dict[str, Any] = {
                    "title": await page.title(),
                    "url": page.url,
                }

                if extract_links:
                    try:
                        links = await page.evaluate(
                            """() => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                                href: a.href,
                                text: (a.innerText || a.textContent || '').trim().substring(0, 200),
                            })).filter(l => l.href && !l.href.startsWith('javascript:'))"""
                        )
                        result["links"] = links[:500]
                        result["total_links"] = len(links)
                    except Exception as exc:
                        result["links_error"] = str(exc)

                if extract_images:
                    try:
                        images = await page.evaluate(
                            """() => Array.from(document.querySelectorAll('img[src]')).map(img => ({
                                src: img.src,
                                alt: (img.alt || '').substring(0, 200),
                                width: img.naturalWidth || img.width,
                                height: img.naturalHeight || img.height,
                            })).filter(i => i.src && !i.src.startsWith('data:'))"""
                        )
                        result["images"] = images[:200]
                        result["total_images"] = len(images)
                    except Exception as exc:
                        result["images_error"] = str(exc)

                if extract_text:
                    try:
                        text = await page.evaluate("() => document.body?.innerText || ''")
                        text = text.strip()[:100000]
                        result["text_length"] = len(text)
                        result["text_preview"] = text[:3000]
                    except Exception as exc:
                        result["text_error"] = str(exc)

                await browser.close()
                return json.dumps(result, ensure_ascii=False)

        except Exception as exc:
            return json.dumps({"error": f"Playwright extract error: {exc}"})

    # Fallback: Selenium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
    except ImportError:
        return json.dumps(
            {
                "error": (
                    "Playwright and Selenium are both unavailable. "
                    "Run `pip install playwright selenium`."
                )
            }
        )

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"user-agent={_random_user_agent()}")
    options.add_argument("--ignore-certificate-errors")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:
        return json.dumps({"error": f"Failed to start Chrome driver: {exc}"})

    try:
        driver.set_page_load_timeout(30)
        driver.get(url)

        result: dict[str, Any] = {
            "title": driver.title,
            "url": driver.current_url,
        }

        if extract_links:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, "a[href]")
                links = []
                for el in elements[:500]:
                    try:
                        href = el.get_attribute("href")
                        text = (el.text or "").strip()[:200]
                        if href and not href.startswith("javascript:"):
                            links.append({"href": href, "text": text})
                    except Exception:
                        pass
                result["links"] = links
                result["total_links"] = len(links)
            except Exception as exc:
                result["links_error"] = str(exc)

        if extract_images:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, "img[src]")
                images = []
                for el in elements[:200]:
                    try:
                        src = el.get_attribute("src")
                        alt = (el.get_attribute("alt") or "")[:200]
                        if src and not src.startswith("data:"):
                            images.append({"src": src, "alt": alt})
                    except Exception:
                        pass
                result["images"] = images
                result["total_images"] = len(images)
            except Exception as exc:
                result["images_error"] = str(exc)

        if extract_text:
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                text = (body.text or "")[:100000]
                result["text_length"] = len(text)
                result["text_preview"] = text[:3000]
            except Exception as exc:
                result["text_error"] = str(exc)

        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"Selenium extract error: {exc}"})
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ===================================================================
# 6. browser__console — 获取浏览器控制台日志
# ===================================================================


@tool(
    name="browser__console",
    description=(
        "Open a URL in a headless browser and capture JavaScript console logs "
        "(log, warn, error, info) for a specified duration. "
        "Useful for debugging SPA/JS-heavy pages, detecting errors, and "
        "inspecting client-side behavior."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to open and capture console logs from",
            },
            "duration_ms": {
                "type": "integer",
                "description": "Duration in milliseconds to capture console logs",
                "default": 5000,
            },
        },
        "required": ["url"],
    },
)
async def browser__console(
    url: str,
    duration_ms: int = 5000,
) -> str:
    """Open a URL and capture browser console logs."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Playwright is required for console capture (selenium doesn't have easy console API)
    try:
        from playwright.async_api import async_playwright, TimeoutError as PwTimeout
    except ImportError:
        return json.dumps(
            {
                "error": (
                    "Playwright is required for console log capture. "
                    "Run `pip install playwright` and `playwright install`."
                )
            }
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent=_random_user_agent(),
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )

            console_logs: list[dict[str, Any]] = []

            def _on_console(msg: Any) -> None:
                try:
                    entry = {
                        "type": msg.type,
                        "text": msg.text[:2000],
                        "location": str(msg.location)[:500] if hasattr(msg, "location") else "",
                    }
                    console_logs.append(entry)
                except Exception:
                    pass

            page.on("console", _on_console)

            try:
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            except PwTimeout:
                pass
            except Exception as exc:
                await browser.close()
                return json.dumps({"error": f"Failed to navigate: {exc}"})

            # Wait for specified duration to capture console logs
            await asyncio.sleep(duration_ms / 1000)

            # Save screenshot
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            screenshot_path = tmp.name
            tmp.close()
            try:
                await page.screenshot(path=screenshot_path, full_page=False)
            except Exception:
                screenshot_path = ""

            # Categorize logs
            log_entries = [e for e in console_logs if e["type"] == "log"]
            warn_entries = [e for e in console_logs if e["type"] == "warning"]
            error_entries = [e for e in console_logs if e["type"] == "error"]
            info_entries = [e for e in console_logs if e["type"] == "info"]
            other_entries = [
                e for e in console_logs if e["type"] not in ("log", "warning", "error", "info")
            ]

            result: dict[str, Any] = {
                "title": await page.title(),
                "url": page.url,
                "total_entries": len(console_logs),
                "summary": {
                    "log": len(log_entries),
                    "warn": len(warn_entries),
                    "error": len(error_entries),
                    "info": len(info_entries),
                    "other": len(other_entries),
                },
                "entries": console_logs[:200],
            }

            if screenshot_path and os.path.isfile(screenshot_path):
                result["screenshot_path"] = os.path.abspath(screenshot_path)

            await browser.close()
            return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"error": f"Console capture error: {exc}"})
