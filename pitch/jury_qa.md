# Jury Q&A — MF news against your investment thesis

Line to remember: **we do not tell you what to buy — we show whether MF facts still support the thesis you wrote.**

The product is an Italian investor desk: example portfolio and watchlist on the sides, MF stories in the middle, company page as one argument — your thesis → what latest results change → MF news grouped by the thesis indicators they touch → a **Decisione da valutare** with actions to consider (held: Mantenere / Aggiungere / Ridurre / Vendere; watchlist: Valutare ingresso / Attendere / Evitare per ora). Prices and matched MF articles come from the warehouse; thesis/earnings/news readings are Gemini with automated quote and number checks; holdings are **demo**. Offline suite: **82** unit tests (`make test`). Manual sample (12 articles): company match **11/12**, strict classification **8/12** (see `eval/manual_article_eval.md`).

---

### 1. What does the product actually do?

**EN:** You state a thesis (motive, up to three indicators, horizon). The desk checks that thesis against the last four earnings windows and against recent MF articles linked to the name, then drafts an indication to evaluate — not an order. With `make serve`, saving an edited thesis marks analysis **Da ricalcolare**, regenerates via the local API, and shows what changed (status, indicators, decision).

**IT:** Scrivi una tesi (motivo, fino a tre indicatori, orizzonte). La scrivania la confronta con gli ultimi quattro earnings e con gli articoli MF recenti sul titolo, poi propone un’indicazione da valutare — non un ordine. Con `make serve`, salvare una tesi modificata marca l’analisi **Da ricalcolare**, la rigenera via API locale e mostra cosa è cambiato (stato, indicatori, decisione).

---

### 2. Is this investment advice or a trading strategy? (MiFID)

**EN:** No. Under a MiFID-style reading it is decision support on public MF copy and exchange prices: an **indication to evaluate**, with explicit disclaimer that it is not an operational order and that no success probability is estimated. There is **no** trained alpha model and **no** claim of personalised advice. The portfolio/watchlist in the demo are **example holdings**, not a live book.

**IT:** No. In ottica MiFID è supporto alla decisione su testi MF pubblici e prezzi di Borsa: un’**indicazione da valutare**, con disclaimer esplicito che non è un ordine operativo e che non stima probabilità di successo. **Nessun** modello di alpha addestrato e **nessuna** consulenza personalizzata. Portafoglio e watchlist nella demo sono **posizioni di esempio**, non un libro reale.

---

### 3. What is real, what is model, what is invented?

**EN:** Three labelled layers: (1) **dataset** — Borsa Italiana prices and MF articles, with source links and separate **price** vs **news** cutoff dates; (2) **model** — Gemini interpretations (earnings vs thesis, news→indicator, decision draft), never treated as raw facts; (3) **example** — demo portfolio weights/positions invented for the hackathon. Stellantis prices stay simulated (Dutch ISIN outside the Italian match universe).

**IT:** Tre livelli etichettati: (1) **dataset** — prezzi Borsa Italiana e articoli MF, con link alle fonti e date di cutoff separate per **prezzi** e **notizie**; (2) **modello** — interpretazioni Gemini (earnings vs tesi, notizie→indicatore, bozza di decisione), mai confusi con i fatti; (3) **esempio** — pesi/posizioni del portafoglio demo inventati per l’hackathon. I prezzi Stellantis restano simulati (ISIN olandese fuori dal match italiano).

---

### 4. What does the company page show above the fold?

**EN:** A compact strip: thesis status after latest results → new supporting / conflicting MF evidence → source (MF link + date) → what to monitor next. Then the full sections: thesis, “Cosa cambia”, four earnings, news analysis by indicator, decision card.

**IT:** Una striscia compatta: stato della tesi dopo gli ultimi risultati → nuove evidenze MF a favore / contro → fonte (link MF + data) → cosa monitorare dopo. Poi le sezioni complete: tesi, “Cosa cambia”, quattro earnings, analisi notizie per indicatore, card decisione.

---

