# QualityGraph

Prototipo open source per ricostruire i legami tra lotti, risultati analitici e deviazioni in uno stabilimento chimico. Combina esportazioni CSV locali e produce un fascicolo JSON con il record di origine di ogni collegamento.

[Analisi comparativa](docs/analisi.md) · [MVP, architettura e roadmap](docs/progetto.md)

## Demo locale

Su macOS, Linux o Windows con Python 3.10 o successivo, aprire un terminale nella directory del progetto. Non occorrono pacchetti esterni, Docker, database o servizi cloud.

```bash
python3 qualitygraph.py examples/synthetic QC-017 > report.json
```

Il caso sintetico parte da `QC-017`, un risultato di viscosità fuori specifica per il lotto intermedio `INT-001`. Il fascicolo riporta due lotti a monte (`RAW-100`, `RAW-200`) e due a valle (`FG-010`, `FG-011`). Segnala un'estrazione incompleta per `FG-011`. Il ramo parallelo `FG-090`, collegato solo attraverso una materia prima comune, è fuori dal perimetro diretto.

Ogni percorso contiene i riferimenti al CSV originale. Gli hash SHA-256 permettono di verificare quali versioni dei file sono state usate. Per il formato delle fonti e del fascicolo, consultare [la specifica](docs/progetto.md).

## Verifica

```bash
python3 -m unittest discover -s tests -v
```

I test verificano il comando su dati sintetici, l'esclusione dei risultati conformi come punto di avvio e il rifiuto di una genealogia con cicli o riferimenti sconosciuti. Il progetto è destinato alla sperimentazione con dati sintetici.

## Licenza

[Apache License 2.0](LICENSE).
