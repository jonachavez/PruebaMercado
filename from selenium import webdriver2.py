from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import logging
import time
import os
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict

#  Configuración 
WAIT_TIMEOUT = 15
MINI_PAUSE = 0.8
SORT_OPTION = "Mayor precio"

REPORT_DIR = os.path.join(os.getcwd(), "report")
os.makedirs(REPORT_DIR, exist_ok=True)
SCREEN_DIR = os.path.join(REPORT_DIR, "screenshots")
os.makedirs(SCREEN_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(REPORT_DIR, "run.log"), encoding="utf-8"),
        logging.StreamHandler()
    ],
)

#  Modelo del reporte
@dataclass
class StepRecord:
    name: str
    start_ts: str
    end_ts: str
    duration_s: float
    status: str        
    message: str = ""
    screenshot: str = "" 

@dataclass
class ExecutionReport:
    started_at: str
    finished_at: str
    total_duration_s: float
    steps: List[StepRecord]
    results: List[Dict]     # productos extraídos
    environment: Dict       # info de entorno

REPORT = ExecutionReport(
    started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    finished_at="",
    total_duration_s=0.0,
    steps=[],
    results=[],
    environment={}
)

def record_step(driver, name, func, *args, **kwargs):
    """Ejecuta un paso, mide tiempos y captura errores/screenshot si falla."""
    start = time.time()
    start_str = datetime.now().strftime("%H:%M:%S")
    status, message, screenshot_path = "OK", "", ""
    try:
        result = func(*args, **kwargs)
        return result
    except Exception as e:
        status = "ERROR"
        message = f"{type(e).__name__}: {e}"
        # evidencia si tenemos driver
        if driver is not None:
            fname = f"{datetime.now().strftime('%H%M%S')}_{name.replace(' ','_')}.png"
            shot_full = os.path.join(SCREEN_DIR, fname)
            try:
                driver.save_screenshot(shot_full)
                screenshot_path = os.path.relpath(shot_full, REPORT_DIR)
            except Exception:
                pass
        logging.exception(f"[{name}] falló: {message}")
        raise
    finally:
        end = time.time()
        end_str = datetime.now().strftime("%H:%M:%S")
        REPORT.steps.append(
            StepRecord(
                name=name,
                start_ts=start_str,
                end_ts=end_str,
                duration_s=round(end - start, 2),
                status=status,
                message=message,
                screenshot=screenshot_path
            )
        )

#  Helpers de scraping 
def safe_click(driver, element):
    try:
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        driver.execute_script("arguments[0].click();", element)

def sort_by(driver, wait, option_text=SORT_OPTION):
    dropdown_candidates = [
        "//button[contains(@class,'andes-dropdown__trigger') and @aria-haspopup='listbox']",
        "//span[contains(@class,'andes-dropdown__display-values')]/ancestor::button[@aria-haspopup='listbox']",
        "//*[contains(.,'Ordenar por')]/following::button[contains(@class,'andes-dropdown__trigger')][1]",
    ]
    opened = False
    for xp in dropdown_candidates:
        try:
            trigger = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            safe_click(driver, trigger)
            opened = True
            break
        except TimeoutException:
            continue
    if not opened:
        raise TimeoutException("No pude abrir el dropdown de 'Ordenar por'.")

    option_candidates = [
        "//ul[@role='listbox']//li[@role='option'][contains(., $TXT)]",
        "//div[@role='listbox']//li[contains(., $TXT)]",
        "//li[contains(@class,'andes-list__item')][contains(., $TXT)]",
        "//a[contains(@class,'andes-list__item')][contains(., $TXT)]",
        "//button[contains(@class,'andes-list__item')][contains(., $TXT)]",
    ]
    option_xpaths = [xp.replace("$TXT", f"'{option_text}'") for xp in option_candidates]
    for xp in option_xpaths:
        try:
            opt = WebDriverWait(driver, WAIT_TIMEOUT).until(EC.element_to_be_clickable((By.XPATH, xp)))
            safe_click(driver, opt)
            time.sleep(MINI_PAUSE)
            return
        except TimeoutException:
            continue
    # reintento
    trigger = wait.until(EC.element_to_be_clickable((By.XPATH, dropdown_candidates[0])))
    safe_click(driver, trigger)
    opt = wait.until(EC.element_to_be_clickable((By.XPATH, option_xpaths[0])))
    safe_click(driver, opt)
    time.sleep(MINI_PAUSE)

