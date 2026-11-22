import os
import signal
import sys
import time
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright


def parse_bool(value: str, default: bool = False) -> bool:
    """Parse a string environment variable into a boolean."""
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_restart_hours(value: str, default: float = 4.0) -> float:
    """Parse the restart interval in hours, falling back to default if invalid."""
    if not value:
        return default
    try:
        hours = float(value.strip())
        if hours > 0:
            return hours
    except ValueError:
        pass
    print(f"WARNING: Invalid RESTART_INTERVAL_HOURS '{value}', falling back to {default} hours.")
    return default


def mask_email(email: str) -> str:
    """Mask the local part of an email address for safer log output."""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


# Read configuration from environment variables
EMAIL = os.environ.get("ECOFLOW_EMAIL", "").strip()
PASSWORD = os.environ.get("ECOFLOW_PASSWORD", "")
REGION = os.environ.get("ECOFLOW_REGION", "eu").strip().strip("/").lower() or "eu"
COUNTRY = os.environ.get("ECOFLOW_COUNTRY", "").strip()
RESTART_INTERVAL_HOURS = parse_restart_hours(os.environ.get("RESTART_INTERVAL_HOURS", "4"))
DEBUG_SCREENSHOTS = parse_bool(os.environ.get("DEBUG_SCREENSHOTS", "false"))
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", "/app/output").strip() or "/app/output"
USER_AGENT = os.environ.get("ECOFLOW_USER_AGENT", "").strip()

shutdown_requested = False


def handle_shutdown(signum, _frame) -> None:
    """Handle SIGTERM/SIGINT so Docker stops the container promptly."""
    global shutdown_requested
    if not shutdown_requested:
        print(f"Shutdown signal ({signum}) received. Exiting cleanly...")
    shutdown_requested = True


def sleep_with_shutdown(seconds: int) -> None:
    """Sleep for the requested seconds while honoring shutdown signals."""
    for _ in range(seconds):
        if shutdown_requested:
            return
        time.sleep(1)


def save_screenshot(page, filename: str) -> None:
    """Save a debug screenshot to SCREENSHOT_DIR when DEBUG_SCREENSHOTS is enabled."""
    if not DEBUG_SCREENSHOTS:
        return
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(SCREENSHOT_DIR, filename)
        page.screenshot(path=path)
        print(f"Debug screenshot saved: {path}")
    except Exception as exc:
        print(f"WARNING: Could not save debug screenshot '{filename}': {exc}")


