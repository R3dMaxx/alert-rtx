"""
Monitor RTX 5070 Ti sui canali Telegram pubblici (versione GitHub Actions).
Legge le pagine web pubbliche https://t.me/s/<canale>, cerca i messaggi nuovi
e, se corrispondono, invia un avviso con il tuo bot Telegram.
Solo libreria standard: nessuna installazione necessaria.
"""
import html
import json
import os
import re
import urllib.parse
import urllib.request

# ---------- CONFIGURAZIONE ----------
CANALI = ["MVOfferte", "prodigeekOfferte", "prophecytechofferte", "JustTrackIt"]

# Riconosce "RTX 5070 Ti", "5070Ti", "5070-ti" ma NON la 5070 liscia
PRODOTTO_RE = re.compile(r"\b5070\s*-?\s*ti\b", re.I)
ESCLUDI = ["laptop", "notebook", "portatile"]
PREZZO_MAX = 1000.0   # avvisa se il prezzo rilevato e' <= a questa soglia
# ------------------------------------

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATO = "stato.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; alert-bot)"}

NUM = r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
PREZZO_RE = re.compile(rf"{NUM}\s*(?:€|eur)|(?:€|eur)\s*{NUM}", re.I)
MIGLIAIA_RE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?")


def estrai_prezzi(testo):
    prezzi = []
    for a, b in PREZZO_RE.findall(testo):
        s = a or b
        if MIGLIAIA_RE.fullmatch(s):
            s = s.replace(".", "").replace(",", ".")   # 1.049,00 -> 1049.00
        else:
            s = s.replace(",", ".")                    # 979,90 -> 979.90
        try:
            prezzi.append(float(s))
        except ValueError:
            pass
    return prezzi


def scarica(canale):
    req = urllib.request.Request(f"https://t.me/s/{canale}", headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def leggi_messaggi(pagina):
    """Ritorna lista di (id, testo, link_esterni) dei messaggi presenti nella pagina."""
    out = []
    for blocco in pagina.split('data-post="')[1:]:
        m = re.match(r'[^/"]+/(\d+)"', blocco)
        if not m:
            continue
        id_ = int(m.group(1))
        t = re.search(r'js-message_text[^>]*>(.*?)</div>', blocco, re.S)
        testo, links = "", []
        if t:
            raw = t.group(1)
            links = [l for l in re.findall(r'href="([^"]+)"', raw) if "t.me/" not in l]
            raw = re.sub(r"<br\s*/?>", "\n", raw)
            testo = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        out.append((id_, testo, html.unescape(" ".join(links[:3]))))
    return out


def invia(testo):
    dati = urllib.parse.urlencode(
        {"chat_id": CHAT_ID, "text": testo, "disable_web_page_preview": "true"}
    ).encode()
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", dati, timeout=20
        )
        return True
    except Exception as e:
        print("Errore invio bot:", e)
        return False


def corrisponde(testo):
    if not PRODOTTO_RE.search(testo):
        return None
    if any(e in testo.lower() for e in ESCLUDI):
        return None
    prezzi = estrai_prezzi(testo)
    if prezzi and min(prezzi) > PREZZO_MAX:
        return None
    return prezzi


def main():
    stato = {}
    if os.path.exists(STATO):
        with open(STATO) as f:
            stato = json.load(f)

    for canale in CANALI:
        try:
            msgs = leggi_messaggi(scarica(canale))
        except Exception as e:
            print(f"[{canale}] errore download: {e}")
            continue
        if not msgs:
            print(f"[{canale}] nessun messaggio letto (canale senza anteprima web?)")
            continue

        ultimo = stato.get(canale)
        nuovo_max = max(i for i, _, _ in msgs)

        if ultimo is None:
            print(f"[{canale}] primo avvio: parto dal messaggio {nuovo_max}, nessun avviso")
        else:
            for id_, testo, links in sorted(msgs):
                if id_ <= ultimo:
                    continue
                prezzi = corrisponde(testo)
                if prezzi is None:
                    continue
                prezzo_txt = (
                    f"Prezzo rilevato: {min(prezzi):.2f} EUR" if prezzi else "Prezzo non rilevato"
                )
                msg = (
                    f"RTX 5070 Ti - {canale}\n{prezzo_txt}\n\n{testo[:500]}\n\n"
                    f"{links}\nhttps://t.me/{canale}/{id_}"
                )
                if not invia(msg):
                    nuovo_max = id_ - 1   # riprova al prossimo giro
                    break
                print(f"[{canale}] avviso inviato per il messaggio {id_}")

        stato[canale] = nuovo_max

    with open(STATO, "w") as f:
        json.dump(stato, f, indent=2)


if __name__ == "__main__":
    main()
