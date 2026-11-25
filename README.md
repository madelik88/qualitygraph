# QualityGraph

Prototipo open source per ricostruire i legami tra lotti, risultati analitici e deviazioni in uno stabilimento chimico. Combina esportazioni CSV locali e produce un fascicolo JSON con il record di origine di ogni collegamento.

[Analisi comparativa](docs/analisi.md) · [MVP, architettura e roadmap](docs/progetto.md)

## Demo locale

Su macOS, Linux o Windows con Python 3.10 o successivo, aprire un terminale nella directory del progetto. Non occorrono pacchetti esterni, Docker o servizi cloud. Il comando può leggere direttamente i CSV oppure salvare le importazioni in un file SQLite locale.

```bash
python3 qualitygraph.py examples/synthetic QC-017 > report.json
```

Il caso sintetico parte da `QC-017`, un risultato di viscosità fuori specifica per il lotto intermedio `INT-001`. Il fascicolo riporta due lotti a monte (`RAW-100`, `RAW-200`) e due a valle (`FG-010`, `FG-011`). Segnala un'estrazione incompleta per `FG-011`. Il ramo parallelo `FG-090`, collegato solo attraverso una materia prima comune, è fuori dal perimetro diretto.

Ogni percorso contiene i riferimenti al CSV originale. Gli hash SHA-256 permettono di verificare quali versioni dei file sono state usate. Per il formato delle fonti e del fascicolo, consultare [la specifica](docs/progetto.md).

## Salvare e riusare un'importazione

```bash
python3 qualitygraph.py --import-db qualitygraph.db examples/synthetic
python3 qualitygraph.py --from-db qualitygraph.db QC-017 > report.json
```

L'importazione restituisce `snapshot_id` e `created`. Se i quattro file sono identici byte per byte a un'importazione esistente, il comando restituisce lo stesso ID e `created: false`. Un input non valido o un errore di scrittura non modifica le importazioni esistenti.

L'indagine legge per impostazione predefinita l'ultima **nuova** importazione salvata. Per ripetere un'indagine su una versione precedente, usa `--from-db qualitygraph.db --snapshot ID QC-017`, sostituendo `ID` con lo `snapshot_id` restituito all'importazione. Il fascicolo conserva l'hash e i numeri di record dei CSV. Conserva i CSV originali se vuoi verificare gli hash in seguito.

## Importare CSV con intestazioni e codici diversi

La demo in `examples/profiled` usa intestazioni diverse e codici lotto separati per laboratorio, produzione e qualità. Verifica le corrispondenze prima di scrivere nel database.

```bash
python3 qualitygraph.py --preview --profile examples/profiled/profile.json examples/profiled
python3 qualitygraph.py --import-db qualitygraph.db --profile examples/profiled/profile.json examples/profiled
```

L'anteprima mostra il conteggio dei record per file, i riferimenti riconciliati con codice originale e canonico e gli errori da correggere. Salva solo con `ready: true`. Se un riferimento è ambiguo o sconosciuto, l'importazione viene rifiutata. Un profilo o un CSV malformato viene segnalato direttamente nel terminale.

Il [profilo di esempio](examples/profiled/profile.json) usa `version: 1` e la sezione `files`. Mantieni i quattro nomi di file standard. Per ciascun file, `columns` associa i campi canonici alle intestazioni esportate. `batch_aliases` associa i codici locali ai lotti del registro `batches.csv`. Gli identificatori senza alias devono essere già canonici. Il fascicolo mantiene file e numero di record originali e aggiunge l'impronta del profilo sotto `@profile`. Conserva il profilo insieme ai CSV per poter verificare la mappatura.

## Aprire la schermata web locale

Con `qualitygraph.db` già importato, avvia il server dalla cartella del progetto.

```bash
python3 qualitygraph_web.py qualitygraph.db
```

Apri [http://127.0.0.1:8765](http://127.0.0.1:8765). Seleziona un'importazione e premi **Carica**, poi seleziona `QC-017` e premi **Apri indagine**. Espandi un lotto per vedere il percorso e clicca sul riferimento al record per leggere la riga corrispondente. **Scarica fascicolo JSON** esporta lo stesso fascicolo restituito dal comando SQLite. Se la porta è occupata, aggiungi `--port 8766` e apri l'indirizzo stampato nel terminale. Premi **Ctrl+C** per fermare il server.

La pagina legge le importazioni esistenti. Per caricare un nuovo set di CSV, usa il comando di importazione e ricarica la pagina.

## Verifica

```bash
python3 -m unittest discover -s tests -v
```

I test verificano l'equivalenza dei fascicoli, la deduplicazione, lo storico, il rollback su errore e il flusso di selezione e download della pagina locale. Il progetto è destinato alla sperimentazione con dati sintetici.

## Licenza

[Apache License 2.0](LICENSE).
