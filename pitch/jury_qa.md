# Jury Q&A — From headlines to signals

Line to remember: **the signal is where the headline and the tape disagree.**

One card per MF article: headline, publication time, one body quote; a deterministic read of the stock’s daily tape (move before / same day / later; size vs a normal day; how much is still in the price at the last session, 23 Sep 2026); a verdict on whether the news was already in the price; one Gemini sentence on whether the headline adjective matches the figure in the body. Prices only from BigQuery. Rule frozen: 20-session baseline, 2σ. Aggregate numbers below are from first articles after the 7-day filter (`data/stats.json`, range 2021-02-01 … 2026-09-15, n = 4746).

---

### 1. Why is the daily move `PRZ_LAST / previous session PRZ_RIF − 1`?

**EN:** On the same row, `PRZ_RIF` equals `PRZ_LAST` in 83% of share rows (920,210 of 1,104,769 with valid prices), so a same-row ratio would be zero almost every day. We divide by the previous session’s `PRZ_RIF`, which is the standard Borsa Italiana daily change.

**IT:** Sulla stessa riga `PRZ_RIF` coincide con `PRZ_LAST` nell’83% delle righe azionarie (920.210 su 1.104.769 con prezzi validi), quindi il rapporto sulla stessa riga sarebbe quasi sempre zero. Dividiamo per il `PRZ_RIF` della seduta precedente, cioè la variazione giornaliera standard di Borsa Italiana.

---

### 2. Why 20 sessions and 2 standard deviations? Was anything tuned?

**EN:** The rule is frozen: baseline = the 20 sessions before the article date; unusual = |move| ≥ 2 × that baseline’s sample standard deviation. Nothing was trained, tuned, or backtested — it is a fixed descriptive threshold, not a model.

**IT:** La regola è congelata: baseline = le 20 sedute prima della data dell’articolo; anomalo = |movimento| ≥ 2 × la deviazione standard campionaria di quella baseline. Niente è stato addestrato, calibrato o backtestato: soglia descrittiva fissa, non un modello.

---

### 3. How often is a normal session “unusual” by chance? Why show chance next to our rates?

**EN:** Over about 1.05 million share sessions on Borsa Italiana since February 2021 (no ETFs), **6.2%** are unusual when the 20-session baseline includes the day itself (how the session before the article is judged), and **7.5%** when the baseline is the 20 sessions before it (same day and later). We always show chance next to our rates, so "unusual" means above what any ordinary day would give.

**IT:** Su circa 1,05 milioni di sedute azionarie di Borsa Italiana da febbraio 2021 (esclusi gli ETF), il **6,2%** è anomalo quando la baseline di 20 sedute include il giorno stesso (come giudichiamo la seduta prima dell’articolo) e il **7,5%** quando la baseline sono le 20 sedute precedenti (stesso giorno e dopo). Mostriamo sempre il caso accanto ai nostri tassi: "anomalo" significa sopra quello che darebbe un giorno qualsiasi.

---

### 4. What are the headline aggregate numbers (first articles)?

**EN** (from `headline_numbers` / `first_articles.per_session`):

- The session before an MF story is unusual **7.3%** of the time, against **6.2%** for any session (ratio **1.18**).
- The first session trading on the story is unusual **17.9%** of the time, **2.4** times chance.
- When MF publishes after the close, the same day had already moved unusually in **18.4%** of cases (**2.5** times chance).
- When MF publishes before the open, the same trading day is unusual **15.9%** of the time (**2.1** times chance).
- After that it fades back to chance (7.5%): **12.7%** one session later, **9.4%** two, **8.5%** three, **7.8%** four and five. A move several sessions after a story is weak evidence.

**IT:**

- La seduta prima di un articolo MF è anomala nel **7,3%** dei casi, contro il **6,2%** di una seduta qualsiasi (rapporto **1,18**).
- La prima seduta che tratta sulla notizia è anomala nel **17,9%** dei casi, **2,4** volte il caso.
- Quando MF pubblica dopo la chiusura, lo stesso giorno si era già mosso in modo anomalo nel **18,4%** dei casi (**2,5** volte il caso).
- Quando MF pubblica prima dell’apertura, la stessa seduta è anomala nel **15,9%** dei casi (**2,1** volte il caso).
- Poi torna al livello del caso (7,5%): **12,7%** una seduta dopo, **9,4%** due, **8,5%** tre, **7,8%** quattro e cinque. Un movimento diverse sedute dopo la notizia è un indizio debole.