def keep_ecoflow_alive() -> None:
    """Log into the EcoFlow user portal and keep the dashboard open to sustain MQTT telemetry."""
    if not EMAIL or not PASSWORD:
        print("ERROR: ECOFLOW_EMAIL and/or ECOFLOW_PASSWORD environment variables are missing.")
        sleep_with_shutdown(60)
        sys.exit(0 if shutdown_requested else 1)

    print(
        f"Starting EcoFlow Keep-Alive for {mask_email(EMAIL)} "
        f"(region={REGION}, restart_interval={RESTART_INTERVAL_HOURS:g}h)"
    )

    try:
        with sync_playwright() as p:
            print("Launching headless Chromium browser...")
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-sandbox",
                ],
            )
            user_agent = USER_AGENT or (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{browser.version} Safari/537.36"
            )
            context = browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            crashed = False

            def handle_crash(*_) -> None:
                nonlocal crashed
                crashed = True
                print("WARNING: Browser page crashed!")

            # Log browser console messages, page errors, and crashes for easier debugging
            page.on("crash", handle_crash)
            page.on("console", lambda msg: print(f"[BROWSER CONSOLE][{msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: print(f"[BROWSER PAGE ERROR] {err}"))

            # Inject CSS to disable all animations and transitions to minimize CPU usage
            def disable_animations(*_) -> None:
                try:
                    page.add_style_tag(
                        content="""
                        *, *::before, *::after {
                            animation-delay: -1s !important;
                            animation-duration: 1ms !important;
                            animation-iteration-count: 1 !important;
                            transition-duration: 0s !important;
                            transition: none !important;
                            scroll-behavior: auto !important;
                        }
                    """
                    )
                    print("Disabled CSS animations to reduce CPU usage.")
                except Exception as exc:
                    print(f"WARNING: Could not disable CSS animations: {exc}")

            # Ensure animations are disabled immediately when the DOM finishes loading
            page.on("domcontentloaded", disable_animations)

            login_url = f"https://user-portal.ecoflow.com/user/{REGION}/en/login"
            print(f"Opening EcoFlow login page ({login_url})...")
            page.goto(login_url, timeout=30000)

            page.wait_for_selector('input[type="text"]', timeout=15000)
            page.wait_for_timeout(2000)

            # Optionally select the configured country if it differs from the default selection
            if COUNTRY:
                try:
                    country_dropdown = page.locator(".ant-select-selection-item").first
                    if country_dropdown.is_visible() and COUNTRY.lower() not in country_dropdown.inner_text().lower():
                        print(f"Selecting country: {COUNTRY}...")
                        country_dropdown.click()
                        page.wait_for_timeout(500)
                        page.locator(".ant-select-selection-search-input, #rc_select_0").first.fill(COUNTRY)
                        page.wait_for_timeout(500)
                        safe_country = COUNTRY.replace('"', '\\"')
                        page.locator(f'div.ant-select-item-option[title="{safe_country}"]').first.click()
                        page.wait_for_timeout(1000)
                except Exception as exc:
                    print(f"WARNING: Could not select country '{COUNTRY}': {exc}")

            # Fill in login credentials
            page.locator("#normal_login_email").click()
            page.locator("#normal_login_email").press_sequentially(EMAIL, delay=100)
            page.locator("#normal_login_password").click()
            page.locator("#normal_login_password").press_sequentially(PASSWORD, delay=100)

            # Check the 'I agree' checkbox using a native click on the input (React best practice)
            checkbox = page.locator('input[type="checkbox"]')
            if checkbox.count() > 0:
                print("Accepting terms checkbox...")
                checkbox.first.click(force=True)
                page.wait_for_timeout(1000)

            # Take an optional pre-click screenshot to verify the login button state
            save_screenshot(page, "screenshot_before_click.png")

            # Click 'Log in'
            print("Submitting login form...")
            page.locator('button[type="submit"]').click(force=True)

            print("Waiting for dashboard navigation...")
            try:
                page.wait_for_url(lambda url: "login" not in url, timeout=15000)
            except PlaywrightTimeoutError:
                pass

            # Verify login succeeded (URL should have changed and no longer contain /login)
            if "login" in page.url:
                print("ERROR: Login failed; still on the login page.")
                save_screenshot(page, "screenshot_failed.png")
                raise RuntimeError(
                    "Login failed: still on the login page. Check credentials, ECOFLOW_REGION, or ECOFLOW_COUNTRY."
                )

            # Give dashboard widgets and MQTT connections a moment to initialize
            page.wait_for_timeout(3000)
            save_screenshot(page, "screenshot.png")
            print("Login successful! Dashboard is open and active.")

            # Keep the page open for the configured interval while checking for crashes or shutdown signals
            total_seconds = max(60, int(RESTART_INTERVAL_HOURS * 3600))
            deadline = time.monotonic() + total_seconds
            print(f"Dashboard is connected and active. Keeping session alive for {RESTART_INTERVAL_HOURS:g} hour(s)...")

            while time.monotonic() < deadline:
                if shutdown_requested:
                    print("Shutdown requested. Closing browser cleanly...")
                    break
                if crashed or page.is_closed():
                    raise RuntimeError("Browser page crashed or closed unexpectedly.")
                remaining_ms = max(500, int((deadline - time.monotonic()) * 1000))
                page.wait_for_timeout(min(5000, remaining_ms))

            # Exit the script so Docker automatically restarts the container cleanly
            if not shutdown_requested:
                print("Restart interval elapsed. Exiting to trigger a clean container restart...")

    except Exception as exc:
        if shutdown_requested:
            print("Shutdown requested during execution. Exiting cleanly...")
            sys.exit(0)
        print(f"Error occurred: {exc}")
        print("Restarting in 60 seconds...")
        sleep_with_shutdown(60)
        sys.exit(0 if shutdown_requested else 1)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    keep_ecoflow_alive()