### 5. What are the board scores if not “signals to trade”?

**EN:** Formerly “Segnali impliciti”. They describe **observed historical price reactions around matched articles** (including sessions after publication), scaled from peak move and unusualness vs a 20-session baseline. They are **descriptive of the past, not predictive**, and not a recommendation.

**IT:** Prima “Segnali impliciti”. Descrivono **reazioni di prezzo storiche osservate intorno agli articoli abbinati** (incluse sedute successive), scalate dal picco e dall’anomalia rispetto a una baseline di 20 sedute. Sono **descrittive del passato, non predittive**, e non sono una raccomandazione.

---

### 6. How do you verify numbers and quotes?

**EN:** Gemini never does arithmetic on prices. Pipeline checks: citazione verbatim in the article body at build time; figures present in body; no recommendation wording unless already in the article; thesis facts drop if numbers are not in sources. Manual audit of 12 varied stories (titles/quotes/topics; bodies not in the export): match 11/12, strict type 8/12; main failure mode is homonym match on “Leonardo” (person vs Leonardo SpA). Full article bodies are not shipped in the dashboard bundle — offline re-check is limited to quotes and flags (see `eval/manual_article_eval.md`).

**IT:** Gemini non fa aritmetica sui prezzi. Check in pipeline: citazione letterale nel body in build; cifre presenti nel body; niente linguaggio di raccomandazione se non già nell’articolo; i fatti di tesi cadono se i numeri non sono nelle fonti. Audit manuale su 12 storie variate (titoli/citazioni/topic; body non nell’export): match 11/12, tipo stretto 8/12; errore principale l’omonimia “Leonardo” (persona vs Leonardo SpA). I body completi non sono nel bundle dashboard: la ri-verifica offline si limita a quote e flag (`eval/manual_article_eval.md`).

---

### 7. Why is the daily move `PRZ_LAST / previous session PRZ_RIF − 1`?

**EN:** On the same row, `PRZ_RIF` equals `PRZ_LAST` in 83% of share rows (920,210 of 1,104,769 with valid prices), so a same-row ratio would be zero almost every day. We divide by the previous session’s `PRZ_RIF`, the standard Borsa Italiana daily change.

**IT:** Sulla stessa riga `PRZ_RIF` coincide con `PRZ_LAST` nell’83% delle righe azionarie (920.210 su 1.104.769 con prezzi validi), quindi il rapporto sulla stessa riga sarebbe quasi sempre zero. Dividiamo per il `PRZ_RIF` della seduta precedente, la variazione giornaliera standard di Borsa Italiana.

---

### 8. Why 20 sessions and 2σ? Was anything tuned?

**EN:** Frozen rule: baseline = 20 sessions before the article date; unusual = |move| ≥ 2 × that baseline’s sample standard deviation. Nothing trained, tuned, or backtested — a fixed descriptive threshold, not a model.

**IT:** Regola congelata: baseline = 20 sedute prima della data articolo; anomalo = |movimento| ≥ 2 × la deviazione standard campionaria di quella baseline. Niente addestrato, calibrato o backtestato: soglia descrittiva fissa, non un modello.

---

### 9. Headline aggregates (first articles) — still true?

**EN** (from `data/stats.json` `headline_numbers` / `first_articles.per_session`, range 2021-02-01 … 2026-09-15, n = 4746 after the 7-day filter):

- Session before an MF story unusual **7.3%** vs **6.2%** chance (ratio **1.18**).
- First session trading the story unusual **17.9%**, **2.4×** chance.
- After-close publish: same day already unusual **18.4%** (**2.5×**).
- Pre-open publish: same day unusual **15.9%** (**2.1×**).
- Then fades toward chance (**7.5%**): **12.7% / 9.4% / 8.5% / 7.8%** one to five sessions later.

**IT:** Stessi numeri da `data/stats.json`. La seduta prima è anomala nel **7,3%** (caso **6,2%**); la prima seduta sulla notizia nel **17,9%** (**2,4×**); after-close **18,4%** (**2,5×**); pre-open **15,9%** (**2,1×**); poi rientra verso il caso.

