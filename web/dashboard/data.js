/*
 * DATI DIMOSTRATIVI — fallback simulato.
 * Le tesi (motivo/indicatori) in questo file sono l’input di esempio usato dall’UI e dalla pipeline.
 * esito, earnings e decisione qui sotto sono solo un fallback: quando la pipeline genera
 * data/theses/<TICKER>.json, real_data.js li sovrascrive con analisi verificate sugli articoli MF.
 * Prezzi e notizie possono già essere reali via real_data.js.
 *
 * Questo file contiene solo dati: app.js lo legge da window.DEMO_DATA e non contiene valori.
 *
 * Forma di un'azienda (dopo l’override reale):
 *   nome, ticker, settore, prezzo, valutazione|null
 *   tesi        { orizzonte, motivo, motivoBreve, indicatori[<=3], pesoPrevisto|null }
 *   tesi_usata  { motivo, indicatori[], orizzonte }  — snapshot usato per generare esito
 *   esito       { stato, sintesi, fatti[{testo,citazione,fonte}|str], interpretazioni[],
 *                 indicatori[{nome,stato,testo,citazione,fonte}], metodo? }
 *   decisione   { contesto, azione, motivazione, aFavore[], rischio, cambierebbe } | null
 *   mancano[]   — quando decisione è null
 *   evoluzione  testo breve sui quattro trimestri
 *   earnings[]  dal più vecchio al più recente; ogni trimestre:
 *               { id, label, periodo, data, fatti[], metriche[], guidance|null, cambiato,
 *                 impatto { effetto, testo }, reazione|null, fonti[] }
 *               oppure { id, label, mancante: true }
 *   metriche:   { nome, valore|null, confronto, base: 'a/a'|'t/t'|null, nota }
 */
