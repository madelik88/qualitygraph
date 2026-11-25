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

## Verifica

```bash
python3 -m unittest discover -s tests -v
```

I test verificano lo stesso fascicolo da CSV e da SQLite, la deduplicazione, la selezione di versioni precedenti e il rollback su errore. Il progetto è destinato alla sperimentazione con dati sintetici.

## Licenza

[Apache License 2.0](LICENSE).
