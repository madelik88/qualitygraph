# Validazione per la v1.0

## Benchmark ripetibile

Dalla cartella del progetto, esegui su macOS o Linux con Python 3.10+.

```bash
python3 benchmark.py
python3 benchmark.py --topology deep
```

Ogni comando genera 10.000 lotti e 100.000 relazioni in una directory temporanea. La topologia `wide` usa un grafo con diramazioni e collegamenti di lunghezza diversa. La topologia `deep` aggiunge una catena di 256 passaggi. Entrambe raggiungono 9.999 lotti a valle nel caso predefinito. Il benchmark misura l'importazione SQLite una volta e la preparazione della pagina in tre processi distinti. Per ciascuna fase registra il tempo e il picco di memoria residente (RSS). La misura della pagina include la lettura SQLite, l'indagine, la generazione HTML e la codifica UTF-8. Il trasferimento HTTP e il rendering del browser restano da misurare separatamente.

### Misure su macOS arm64, Python 3.14.3

| Grafo | Importazione | Mediana pagina lato server | Picco RSS tra le fasi | HTML prima pagina |
| --- | ---: | ---: | ---: | ---: |
| Ramificato | 0,267 s | 0,177 s | 127,3 MB | 45,0 kB |
| Profondo | 0,276 s | 0,181 s | 127,5 MB | 144,9 kB |

Tre campioni per topologia, kB e MB decimali. Nella v0.5 l'HTML completo era di 17,6–18,9 MB. La pagina ora mostra fino a 50 percorsi per direzione per pagina e conserva il download JSON completo. Le misure lato server soddisfano i traguardi di 2 s e 1 GB.

### Misura nel browser

Avvia il benchmark su una porta separata da quella della demo.

```bash
python3 benchmark.py --serve
```

Apri l'indirizzo stampato sul Mac. Nello strumento di sviluppo del browser, usa la scheda Rete e ricarica la pagina tre volte. Registra per ciascun caricamento il tempo fino all'evento `load`, con cache disabilitata, e verifica che sia possibile espandere il primo percorso. Calcola la mediana delle tre misure. Ripeti con `python3 benchmark.py --topology deep --serve`, dopo aver chiuso la prima prova con **Ctrl+C**. Obiettivo: mediana inferiore a 2 s per entrambe le topologie. Il comando usa una copia temporanea separata dal database della demo.

### Riscontro nel browser

Tre ricariche del caso da 10.000 lotti e 100.000 relazioni hanno richiesto 302, 248 e 255 ms (mediana 255 ms), dal comando di ricarica al completamento del caricamento e alla verifica del titolo visibile. Sono tempi misurati dall'automazione del browser, comprensivi del suo overhead. Il passaggio a pagina 2 di 200 è stato verificato. Sul grafo profondo, con la stessa procedura, le tre ricariche hanno richiesto 336, 253 e 262 ms (mediana 262 ms). In pagina 2 è stato espanso un percorso e verificata la presenza di tutti e 100 i collegamenti alle evidenze. Entrambe le mediane sono sotto i 2 s.

## Confronto con la procedura manuale

Prepara una copia della demo con cinque risultati fuori specifica.

```bash
validation_dir=$(mktemp -d)
cp examples/synthetic/*.csv "$validation_dir/"
tail -n +2 examples/validation/results_extra.csv >> "$validation_dir/results.csv"
python3 qualitygraph.py --import-db "$validation_dir/validation.db" "$validation_dir"
python3 qualitygraph_web.py "$validation_dir/validation.db"
```

Per ogni risultato, registra il lotto di origine, i lotti raggiungibili a monte e a valle, la lacuna nota e almeno un riferimento di origine per percorso. Usa le stesse regole per i due metodi: parti dalla riga di `results.csv`, segui `lineage.csv` in ciascuna direzione e leggi la copertura in `batches.csv`. Cronometra dal momento in cui viene assegnato l'identificatore fino alla consegna degli esiti con i riferimenti. Avvia QualityGraph e carica il database prima della prova. Registra l'importazione a parte. Se possibile, usa due partecipanti e inverti l'ordine dei metodi tra loro per limitare l'effetto memoria.

| Caso | Tempo CSV (s) | Tempo QualityGraph (s) | Lotti omessi CSV / app | Lotti aggiunti per errore CSV / app | Lacuna segnalata CSV / app |
| --- | --- | --- | --- | --- | --- |
| QC-017 | | | | | |
| QC-RAW | | | | | |
| QC-FILL | | | | | |
| QC-GAP | | | | | |
| QC-ISO | | | | | |

Apri la chiave solo al termine della prova. Confronta la mediana del tempo sui cinque casi per ciascun metodo. Obiettivo iniziale: riduzione relativa di almeno il 50%, insieme a zero lotti omessi o aggiunti per errore e alle segnalazioni attese.

<details>
<summary>Chiave di correzione</summary>

| Caso | Origine | A monte | A valle | Lacuna |
| --- | --- | --- | --- | --- |
| QC-017 | INT-001 | RAW-100, RAW-200 | FG-010, FG-011 | FG-011 |
| QC-RAW | RAW-100 | — | INT-001, FG-010, FG-011, FG-090 | FG-011 |
| QC-FILL | FG-010 | INT-001, RAW-100, RAW-200 | FG-011 | FG-011 |
| QC-GAP | FG-011 | FG-010, INT-001, RAW-100, RAW-200 | — | FG-011 |
| QC-ISO | FG-099 | — | — | — |

I test automatici confrontano tutti e cinque i casi con questa chiave. I tempi manuali richiedono una prova con partecipanti.

</details>

## Stato del rilascio

La versione candidata include importazione CSV con profili, snapshot SQLite, indagini locali con paginazione e download JSON completo. Tutti i cinque casi sono stati ricostruiti dai CSV e verificati con i test. Il benchmark nel browser è concluso per entrambi i grafi. Resta da misurare il tempo del confronto con partecipanti prima del rilascio stabile.
