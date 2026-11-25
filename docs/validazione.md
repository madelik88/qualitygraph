# Validazione della v0.5

## Benchmark ripetibile

Dalla cartella del progetto, esegui su macOS o Linux con Python 3.10+.

```bash
python3 benchmark.py
python3 benchmark.py --topology deep
```

Ogni comando genera 10.000 lotti e 100.000 relazioni in una directory temporanea. La topologia `wide` usa un grafo con diramazioni e collegamenti di lunghezza diversa. La topologia `deep` aggiunge una catena di 256 passaggi. Entrambe raggiungono 9.999 lotti a valle nel caso predefinito. Il benchmark misura l'importazione SQLite una volta e la preparazione della pagina in tre processi distinti. Per ciascuna fase registra il tempo e il picco di memoria residente (RSS). La misura della pagina include la lettura SQLite, l'indagine, la generazione HTML e la codifica UTF-8. Il trasferimento HTTP e il rendering del browser restano da misurare separatamente.

### Misure su macOS arm64, Python 3.14.3

| Grafo | Importazione | Mediana pagina lato server | Picco RSS tra le fasi | HTML |
| --- | ---: | ---: | ---: | ---: |
| Ramificato | 0,275 s | 0,270 s | 269,7 MB | 17,6 MB |
| Profondo | 0,280 s | 0,279 s | 280,2 MB | 18,9 MB |

Tre campioni per topologia, MB decimali. Entrambe le prove sono sotto i traguardi lato server di 2 s e 1 GB. L'HTML contiene tutti i percorsi e le rispettive evidenze. Per misurare l'esperienza utente, cronometrare dal clic su **Apri indagine** fino alla disponibilità dei controlli nel browser, distinguendo la prima apertura dalle successive.

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