---

### 5. Timestamps are UTC; titles are often rewritten after the close — how do you handle that?

**EN:** We convert `data_pubblicazione` from UTC to Europe/Rome for the local clock and `pub_date`. `publication_phase` is pre_open / in_session / after_close / non_trading_day from that Rome time. Titles and bodies in the warehouse are the last edited version, often rewritten after the close; `headline_reports_move` flags when the title itself narrates the stock’s price move, so the card does not treat a tape-recap headline as fresh news.

**IT:** Convertiamo `data_pubblicazione` da UTC a Europe/Rome per l’orario locale e la `pub_date`. La `publication_phase` è pre_open / in_session / after_close / non_trading_day da quell’ora di Roma. Titoli e body nel warehouse sono l’ultima versione editata, spesso riscritta dopo la chiusura; `headline_reports_move` segnala quando il titolo racconta il movimento del prezzo, così la card non tratta un riassunto di nastro come notizia fresca.

---

### 6. What does MOSTLY_AT_OPEN mean? Is the 50% rule tuning?

**EN:** For an in-session article whose peak unusual move is on the reaction day, if more than half of that day’s move was already in the opening gap (`open_share` > `OPEN_MAJORITY` = **0.5**), the status is MOSTLY_AT_OPEN. A simple majority is a fixed interpretative cut, not a parameter we fit to maximise a metric.

**IT:** Per un articolo in seduta il cui picco anomalo è sul giorno di reazione, se più della metà del movimento della giornata era già nel gap di apertura (`open_share` > `OPEN_MAJORITY` = **0,5**), lo status è MOSTLY_AT_OPEN. La maggioranza semplice è un taglio interpretativo fisso, non un parametro calibrato per massimizzare una metrica.

---

### 7. How do you match the article to the company without a ticker?

**EN:** Title regex on `DES_AZIONE` (Italian ordinary shares, ISIN `IT%`, length ≥ 3). First letter must be capitalised in the title (unless the name itself starts lowercase, e.g. doValue). Stoplist of everyday/foreign-word names: Reti, Impianti, Energy, Maps, Simone, Plc, Circle, Pattern, Predict, Friends, Adventure, Tecno. Live blogs / daily recaps excluded (`Borse oggi in diretta`, `Cos’è successo oggi`). Keep only titles that match **exactly one** company, with 20 baseline sessions. Limits: no ticker field; missed aliases; multi-name titles dropped; stoplist names never matched.

**IT:** Regex sul titolo contro `DES_AZIONE` (ordinarie italiane, ISIN `IT%`, lunghezza ≥ 3). La prima lettera nel titolo deve essere maiuscola (salvo nomi già minuscoli, es. doValue). Stoplist di nomi-parole comuni: Reti, Impianti, Energy, Maps, Simone, Plc, Circle, Pattern, Predict, Friends, Adventure, Tecno. Esclusi live blog / riepiloghi (`Borse oggi in diretta`, `Cos’è successo oggi`). Solo titoli con **esattamente una** società e 20 sedute di baseline. Limiti: niente ticker; alias mancati; titoli multi-nome esclusi; nomi in stoplist mai matchati.

---

### 8. What is the first-article filter (7 days) and why?

**EN:** Per company, keep an article only if there is no earlier matched article within 7 days by Rome `pub_local` (or it is the first). That cuts clusters of follow-ups on the same name so aggregates are not dominated by the same story told many times (`12867` → `4746` articles).

**IT:** Per società, teniamo un articolo solo se non ce n’è uno precedente entro 7 giorni su `pub_local` di Roma (o è il primo). Così riduciamo i cluster di follow-up sullo stesso nome e gli aggregati non sono dominati dalla stessa storia ripetuta (`12867` → `4746` articoli).

---

### 9. What does Gemini do — and what do the automatic checks enforce?

