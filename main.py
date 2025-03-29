with open("debug.log", "a") as f:
    f.write("🔥 main.py wordt uitgevoerd\n")

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing.resource_tracker")

import shutil
import time
import pickle
import os
import sys
import atexit
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver import ActionChains

import os
import contextlib
import subprocess

COOKIES_FILE = "cookies.pkl"
LOGIN_URL = "https://aternos.org/go/"
SERVER_URL = "https://aternos.org/servers/"
MAX_RETRY_COUNT = 3
MAX_WAIT_ONLINE = 300  # 5 minuten
SCRIPT_VERSION = "1.2.1"

# Globale variabelen
driver = None
browser_closed = False
audio_muted_once = False  # Zorgt ervoor dat het debugbericht voor audio muting slechts één keer verschijnt

def debug_print(msg):
    """Print een debug-bericht met timestamp en log het naar een bestand."""
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg, flush=True)
    with open("debug.log", "a") as log:
        log.write(log_msg + "\n")

def save_debug_snapshot(name):
    """Sla een screenshot en HTML-source op in de map 'screens/' met de gegeven naam."""
    try:
        os.makedirs("screens", exist_ok=True)
        if driver:
            screenshot_path = f"screens/{name}.png"
            html_path = f"screens/{name}.html"
            driver.save_screenshot(screenshot_path)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            debug_print(f"📸 Snapshot opgeslagen als {name}.png en {name}.html")
    except Exception as e:
        debug_print(f"✗ Fout bij opslaan snapshot {name}: {str(e)}")

def cleanup_browser():
    """Sluit browser netjes af als dat nog niet gebeurd is."""
    global driver, browser_closed
    if 'driver' in globals() and driver and not browser_closed:
        try:
            driver.service.process.send_signal(15)  # SIGTERM
            time.sleep(0.5)
            driver.service.process.kill()  # SIGKILL als backup
            driver.quit()
            browser_closed = True
        except Exception as e:
            debug_print(f"Fout tijdens afsluiten browser: {str(e)}")

def cleanup_and_exit(exit_code=0, message=None):
    global driver
    if exit_code == 0:
        debug_print("🏁 Server 🆙! 🎮 Veel plezier, Ⓜ️☪️ met maten!👨‍❤️‍💋‍👨")
    else:
         debug_print(f"Script beëindigd met exit code {exit_code}")
    if 'driver' in globals():
        try:
            del driver
        except Exception:
            pass
    sys.exit(exit_code)  # <-- netjes afsluiten i.p.v. os._exit

def is_fly_io():
    return os.getenv("FLY_APP_NAME") is not None

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
debug_print(f"🔍 USERNAME uit omgeving: {USERNAME}")
debug_print(f"🔍 PASSWORD lengte: {len(PASSWORD) if PASSWORD else 'None'}")

if not USERNAME or not PASSWORD:
    debug_print(f"❌ USERNAME = {USERNAME}, PASSWORD lengte = {len(PASSWORD) if PASSWORD else 'None'}")
    cleanup_and_exit(1, "Omgevingsvariabelen ontbreken")