(function () {
  'use strict';

  const M = (nome, valore, confronto, base, nota) => ({ nome, valore, confronto, base, nota });
  const R = (pct, da, a, nota) => ({ pct, da, a, nota });
  const I = (effetto, testo) => ({ effetto, testo });

  window.DEMO_DATA = {
    aggiornamento: '25 set 2026',

    portafoglio: [
      { ticker: 'PRY', quantita: 430 },
      { ticker: 'ENEL', quantita: 2700 },
      { ticker: 'ISP', quantita: 3950 },
      { ticker: 'LDO', quantita: 325 },
      { ticker: 'STLAM', quantita: 1450 },
      { ticker: 'TIT', quantita: 22400 }
    ],

    watchlist: [
      { ticker: 'REC' },
      { ticker: 'MONC' },
      { ticker: 'SPM' },
      { ticker: 'TPRO' }
    ],

    aziende: {
      /* ---------------------------------------------------------------- PRYSMIAN */
      PRY: {
        nome: 'Prysmian', ticker: 'PRY', settore: 'Cavi e sistemi per l’energia', prezzo: 78.40,
        valutazione: 'P/E atteso 24x, sopra la media a 5 anni (19x)',
        tesi: {
          orizzonte: '3–5 anni',
          motivo: 'Aumento della domanda di data center e di nuove reti elettriche, che richiedono cavi ad alta tensione e in fibra ottica.',
          motivoBreve: 'Domanda di data center e reti elettriche',
          indicatori: ['Portafoglio ordini nella trasmissione', 'Crescita dei ricavi legati ai data center', 'Margine EBITDA rettificato'],
          pesoPrevisto: null
        },
        esito: {
          stato: 'rafforzata',
          sintesi: 'Gli ultimi risultati vanno nella direzione della tua tesi: gli ordini per la trasmissione sono cresciuti ancora e la parte legata ai data center accelera. Il punto da tenere d’occhio è la valutazione, ormai sopra la media storica.',
          fatti: [
            'Portafoglio ordini nella trasmissione a 18,4 miliardi di euro, +12% anno su anno.',
            'Ricavi del segmento Digital Solutions +21% anno su anno, trainati dai cavi in fibra per data center.',
            'Guidance 2026 sull’EBITDA rettificato alzata a 2,45–2,55 miliardi di euro.'
          ],
          interpretazioni: [
            'La domanda dei data center sembra ormai un motore misurabile dei ricavi, non più solo una prospettiva.'
          ]
        },
        decisione: {
          contesto: 'portafoglio', azione: 'mantenere',
          motivazione: 'La tesi si è rafforzata, ma il titolo pesa già circa il 28% del portafoglio e la valutazione è sopra la media storica. Aggiungere aumenterebbe la concentrazione senza un margine di sicurezza evidente.',
          aFavore: ['Ordini in crescita per quattro trimestri di fila', 'Guidance alzata nell’ultimo trimestre', 'Reazione positiva del prezzo ai risultati (+4,8%)'],
          rischio: 'Un rallentamento degli investimenti nei data center colpirebbe proprio il segmento che oggi giustifica il premio di valutazione.',
          cambierebbe: 'Un ritorno dei multipli verso la media storica renderebbe più sensato aggiungere; un calo degli ordini per due trimestri consecutivi indebolirebbe la tesi.'
        },
        evoluzione: 'In quattro trimestri la tesi è passata da un tema citato dal management (3T 2025) a un motore misurabile dei ricavi (2T 2026). L’unico trimestre neutro è stato il 4T 2025, per la debolezza dell’edilizia, che non riguarda la tua tesi.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '6 nov 2025',
            fatti: ['Nuove commesse per collegamenti elettrici sottomarini.', 'Ricavi Digital Solutions +9% anno su anno.', 'Il management cita per la prima volta la domanda dei data center per l’intelligenza artificiale.'],
            metriche: [M('Ricavi', '4,12 mld €', '+6,8%', 'a/a'), M('Margine EBITDA rett.', '12,5%', '+0,3 pp', 'a/a'), M('EPS', '0,81 €', '+7%', 'a/a'), M('Free cash flow', '350 mln €', '+5%', 'a/a')],
            guidance: 'Obiettivi 2025 confermati.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('rafforza', 'Primo segnale esplicito che la domanda dei data center riguarda l’azienda.'),
            reazione: R(3.1, 'chiusura del 5 nov 2025', 'chiusura del 6 nov 2025', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '26 feb 2026',
            fatti: ['Ricavi 2025 in crescita del 6% anno su anno.', 'Dividendo proposto in aumento.', 'Rallentamento temporaneo dei cavi per l’edilizia.'],
            metriche: [M('Ricavi', '4,05 mld €', '+5,2%', 'a/a'), M('Margine EBITDA rett.', '12,2%', '+0,2 pp', 'a/a'), M('EPS', '0,74 €', '+4%', 'a/a'), M('Free cash flow', '690 mln €', '+6%', 'a/a')],
            guidance: 'Obiettivi 2026 di crescita moderata, con priorità alla trasmissione.',
            cambiato: 'Rispetto al 3T 2025 l’edilizia rallenta; la trasmissione resta in linea.',
            impatto: I('invariata', 'Nessuna novità sui data center: tesi confermata ma non rafforzata.'),
            reazione: R(-1.2, 'chiusura del 26 feb 2026', 'chiusura del 27 feb 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '7 mag 2026',
            fatti: ['Ordini nella trasmissione a 17,1 miliardi di euro, nuovo massimo.', 'Ricavi Digital Solutions +14% anno su anno.', 'Aumento del prezzo del rame trasferito in parte sui clienti.'],
            metriche: [M('Ricavi', '4,31 mld €', '+7,4%', 'a/a'), M('Margine EBITDA rett.', '12,9%', '+0,4 pp', 'a/a'), M('EPS', '0,86 €', '+9%', 'a/a'), M('Free cash flow', '−120 mln €', 'era −180 mln €', 'a/a', 'Negativo per stagionalità del primo trimestre.')],
            guidance: 'Guidance 2026 confermata.',
            cambiato: 'Rispetto al 4T 2025 gli ordini crescono ancora e i margini tengono nonostante il rame.',
            impatto: I('rafforza', 'Ordini e data center in crescita insieme, come previsto dalla tesi.'),
            reazione: R(1.9, 'chiusura del 6 mag 2026', 'chiusura del 7 mag 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '30 lug 2026',
            fatti: ['Ordini nella trasmissione a 18,4 miliardi di euro, +12% anno su anno.', 'Ricavi Digital Solutions +21% anno su anno.', 'Guidance 2026 sull’EBITDA rettificato alzata.'],
            metriche: [M('Ricavi', '4,62 mld €', '+9,1%', 'a/a'), M('Margine EBITDA rett.', '13,6%', '+0,8 pp', 'a/a'), M('EPS', '0,98 €', '+14%', 'a/a'), M('Free cash flow', '410 mln €', '+18%', 'a/a')],
            guidance: 'EBITDA rettificato 2026 atteso tra 2,45 e 2,55 miliardi di euro (prima 2,35–2,45).',
            cambiato: 'Rispetto al 1T 2026 i ricavi dei data center accelerano (da +14% a +21%) e la guidance viene alzata.',
            impatto: I('rafforza', 'Conferma diretta del motivo di investimento: la domanda dei data center cresce più delle attese.'),
            reazione: R(4.8, 'chiusura del 30 lug 2026', 'chiusura del 31 lug 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          }
        ]
      },

      /* ---------------------------------------------------------------- ENEL */
      ENEL: {
        nome: 'Enel', ticker: 'ENEL', settore: 'Energia e reti', prezzo: 8.914,
        valutazione: 'P/E atteso 11x, in linea con la media a 5 anni',
        tesi: {
          orizzonte: 'Oltre 5 anni',
          motivo: 'Forte generazione di free cash flow e un dividendo stabile, sostenuti dalle reti elettriche regolate.',
          motivoBreve: 'Free cash flow e dividendo stabile',
          indicatori: ['Free cash flow dopo gli investimenti', 'Debito netto / EBITDA', 'Dividendo per azione confermato'],
          pesoPrevisto: null
        },
        esito: {
          stato: 'invariata',
          sintesi: 'I risultati non cambiano il quadro: il cash flow è in linea con il piano e il dividendo è confermato. Il debito resta alto ma stabile.',
          fatti: [
            'Free cash flow del trimestre 1,2 miliardi di euro, +4% anno su anno.',
            'Dividendo 2026 confermato a 0,47 euro per azione.',
            'Debito netto a 58,9 miliardi di euro, stabile rispetto a marzo.'
          ],
          interpretazioni: [
            'Il dividendo appare coperto dal cash flow, ma con poco spazio per aumenti.',
            'Finché il debito non scende, la sensibilità ai tassi resta il punto debole.'
          ]
        },
        decisione: {
          contesto: 'portafoglio', azione: 'mantenere',
          motivazione: 'La tesi è intatta e il tuo orizzonte è lungo; un peso intorno al 20% è coerente con un titolo difensivo. Non emergono elementi né per aumentare né per ridurre.',
          aFavore: ['Dividendo confermato', 'Cash flow in linea con il piano', 'Valutazione nella media storica'],
          rischio: 'Un rialzo dei tassi aumenterebbe il costo del debito e ridurrebbe lo spazio per il dividendo.',
          cambierebbe: 'Un taglio del dividendo o un debito sopra 3 volte l’EBITDA indebolirebbero la tesi; una riduzione del debito la rafforzerebbe.'
        },
        evoluzione: 'Tesi stabile. Il 4T 2025 l’ha rafforzata con il dividendo minimo garantito nel nuovo piano; gli altri trimestri l’hanno confermata senza novità. L’elemento da seguire è il debito.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '7 nov 2025',
            fatti: ['Utile ordinario in linea con le attese.', 'Investimenti nelle reti +6% anno su anno.', 'Debito netto sostanzialmente stabile.'],
            metriche: [M('Ricavi', '19,6 mld €', '−4,2%', 'a/a'), M('Margine operativo', '15,9%', '+0,4 pp', 'a/a'), M('EPS', '0,16 €', '+1%', 'a/a'), M('Free cash flow', null, '', null, 'Non comunicato per il singolo trimestre.')],
            guidance: 'Obiettivi 2025 confermati.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('invariata', 'Nessun elemento nuovo su cash flow o dividendo.'),
            reazione: R(0.2, 'chiusura del 6 nov 2025', 'chiusura del 7 nov 2025', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '13 mar 2026',
            fatti: ['Nuovo piano 2026–2028 con dividendo minimo garantito.', 'Utile ordinario 2025 +3% anno su anno.', 'Più investimenti nelle reti regolate.'],
            metriche: [M('Ricavi', '21,2 mld €', '−2,0%', 'a/a'), M('Margine operativo', '15,8%', '+0,5 pp', 'a/a'), M('EPS', '0,16 €', '+3%', 'a/a'), M('Free cash flow', '1,6 mld €', '+12%', 'a/a')],
            guidance: 'Dividendo minimo di 0,47 euro per azione fino al 2028.',
            cambiato: 'Rispetto al 3T 2025 arriva un impegno esplicito sul dividendo.',
            impatto: I('rafforza', 'Il dividendo minimo garantito sostiene direttamente il motivo di investimento.'),
            reazione: R(2.3, 'chiusura del 12 mar 2026', 'chiusura del 13 mar 2026', 'Risultati e piano presentati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '8 mag 2026',
            fatti: ['Ricavi in calo per prezzi dell’energia più bassi.', 'Investimenti nelle reti +8% anno su anno.', 'Debito netto in lieve aumento a 59,3 miliardi di euro.'],
            metriche: [M('Ricavi', '20,4 mld €', '−5,0%', 'a/a'), M('Margine operativo', '17,1%', '+0,7 pp', 'a/a'), M('EPS', '0,19 €', '+2%', 'a/a'), M('Free cash flow', '0,9 mld €', '−3%', 'a/a')],
            guidance: 'Guidance 2026 confermata.',
            cambiato: 'Rispetto al 4T 2025 il debito sale leggermente; il cash flow cala di poco.',
            impatto: I('invariata', 'Piccolo peggioramento del debito, non sufficiente a cambiare la tesi.'),
            reazione: R(-0.4, 'chiusura del 7 mag 2026', 'chiusura dell’8 mag 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '29 lug 2026',
            fatti: ['Free cash flow 1,2 miliardi di euro, +4% anno su anno.', 'Dividendo 2026 confermato.', 'Debito netto stabile a 58,9 miliardi di euro.'],
            metriche: [M('Ricavi', '18,9 mld €', '−3,1%', 'a/a'), M('Margine operativo', '16,4%', '+0,6 pp', 'a/a'), M('EPS', '0,17 €', '+2%', 'a/a'), M('Free cash flow', '1,2 mld €', '+4%', 'a/a')],
            guidance: 'Obiettivi 2026 e dividendo confermati.',
            cambiato: 'Rispetto al 1T 2026 il debito smette di salire e il cash flow torna a crescere.',
            impatto: I('invariata', 'Tesi confermata: cash flow e dividendo in linea con il piano.'),
            reazione: R(0.6, 'chiusura del 29 lug 2026', 'chiusura del 30 lug 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          }
        ]
      },

      /* ---------------------------------------------------------------- INTESA SANPAOLO */
      ISP: {
        nome: 'Intesa Sanpaolo', ticker: 'ISP', settore: 'Banche', prezzo: 5.482,
        valutazione: 'P/E atteso 8x, sotto la media delle banche europee (9x)',
        tesi: {
          orizzonte: '3–5 anni',
          motivo: 'Utili elevati e una distribuzione generosa agli azionisti, tra dividendi e riacquisto di azioni proprie.',
          motivoBreve: 'Utili elevati e distribuzione agli azionisti',
          indicatori: ['Utile netto trimestrale', 'CET1 ratio (solidità del capitale)', 'Distribuzione annunciata agli azionisti'],
          pesoPrevisto: null
        },
        esito: {
          stato: 'rafforzata',
          sintesi: 'Utile e solidità del capitale sono sopra le attese e la banca ha annunciato un nuovo riacquisto di azioni. Il calo dei tassi pesa sul margine di interesse, ma è compensato dalla crescita delle commissioni.',
          fatti: [
            'Utile netto semestrale 5,1 miliardi di euro, +6% anno su anno.',
            'CET1 ratio al 13,9%, sopra l’obiettivo del 12%.',
            'Nuovo riacquisto di azioni proprie da 2 miliardi di euro.'
          ],
          interpretazioni: [
            'La crescita delle commissioni rende gli utili meno dipendenti dai tassi.',
            'Con un peso intorno al 18% e un orizzonte di 3–5 anni resta spazio per un aumento graduale.'
          ]
        },
        decisione: {
          contesto: 'portafoglio', azione: 'aggiungere',
          motivazione: 'La tesi si è rafforzata per due trimestri consecutivi, la valutazione resta contenuta e il peso attuale lascia spazio in un orizzonte di 3–5 anni. Un eventuale aumento andrebbe valutato in modo graduale.',
          aFavore: ['Nuovo riacquisto di azioni', 'Capitale sopra gli obiettivi', 'Valutazione sotto la media del settore'],
          rischio: 'Un calo dei tassi più rapido del previsto ridurrebbe il margine di interesse, ancora la prima fonte di utile.',
          cambierebbe: 'Un aumento dei crediti deteriorati o una distribuzione inferiore al piano renderebbero preferibile mantenere.'
        },
        evoluzione: 'Da invariata a rafforzata: nei primi due trimestri della serie il calo dei tassi pesava sul margine; negli ultimi due le commissioni e il nuovo riacquisto di azioni hanno sostenuto la tesi.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '4 nov 2025',
            fatti: ['Margine di interesse in calo per la discesa dei tassi.', 'Commissioni +4% anno su anno.', 'Costo del rischio ai minimi storici.'],
            metriche: [M('Proventi operativi', '6,8 mld €', '−1,2%', 'a/a'), M('Margine operativo', '54,1%', '−0,4 pp', 'a/a'), M('EPS', '0,25 €', '+2%', 'a/a'), M('Free cash flow', null, '', null, 'Non applicabile a una banca.')],
            guidance: 'Utile 2025 atteso intorno a 9 miliardi di euro.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('invariata', 'Utili solidi ma sotto pressione per i tassi: nessun cambiamento.'),
            reazione: R(-1.1, 'chiusura del 3 nov 2025', 'chiusura del 4 nov 2025', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '4 feb 2026',
            fatti: ['Utile 2025 record.', 'Distribuzione in linea con il piano.', 'CET1 ratio al 13,6%.'],
            metriche: [M('Proventi operativi', '6,9 mld €', '+0,5%', 'a/a'), M('Margine operativo', '54,6%', '+0,2 pp', 'a/a'), M('EPS', '0,26 €', '+4%', 'a/a'), M('Free cash flow', null, '', null, 'Non applicabile a una banca.')],
            guidance: 'Utile 2026 atteso intorno a 9 miliardi di euro.',
            cambiato: 'Rispetto al 3T 2025 il margine di interesse si stabilizza.',
            impatto: I('invariata', 'Tesi confermata, senza distribuzioni aggiuntive.'),
            reazione: R(0.3, 'chiusura del 3 feb 2026', 'chiusura del 4 feb 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '5 mag 2026',
            fatti: ['Utile netto +5% anno su anno.', 'Commissioni da risparmio gestito +8%.', 'CET1 ratio al 13,8%.'],
            metriche: [M('Proventi operativi', '7,0 mld €', '+1,5%', 'a/a'), M('Margine operativo', '55,0%', '+0,5 pp', 'a/a'), M('EPS', '0,28 €', '+6%', 'a/a'), M('Free cash flow', null, '', null, 'Non applicabile a una banca.')],
            guidance: 'Utile 2026 atteso sopra 9 miliardi di euro.',
            cambiato: 'Rispetto al 4T 2025 le commissioni accelerano e la guidance migliora.',
            impatto: I('rafforza', 'Più utile e più capitale disponibile per gli azionisti.'),
            reazione: R(1.4, 'chiusura del 4 mag 2026', 'chiusura del 5 mag 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '31 lug 2026',
            fatti: ['Utile netto semestrale 5,1 miliardi di euro, +6% anno su anno.', 'CET1 ratio al 13,9%.', 'Nuovo riacquisto di azioni da 2 miliardi di euro.'],
            metriche: [M('Proventi operativi', '7,1 mld €', '+1,8%', 'a/a'), M('Margine operativo', '55,2%', '+0,6 pp', 'a/a'), M('EPS', '0,29 €', '+7%', 'a/a'), M('Free cash flow', null, '', null, 'Non applicabile a una banca.')],
            guidance: 'Utile 2026 atteso sopra 9 miliardi di euro, con distribuzione aggiuntiva.',
            cambiato: 'Rispetto al 1T 2026 arriva il nuovo riacquisto di azioni.',
            impatto: I('rafforza', 'La distribuzione agli azionisti, cuore della tesi, aumenta.'),
            reazione: R(2.6, 'chiusura del 30 lug 2026', 'chiusura del 31 lug 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          }
        ]
      },

      /* ---------------------------------------------------------------- LEONARDO */
      LDO: {
        nome: 'Leonardo', ticker: 'LDO', settore: 'Aerospazio e difesa', prezzo: 51.86,
        valutazione: 'P/E atteso 22x, salito da 14x in un anno',
        tesi: {
          orizzonte: '3–5 anni',
          motivo: 'Crescita della spesa per la difesa in Europa, con ordini pluriennali per elettronica ed elicotteri.',
          motivoBreve: 'Spesa europea per la difesa',
          indicatori: ['Ordini acquisiti (book-to-bill)', 'Ricavi dell’elettronica per la difesa', 'Free cash flow operativo'],
          pesoPrevisto: null
        },
        esito: {
          stato: 'invariata',
          sintesi: 'Gli ordini restano forti, ma il free cash flow del semestre è più debole del previsto. La tesi non è messa in discussione, ma in questo trimestre non si rafforza.',
          fatti: [
            'Ordini semestrali 11,2 miliardi di euro, rapporto ordini/ricavi 1,2.',
            'Ricavi +8% anno su anno.',
            'Free cash flow operativo semestrale −0,6 miliardi di euro, peggiore dell’anno precedente.'
          ],
          interpretazioni: [
            'Il cash flow negativo del semestre è in parte stagionale: andrà verificato a fine anno.',
            'La domanda europea di difesa resta il motore principale, come prevede la tesi.'
          ]
        },
        decisione: {
          contesto: 'portafoglio', azione: 'mantenere',
          motivazione: 'Tesi invariata, peso già significativo e valutazione molto salita nell’ultimo anno. In attesa di conferme sul cash flow ha senso mantenere la posizione così com’è.',
          aFavore: ['Ordini superiori ai ricavi', 'Guidance annuale confermata'],
          rischio: 'Ritardi nei pagamenti dei governi o revisioni dei bilanci della difesa.',
          cambierebbe: 'Un free cash flow annuale in linea con la guidance (0,9 miliardi di euro) renderebbe la tesi più solida.'
        },
        evoluzione: 'La tesi si è rafforzata tra fine 2025 e inizio 2026 con ordini record; nell’ultimo trimestre il cash flow più debole l’ha riportata a invariata.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '5 nov 2025',
            fatti: ['Ordini in crescita del 9% nei nove mesi.', 'Ricavi elicotteri stabili.', 'Guidance 2025 confermata.'],
            metriche: [M('Ricavi', '4,3 mld €', '+6%', 'a/a'), M('Margine operativo', '8,4%', '+0,2 pp', 'a/a'), M('EPS', '0,31 €', '+5%', 'a/a'), M('Free cash flow', '−0,2 mld €', 'era −0,3 mld €', 'a/a')],
            guidance: 'Obiettivi 2025 confermati.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('invariata', 'Andamento in linea, senza sorprese.'),
            reazione: R(0.8, 'chiusura del 4 nov 2025', 'chiusura del 5 nov 2025', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '10 mar 2026',
            fatti: ['Ordini 2025 record.', 'Nuovi contratti europei nell’elettronica per la difesa.', 'Free cash flow annuale sopra la guidance.'],
            metriche: [M('Ricavi', '6,1 mld €', '+10%', 'a/a'), M('Margine operativo', '10,2%', '+0,6 pp', 'a/a'), M('EPS', '0,62 €', '+12%', 'a/a'), M('Free cash flow', '1,4 mld €', '+15%', 'a/a')],
            guidance: 'Crescita dei ricavi 2026 attesa intorno all’8%.',
            cambiato: 'Rispetto al 3T 2025 accelerano ordini e cash flow.',
            impatto: I('rafforza', 'Gli ordini confermano la crescita della spesa europea.'),
            reazione: R(4.2, 'chiusura del 10 mar 2026', 'chiusura dell’11 mar 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '6 mag 2026',
            fatti: ['Ordini +18% anno su anno.', 'Ricavi dell’elettronica per la difesa +12%.', 'Guidance 2026 confermata.'],
            metriche: [M('Ricavi', '4,1 mld €', '+9%', 'a/a'), M('Margine operativo', '7,9%', '+0,3 pp', 'a/a'), M('EPS', '0,24 €', '+10%', 'a/a'), M('Free cash flow', '−1,0 mld €', 'era −0,9 mld €', 'a/a', 'Stagionalmente negativo nel primo trimestre.')],
            guidance: 'Guidance 2026 confermata.',
            cambiato: 'Rispetto al 4T 2025 gli ordini crescono ancora; il cash flow resta stagionalmente negativo.',
            impatto: I('rafforza', 'Ordini in forte crescita, coerenti con la tesi.'),
            reazione: R(3.5, 'chiusura del 5 mag 2026', 'chiusura del 6 mag 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '31 lug 2026',
            fatti: ['Ordini semestrali 11,2 miliardi di euro.', 'Ricavi +8% anno su anno.', 'Free cash flow semestrale più debole dell’anno precedente.'],
            metriche: [M('Ricavi', '4,6 mld €', '+8%', 'a/a'), M('Margine operativo', '8,6%', '+0,2 pp', 'a/a'), M('EPS', '0,33 €', '+6%', 'a/a'), M('Free cash flow', '0,4 mld €', '−0,1 mld €', 't/t')],
            guidance: 'Guidance 2026 confermata, compreso un free cash flow di circa 0,9 miliardi di euro.',
            cambiato: 'Rispetto al 1T 2026 la crescita degli ordini rallenta e il cash flow non recupera quanto atteso.',
            impatto: I('invariata', 'Ordini ancora buoni, ma il cash flow non conferma: nessun rafforzamento.'),
            reazione: R(-2.1, 'chiusura del 30 lug 2026', 'chiusura del 31 lug 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          }
        ]
      },

      /* ---------------------------------------------------------------- STELLANTIS */
      STLAM: {
        nome: 'Stellantis', ticker: 'STLAM', settore: 'Automobili', prezzo: 9.12,
        valutazione: 'P/E atteso 7x, sotto la media a 5 anni (5x nei minimi del 2020)',
        tesi: {
          orizzonte: '1–3 anni',
          motivo: 'Ripresa dei margini in Nord America grazie a nuovi modelli e a scorte più basse presso i concessionari.',
          motivoBreve: 'Ripresa dei margini in Nord America',
          indicatori: ['Margine operativo rettificato Nord America', 'Scorte presso i concessionari USA', 'Free cash flow industriale'],
          pesoPrevisto: null
        },
        esito: {
          stato: 'indebolita',
          sintesi: 'I margini in Nord America non sono ripartiti e il free cash flow industriale è negativo. Due dei tre indicatori che segui vanno nella direzione opposta alla tesi.',
          fatti: [
            'Margine operativo rettificato Nord America al 3,1%, −2,4 punti anno su anno.',
            'Free cash flow industriale semestrale −2,3 miliardi di euro.',
            'Guidance 2026 sul margine abbassata a “bassa cifra singola”.'
          ],
          interpretazioni: [
            'La ripresa dei margini sembra rinviata al 2027, oltre il tuo orizzonte di 1–3 anni.',
            'La riduzione delle scorte procede: è l’unico indicatore a favore.'
          ]
        },
        decisione: {
          contesto: 'portafoglio', azione: 'ridurre',
          motivazione: 'La tesi si è indebolita per due trimestri e i tempi della ripresa si allungano rispetto al tuo orizzonte. Ridurre il peso limiterebbe l’esposizione a una tesi non confermata, senza chiudere del tutto la posizione.',
          aFavore: ['Margini Nord America in calo per due trimestri', 'Guidance abbassata', 'Reazione negativa del prezzo ai risultati (−6,2%)'],
          rischio: 'Il prezzo sconta già molte notizie negative: un recupero rapido dei margini renderebbe la riduzione prematura.',
          cambierebbe: 'Un margine Nord America di nuovo sopra il 6% nel prossimo trimestre riaprirebbe la tesi.'
        },
        evoluzione: 'Da invariata a indebolita: nel 2025 la tesi era ancora aperta, nel 2026 due trimestri consecutivi di margini in calo l’hanno messa in discussione.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '30 ott 2025',
            fatti: ['Consegne in Nord America −4% anno su anno.', 'Scorte presso i concessionari in calo.', 'Nuovi modelli annunciati per il 2026.'],
            metriche: [M('Ricavi', '37,2 mld €', '−3%', 'a/a'), M('Margine operativo', '5,1%', '−1,0 pp', 'a/a'), M('EPS', null, '', null, 'Non comunicato nel trimestre.'), M('Free cash flow', null, '', null, 'Comunicato solo su base semestrale.')],
            guidance: 'Ripresa attesa nella seconda metà del 2026.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('invariata', 'Tesi ancora aperta: la ripresa è attesa più avanti.'),
            reazione: R(-0.5, 'chiusura del 29 ott 2025', 'chiusura del 30 ott 2025', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '26 feb 2026',
            fatti: ['Scorte USA scese sotto l’obiettivo.', 'Margine annuale 5,5%.', 'Dividendo ridotto.'],
            metriche: [M('Ricavi', '152 mld €', '−8%', 'a/a'), M('Margine operativo', '5,5%', '−4,5 pp', 'a/a'), M('EPS', '1,21 €', '−38%', 'a/a'), M('Free cash flow', '−1,1 mld €', 'era +4,2 mld €', 'a/a')],
            guidance: 'Margine 2026 atteso a “media cifra singola”.',
            cambiato: 'Rispetto al 3T 2025 le scorte migliorano, i margini no.',
            impatto: I('invariata', 'Un indicatore migliora e uno peggiora: quadro ancora incerto.'),
            reazione: R(1.1, 'chiusura del 25 feb 2026', 'chiusura del 26 feb 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '30 apr 2026',
            fatti: ['Consegne in Nord America −7% anno su anno.', 'Margine Nord America in calo.', 'Ritardi nel lancio di due nuovi modelli.'],
            metriche: [M('Ricavi', '35,8 mld €', '−6%', 'a/a'), M('Margine operativo', '4,2%', '−0,9 pp', 't/t'), M('EPS', null, '', null, 'Non comunicato nel trimestre.'), M('Free cash flow', null, '', null, 'Comunicato solo su base semestrale.')],
            guidance: 'Guidance 2026 confermata con cautela.',
            cambiato: 'Rispetto al 4T 2025 i margini scendono ancora e i lanci slittano.',
            impatto: I('indebolisce', 'La ripresa dei margini non si vede e i nuovi modelli arrivano in ritardo.'),
            reazione: R(-3.4, 'chiusura del 29 apr 2026', 'chiusura del 30 apr 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '29 lug 2026',
            fatti: ['Margine Nord America al 3,1%, −2,4 punti anno su anno.', 'Free cash flow industriale semestrale −2,3 miliardi di euro.', 'Guidance sul margine abbassata.'],
            metriche: [M('Ricavi', '36,4 mld €', '−5%', 'a/a'), M('Margine operativo', '3,8%', '−2,0 pp', 'a/a'), M('EPS', '0,38 €', '−41%', 'a/a', 'Dato semestrale.'), M('Free cash flow', '−2,3 mld €', 'era −0,4 mld €', 'a/a', 'Dato semestrale.')],
            guidance: 'Margine 2026 atteso a “bassa cifra singola” (prima “media cifra singola”).',
            cambiato: 'Rispetto al 1T 2026 peggiorano sia i margini sia il cash flow; la guidance viene tagliata.',
            impatto: I('indebolisce', 'Due indicatori su tre vanno contro la tesi e i tempi si allungano.'),
            reazione: R(-6.2, 'chiusura del 28 lug 2026', 'chiusura del 29 lug 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          }
        ]
      },

      /* ---------------------------------------------------------------- TELECOM ITALIA */
      TIT: {
        nome: 'Telecom Italia', ticker: 'TIT', settore: 'Telecomunicazioni', prezzo: 0.4821,
        valutazione: 'Valore d’impresa / EBITDA 4,5x, vicino ai concorrenti europei',
        tesi: {
          orizzonte: '1–3 anni',
          motivo: 'Valorizzazione della rete fissa con la cessione e conseguente riduzione del debito.',
          motivoBreve: 'Cessione della rete e riduzione del debito',
          indicatori: ['Debito netto dopo la cessione', 'Ricavi da servizi in Italia', 'Remunerazione degli azionisti'],
          pesoPrevisto: null
        },
        esito: {
          stato: 'indebolita',
          sintesi: 'La cessione della rete è completata e il debito è sceso: l’evento su cui si basava la tua tesi si è già realizzato. Quello che resta, ricavi in Italia in calo e nessuna distribuzione agli azionisti, non la sostiene.',
          fatti: [
            'Debito netto a 7,8 miliardi di euro dopo la cessione, dimezzato in un anno.',
            'Ricavi da servizi in Italia −3% anno su anno.',
            'Nessun dividendo previsto per il 2026.'
          ],
          interpretazioni: [
            'Il beneficio della cessione sembra già riflesso nel prezzo dopo la reazione del 4T 2025.',
            'Senza un nuovo motore di crescita la tesi originale non ha più un catalizzatore.'
          ]
        },
        decisione: {
          contesto: 'portafoglio', azione: 'vendere',
          motivazione: 'Il motivo per cui hai comprato si è realizzato ed è in larga parte già nel prezzo. Ciò che resta non sostiene la tesi, e con un orizzonte di 1–3 anni non emerge un nuovo catalizzatore.',
          aFavore: ['Obiettivo della tesi raggiunto', 'Ricavi in Italia in calo', 'Nessuna remunerazione per gli azionisti'],
          rischio: 'Un’eventuale operazione straordinaria (fusione o offerta) potrebbe far salire il prezzo dopo la vendita.',
          cambierebbe: 'Un piano credibile di distribuzione agli azionisti o di consolidamento del mercato italiano.'
        },
        evoluzione: 'La tesi ha raggiunto il suo obiettivo nel 4T 2025, con la cessione e la riduzione del debito. Da allora i trimestri non hanno aggiunto nuovi motivi per restare investiti.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '6 nov 2025',
            fatti: ['Autorizzazioni alla cessione della rete in via di completamento.', 'Ricavi da servizi in Italia −2%.', 'Debito netto ancora sopra 20 miliardi di euro.'],
            metriche: [M('Ricavi', '3,5 mld €', '−2%', 'a/a'), M('Margine operativo', '9,1%', '−0,3 pp', 'a/a'), M('EPS', '−0,01 €', 'era −0,01 €', 'a/a'), M('Free cash flow', '0,1 mld €', 'stabile', 'a/a')],
            guidance: 'Chiusura della cessione attesa entro fine anno.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('invariata', 'In attesa della chiusura della cessione.'),
            reazione: R(-0.9, 'chiusura del 5 nov 2025', 'chiusura del 6 nov 2025', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '12 mar 2026',
            fatti: ['Cessione della rete completata.', 'Debito netto dimezzato.', 'Nuovo piano senza dividendo.'],
            metriche: [M('Ricavi', '3,6 mld €', '−3%', 'a/a'), M('Margine operativo', '8,4%', '−0,7 pp', 'a/a'), M('EPS', '0,02 €', 'era −0,02 €', 'a/a'), M('Free cash flow', '0,3 mld €', '+0,2 mld €', 'a/a')],
            guidance: 'Riduzione del debito completata; focus su efficienza.',
            cambiato: 'Rispetto al 3T 2025 la cessione è conclusa.',
            impatto: I('rafforza', 'L’obiettivo della tesi si realizza: debito dimezzato.'),
            reazione: R(5.8, 'chiusura dell’11 mar 2026', 'chiusura del 12 mar 2026', 'Risultati pubblicati prima dell’apertura.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '13 mag 2026',
            fatti: ['Primo trimestre senza la rete.', 'Ricavi da servizi in Italia −3%.', 'Costi in calo del 6%.'],
            metriche: [M('Ricavi', '3,3 mld €', '−3%', 'a/a'), M('Margine operativo', '7,9%', '−0,5 pp', 't/t'), M('EPS', '0,00 €', 'era −0,01 €', 'a/a'), M('Free cash flow', '0,1 mld €', '−0,2 mld €', 't/t')],
            guidance: 'Guidance 2026 confermata.',
            cambiato: 'Rispetto al 4T 2025 manca un nuovo motore dopo la cessione.',
            impatto: I('invariata', 'Nessun nuovo elemento a favore o contro.'),
            reazione: R(0.5, 'chiusura del 12 mag 2026', 'chiusura del 13 mag 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '5 ago 2026',
            fatti: ['Debito netto a 7,8 miliardi di euro.', 'Ricavi da servizi in Italia −3%.', 'Confermata l’assenza di dividendo nel 2026.'],
            metriche: [M('Ricavi', '3,3 mld €', '−3%', 'a/a'), M('Margine operativo', '7,6%', '−0,3 pp', 't/t'), M('EPS', '−0,01 €', 'era 0,00 €', 't/t'), M('Free cash flow', '0,05 mld €', '−0,05 mld €', 't/t')],
            guidance: 'Nessuna distribuzione agli azionisti nel 2026.',
            cambiato: 'Rispetto al 1T 2026 i ricavi continuano a calare e si esclude il dividendo.',
            impatto: I('indebolisce', 'Obiettivo già raggiunto e nessun nuovo motivo per restare investiti.'),
            reazione: R(-4.0, 'chiusura del 4 ago 2026', 'chiusura del 5 ago 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          }
        ]
      },

      /* ================================================================ WATCHLIST */

      /* ---------------------------------------------------------------- RECORDATI */
      REC: {
        nome: 'Recordati', ticker: 'REC', settore: 'Farmaceutico', prezzo: 49.60,
        valutazione: 'P/E atteso 17x, sotto la media a 5 anni (20x) dopo il calo estivo',
        tesi: {
          orizzonte: '3–5 anni',
          motivo: 'Crescita dei farmaci per malattie rare, un mercato con pochi concorrenti e margini elevati.',
          motivoBreve: 'Crescita dei farmaci per malattie rare',
          indicatori: ['Crescita dei ricavi malattie rare', 'Margine EBITDA', 'Debito netto / EBITDA'],
          pesoPrevisto: 5
        },
        esito: {
          stato: 'rafforzata',
          sintesi: 'I farmaci per malattie rare crescono a doppia cifra e i margini restano elevati. La tesi è confermata per il quarto trimestre di fila.',
          fatti: [
            'Ricavi malattie rare +14% anno su anno.',
            'Margine EBITDA al 37,8%.',
            'Debito netto sceso a 2,1 volte l’EBITDA.'
          ],
          interpretazioni: [
            'La crescita non dipende da un solo farmaco: il rischio di concentrazione si riduce.',
            'Il calo del prezzo in estate non sembra legato ai risultati.'
          ]
        },
        decisione: {
          contesto: 'watchlist', azione: 'valutare_ingresso',
          motivazione: 'La tesi è confermata negli ultimi quattro trimestri e la valutazione è scesa sotto la media storica. Il peso previsto del 5% è compatibile con un ingresso graduale.',
          aFavore: ['Crescita a doppia cifra nelle malattie rare', 'Margini stabili sopra il 37%', 'Valutazione sotto la media a 5 anni'],
          rischio: 'La concorrenza dei farmaci generici sui prodotti con brevetto in scadenza.',
          cambierebbe: 'Un rallentamento delle malattie rare sotto il +8% o un’acquisizione molto costosa.'
        },
        evoluzione: 'Tesi confermata in tutti e quattro i trimestri; nel 4T 2025 il rallentamento dei farmaci tradizionali non ha toccato le malattie rare.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '30 ott 2025',
            fatti: ['Ricavi malattie rare +12%.', 'Margine EBITDA al 37,2%.', 'Guidance alzata.'],
            metriche: [M('Ricavi', '0,62 mld €', '+9%', 'a/a'), M('Margine EBITDA', '37,2%', '+0,4 pp', 'a/a'), M('EPS', '0,72 €', '+10%', 'a/a'), M('Free cash flow', '0,15 mld €', '+8%', 'a/a')],
            guidance: 'Guidance 2025 alzata.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('rafforza', 'Crescita delle malattie rare sopra le attese.'),
            reazione: R(2.2, 'chiusura del 29 ott 2025', 'chiusura del 30 ott 2025', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '26 feb 2026',
            fatti: ['Ricavi malattie rare +11%.', 'Farmaci tradizionali in lieve calo.', 'Dividendo in aumento.'],
            metriche: [M('Ricavi', '0,63 mld €', '+6%', 'a/a'), M('Margine EBITDA', '36,9%', '−0,1 pp', 'a/a'), M('EPS', '0,70 €', '+6%', 'a/a'), M('Free cash flow', '0,17 mld €', '+5%', 'a/a')],
            guidance: 'Crescita 2026 attesa tra 6% e 8%.',
            cambiato: 'Rispetto al 3T 2025 rallentano i farmaci tradizionali, non le malattie rare.',
            impatto: I('invariata', 'La parte legata alla tesi tiene; il resto rallenta.'),
            reazione: R(-0.8, 'chiusura del 25 feb 2026', 'chiusura del 26 feb 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '6 mag 2026',
            fatti: ['Ricavi malattie rare +13%.', 'Nuovo farmaco approvato in Europa.', 'Debito in calo.'],
            metriche: [M('Ricavi', '0,65 mld €', '+8%', 'a/a'), M('Margine EBITDA', '37,5%', '+0,3 pp', 'a/a'), M('EPS', '0,75 €', '+9%', 'a/a'), M('Free cash flow', '0,16 mld €', '+7%', 'a/a')],
            guidance: 'Guidance 2026 confermata.',
            cambiato: 'Rispetto al 4T 2025 le malattie rare accelerano.',
            impatto: I('rafforza', 'Nuova approvazione a sostegno della crescita futura.'),
            reazione: R(1.6, 'chiusura del 5 mag 2026', 'chiusura del 6 mag 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '30 lug 2026',
            fatti: ['Ricavi malattie rare +14%.', 'Margine EBITDA al 37,8%.', 'Debito netto a 2,1 volte l’EBITDA.'],
            metriche: [M('Ricavi', '0,67 mld €', '+9%', 'a/a'), M('Margine EBITDA', '37,8%', '+0,5 pp', 'a/a'), M('EPS', '0,78 €', '+11%', 'a/a'), M('Free cash flow', '0,18 mld €', '+10%', 'a/a')],
            guidance: 'Guidance 2026 confermata nella parte alta.',
            cambiato: 'Rispetto al 1T 2026 crescita e margini migliorano ancora.',
            impatto: I('rafforza', 'Quarto trimestre coerente con la tesi.'),
            reazione: R(1.2, 'chiusura del 29 lug 2026', 'chiusura del 30 lug 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          }
        ]
      },

      /* ---------------------------------------------------------------- MONCLER */
      MONC: {
        nome: 'Moncler', ticker: 'MONC', settore: 'Lusso', prezzo: 52.30,
        valutazione: 'P/E atteso 26x, sopra la media del lusso europeo (22x)',
        tesi: {
          orizzonte: '3–5 anni',
          motivo: 'Tenuta della domanda di lusso in Asia grazie alla forza del marchio.',
          motivoBreve: 'Domanda di lusso in Asia',
          indicatori: ['Crescita dei ricavi in Asia', 'Vendite nei negozi diretti', 'Margine operativo'],
          pesoPrevisto: 4
        },
        esito: {
          stato: 'invariata',
          sintesi: 'L’Asia cresce poco, con la Cina debole compensata da Giappone e Corea. I margini sono stabili: la tesi non è né confermata né smentita.',
          fatti: [
            'Ricavi in Asia +3% anno su anno, Cina in calo.',
            'Vendite nei negozi diretti +5%.',
            'Margine operativo stabile al 29%.'
          ],
          interpretazioni: [
            'La forza del marchio sembra tenere, ma la domanda cinese non è ancora ripartita.'
          ]
        },
        decisione: {
          contesto: 'watchlist', azione: 'attendere',
          motivazione: 'La tesi non è né rafforzata né indebolita e la valutazione non lascia margine d’errore. Attendere il 3T 2026 permette di vedere se la domanda in Cina riparte.',
          aFavore: ['Margini stabili', 'Marchio forte anche in un mercato debole'],
          rischio: 'Entrare ora a una valutazione alta prima di una ripresa che potrebbe non arrivare.',
          cambierebbe: 'Una crescita in Asia sopra il 7% o un calo del prezzo che riporti la valutazione in media.'
        },
        evoluzione: 'Tesi rimasta invariata per tre trimestri su quattro; il 1T 2026 l’ha indebolita con il calo della Cina, poi recuperato in parte.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '23 ott 2025',
            fatti: ['Ricavi in Asia +4%.', 'Europa stabile.', 'Margini in linea.'],
            metriche: [M('Ricavi', '0,61 mld €', '+3%', 'a/a'), M('Margine operativo', null, '', null, 'Comunicato solo su base semestrale.'), M('EPS', null, '', null, 'Comunicato solo su base semestrale.'), M('Free cash flow', null, '', null, 'Comunicato solo su base semestrale.')],
            guidance: 'Nessuna guidance numerica.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('invariata', 'Andamento in linea, senza novità sull’Asia.'),
            reazione: R(0.4, 'chiusura del 23 ott 2025', 'chiusura del 24 ott 2025', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '26 feb 2026',
            fatti: ['Ricavi 2025 +4%.', 'Asia +5% nel trimestre.', 'Dividendo in aumento.'],
            metriche: [M('Ricavi', '1,21 mld €', '+5%', 'a/a'), M('Margine operativo', '29,4%', '−0,4 pp', 'a/a'), M('EPS', '2,34 €', '+3%', 'a/a', 'Dato annuale.'), M('Free cash flow', '0,72 mld €', '+2%', 'a/a', 'Dato annuale.')],
            guidance: 'Prudenza sul 2026.',
            cambiato: 'Rispetto al 3T 2025 l’Asia migliora leggermente.',
            impatto: I('invariata', 'Piccolo miglioramento, non sufficiente a cambiare la tesi.'),
            reazione: R(1.8, 'chiusura del 25 feb 2026', 'chiusura del 26 feb 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '22 apr 2026',
            fatti: ['Cina −6%.', 'Asia complessiva +1%.', 'Europa in crescita grazie al turismo.'],
            metriche: [M('Ricavi', '0,82 mld €', '+1%', 'a/a'), M('Margine operativo', null, '', null, 'Comunicato solo su base semestrale.'), M('EPS', null, '', null, 'Comunicato solo su base semestrale.'), M('Free cash flow', null, '', null, 'Comunicato solo su base semestrale.')],
            guidance: 'Nessuna guidance numerica.',
            cambiato: 'Rispetto al 4T 2025 la Cina torna a scendere.',
            impatto: I('indebolisce', 'La Cina, parte centrale della tesi, rallenta.'),
            reazione: R(-3.9, 'chiusura del 22 apr 2026', 'chiusura del 23 apr 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '23 lug 2026',
            fatti: ['Asia +3%, Cina ancora in calo.', 'Negozi diretti +5%.', 'Margine operativo semestrale stabile al 29%.'],
            metriche: [M('Ricavi', '0,48 mld €', '+3%', 'a/a'), M('Margine operativo', '29,0%', '0,0 pp', 'a/a', 'Dato semestrale.'), M('EPS', '0,62 €', '+1%', 'a/a', 'Dato semestrale.'), M('Free cash flow', '0,11 mld €', '−4%', 'a/a', 'Dato semestrale.')],
            guidance: 'Prudenza confermata per la seconda metà dell’anno.',
            cambiato: 'Rispetto al 1T 2026 l’Asia torna a crescere, ma poco.',
            impatto: I('invariata', 'Recupero parziale: la tesi resta aperta.'),
            reazione: R(0.9, 'chiusura del 23 lug 2026', 'chiusura del 24 lug 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          }
        ]
      },

      /* ---------------------------------------------------------------- SAIPEM */
      SPM: {
        nome: 'Saipem', ticker: 'SPM', settore: 'Servizi per l’energia', prezzo: 2.18,
        valutazione: 'P/E atteso 12x',
        tesi: {
          orizzonte: '1–3 anni',
          motivo: 'Ciclo di investimenti nell’energia offshore, con ordini pluriennali e margini in ripresa.',
          motivoBreve: 'Ciclo di investimenti offshore',
          indicatori: ['Nuovi ordini acquisiti', 'Margine EBITDA', 'Debito netto'],
          pesoPrevisto: null
        },
        esito: {
          stato: 'indebolita',
          sintesi: 'I nuovi ordini sono in calo e i margini sono sotto pressione per extra-costi su due progetti. Il ciclo offshore resta positivo per il settore, ma non si riflette sui conti dell’azienda.',
          fatti: [
            'Nuovi ordini semestrali −22% anno su anno.',
            'Margine EBITDA al 9,1%, −1,4 punti.',
            'Extra-costi su due progetti in Medio Oriente.'
          ],
          interpretazioni: [
            'I problemi di esecuzione sembrano pesare più del ciclo di settore.',
            'Senza un peso previsto indicato è difficile valutare quanta esposizione ti interessa.'
          ]
        },
        decisione: {
          contesto: 'watchlist', azione: 'evitare',
          motivazione: 'Due trimestri di ordini in calo e margini in peggioramento vanno contro la tesi, e il tuo orizzonte di 1–3 anni lascia poco tempo per una ripresa.',
          aFavore: ['Ordini in calo', 'Extra-costi sui progetti', 'Reazione negativa del prezzo (−7,4%)'],
          rischio: 'Una ripresa degli ordini nel secondo semestre potrebbe far risalire rapidamente il prezzo.',
          cambierebbe: 'Nuovi ordini sopra i ricavi (book-to-bill superiore a 1) e la chiusura dei progetti problematici.'
        },
        evoluzione: 'Da rafforzata a indebolita: nel 2025 gli ordini sostenevano la tesi, nel 2026 i problemi su due progetti e il calo degli ordini l’hanno messa in discussione.',
        earnings: [
          {
            id: '3T25', label: '3T 2025', periodo: 'luglio–settembre 2025', data: '28 ott 2025',
            fatti: ['Ordini +15%.', 'Margine EBITDA al 10,4%.', 'Debito netto in calo.'],
            metriche: [M('Ricavi', '3,6 mld €', '+11%', 'a/a'), M('Margine EBITDA', '10,4%', '+0,6 pp', 'a/a'), M('EPS', '0,05 €', '+25%', 'a/a'), M('Free cash flow', '0,2 mld €', '+0,1 mld €', 'a/a')],
            guidance: 'Guidance 2025 alzata.',
            cambiato: 'Primo trimestre della serie: fa da riferimento per i successivi.',
            impatto: I('rafforza', 'Ordini e margini in crescita, come previsto.'),
            reazione: R(3.3, 'chiusura del 27 ott 2025', 'chiusura del 28 ott 2025', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '4T25', label: '4T 2025', periodo: 'ottobre–dicembre 2025', data: '25 feb 2026',
            fatti: ['Ordini annuali record.', 'Primi segnali di extra-costi su un progetto.', 'Debito netto stabile.'],
            metriche: [M('Ricavi', '3,8 mld €', '+8%', 'a/a'), M('Margine EBITDA', '10,1%', '+0,2 pp', 'a/a'), M('EPS', '0,05 €', 'stabile', 'a/a'), M('Free cash flow', '0,3 mld €', 'stabile', 'a/a')],
            guidance: 'Obiettivi 2026 di crescita.',
            cambiato: 'Rispetto al 3T 2025 compaiono i primi extra-costi.',
            impatto: I('invariata', 'Ordini forti, ma un primo segnale di rischio di esecuzione.'),
            reazione: R(-1.5, 'chiusura del 24 feb 2026', 'chiusura del 25 feb 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '1T26', label: '1T 2026', periodo: 'gennaio–marzo 2026', data: '29 apr 2026',
            fatti: ['Ordini −18%.', 'Extra-costi su due progetti.', 'Margine EBITDA in calo.'],
            metriche: [M('Ricavi', '3,5 mld €', '+2%', 'a/a'), M('Margine EBITDA', '9,4%', '−0,7 pp', 't/t'), M('EPS', '0,02 €', '−60%', 'a/a'), M('Free cash flow', '−0,1 mld €', '−0,4 mld €', 't/t')],
            guidance: 'Guidance 2026 abbassata.',
            cambiato: 'Rispetto al 4T 2025 calano gli ordini e peggiorano i margini.',
            impatto: I('indebolisce', 'Gli ordini, primo indicatore della tesi, scendono.'),
            reazione: R(-5.1, 'chiusura del 28 apr 2026', 'chiusura del 29 apr 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '28 lug 2026',
            fatti: ['Nuovi ordini semestrali −22%.', 'Margine EBITDA al 9,1%.', 'Extra-costi confermati.'],
            metriche: [M('Ricavi', '3,4 mld €', '−3%', 'a/a'), M('Margine EBITDA', '9,1%', '−1,4 pp', 'a/a'), M('EPS', '0,01 €', '−80%', 'a/a'), M('Free cash flow', '−0,2 mld €', '−0,1 mld €', 't/t')],
            guidance: 'Guidance 2026 confermata dopo il taglio di aprile.',
            cambiato: 'Rispetto al 1T 2026 gli ordini calano ancora e i ricavi iniziano a scendere.',
            impatto: I('indebolisce', 'Secondo trimestre consecutivo contro la tesi.'),
            reazione: R(-7.4, 'chiusura del 27 lug 2026', 'chiusura del 28 lug 2026', 'Risultati pubblicati a mercati chiusi.'),
            fonti: []
          }
        ]
      },

      /* ---------------------------------------------------------------- TECHNOPROBE (dati incompleti) */
      TPRO: {
        nome: 'Technoprobe', ticker: 'TPRO', settore: 'Semiconduttori', prezzo: 7.84,
        valutazione: null,
        tesi: {
          orizzonte: '3–5 anni',
          motivo: 'Domanda di schede di test per i chip dedicati all’intelligenza artificiale.',
          motivoBreve: 'Schede di test per chip AI',
          indicatori: ['Crescita dei ricavi', 'Quota di ricavi da clienti AI', 'Margine EBITDA'],
          pesoPrevisto: null
        },
        esito: {
          stato: 'insufficiente',
          sintesi: 'Nella demo sono disponibili i dati di un solo trimestre, e manca la quota di ricavi legata all’intelligenza artificiale, cioè l’indicatore centrale della tua tesi. Non è possibile dire se la tesi sia rafforzata o indebolita.',
          fatti: ['Ricavi del 2T 2026 +18% anno su anno.'],
          interpretazioni: []
        },
        decisione: null,
        mancano: ['Almeno due trimestri di risultati confrontabili', 'Quota di ricavi da clienti AI', 'Una valutazione di riferimento (es. P/E atteso)'],
        evoluzione: 'Con un solo trimestre disponibile non è possibile ricostruire l’evoluzione della tesi.',
        earnings: [
          { id: '3T25', label: '3T 2025', mancante: true },
          { id: '4T25', label: '4T 2025', mancante: true },
          { id: '1T26', label: '1T 2026', mancante: true },
          {
            id: '2T26', label: '2T 2026', periodo: 'aprile–giugno 2026', data: '10 set 2026',
            fatti: ['Ricavi +18% anno su anno.', 'Nuovo stabilimento in costruzione.', 'Nessun dettaglio sui ricavi per tipo di cliente.'],
            metriche: [M('Ricavi', '0,15 mld €', '+18%', 'a/a'), M('Margine EBITDA', null, '', null, 'Non disponibile nella demo.'), M('EPS', null, '', null, 'Non disponibile nella demo.'), M('Free cash flow', null, '', null, 'Non disponibile nella demo.')],
            guidance: 'Non disponibile nella demo.',
            cambiato: 'Trimestre precedente non disponibile: nessun confronto possibile.',
            impatto: I('invariata', 'Crescita dei ricavi, ma senza il dato che collega la crescita all’AI.'),
            reazione: null,
            fonti: []
          }
        ]
      }
    }
  };
})();

/*
 * Mercato, notizie e storico prezzi — fallback dimostrativo (sostituito da real_data.js se presente).
 * Le notizie imitano la forma degli articoli MF (titolo, riassunto_gen, data_pubblicazione)
 * e il collegamento articolo → strumento via similarità tra embedding (soglia 0,60).
 * segnale = reazione di prezzo osservata (dir/forza), non una previsione né un consiglio operativo.
 * STLAM resta solo qui: COD_AZIONE FIAT assente dal bundle prezzi offline.
 */
(function () {
  'use strict';
  const D = window.DEMO_DATA;

  D.soglia = 0.60;

  /* Variazione % dell'ultima seduta (25 set 2026). */
  D.mercato = {
    PRY: 1.24, ENEL: 0.62, ISP: 1.14, LDO: 0.41, STLAM: -1.93, TIT: -2.14,
    REC: 0.35, MONC: -0.58, SPM: -1.12, TPRO: 2.40
  };

  D.indici = [
    { nome: 'FTSE MIB', valore: '43.812,55', var: 0.48 },
    { nome: 'FTSE Italia All-Share', valore: '46.020,11', var: 0.41 },
    { nome: 'FTSE Italia Star', valore: '51.337,80', var: -0.22 },
    { nome: 'Spread BTP-Bund', valore: '86 pb', var: -1.15 },
    { nome: 'EUR/USD', valore: '1,1742', var: 0.08 }
  ];

  D.settori = {
    PRY: 'Industria', LDO: 'Industria', ENEL: 'Utility', ISP: 'Banche', STLAM: 'Auto', TIT: 'Telecom'
  };

  D.notizie = [
    {
      id: 'n1', data: '2026-09-25T08:12', sezione: 'Banche',
      titolo: 'Intesa Sanpaolo, gli analisti alzano i prezzi obiettivo dopo il nuovo buyback',
      riassunto: 'Diverse case d’affari rivedono al rialzo le stime: pesano la solidità del capitale e la distribuzione prevista per il 2026.',
      strumenti: [{ ticker: 'ISP', sim: 0.74, dir: 'up' }],
      segnale: { dir: 'up', forza: 0.72, storico: { pct: 1.4, sedute: 3, n: 31 } },
      indicatore: { ticker: 'ISP', nome: 'Distribuzione annunciata agli azionisti' }
    },
    {
      id: 'n2', data: '2026-09-25T09:05', sezione: 'Energia',
      titolo: 'Reti elettriche, nuova gara europea per le interconnessioni: in corsa anche i cavisti italiani',
      riassunto: 'Il bando riguarda collegamenti sottomarini ad alta tensione con consegne dal 2028.',
      strumenti: [{ ticker: 'PRY', sim: 0.71, dir: 'up' }, { ticker: 'ENEL', sim: 0.58, dir: 'flat' }],
      segnale: { dir: 'up', forza: 0.64, storico: { pct: 1.1, sedute: 3, n: 22 } },
      indicatore: { ticker: 'PRY', nome: 'Portafoglio ordini nella trasmissione' }
    },
    {
      id: 'n3', data: '2026-09-25T10:30', sezione: 'Auto',
      titolo: 'Stellantis, immatricolazioni in calo in Europa ad agosto',
      riassunto: 'Il gruppo perde quota nei principali mercati europei, mentre crescono i marchi cinesi.',
      strumenti: [{ ticker: 'STLAM', sim: 0.69, dir: 'down' }],
      segnale: { dir: 'down', forza: 0.66, storico: { pct: -1.3, sedute: 3, n: 41 } },
      indicatore: null,
      notaTesi: 'Riguarda l’Europa: non tocca gli indicatori della tua tesi, centrata sul Nord America.'
    },
    {
      id: 'n4', data: '2026-09-24T17:48', sezione: 'Mercati',
      titolo: 'Data center, i piani di spesa dei grandi operatori cloud salgono ancora per il 2027',
      riassunto: 'Le stime di investimento aggregate crescono di un altro 15%, con effetti sulla filiera di cavi e semiconduttori.',
      strumenti: [{ ticker: 'PRY', sim: 0.66, dir: 'up' }, { ticker: 'TPRO', sim: 0.62, dir: 'up' }],
      segnale: { dir: 'up', forza: 0.70, storico: { pct: 1.6, sedute: 3, n: 18 } },
      indicatore: { ticker: 'PRY', nome: 'Crescita dei ricavi legati ai data center' }
    },
    {
      id: 'n5', data: '2026-09-24T15:20', sezione: 'Tlc',
      titolo: 'Telecom Italia, il mercato attende il piano sulla remunerazione degli azionisti',
      riassunto: 'Dopo la cessione della rete, gli investitori chiedono indicazioni su dividendi o riacquisti.',
      strumenti: [{ ticker: 'TIT', sim: 0.72, dir: 'flat' }],
      segnale: { dir: 'flat', forza: 0.30, storico: { pct: -0.2, sedute: 3, n: 26 } },
      indicatore: { ticker: 'TIT', nome: 'Remunerazione degli azionisti' }
    },
    {
      id: 'n6', data: '2026-09-24T12:02', sezione: 'Difesa',
      titolo: 'Leonardo, nuove commesse europee nell’elettronica per la difesa',
      riassunto: 'Gli ordini arrivano da tre Paesi dell’Unione e riguardano radar e sistemi di comunicazione.',
      strumenti: [{ ticker: 'LDO', sim: 0.73, dir: 'up' }],
      segnale: { dir: 'up', forza: 0.68, storico: { pct: 1.2, sedute: 3, n: 19 } },
      indicatore: { ticker: 'LDO', nome: 'Ordini acquisiti (book-to-bill)' }
    },
    {
      id: 'n7', data: '2026-09-24T09:40', sezione: 'Lusso',
      titolo: 'Moncler, segnali deboli dalla domanda cinese nel terzo trimestre',
      riassunto: 'I dati sulle vendite nei grandi magazzini cinesi indicano un rallentamento del lusso.',
      strumenti: [{ ticker: 'MONC', sim: 0.70, dir: 'down' }],
      segnale: { dir: 'down', forza: 0.55, storico: { pct: -1.0, sedute: 3, n: 24 } },
      indicatore: { ticker: 'MONC', nome: 'Crescita dei ricavi in Asia' }
    },
    {
      id: 'n8', data: '2026-09-23T18:10', sezione: 'Energia',
      titolo: 'Saipem, slitta l’assegnazione di un contratto offshore in Medio Oriente',
      riassunto: 'Il committente ha rinviato la decisione al 2027 per rivedere il progetto.',
      strumenti: [{ ticker: 'SPM', sim: 0.68, dir: 'down' }],
      segnale: { dir: 'down', forza: 0.61, storico: { pct: -2.2, sedute: 3, n: 14 } },
      indicatore: { ticker: 'SPM', nome: 'Nuovi ordini acquisiti' }
    },
    {
      id: 'n9', data: '2026-09-23T14:15', sezione: 'Farmaceutica',
      titolo: 'Recordati, via libera europeo a un nuovo farmaco per malattie rare',
      riassunto: 'L’autorizzazione riguarda una terapia per una patologia metabolica rara, con lancio previsto nel 2027.',
      strumenti: [{ ticker: 'REC', sim: 0.75, dir: 'up' }],
      segnale: { dir: 'up', forza: 0.74, storico: { pct: 1.8, sedute: 3, n: 12 } },
      indicatore: { ticker: 'REC', nome: 'Crescita dei ricavi malattie rare' }
    },
    {
      id: 'n10', data: '2026-09-23T11:00', sezione: 'Macro',
      titolo: 'Bce, i verbali confermano un approccio prudente sui tassi',
      riassunto: 'Il consiglio direttivo non esclude ulteriori tagli, ma solo con un’inflazione stabilmente al 2%.',
      strumenti: [],
      migliore: 0.51,
      segnale: null,
      indicatore: null
    },
    {
      id: 'n11', data: '2026-09-22T16:30', sezione: 'Energia',
      titolo: 'Enel, confermato il calendario del dividendo 2026',
      riassunto: 'Il saldo sarà pagato a gennaio, in linea con l’impegno del piano 2026–2028.',
      strumenti: [{ ticker: 'ENEL', sim: 0.70, dir: 'up' }],
      segnale: { dir: 'up', forza: 0.40, storico: { pct: 0.4, sedute: 3, n: 33 } },
      indicatore: { ticker: 'ENEL', nome: 'Dividendo per azione confermato' }
    },
    {
      id: 'n12', data: '2026-09-22T10:05', sezione: 'Banche',
      titolo: 'Tassi in calo, pressione sul margine di interesse delle banche italiane',
      riassunto: 'Le stime per il 2027 scendono in media del 4% per il settore.',
      strumenti: [{ ticker: 'ISP', sim: 0.61, dir: 'down' }],
      segnale: { dir: 'down', forza: 0.45, storico: { pct: -0.7, sedute: 3, n: 40 } },
      indicatore: { ticker: 'ISP', nome: 'Utile netto trimestrale' }
    }
  ];

  /* Storico prezzi simulato: sedute dal 4 gen 2021 al 25 set 2026 (giorni feriali). */
  const giorni = [];
  for (let d = new Date(Date.UTC(2021, 0, 4)); d <= new Date(Date.UTC(2026, 8, 25)); d.setUTCDate(d.getUTCDate() + 1)) {
    const w = d.getUTCDay();
    if (w > 0 && w < 6) giorni.push(new Date(d));
  }
  D.giorni = giorni;

  const hash = s => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };
  const rng = seed => () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const cache = {};

  /* Serie deterministica che termina al prezzo indicato e rispetta la variazione dell'ultima seduta. */
  D.serie = function (ticker, prezzo, variazione) {
    const key = ticker + ':' + prezzo;
    if (cache[key]) return cache[key];
    const r = rng(hash(ticker)), n = giorni.length, a = new Array(n);
    const drift = (r() - 0.35) * 0.0012, vol = 0.010 + r() * 0.008;
    let v = 1;
    for (let i = 0; i < n; i++) { v *= 1 + drift + (r() + r() + r() - 1.5) * vol; a[i] = v; }
    const k = prezzo / a[n - 1];
    for (let i = 0; i < n; i++) a[i] *= k;
    a[n - 2] = prezzo / (1 + (variazione || 0) / 100);
    return (cache[key] = a);
  };
})();
