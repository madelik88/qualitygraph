# MVP, architettura e roadmap

## Perimetro dell'MVP

Un impianto virtuale, un caso di risultato fuori specifica (OOS) e una sessione di indagine locale. L'analista carica quattro CSV e seleziona il risultato. La vista mostra genealogia osservata, risultati e deviazioni pertinenti, lacune note e il percorso verso ciascun lotto. L'analista può esportare il fascicolo e risalire alle fonti. Il risultato OOS è uno stato fornito dal LIMS. La qualificazione del prodotto, la determinazione della causa e l'approvazione delle azioni restano responsabilità del team qualità.

Lo starter consegna il percorso completo da terminale. L'MVP aggiunge una vista locale utilizzabile dal team QA, conservazione delle importazioni e un confronto controllato con un'indagine manuale.

## Architettura

| Componente | Starter | MVP |
| --- | --- | --- |
| Acquisizione | Quattro file CSV versionati con hash, validazione di chiavi e relazioni | Profili di importazione per riconciliare chiavi ERP/MES/LIMS/QMS, con anteprima degli scarti e dei campi mancanti |
| Modello | Lotti, trasformazioni dirette, risultati e deviazioni | Tabelle SQLite indicizzate per snapshot, identità dei lotti ed eventi, con transazioni atomiche per importazione |
| Indagine | Ricerca in ampiezza separata a monte e a valle. Un percorso minimo documentato per ogni lotto | Filtri per contesto e finestre temporali, segnalazione di rami paralleli come ipotesi separate |
| Interfaccia | Comando Python e fascicolo JSON | Interfaccia web vincolata a localhost, con vista dell'indagine e link ai singoli record |
| Verifica | Fixture sintetica e casi di errore | Dataset a copertura nota, casi con dati mancanti e benchmark di tempo, memoria e correttezza |

SQLite consente di iniziare con un processo e un file locale. Se i test lo richiedono, si potrà spostare la ricerca su tabelle indicizzate. Con lo starter, file e grafo risiedono in memoria. Su catene profonde, il JSON può ripetere molti tratti di percorso. I test di carico dovranno misurare anche le dimensioni del fascicolo.

Il computo iniziale è deterministico. Una fase successiva può suggerire eventi simili usando metadati come materiale, linea e metodo analitico, con criteri visibili su ogni suggerimento. La verifica dei suggerimenti richiede un insieme di casi etichettati. Il progetto iniziale usa Python standard e dati sintetici, con costo software di sviluppo pari a 0 €. Il costo di un pilota dipende dalla pulizia dei dati e dal tempo di configurazione.

## Specifica delle esportazioni

UTF-8, intestazioni presenti, separatore virgola e identificatori univoci per ogni entità. Se i codici si ripetono nelle fonti, qualificare l'identificatore prima dell'importazione, ad esempio con sito, materiale e codice lotto.

| File | Colonne | Semantica |
| --- | --- | --- |
| `batches.csv` | `batch_id,material,coverage` | Copertura dichiarata come `no_known_gap`, `known_gap` o `unknown`. `no_known_gap` significa che la fonte non segnala lacune. |
| `lineage.csv` | `parent_batch,child_batch,operation_id` | Relazione dal lotto consumato al lotto risultante. Per rappresentare una rilavorazione dello stesso codice, usare una nuova identità per ciascuna versione. |
| `results.csv` | `result_id,batch_id,analyte,value,unit,status` | Risultato della fonte, con unità e stato `PASS` o `OOS`. Il valore viene riportato come testo della sorgente, senza conversioni. |
| `events.csv` | `event_id,batch_id,description` | Deviazione o evento attribuito a un lotto. |

I record di origine sono numerati a partire da 2 con l'intestazione al numero 1. Un campo CSV con ritorni a capo resta parte dello stesso record. Nel percorso a monte gli archi sono elencati nell'ordine in cui vengono visitati a partire dal lotto di origine, mantenendo i campi genitore e figlio della fonte. Tra percorsi di pari lunghezza viene conservato quello incontrato per primo nell'ordine dei record. Le avvertenze riflettono la copertura dichiarata nel CSV. La genealogia osservata può essere incompleta anche quando nessuna lacuna è indicata.

## Roadmap indicativa per una persona

| Fase | Consegna | Criterio di passaggio |
| --- | --- | --- |
| Avvio, completato | Analisi comparativa, fixture e comando locale | La demo ricostruisce i lotti attesi e marca la lacuna simulata. |
| Settimane 1–2 | Contratto di importazione, riconciliazione delle chiavi, snapshot SQLite | Importazione ripetibile con esito identico e rollback su errori. |
| Settimane 3–4 | Vista QA locale ed esportazione del fascicolo | Un utente ripercorre ciascun percorso e identifica il record di origine. |
| Settimane 5–6 | Benchmark sintetico su Mac M3 e prove guidate | Target iniziali sullo stesso hardware: 10.000 lotti e 100.000 relazioni, apertura dell'indagine in meno di 2 secondi dopo importazione e memoria di picco sotto 1 GB. Misurare importazione e report separatamente, includendo grafi profondi e ramificati. |
| Dopo la prima validazione | Pilota su un caso autorizzato e confronto con il flusso manuale | Usare i criteri descritti nell'[analisi](analisi.md) per decidere se investire nei connettori. |

Il passaggio a un ambiente industriale richiede requisiti concordati su accessi, conservazione, responsabilità sulle fonti e validazione. In questa fase lo strumento opera come demo locale con input sintetici.
