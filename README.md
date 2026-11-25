# TorinoMeteo per Home Assistant

L’integrazione crea un’entità `weather.*` per ogni stazione scelta. Temperatura, umidità, pressione, punto di rugiada e vento provengono dalle rilevazioni della stazione. La condizione corrente usa l’icona Yr fornita dall’API realtime, quando riconoscibile. Il bollettino regionale è condiviso fra tutte le stazioni.

## Installazione dal Marketplace

1. Apri **Impostazioni → Marketplace → Aggiungi da link**. Collega GitHub se Home Assistant lo richiede.
2. Inserisci `https://github.com/Dieghito72/torinometeo-home-assistant`. Se viene richiesto il tipo, seleziona **Integrazione**.
3. Apri **TorinoMeteo** nel Marketplace e seleziona **Installa**. Riavvia Home Assistant se richiesto.
4. Apri **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**, cerca **TorinoMeteo** e indica la tua stazione, ad esempio `torino-regio-parco`.

## Installazione manuale

1. Estrai lo ZIP e copia la cartella `custom_components/torinometeo` nella cartella di configurazione di Home Assistant, accanto a `configuration.yaml`. Il risultato deve includere `<config>/custom_components/torinometeo/manifest.json`.
2. Riavvia Home Assistant.
3. Apri **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **TorinoMeteo**.
4. Inserisci l’identificativo della stazione, per esempio `torino-regio-parco`. Per un’altra stazione, apri la pagina della stazione nella [mappa TorinoMeteo](https://www.torinometeo.org/new-map/) e copia l’ultimo segmento dell’indirizzo `/realtime/<identificativo>`.

La configurazione avviene dall’interfaccia. Le API pubbliche non richiedono credenziali. Pensato per Home Assistant 2025.12 e versioni successive.

## Dashboard e automazioni

Se la stazione pubblica una webcam su TorinoMeteo, l’integrazione aggiunge automaticamente un’entità `image.*` con la dicitura **Webcam**. Nella dashboard puoi mostrare la foto con la scheda **Entità immagine** (Picture entity), selezionando l’entità Webcam. Home Assistant recupera lo scatto quando serve e lo conserva fino al successivo aggiornamento della stazione.

Per le rilevazioni attuali, aggiungi la scheda **Previsioni meteo** e seleziona l’entità TorinoMeteo. Per leggere il bollettino completo, aggiungi anche una scheda **Markdown**, apri l’editor del codice e incolla il contenuto di `scheda-bollettino.yaml`. Sostituisci l’ID nella prima riga del modello con l’ID effettivo della tua entità, che trovi nella pagina dell’integrazione o in **Strumenti per sviluppatori → Stati**.

Quando sono disponibili previsioni giornaliere con temperature numeriche, puoi interrogarle in **Strumenti per sviluppatori → Azioni** o in un’automazione. Sostituisci l’ID nell’esempio:

```yaml
action: weather.get_forecasts
target:
  entity_id: weather.torinometeo_to_r_parco_250_m
data:
  type: daily
```

In un’automazione, aggiungi `response_variable: previsioni` allo stesso livello di `action` per leggere il risultato nei passaggi successivi.

## Dati e aggiornamento

- Misure ogni 10 minuti. L’attributo `observed_at` riporta l’ora dell’ultima rilevazione, utile se la stazione pubblica in ritardo.
- Bollettino ogni ora. In caso di errore resta disponibile l’ultimo bollettino scaricato finché contiene giorni validi. Le date trascorse sono escluse secondo il fuso orario di Roma. Se il bollettino è scaduto, i dettagli dell’entità mostrano la sua ultima data di validità. Gli attributi `bulletin_status` e `bulletin_valid_until` espongono lo stato e la data per dashboard e automazioni.
- L’API fornisce temperature e vento in forma testuale. Il testo, le mappe e l’affidabilità restano negli attributi `bulletin_summary` e `bulletin_days`. La previsione giornaliera nativa contiene una condizione solo quando il testo corrisponde a una descrizione semplice e una minima e massima solo quando il campo contiene una singola coppia esplicita in °C. Il pannello meteo nativo si attiva quando c’è almeno un giorno con temperature numeriche. La scheda Markdown mostra anche i giorni con previsioni solo testuali.

Fonti: [API previsioni](https://www.torinometeo.org/api-tmforecast/) e [API realtime](https://www.torinometeo.org/api-realtime/). Le icone realtime provengono da MET Norway / Yr.

L’icona dell’integrazione usa il [logo del sito TorinoMeteo](https://www.torinometeo.org/static/core/src/img/logoTM.a91906971005.png).