**EN:** Gemini reads only titolo and body (plus the already-computed price facts as given text). It never does arithmetic and never says buy/sell. It returns one sentence on whether the title adjective matches the figure in the body, and how that fits the tape verdict. Automatic checks: quote verbatim in body; figure in body; adjective in title; no numbers outside article/facts; no recommendation words unless already in the article.

**IT:** Gemini legge solo titolo e body (più i fatti di prezzo già calcolati, come testo dato). Non fa aritmetica e non dice compra/vendi. Restituisce una frase su se l’aggettivo del titolo combacia con la cifra nel body, e come questo si lega al verdetto di nastro. Check automatici: citazione letterale nel body; cifra nel body; aggettivo nel titolo; nessun numero fuori da articolo/fatti; niente parole di raccomandazione se non già nell’articolo.

---

### 10. Is this investment advice or a trading strategy?

**EN:** No. It is a publisher tool that reports facts already in MF copy and in exchange prices — like a clearer byline on timing, not personalised advice under MiFID. There is no portfolio, no signal to trade, no trained alpha model.

**IT:** No. È uno strumento editoriale che riporta fatti già presenti nel testo MF e nei prezzi di borsa — un byline più chiaro sul timing, non consulenza personalizzata ai sensi della MiFID. Nessun portafoglio, nessun segnale di trading, nessun modello di alpha addestrato.

---

### 11. Why can the headline % and our % differ slightly?

**EN:** The article may measure from a different price (the last trade, an intraday level, or a moment before the close), while we always use the last price over the previous session's reference price. A gap like 7.9% against 8.0% is a difference in reference point, not a calculation error.

**IT:** L’articolo può misurare da un prezzo diverso (l’ultimo scambio, un livello intraday o un momento prima della chiusura), mentre noi usiamo sempre l’ultimo prezzo sul prezzo di riferimento della seduta precedente. Uno scarto come 7,9% contro 8,0% è una differenza di riferimento, non un errore di calcolo.

---

### 12. What would production at MF look like?

**EN:** The same SQL runs as a scheduled BigQuery job after each close and writes one card per matched article, shown next to the story on the site. Gemini only writes the sentence and never touches the prices, and the whole thing can be managed from the Enterprise console.

**IT:** Le stesse query girano come job BigQuery programmato dopo ogni chiusura e scrivono una card per articolo, mostrata accanto alla notizia sul sito. Gemini scrive solo la frase e non tocca mai i prezzi; il tutto si gestisce dalla console Enterprise.

---

### 13. What limitations would you admit?

**EN:** Title-only company match (no ticker); last-edited titles can rewrite after the close; daily closes only (no intraday tape beyond open share); frozen 2σ/20-day rule is coarse; a "delayed" move several sessions later is close to chance; Gemini can fail checks and be omitted; descriptive counts, not causal proof that MF caused the move.

**IT:** Match solo sul titolo (niente ticker); titoli last-edit spesso riscritti dopo la chiusura; solo chiusure giornaliere (niente nastro intraday oltre l’open share); regola 2σ/20 sedute grezza; un movimento "ritardato" diverse sedute dopo è vicino al caso; Gemini può fallire i check e essere omesso; conteggi descrittivi, non prova causale che MF abbia causato il movimento.

---

### 14. What are the verdict statuses in one line each?

**EN:** NO_REACTION — no |z|≥2 in the window · ALREADY_IN_PRICE — peak unusual session closed before publication · PARTLY_IN_PRICE — some unusual move before, peak did not · MOSTLY_AT_OPEN — >50% of the day’s move already at the open for an in-session article · REACTED — peak unusual on the reaction session · DELAYED — peak unusual after the reaction session.

**IT:** NO_REACTION — nessun |z|≥2 nella finestra · ALREADY_IN_PRICE — picco anomalo chiuso prima della pubblicazione · PARTLY_IN_PRICE — qualcosa di anomalo prima, ma non il picco · MOSTLY_AT_OPEN — >50% del movimento del giorno già all’apertura per articolo in seduta · REACTED — picco anomalo sulla seduta di reazione · DELAYED — picco anomalo dopo la seduta di reazione.