def get_first_results_cards(driver, wait, n=5):
    cards_xpath = "(//li[contains(@class,'ui-search-layout__item')])[position()<=30]"
    wait.until(EC.presence_of_element_located((By.XPATH, cards_xpath)))
    cards = driver.find_elements(By.XPATH, cards_xpath)
    clean = []
    for li in cards:
        try:
            ad_badge = li.find_elements(By.XPATH, ".//span[contains(.,'Publicidad') or contains(.,'Anuncio')]")
            if ad_badge:
                continue
        except Exception:
            pass
        clean.append(li)
        if len(clean) >= n:
            break
    return clean

def extract_title_and_price_js(driver, card):
    return driver.execute_script("""
const li = arguments[0];
function txt(el){ return el ? (el.innerText || el.textContent || "").trim() : ""; }
function clean(s){ return (s||"").replace(/\\s+/g," ").trim(); }
function looksLikePrice(s){
  if (!s) return false;
  const t = s.toLowerCase();
  if (t.includes('pesos')) return true;
  if (t.includes('$')) return true;
  const digits = (s.match(/[0-9.,\\s]/g)||[]).length;
  return (digits / s.length) > 0.7;
}
// Título
let title = "";
const a = li.querySelector("a.ui-search-link") || li.querySelector("a[href]");
if (a){
  title = a.getAttribute("title") || a.getAttribute("aria-label") || "";
  if (!title){
    const h2in = a.querySelector("h2");
    if (h2in) title = txt(h2in);
  }
}
if (!title || looksLikePrice(title)){
  const h2 = li.querySelector("h2.ui-search-item__title") || li.querySelector("h2");
  const t2 = txt(h2);
  if (!looksLikePrice(t2)) title = t2 || title;
}
if (!title || looksLikePrice(title)){
  const img = li.querySelector("img[alt]");
  const alt = img ? img.getAttribute("alt") : "";
  if (alt && !looksLikePrice(alt)) title = alt;
}
if (!title || looksLikePrice(title)){
  const any = li.querySelector("[aria-label]") || li.querySelector("a[title]") || li.querySelector("a");
  const t3 = (any && (any.getAttribute("aria-label") || any.getAttribute("title"))) || txt(any);
  if (!looksLikePrice(t3)) title = t3 || title;
}
title = clean(title);

// Precio
let price = "";
const box = li.querySelector("span.andes-money-amount");
if (box) price = clean(txt(box));
if (!price){
  const cur  = txt(li.querySelector("span.andes-money-amount__currency-symbol"));
  const frac = txt(li.querySelector("span.andes-money-amount__fraction"));
  const cent = txt(li.querySelector("span.andes-money-amount__cents"));
  price = clean(cur + frac + (cent ? "."+cent : ""));
}

return [title, price];
""", card)

# Generación de reportes 
def save_results_csv(results: List[Dict], path_csv: str):
    import csv
    with open(path_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pos", "title", "price"])
        writer.writeheader()
        writer.writerows(results)

def save_results_json(results: List[Dict], path_json: str):
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def render_html_report(report: ExecutionReport, out_path: str):
    """Genera un HTML simple y legible con pasos + resultados."""
    steps_rows = "\n".join(
        f"<tr><td>{i+1}</td><td>{s.name}</td><td>{s.start_ts}</td><td>{s.end_ts}</td>"
        f"<td>{s.duration_s:.2f}s</td><td style='color:{'green' if s.status=='OK' else 'red'}'>{s.status}</td>"
        f"<td>{s.message}</td><td>{('<a href=\"'+s.screenshot+'\">ver</a>') if s.screenshot else ''}</td></tr>"
        for i, s in enumerate(report.steps)
    )
    results_rows = "\n".join(
        f"<tr><td>{r['pos']}</td><td>{r['title']}</td><td>{r['price']}</td></tr>"
        for r in report.results
    )
    env_rows = "\n".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in report.environment.items()
    )

    html = f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<title>Reporte de Ejecución - MercadoLibre</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
