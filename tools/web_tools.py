"""
tools/web_tools.py
Navigazione web per CESARE tramite browser Playwright reale (headless).
Fallback automatico su requests/DDG se Playwright non disponibile.
"""
import threading
import logging
import requests
from bs4 import BeautifulSoup
from core.security import audit_log

logger = logging.getLogger("CESARE.WebTools")

# --- Disponibilità Playwright ---
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("Playwright non disponibile — uso requests come fallback.")

def _search_duckduckgo_fallback(query: str) -> str:
    """Fallback su DuckDuckGo quando Playwright/Google non è disponibile."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            if not results:
                return f"Nessun risultato trovato su internet per la query: '{query}'. Prova a riformulare la ricerca con parole chiave diverse."
            
            formatted_results = []
            for r in results:
                formatted_results.append(f"Titolo: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
            return "\n---\n".join(formatted_results)
    except Exception as e:
        return f"Errore durante la ricerca di fallback: {str(e)}"

def _browse_requests_fallback(url: str) -> str:
    """Fallback su requests + BeautifulSoup per la navigazione statica."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=(3, 6))
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
            element.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        return f"[FALLBACK REQUESTS] Contenuto di {url}:\n\n{text[:5000]}"
    except Exception as e:
        return f"Errore: Impossibile raggiungere il sito {url}. Il dominio potrebbe essere inesistente o digitato male (Dettaglio: {str(e)}). Suggerimento: usa il tool 'search_web' per trovare l'indirizzo corretto."

def search_web_tool(query: str):
    """Cerca su internet tramite Google (Playwright) con fallback su DDG."""
    audit_log("WEB_SEARCH", f"Ricerca query: {query}")

    if not PLAYWRIGHT_AVAILABLE:
        return _search_duckduckgo_fallback(query)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
            page = context.new_page()
            
            # Google search URL in italiano, 5 risultati
            url = f"https://www.google.com/search?q={query}&hl=it&num=5"
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
            
            # Controllo Anti-bot
            if 'unusual traffic' in page.content().lower() or 'captcha' in page.url:
                logger.warning("Google CAPTCHA rilevato — fallback su DuckDuckGo.")
                browser.close()
                return _search_duckduckgo_fallback(query)

            # Estrazione risultati organici
            results_elements = page.query_selector_all('div.g')
            formatted_results = []
            
            for res in results_elements:
                title_el = res.query_selector('h3')
                link_el = res.query_selector('a')
                snippet_el = res.query_selector('div.VwiC3b')
                
                if title_el and link_el:
                    title = title_el.inner_text()
                    href = link_el.get_attribute('href')
                    snippet = snippet_el.inner_text() if snippet_el else "Nessuno snippet disponibile."
                    formatted_results.append(f"Titolo: {title}\nURL: {href}\nSnippet: {snippet}\n")

            page.close()
            browser.close()

            if not formatted_results:
                return _search_duckduckgo_fallback(query)
                
            return "\n---\n".join(formatted_results)
    except Exception as e:
        logger.error(f"Errore Playwright Search: {str(e)}")
        return _search_duckduckgo_fallback(query)

def browse_web_tool(url: str):
    """Naviga su un URL tramite Playwright per gestire JS, con fallback su requests."""
    audit_log("WEB_BROWSE", f"Navigazione URL: {url}")

    # Controllo se l'input è un URL o solo un nome
    if not url.startswith(("http://", "https://")):
        return (f"ERRORE: '{url}' non sembra un URL valido. "
                f"Per 'collegarti' a questo sito, devi prima usare 'search_web' con la query '{url}' per trovare l'indirizzo corretto.")
    
    if not PLAYWRIGHT_AVAILABLE:
        return _browse_requests_fallback(url)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # Pulizia della pagina via JavaScript
            page.evaluate("""
                () => {
                    const selectors = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript', 'ad', 'banner'];
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => el.remove());
                    });
                }
            """)
            
            text = page.inner_text('body')
            page.close()
            browser.close()
            return f"Contenuto di {url} (via Playwright):\n\n{text[:5000]}"
    except Exception as e:
        logger.error(f"Errore Playwright Browse: {str(e)}")
        return _browse_requests_fallback(url) # Questo a sua volta ora restituisce il suggerimento

def cleanup_browser():
    """Mantenuto per compatibilità, la pulizia è ora gestita dai context manager."""
    pass