def save_cookies(driver, file_path):
    """Sla cookies op voor hergebruik."""
    try:
        with open(file_path, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
        debug_print("✓ Cookies opgeslagen.")
        return True
    except Exception as e:
        debug_print(f"✗ Fout bij opslaan cookies: {str(e)}")
        return False

def load_cookies(driver, file_path):
    """Laad opgeslagen cookies."""
    try:
        if not os.path.exists(file_path):
            debug_print("✗ Cookies-bestand niet gevonden.")
            return False
        with open(file_path, "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        debug_print("🔋 Cookies geladen")
        return True
    except Exception as e:
        debug_print(f"✗ Fout bij laden cookies: {str(e)}")
        return False

def apply_audio_muting(driver):
    """Forceer audio muting voor alle media-elementen; debugbericht slechts één keer weergeven."""
    global audio_muted_once
    try:
        driver.execute_script("""
            // Dempt alle audio- en video-elementen
            document.querySelectorAll('audio, video').forEach(el => {
                el.muted = true;
                el.volume = 0;
                el.pause();
            });
            // AudioContext aanpassen zodat nieuwe audio automatisch gemute wordt
            if (window.AudioContext || window.webkitAudioContext) {
                const OrigAudioContext = window.AudioContext || window.webkitAudioContext;
                window.AudioContext = window.webkitAudioContext = class extends OrigAudioContext {
                    constructor() {
                        super();
                        if (this.destination && this.destination.gain) {
                            this.destination.gain.value = 0;
                        }
                    }
                };
            }
        """)
        if not audio_muted_once:
            audio_muted_once = True
        return True
    except Exception as e:
        debug_print(f"✗ Fout bij audio muting: {str(e)}")
        return False

def click_consent_buttons(driver, timeout=30):
    """Zoek en klik op consent-knoppen."""
    try:
        end_time = time.time() + timeout
        clicked = False
        while time.time() < end_time:
            consent_buttons = driver.find_elements(By.XPATH, "//button[@aria-label='Consent']")
            if not consent_buttons:
                break
            for btn in consent_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    driver.execute_script("arguments[0].click();", btn)
                    clicked = True
                    time.sleep(0.5)
                    return True
            if not clicked:
                break
        if clicked:
            debug_print("✓ Consent-knoppen verwerkt.")
        return clicked
    except Exception as e:
        debug_print("✗ Fout bij verwerken consent-knoppen: " + str(e))
        return False

def wait_for_element(driver, locator, timeout=30, condition="presence"):
    """Wacht op een element met foutafhandeling."""
    try:
        if condition == "presence":
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
        elif condition == "clickable":
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
        elif condition == "visible":
            element = WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located(locator)
            )
        return element
    except TimeoutException:
        return None
    except Exception as e:
        debug_print(f"✗ Fout bij wachten op element {locator}: {str(e)}")
        return None

def is_server_online(driver):
    """Controleer of de server online is via verschillende methoden."""
    try:
        try:
            online_status = driver.find_element(By.CSS_SELECTOR, "div.status.online")
            if online_status.is_displayed():
                return True
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        try:
            status_label = driver.find_element(By.CSS_SELECTOR, "span.statuslabel-label")
            if status_label and "Online" in status_label.text:
                return True
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        return False
    except Exception as e:
        debug_print("✗ Fout bij controleren online status: " + str(e))
        return False

def get_remaining_time(driver):
    """Haal de resterende tijd op indien beschikbaar."""
    try:
        countdown = driver.find_element(By.CSS_SELECTOR, "div.server-end-countdown")
        if countdown.is_displayed():
            return countdown.text
    except (NoSuchElementException, StaleElementReferenceException):
        pass
    return None

def initialize_browser():
    debug_print("➡️ Browser initialisatie...")
    PROXY = os.getenv("CHROME_PROXY")  # Formaat: "ip:port"
    options = uc.ChromeOptions()
    options.binary_location = "/usr/bin/google-chrome"
    if PROXY:
        debug_print(f"🌐 Proxy ingesteld: {PROXY}")
        options.add_argument(f'--proxy-server=http://{PROXY}')
    debug_print("🛠 ChromeOptions object aangemaakt")
    options.add_argument("--lang=nl-NL,nl")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--incognito")
    # Removed options.headless = True and duplicate options.binary_location assignment
    options.add_argument("--headless=new")  # of "--headless=new"
    options.add_argument("--no-zygote")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-audio-output")
    options.add_argument("--use-fake-ui-for-media-stream")
    options.add_argument("--use-fake-device-for-media-stream")
    options.add_argument("--disable-webrtc")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--referer=https://aternos.org/")
    options.add_argument("--origin=https://aternos.org/")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-hang-monitor")
    options.add_argument("--disable-prompt-on-repost")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--no-first-run")
    options.add_argument("--enable-automation")
    options.add_argument("--disable-component-extensions-with-background-pages")
 
    try:
        browser = uc.Chrome(
            options=options,
            version_main=115,
            driver_path="/usr/local/bin/chromedriver"
        )
        browser.set_window_size(1024, 768)

        # Extra anti-bot spoofing via CDP
        browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": '''
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['nl-NL', 'nl'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [
                    { name: "Chrome PDF Plugin" },
                    { name: "Chrome PDF Viewer" },
                    { name: "Native Client" }
                ] });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
                Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            '''
        })
        browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": '''
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['nl-NL', 'nl'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            '''
        })
        browser.execute_script("HTMLMediaElement.prototype.play = function() { return Promise.resolve(); };")
        browser.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        debug_print("✅ Browser succesvol geïnitialiseerd")
        return browser
    except Exception as e:
        debug_print("✗ Fout bij initialiseren browser: " + str(e))
        return None

def login_with_cookies(driver):
    """Probeer in te loggen met opgeslagen cookies."""
    try:
        driver.get(SERVER_URL)
        apply_audio_muting(driver)
        if not load_cookies(driver, COOKIES_FILE):
            return False
        driver.refresh()
        apply_audio_muting(driver)
        account_element = wait_for_element(driver, (By.CSS_SELECTOR, "div.user a[title='Account']"), timeout=30)
        if account_element:
            return True
        else:
            debug_print("✗ Cookies verlopen of ongeldig")
            debug_print("⚠️ Element 'Account' niet gevonden na cookie-login, URL: " + driver.current_url)
            driver.save_screenshot("cookies_login_failed.png")
            return False
    except Exception as e:
        debug_print("✗ Fout bij inloggen met cookies: " + str(e))
        return False

def login_manually(driver):
    """Voer handmatige login uit."""
    try:
        debug_print("➡️ login_manually() start")
        debug_print("🔐 Handmatig inloggen...")
        driver.get(LOGIN_URL)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")

        actions = ActionChains(driver)
        actions.move_by_offset(100, 100).perform()
        time.sleep(0.5)     

        save_debug_snapshot("login_url_loaded")
        apply_audio_muting(driver)
        click_consent_buttons(driver)  # ✅ Nieuw toegevoegd
        debug_print("🌐 Huidige URL: " + driver.current_url)
        WebDriverWait(driver, 30).until(lambda d: d.execute_script("return document.readyState")=="complete")
        # JS polling als fallback om te wachten op login form
        driver.execute_script("""
            new Promise(r => {
                let i = setInterval(() => {
                    if (document.querySelector('.username')) {
                        clearInterval(i);
                        r();
                    }
                }, 500);
            })
        """)
        time.sleep(2)
        login_wrapper = wait_for_element(driver, (By.CLASS_NAME, "login-wrapper"), timeout=90)  # ⏱ timeout verhoogd
        if not login_wrapper:
            debug_print("✗ Login formulier niet gevonden")

# Detectie van CAPTCHA
            if "captcha" in driver.page_source.lower():
                debug_print("⚠️ CAPTCHA gedetecteerd op pagina")
                save_debug_snapshot("captcha_detected")
                debug_print("🕓 CAPTCHA gedetecteerd, wacht 30 seconden uit voor retry...")
                time.sleep(30)
                save_debug_snapshot("possible_captcha_pause")
                cleanup_and_exit(1, "CAPTCHA gedetecteerd — afgebroken")

        # Extra snapshot maken voor analyse
        save_debug_snapshot("no_login_form_found")
        debug_print("✏️ Vul gebruikersnaam in...")
        driver.find_element(By.CSS_SELECTOR, "input[type='text'].username").send_keys(USERNAME)
        debug_print("✏️ Gebruikersnaam ingevuld")
        debug_print("✏️ Vul wachtwoord in...")
        driver.find_element(By.CSS_SELECTOR, "input[type='password'].password").send_keys(PASSWORD)
        debug_print("✏️ Wachtwoord ingevuld")
        driver.find_element(By.CLASS_NAME, "login-button").click()
        save_debug_snapshot("after_login_click")
        WebDriverWait(driver, 30).until(lambda d: d.current_url != LOGIN_URL)  # timeout ook iets verhoogd
        WebDriverWait(driver, 30).until(lambda d: d.current_url != LOGIN_URL)
        if "/servers" in driver.current_url:
            debug_print("✓ Handmatig inloggen succesvol, URL: " + driver.current_url)
            save_cookies(driver, COOKIES_FILE)  # <- Voeg deze regel toe
            save_debug_snapshot("manual_login_success")
        else:
            debug_print("✗ Handmatig inloggen mislukt")
            driver.save_screenshot("screens/login_failed.png")
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
                debug_print("⚠️ Cookies-bestand verwijderd na mislukte login.")
            debug_print("⏹️ login_manually() end")
            return False
    except Exception as e:
        debug_print("✗ Fout bij handmatig inloggen: " + str(e))
        driver.save_screenshot("login_error.png")
        return False

def navigate_to_server(driver):
    """Navigeer naar de serverdetailpagina."""
    try:
        debug_print("➡️ navigate_to_server() start")
        driver.get(SERVER_URL)
        save_debug_snapshot("server_url_loaded")
        WebDriverWait(driver, 30).until(lambda d: d.execute_script("return document.readyState")=="complete")
        apply_audio_muting(driver)
        click_consent_buttons(driver)
        retry_count = 0
        debug_print("⏳ Navigatiepoging naar server start...")
        server_clicked = False
        if not driver.session_id:
            debug_print("✗ Driver session ongeldig vóór navigatiepogingen, browser is mogelijk gecrasht.")
            return False
        while retry_count < MAX_RETRY_COUNT and not server_clicked:
            try:
                server_xpath = ("//div[contains(@class, 'servercard') and .//div[contains(@class, 'server-name') "
                                "and normalize-space(text())='Nick90NL']]//div[contains(@class, 'server-name')]")
                server_element = wait_for_element(driver, (By.XPATH, server_xpath), timeout=30, condition="clickable")
                if server_element:
                    driver.execute_script("arguments[0].scrollIntoView(true);", server_element)
                    driver.execute_script("arguments[0].click();", server_element)
                    debug_print(f"🚀 Server 'Nick90NL' geselecteerd {retry_count + 1}/{MAX_RETRY_COUNT}")
                    save_debug_snapshot("server_click")
                    if WebDriverWait(driver, 30).until(EC.url_contains("/server/")):
                        apply_audio_muting(driver)
                        server_clicked = True
                        debug_print("🌐 Navigatie naar serverdetailpagina succesvol")
                        debug_print("⏹️ navigate_to_server() end")
                        return True
                else:
                    debug_print(f"Server element niet gevonden (poging {retry_count+1}/{MAX_RETRY_COUNT})")
            except Exception as e:
                pass
            retry_count += 1
            time.sleep(5)
        if not server_clicked:
            debug_print("✗ Kon niet navigeren naar server na meerdere pogingen")
            if driver.session_id:
                driver.save_screenshot("screens/server_click_failed.png")
            else:
                debug_print("⚠️ Screenshot overgeslagen: session_id is ongeldig (browser waarschijnlijk gesloten)")
            debug_print("⏹️ navigate_to_server() end")
            return False
    except Exception as e:
        debug_print("✗ Onverwachte fout bij navigeren naar server: " + str(e))
        if driver and driver.session_id:
            driver.save_screenshot("server_navigation_failed.png")
        else:
            debug_print("⚠️ Screenshot overgeslagen: session_id is ongeldig (browser waarschijnlijk gesloten)")
        return False

def check_server_status_and_start(driver):
    """Controleer server status en start indien nodig.
    Zodra de server online is, stopt het script (zonder extra loop-berichten voor audio)."""
    try:
        debug_print("➡️ check_server_status_and_start() start")
        status_element = wait_for_element(driver, (By.CSS_SELECTOR, "div.status"), timeout=30)
        if not status_element:
            debug_print("✗ Kan server status niet vinden")
            driver.save_screenshot("screens/no_status.png")
            debug_print("⏹️ check_server_status_and_start() end")
            return False
        if is_server_online(driver):
            time_left = get_remaining_time(driver)
            if time_left:
                debug_print(f"✓ Server is al online! Resterende tijd: {time_left}")
            else:
                debug_print("✓ Server is al online!")
            driver.save_screenshot("screens/server_already_online.png")
            debug_print("⏹️ check_server_status_and_start() end")
            return True
        debug_print("⛔️ Server is offline, no worries... Daar gaat ie!🚀🚀🚀")
        # Wacht eerst tot het element aanwezig is
        start_button = wait_for_element(driver, (By.ID, "start"), timeout=30, condition="presence")
        if not start_button:
            debug_print("✗ Startknop niet gevonden binnen 30 seconden (presence check).")
            driver.save_screenshot("start_button_not_found_presence.png")
            return False

        # Wacht daarna tot het element klikbaar is
        start_button_clickable = wait_for_element(driver, (By.ID, "start"), timeout=30, condition="clickable")
        if not start_button_clickable:
            debug_print("✗ Startknop gevonden maar niet klikbaar binnen 15 seconden.")
            driver.save_screenshot("start_button_not_clickable.png")
            return False

        driver.execute_script("arguments[0].click();", start_button_clickable)
        save_debug_snapshot("start_button_clicked")
        debug_print("▶️ 💲tart!🔥🔥")
        try:
            no_button = wait_for_element(driver, (By.XPATH, "//button[normalize-space(text())='Nee']"), timeout=30, condition="clickable")
            if no_button:
                driver.execute_script("arguments[0].click();", no_button)
                debug_print("✓ 'Nee' knop voor meldingen aangeklikt")
        except TimeoutException:
            debug_print("Geen 'Nee' knop gevonden, doorgaan...")
        debug_print(f"⏳ Wachten tot server online komt (klein minuutje nog ⏰)...")
        start_time = time.time()
        while time.time() - start_time < MAX_WAIT_ONLINE:
            # Voer periodiek audio muting uit zonder debug-output
            apply_audio_muting(driver)
            if is_server_online(driver):
                time_left = get_remaining_time(driver)
                apply_audio_muting(driver)
                return True
            time.sleep(1)
        debug_print("✗ Server is niet online gekomen na 5 minuten")
        driver.save_screenshot("screens/server_not_online.png")
        debug_print("⏹️ check_server_status_and_start() end")
        return False
    except Exception as e:
        debug_print("✗ Fout bij controleren/starten van server: " + str(e))
        driver.save_screenshot("server_check_error.png")
        return False

def main():
    """Hoofdfunctie van het script."""
    global driver
    debug_print("🎯 Render test-modus actief")
    if driver:
        atexit.unregister(cleanup_browser)
    atexit.register(cleanup_browser)
    try:
        driver = None
        driver = initialize_browser()
        if not driver:
            debug_print("⚠️ initialize_browser() returned None")
            cleanup_and_exit(1, "Kon browser niet initialiseren, script wordt afgebroken.")
        logged_in = login_with_cookies(driver)
        
        if not logged_in:
            debug_print("⚠️ login_with_cookies() mislukt, probeer handmatig in te loggen...")
            logged_in = login_manually(driver)
            WebDriverWait(driver, 30).until(lambda d: d.current_url != LOGIN_URL)
            if not logged_in:
                debug_print("✗ Handmatige login is ook mislukt")
                cleanup_and_exit(1, "Kon niet inloggen, script wordt afgebroken.")
        if not navigate_to_server(driver):
            debug_print("✗ Navigatie naar server is mislukt")
            cleanup_and_exit(1, "Kon niet naar server navigeren, script wordt afgebroken.")
        server_online = check_server_status_and_start(driver)
        if server_online:
            cleanup_and_exit(0, "✓ Succes! Server is online. Script voltooid.")
        else:
            debug_print("✗ check_server_status_and_start() faalde")
            cleanup_and_exit(1, "✗ Kon server niet online krijgen. Script gefaald.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        debug_print("⚠️ Traceback geschreven naar console.")
        debug_print("✗ Onverwachte fout in hoofdprogramma: " + str(e))
        if driver and hasattr(driver, "session_id"):
            try:
                driver.save_screenshot("unexpected_error.png")
            except Exception:
                debug_print("⚠️ Kon geen screenshot maken bij onverwachte fout (waarschijnlijk browser gesloten)")
        cleanup_and_exit(1, "Script afgebroken door onverwachte fout.")

if __name__ == "__main__":
    main()
    