---

### 10. How do you match article → company without a ticker?

**EN:** Title regex on `DES_AZIONE` (Italian ordinaries, ISIN `IT%`, length ≥ 3), capitalised first letter (unless the name is lowercase, e.g. doValue), stoplist of everyday words, live blogs excluded, keep **exactly one** company and 20 baseline sessions. Known limit (confirmed in eval): shared tokens like **Leonardo** pull in Leonardo Maria Del Vecchio / non-issuer stories — mitigation is negative patterns and tighter context, not pretending the match is perfect.

**IT:** Regex sul titolo contro `DES_AZIONE` (ordinarie IT, ISIN `IT%`, ≥ 3), maiuscola iniziale, stoplist, esclusi live blog, solo **esattamente una** società e 20 sedute di baseline. Limite noto (confermato in eval): token condivisi come **Leonardo** agganciano Leonardo Maria Del Vecchio / storie non-emittente — si mitiga con pattern negativi, senza fingere un match perfetto.

---

### 11. What does Gemini do on cards vs on theses?

**EN:** On story cards: reads title+body (+ given price facts as text) and returns one sentence on whether the title adjective matches the body figure and how that sits with the tape verdict. On theses: reads MF bodies for earnings vs your indicators, maps headlines to indicators, and drafts the decision from earnings outcome + news rollup (`decisione.basata_su`). Same refusal of buy/sell language unless already in the source.

**IT:** Sulle card: legge titolo+body (+ fatti di prezzo già calcolati) e scrive una frase su aggettivo del titolo vs cifra nel body e vs verdetto di nastro. Sulle tesi: legge i body MF per earnings vs indicatori, collega i titoli agli indicatori e abbozza la decisione da esito earnings + rollup notizie (`decisione.basata_su`). Stesso divieto di linguaggio compra/vendi se non già in fonte.

---

### 12. What would production at MF look like?

**EN:** Scheduled BigQuery after each close writes matched cards next to stories; thesis rebuild runs when a reader edits indicators (`make serve` / Enterprise job). Gemini never writes prices. Provenance labels stay visible: dataset vs model vs example portfolio.

**IT:** Job BigQuery dopo ogni chiusura scrive le card accanto alle notizie; il rebuild di tesi parte quando il lettore modifica gli indicatori (`make serve` / job Enterprise). Gemini non scrive mai i prezzi. Le etichette di provenienza restano visibili: dataset vs modello vs portafoglio esempio.

---

### 13. What limitations do you admit?

**EN:** Title-only company match (homonyms); last-edited titles; daily closes only; frozen 2σ/20d rule; delayed moves near chance; Gemini can fail checks and be omitted; thesis–news links can be loose; bodies not in the static export; descriptive tape stats ≠ causal proof that MF moved the stock; demo portfolio is invented.

**IT:** Match solo sul titolo (omonimi); titoli last-edit; solo chiusure; regola 2σ/20 grezza; movimenti ritardati vicini al caso; Gemini può fallire i check; link tesi–notizie a volte laschi; body non nell’export statico; stats di nastro descrittive ≠ prova causale; portafoglio demo inventato.

---

### 14. Verdict statuses in one line each?

**EN:** NO_REACTION — no |z|≥2 in the window · ALREADY_IN_PRICE — peak unusual session closed before publication · PARTLY_IN_PRICE — some unusual move before, peak did not · MOSTLY_AT_OPEN — >50% of the day’s move already at the open for an in-session article · REACTED — peak unusual on the reaction session · DELAYED — peak unusual after the reaction session.

**IT:** NO_REACTION — nessun |z|≥2 · ALREADY_IN_PRICE — picco anomalo chiuso prima della pubblicazione · PARTLY_IN_PRICE — anomalo prima ma non il picco · MOSTLY_AT_OPEN — >50% del giorno già in apertura · REACTED — picco sulla seduta di reazione · DELAYED — picco dopo la reazione.
