# Analisi comparativa e scelta del progetto

25 novembre 2026 · Valutazione preliminare su documentazione pubblica

## Problema da risolvere

In uno stabilimento chimico, un risultato fuori specifica può essere registrato nel LIMS, mentre il consumo e la trasformazione dei lotti vengono registrati in ERP o MES e la deviazione nel QMS. L'ipotesi da validare è che, quando questi flussi non sono già integrati, il team qualità debba ricostruire manualmente i legami prima di poter circoscrivere l'evento. Le conseguenze possibili sono un perimetro iniziale troppo ampio, una revisione lenta e una ricostruzione difficile da ripetere. Il [sondaggio Deloitte 2025](https://www.deloitte.com/us/en/about/press-room/deloitte-2025-smart-manufacturing-survey.html) indica investimenti nelle basi dati e nella gestione qualità, ma non misura la frequenza o il costo di questo specifico problema.

| Progetto | Problema e offerta esistente | Punto di ingresso e ostacolo |
| --- | --- | --- |
| FactoryMind | Coordinamento della produzione. [Siemens Opcenter](https://www.siemens.com/de-de/content/architecture-hub/op-center/) integra MES e Industrial Edge. [Sepasoft](https://www.sepasoft.com/downloads/) copre OEE, tracciabilità e SPC. [Eclipse BaSyx](https://eclipse.dev/basyx/) è un middleware open source per Industria 4.0. | Una vista delle fermate tra linee è dimostrabile, ma l'integrazione con sorgenti OT e la concorrenza dei MES ampliano il primo progetto. |
| QualityGraph | Indagini qualità tra sistemi. [SAP Batch Information Cockpit](https://help.sap.com/docs/SAP_ERP/4e5299fdbcc34b2eb3c877efcc995105/bf9ccf535b804808e10000000a174cb4.html) ha già la genealogia dei lotti. [ETQ Reliance](https://host.etq.com/app/uploads/2022/06/ETQ-Quality-Event-data-sheet-1.pdf), [MasterControl](https://www.mastercontrol.com/quality/capa-software/database/) e [Tulip](https://support.tulip.co/docs/quality-event-management) supportano indagini o CAPA. [ERPNext](https://docs.frappe.io/erpnext/quality-management) offre ispezioni, non conformità e tracciamento dei lotti. | Unire esportazioni esistenti in sola lettura e produrre una risposta ripetibile e documentata. Ostacolo principale: qualità e compatibilità delle chiavi fra sistemi. |
| OpenLab Intelligence | Risultati, campioni e controlli. [LabWare](https://www.labware.com/lims/saas/qaqc) e l'open source [SENAITE](https://github.com/senaite/senaite.core) coprono il flusso LIMS. | Un modulo di revisione dati analitici è dimostrabile. Formati strumentali, integrazioni e fiducia nei dati rendono il passaggio in laboratorio più lento. |
| ProcessTwin | Simulare scenari produttivi. [Siemens Plant Simulation](https://www.siemens.com/de-de/products/tecnomatix/plant-simulation-software/) copre la simulazione di fabbrica. [OpenModelica](https://openmodelica.org/) offre modellazione e simulazione open source. | Una linea sintetica è fattibile. Per sostenere una decisione reale servono parametri, calibrazione e confronto sistematico con il processo. |
| PredictEdge | Anticipare guasti attraverso la telemetria. [Siemens Senseye](https://cache.industry.siemens.com/dl/files/319/109955319/att_1350959/v1/109955319_Senseye-product-sheet-V1.6_Nov25-2.pdf) integra dati macchina. [Merlion](https://github.com/salesforce/Merlion) offre componenti open source per serie temporali. | Un rilevatore offline è semplice da dimostrare. Guasti rari, differenti regimi operativi e costi dei falsi allarmi richiedono telemetria reale rappresentativa. |

### Matrice decisionale

Scala da 1 (debole) a 5 (forte). Totale su 100 pari alla somma di punteggio × peso ÷ 5. I voti riflettono la fase di prototipazione individuale e sono giudizi progettuali, non risultati di un sondaggio o stime di mercato.

| Candidato | Valore del problema 25% | Fattibilità locale 25% | Differenziazione 20% | Accesso al pilota 20% | Demo con dati sintetici 10% | Totale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QualityGraph | 5 | 5 | 4 | 4 | 4 | 90 |
| OpenLab Intelligence | 4 | 4 | 3 | 4 | 4 | 76 |
| PredictEdge | 5 | 3 | 2 | 4 | 2 | 68 |
| FactoryMind | 5 | 2 | 2 | 4 | 2 | 63 |
| ProcessTwin | 4 | 3 | 3 | 3 | 2 | 63 |

## Direzione proposta

**QualityGraph** parte da un'indagine ricorrente in impianti chimici a lotti. Un risultato fuori specifica avvia una ricerca sui legami di trasformazione diretti e indiretti, in entrambe le direzioni. Per ogni lotto trovato, il software mostra il percorso, le sorgenti e i record collegati. Le lacune note nell'estrazione restano visibili. I collegamenti documentano genealogia e contesto, mentre la valutazione della causa e le decisioni di rilascio restano agli operatori.

L'ipotesi distintiva riguarda il costo e il tempo per ottenere un fascicolo verificabile da esportazioni indipendenti, con installazione locale e formati aperti. La genealogia, il trending e l'indagine esistono già sul mercato. [Seeq](https://www.seeq.com/resources/blog/Operationalizing-Batch-Analytics/) offre analisi per lotti, mentre [GS1 EPCIS](https://ref.gs1.org/standards/epcis/2.0.0/) offre un riferimento per eventi di trasformazione. Questa analisi documentale non stabilisce l'assenza di prodotti equivalenti, ruoli di mercato o prezzi. In demo guidate con i concorrenti, verificare import multi-sorgente, evidenze a livello di record e tempi di configurazione sullo stesso scenario.

## Ipotesi commerciale e verifica

Primo utilizzatore: analista qualità o ingegnere di processo. Sponsor da verificare: responsabile QA del sito. Partenza con chimica specializzata o materiali, una linea e un solo tipo di deviazione. Proposta commerciale da testare: integrazione, formazione e supporto per installazioni locali, con il nucleo e i formati sotto Apache-2.0. Una singola sede può adottarlo prima di proporlo al gruppo.

Condurre cinque colloqui con QA/produzione e chiedere di ricostruire un caso anonimizzato. Proseguire se almeno tre interlocutori descrivono il lavoro manuale tra due o più sistemi e almeno uno sponsor accetta di valutare un pilota. Confrontare almeno cinque casi contro la procedura corrente, registrando tempo di ricostruzione, copertura rispetto a una genealogia convalidata dall'operatore e falsi collegamenti. Obiettivo pilota: riduzione della mediana del tempo di almeno il 50% e nessun lotto di riferimento omesso nei casi completi. Con dati incompleti, verificare che ogni lacuna nota appaia nel fascicolo. Questi valori sono soglie di sperimentazione. Il prototipo con dati sintetici non dimostra risparmio o interesse commerciale.
