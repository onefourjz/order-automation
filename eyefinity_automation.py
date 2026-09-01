"""
Eyefinity Browser Automation Module using Playwright (async)
Automates login and order/claim form population on Eyefinity.
Uses a persistent event loop thread so browser objects can be
accessed from any thread (Flask routes, background threads, etc.)
"""

import time
import yaml
import os
import asyncio
import threading
from typing import Dict, Optional


class EyefinityAutomation:
    """Automates ordering on the Eyefinity website using Playwright async API."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._playwright = None
        self.browser = None
        self.page = None
        self.logged_in = False

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        config_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(config_dir, config_path)
        try:
            with open(full_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            full_path = os.path.join(os.getcwd(), config_path)
            with open(full_path, 'r') as f:
                return yaml.safe_load(f)

    def _ensure_loop(self):
        """Ensure a persistent event loop is running in a background thread."""
        if self._loop and self._loop.is_running():
            return

        self._loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

    def _run(self, coro):
        """Run a coroutine on the persistent event loop and wait for the result."""
        self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=120)

    async def _start_browser_async(self):
        """Async: initialize and start the Chromium browser."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        headless = self.config.get("browser", {}).get("headless", False)
        self.browser = await self._playwright.chromium.launch(headless=headless)
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(20000)
        print("Browser started.")

    def start_browser(self):
        """Initialize and start the Chromium browser."""
        self._run(self._start_browser_async())

    async def _login_async(self) -> bool:
        """Async: log in to Eyefinity."""
        try:
            eyefinity_config = self.config.get("eyefinity", {})
            url = eyefinity_config.get("url", "https://www.eyefinity.com")
            username = eyefinity_config.get("username", "")
            password = eyefinity_config.get("password", "")

            print(f"Navigating to {url[:60]}...")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(5000)

            # If we're on the portal login page, click the OAuth2 link to get a fresh SSO URL
            # The portal page shows "Login with OAuth 2.0" with a link to /secure-welcome/oauth2/authorization/vspglobal
            oauth_link = self.page.locator("a[href*='oauth2/authorization']").first
            try:
                if await oauth_link.wait_for(state="visible", timeout=5000):
                    print("Found OAuth2 login link - clicking to get fresh SSO URL...")
                    await oauth_link.click()
                    await self.page.wait_for_timeout(8000)
                    print(f"Redirected to: {self.page.url[:60]}...")
            except Exception:
                pass

            # Find username field
            username_selectors = [
                "#username",
                "input[name='pf.username']",
                "input[name='username']",
                "#email",
                "input[name='email']",
                "input[type='email']",
                "input[placeholder*='Username' i]",
            ]
            username_locator = None
            for selector in username_selectors:
                locator = self.page.locator(selector).first
                try:
                    if await locator.wait_for(state="visible", timeout=5000):
                        username_locator = locator
                        break
                except Exception:
                    continue

            if not username_locator:
                print("Could not find username field. Page may have loaded differently.")
                await self.page.screenshot(path="login_debug.png")
                # Give user 60 seconds to log in manually
                print("Please log in manually in the browser window...")
                await self.page.wait_for_timeout(60000)
                if await self._check_login_success_async():
                    self.logged_in = True
                    print("Successfully logged in to Eyefinity (manual)!")
                    return True
                return False

            await username_locator.fill(username)
            await self.page.wait_for_timeout(500)

            # Find password field
            password_selectors = [
                "#password",
                "input[name='pf.pass']",
                "input[name='password']",
                "input[type='password']",
                "input[placeholder*='Password' i]",
            ]
            password_locator = None
            for selector in password_selectors:
                locator = self.page.locator(selector).first
                try:
                    if await locator.wait_for(state="visible", timeout=5000):
                        password_locator = locator
                        break
                except Exception:
                    continue

            if not password_locator:
                print("Could not find password field.")
                return False

            await password_locator.fill(password)
            await self.page.wait_for_timeout(500)

            # Submit login - try button first, then Enter key
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Sign In')",
                "button:has-text('Log In')",
                "button:has-text('Login')",
            ]
            submitted = False
            for selector in submit_selectors:
                locator = self.page.locator(selector).first
                try:
                    if await locator.wait_for(state="visible", timeout=3000):
                        await locator.click()
                        submitted = True
                        break
                except Exception:
                    continue
            if not submitted:
                await password_locator.press("Enter")
            await self.page.wait_for_timeout(5000)

            # Check login success
            if await self._check_login_success_async():
                self.logged_in = True
                print("Successfully logged in to Eyefinity!")
                return True

            # Check for login error messages
            error_selectors = [
                "div.error",
                "span.error",
                "p:has-text('Invalid')",
                "p:has-text('incorrect')",
            ]
            for selector in error_selectors:
                try:
                    error_elem = self.page.locator(selector).first
                    if await error_elem.wait_for(state="visible", timeout=3000):
                        text = await error_elem.inner_text()
                        print(f"Login error: {text}")
                        return False
                except Exception:
                    continue

            print("Login status uncertain - page may have changed.")
            await self.page.screenshot(path="login_status.png")
            return False

        except Exception as e:
            print(f"Error during login: {e}")
            try:
                await self.page.screenshot(path="login_error.png")
            except Exception:
                pass
            return False

    def login(self) -> bool:
        """Log in to Eyefinity."""
        if not self.browser or not self.page:
            self.start_browser()
        return self._run(self._login_async())

    async def _check_login_success_async(self) -> bool:
        """Async: check if login was successful."""
        success_selectors = [
            "a:has-text('Dashboard')",
            "a:has-text('Order')",
            "a:has-text('Orders')",
            "a:has-text('Logout')",
            "a:has-text('Sign Out')",
            "div.dashboard",
        ]
        for selector in success_selectors:
            try:
                locator = self.page.locator(selector).first
                if await locator.wait_for(state="visible", timeout=5000):
                    return True
            except Exception:
                continue
        return False

    def _check_login_success(self) -> bool:
        """Check if login was successful (sync wrapper)."""
        return self._run(self._check_login_success_async())

    async def _navigate_to_order_form_async(self) -> bool:
        """Async: navigate to the order/claim form."""
        if not self.logged_in:
            print("Not logged in. Please login first.")
            return False

        try:
            order_links = [
                "a:has-text('Order Entry')",
                "a:has-text('New Order')",
                "a:has-text('Place Order')",
                "a:has-text('Spectacle Order')",
                "a:has-text('Order')",
                "a[href*='order' i]",
                "button:has-text('Order')",
            ]

            for selector in order_links:
                try:
                    locator = self.page.locator(selector).first
                    if await locator.wait_for(state="visible", timeout=5000):
                        await locator.click()
                        await self.page.wait_for_timeout(3000)
                        print("Navigated to order section.")
                        return True
                except Exception:
                    continue

            print("Could not find order link automatically.")
            await self.page.screenshot(path="order_nav_debug.png")
            print("Please navigate to the order form manually.")
            await self.page.wait_for_timeout(30000)
            return True

        except Exception as e:
            print(f"Error navigating to order form: {e}")
            return False

    def navigate_to_order_form(self) -> bool:
        """Navigate to the spectacle order/claim form."""
        return self._run(self._navigate_to_order_form_async())

    async def _populate_order_form_async(self, data: Dict[str, str]) -> bool:
        """Async: populate the order/claim form."""
        if not self.logged_in:
            print("Not logged in. Please login first.")
            return False

        try:
            print("\nPopulating order form with extracted data...")
            await self.page.wait_for_timeout(2000)

            field_mappings = self._get_field_mappings()

            for field_name, value in data.items():
                if not value:
                    continue
                if field_name in field_mappings:
                    await self._fill_field_async(field_mappings[field_name], value, field_name)

            print("Form population complete!")
            return True

        except Exception as e:
            print(f"Error populating form: {e}")
            try:
                await self.page.screenshot(path="form_populate_error.png")
            except Exception:
                pass
            return False

    def populate_order_form(self, data: Dict[str, str]) -> bool:
        """Populate the order/claim form with extracted data."""
        return self._run(self._populate_order_form_async(data))

    async def _fill_field_async(self, selectors: list, value: str, field_name: str):
        """Try to fill a form field using multiple selectors."""
        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                if await locator.wait_for(state="visible", timeout=3000):
                    await locator.fill(value)
                    print(f"  ✓ {field_name}: {value}")
                    return
            except Exception:
                continue
        print(f"  ✗ {field_name}: Could not find field on page")

    def _get_field_mappings(self) -> Dict[str, list]:
        """Get Eyefinity field selector mappings."""
        return {
            "patient_name": [
                "#patientName",
                "input[name='patientName']",
                "input[name='patient_name']",
                "label:has-text('Patient Name') + input",
                "label:has-text('Patient Name') ~ input",
            ],
            "patient_dob": [
                "#dob",
                "input[name='dob']",
                "input[name='DOB']",
                "label:has-text('DOB') + input",
                "label:has-text('Date of Birth') + input",
            ],
            "patient_id": [
                "#patientId",
                "#memberId",
                "input[name='patientId']",
                "label:has-text('Patient ID') + input",
                "label:has-text('Member ID') + input",
            ],
            "doctor_name": [
                "#doctorName",
                "#providerName",
                "input[name='doctorName']",
                "label:has-text('Doctor') + input",
                "label:has-text('Provider') + input",
            ],
            "date_of_exam": [
                "#examDate",
                "#dateOfExam",
                "input[name='examDate']",
                "label:has-text('Exam Date') + input",
            ],
            "od_sph": [
                "#odSph",
                "#ODSphere",
                "input[name='odSphere']",
                "label:has-text('OD SPH') + input",
                "label:has-text('Right Sphere') + input",
            ],
            "od_cyl": [
                "#odCyl",
                "#ODCylinder",
                "input[name='odCylinder']",
                "label:has-text('OD CYL') + input",
                "label:has-text('Right Cylinder') + input",
            ],
            "od_axis": [
                "#odAxis",
                "#ODAxis",
                "input[name='odAxis']",
                "label:has-text('OD Axis') + input",
                "label:has-text('Right Axis') + input",
            ],
            "od_add": [
                "#odAdd",
                "#ODAdd",
                "input[name='odAdd']",
                "label:has-text('OD ADD') + input",
                "label:has-text('Right Add') + input",
            ],
            "os_sph": [
                "#osSph",
                "#OSSphere",
                "input[name='osSphere']",
                "label:has-text('OS SPH') + input",
                "label:has-text('Left Sphere') + input",
            ],
            "os_cyl": [
                "#osCyl",
                "#OSCylinder",
                "input[name='osCylinder']",
                "label:has-text('OS CYL') + input",
                "label:has-text('Left Cylinder') + input",
            ],
            "os_axis": [
                "#osAxis",
                "#OSAxis",
                "input[name='osAxis']",
                "label:has-text('OS Axis') + input",
                "label:has-text('Left Axis') + input",
            ],
            "os_add": [
                "#osAdd",
                "#OSAdd",
                "input[name='osAdd']",
                "label:has-text('OS ADD') + input",
                "label:has-text('Left Add') + input",
            ],
            "pd_distance": [
                "#pdDistance",
                "#PD",
                "input[name='pd']",
                "label:has-text('PD') + input",
            ],
            "od_pd_distance": [
                "#odPdDistance",
                "#odPd",
                "input[name='odPd']",
                "label:has-text('OD PD') + input",
                "label:has-text('Right PD') + input",
            ],
            "os_pd_distance": [
                "#osPdDistance",
                "#osPd",
                "input[name='osPd']",
                "label:has-text('OS PD') + input",
                "label:has-text('Left PD') + input",
            ],
            "od_seg_height": [
                "#odSegHeight",
                "#odSegHt",
                "input[name='odSegHeight']",
                "label:has-text('OD Seg Ht') + input",
                "label:has-text('Right Seg Ht') + input",
            ],
            "os_seg_height": [
                "#osSegHeight",
                "#osSegHt",
                "input[name='osSegHeight']",
                "label:has-text('OS Seg Ht') + input",
                "label:has-text('Left Seg Ht') + input",
            ],
            "frame_manufacturer": [
                "#frameManufacturer",
                "#frameBrand",
                "input[name='frameManufacturer']",
                "label:has-text('Frame Manufacturer') + input",
                "label:has-text('Frame Brand') + input",
            ],
            "frame_model": [
                "#frameModel",
                "input[name='frameModel']",
                "label:has-text('Frame Model') + input",
            ],
            "frame_color": [
                "#frameColor",
                "input[name='frameColor']",
                "label:has-text('Frame Color') + input",
            ],
            "frame_bridge": [
                "#frameBridge",
                "input[name='frameBridge']",
                "label:has-text('Bridge') + input",
            ],
            "frame_eye": [
                "#frameEye",
                "input[name='frameEye']",
                "label:has-text('Eye') + input",
            ],
            "frame_temple": [
                "#frameTemple",
                "input[name='frameTemple']",
                "label:has-text('Temple') + input",
            ],
            "lens_type": [
                "#lensType",
                "input[name='lensType']",
                "label:has-text('Lens Type') + input",
            ],
            "lens_material": [
                "#lensMaterial",
                "input[name='lensMaterial']",
                "label:has-text('Lens Material') + input",
            ],
            "lens_coatings": [
                "#lensCoatings",
                "input[name='lensCoatings']",
                "label:has-text('Lens Coating') + input",
            ],
            "lens_tint": [
                "#lensTint",
                "input[name='lensTint']",
                "label:has-text('Tint') + input",
            ],
            "lens_photochromic": [
                "#lensPhotochromic",
                "input[name='lensPhotochromic']",
                "label:has-text('Photochromic') + input",
            ],
            "lens_polarized": [
                "#lensPolarized",
                "input[name='lensPolarized']",
                "label:has-text('Polarized') + input",
            ],
            "lens_scratch_coat": [
                "#lensScratchCoat",
                "input[name='lensScratchCoat']",
                "label:has-text('Scratch') + input",
            ],
            "vsp_auth": [
                "#vspAuth",
                "#authNumber",
                "input[name='vspAuth']",
                "input[name='authNumber']",
                "label:has-text('Auth') + input",
                "label:has-text('Authorization') + input",
            ],
            "order_date": [
                "#orderDate",
                "input[name='orderDate']",
                "label:has-text('Order Date') + input",
            ],
            "order_number": [
                "#orderNumber",
                "input[name='orderNumber']",
                "label:has-text('Order #') + input",
            ],
            "comments": [
                "#comments",
                "#notes",
                "#specialInstructions",
                "textarea[name='comments']",
                "label:has-text('Comments') + textarea",
                "label:has-text('Notes') + textarea",
            ],
        }

    async def _submit_order_async(self) -> bool:
        """Async: submit the order form."""
        try:
            submit_selectors = [
                "#submit",
                "button:has-text('Submit')",
                "button:has-text('Place Order')",
                "input[type='submit']",
                "button:has-text('Save')",
                "a:has-text('Submit')",
            ]

            for selector in submit_selectors:
                try:
                    locator = self.page.locator(selector).first
                    if await locator.wait_for(state="visible", timeout=5000):
                        await locator.click()
                        await self.page.wait_for_timeout(3000)
                        print("Order submitted successfully!")
                        return True
                except Exception:
                    continue

            print("Could not find submit button.")
            await self.page.screenshot(path="submit_button_not_found.png")
            return False

        except Exception as e:
            print(f"Error submitting order: {e}")
            return False

    def submit_order(self) -> bool:
        """Submit the order form."""
        return self._run(self._submit_order_async())

    async def _close_async(self):
        """Async: close the browser."""
        try:
            if self.browser:
                await self.browser.close()
            if self._playwright:
                await self._playwright.stop()
            print("Browser closed.")
        except Exception as e:
            print(f"Error closing browser: {e}")
        finally:
            self.browser = None
            self.page = None
            self._playwright = None
            self.logged_in = False

    def close(self):
        """Close the browser."""
        if self._loop and self._loop.is_running():
            try:
                self._run(self._close_async())
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.browser = None
        self.page = None
        self._playwright = None
        self.logged_in = False


if __name__ == "__main__":
    automation = EyefinityAutomation()

    try:
        print("Testing Eyefinity Automation...")
        print("=" * 50)

        if automation.login():
            print("\n✓ Login successful")

            if automation.navigate_to_order_form():
                print("✓ Navigated to order form")

                sample_data = {
                    "patient_name": "John Doe",
                    "patient_dob": "01/15/1985",
                    "od_sph": "-2.50",
                    "od_cyl": "-0.75",
                    "od_axis": "180",
                    "os_sph": "-1.75",
                    "os_cyl": "-0.50",
                    "os_axis": "005",
                }

                print("\nPopulating sample data...")
                automation.populate_order_form(sample_data)

        else:
            print("\n✗ Login failed. Check credentials in config.yaml")

    finally:
        input("\nPress Enter to close browser...")
        automation.close()