h1,h2 {{ margin-bottom: 8px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 14px; }}
th {{ background: #f2f2f2; text-align: left; }}
.badge {{ padding: 2px 6px; border-radius: 4px; color: #fff; }}
</style></head><body>
<h1>Reporte de Ejecución - MercadoLibre</h1>
<p><b>Inicio:</b> {report.started_at} &nbsp; | &nbsp; <b>Fin:</b> {report.finished_at} &nbsp; | &nbsp; <b>Duración total:</b> {report.total_duration_s:.2f}s</p>

<h2>Entorno</h2>
<table><thead><tr><th>Clave</th><th>Valor</th></tr></thead>
<tbody>{env_rows}</tbody></table>

<h2>Pasos</h2>
<table>
<thead><tr><th>#</th><th>Paso</th><th>Inicio</th><th>Fin</th><th>Duración</th><th>Estado</th><th>Mensaje</th><th>Screenshot</th></tr></thead>
<tbody>{steps_rows}</tbody></table>

<h2>Resultados (Top 5)</h2>
<table>
<thead><tr><th>#</th><th>Nombre</th><th>Precio</th></tr></thead>
<tbody>{results_rows}</tbody></table>

</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

# Flujo principal con reporte
def main():
    start_time = time.time()

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    # entorno
    REPORT.environment = {
        "browser": "Chrome",
        "selenium": "v4",
        "wait_timeout_s": WAIT_TIMEOUT,
        "sort_option": SORT_OPTION,
        "os_cwd": os.getcwd()
    }

    try:
        # 
        record_step(driver, "Abrir sitio", lambda: driver.get("https://www.mercadolibre.com"))

        # País
        def choose_country():
            try:
                mx = driver.find_element(By.PARTIAL_LINK_TEXT, "México")
                mx.click()
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
            except Exception:
                pass
        record_step(driver, "Seleccionar México (si aplica)", choose_country)

        # Cookies
        def accept_cookies():
            try:
                cookies_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[@id='onetrust-accept-btn-handler' or contains(@class,'onetrust')]"))
                )
                safe_click(driver, cookies_btn)
            except TimeoutException:
                pass
        record_step(driver, "Aceptar cookies (si aparece)", accept_cookies)

        # Buscar
        def search_ps5():
            try:
                sb = driver.find_element(By.NAME, "as_word")
            except Exception:
                sb = driver.find_element(By.ID, "cb1-edit")
            sb.clear()
            sb.send_keys("playstation 5")
            sb.send_keys(Keys.RETURN)
        record_step(driver, "Buscar 'playstation 5'", search_ps5)

        # Filtro Nuevo
        def apply_new_filter():
            nuevo = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//span[@class='ui-search-filter-name' and normalize-space()='Nuevo'] | //a[.//span[normalize-space()='Nuevo']]"
            )))
            safe_click(driver, nuevo)
        record_step(driver, "Aplicar filtro 'Nuevo'", apply_new_filter)

        # Orden
        record_step(driver, "Ordenar por 'Mayor precio'", lambda: sort_by(driver, wait, option_text=SORT_OPTION))

        # Datos
        def grab_top5():
            cards = get_first_results_cards(driver, wait, n=5)
            out = []
            for i, card in enumerate(cards, start=1):
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                title, price = extract_title_and_price_js(driver, card)
                if not title or not price:
                    time.sleep(0.4)
                    title, price = extract_title_and_price_js(driver, card)
                out.append({"pos": i, "title": title or "—", "price": price or "—"})
            REPORT.results = out
        record_step(driver, "Extraer Top 5 (nombre/precio)", grab_top5)

        # Exportar archivos
        record_step(driver, "Exportar CSV", lambda: save_results_csv(REPORT.results, os.path.join(REPORT_DIR, "productos.csv")))
        record_step(driver, "Exportar JSON", lambda: save_results_json(REPORT.results, os.path.join(REPORT_DIR, "productos.json")))

    finally:
        driver.quit()
        end_time = time.time()
        REPORT.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        REPORT.total_duration_s = round(end_time - start_time, 2)
        # HTML
        render_html_report(REPORT, os.path.join(REPORT_DIR, "reporte_mercadolibre.html"))
        # JSON del reporte completo
        with open(os.path.join(REPORT_DIR, "reporte_mercadolibre.json"), "w", encoding="utf-8") as f:
            json.dump({
                **asdict(REPORT),
                "steps": [asdict(s) for s in REPORT.steps]
            }, f, ensure_ascii=False, indent=2)

        logging.info(f"Reporte HTML: {os.path.join(REPORT_DIR, 'reporte_mercadolibre.html')}")
        logging.info(f"CSV: {os.path.join(REPORT_DIR, 'productos.csv')}")
        logging.info(f"JSON: {os.path.join(REPORT_DIR, 'productos.json')}")
        logging.info(f"Log:  {os.path.join(REPORT_DIR, 'run.log')}")

if __name__ == "__main__":
    main()


