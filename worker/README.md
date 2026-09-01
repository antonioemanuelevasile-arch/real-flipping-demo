# Backend del Consulente IA — deploy in 10 minuti

Questo Worker è l'unico pezzo di "backend" della demo: serve solo a tenere la
chiave API di Anthropic fuori dal sito statico (che resta su GitHub Pages o
dove preferisci) e a inoltrare le domande del Consulente IA a un vero
modello Claude. Se non lo deployi, il sito funziona comunque come prima,
con il motore a regole locale — non è un passaggio obbligatorio, è un
upgrade.

## Cosa ti serve

- Un account [Cloudflare](https://dash.cloudflare.com/sign-up) (il piano
  gratuito basta abbondantemente per un MVP).
- Una API key Anthropic da [console.anthropic.com](https://console.anthropic.com/settings/keys)
  — tieni presente che ogni domanda del Consulente IA consuma credito su
  quella chiave, a consumo.
- Node.js installato sul tuo computer (per usare `wrangler`, il CLI di
  Cloudflare).

## Passi

1. **Installa wrangler** (una volta sola):
   ```bash
   npm install -g wrangler
   ```

2. **Accedi al tuo account Cloudflare**:
   ```bash
   cd worker
   wrangler login
   ```
   Si apre il browser, autorizzi e torni al terminale.

3. **Configura la chiave Anthropic come secret** (non finisce mai su GitHub,
   resta solo dentro Cloudflare):
   ```bash
   wrangler secret put ANTHROPIC_API_KEY
   ```
   Incolla la chiave quando richiesto.

4. **Deploya il Worker**:
   ```bash
   wrangler deploy
   ```
   Alla fine stampa un URL tipo:
   ```
   https://realflipping-ai.<tuo-account>.workers.dev
   ```
   Copialo.

5. **Collega il sito al Worker**: apri `index.html` (nella cartella
   principale del repo, non qui in `worker/`) e cerca la riga:
   ```js
   const AI_BACKEND_URL = "";
   ```
   Incolla lì l'URL copiato al passo 4:
   ```js
   const AI_BACKEND_URL = "https://realflipping-ai.<tuo-account>.workers.dev";
   ```
   Salva, fai commit e pubblica come al solito.

6. **(Consigliato) Restringi chi può chiamare il Worker.** Apri
   `worker/wrangler.toml` e cambia:
   ```toml
   ALLOWED_ORIGIN = "*"
   ```
   con il dominio dove pubblichi il sito, es.:
   ```toml
   ALLOWED_ORIGIN = "https://tuo-utente.github.io"
   ```
   poi rideploya (`wrangler deploy`). Senza questo passaggio, chiunque trovi
   l'URL del Worker può usarlo da un'altra pagina e consumare la tua quota
   Anthropic — con `ALLOWED_ORIGIN` impostato, il browser blocca le
   chiamate da altri domini.

7. **(Consigliato) Aggiungi una Rate Limiting Rule** da dashboard
   Cloudflare (Security → WAF → Rate limiting rules) sul percorso del
   Worker, per esempio "max 20 richieste al minuto per IP". Lo script del
   Worker fa solo controlli minimi (lunghezza messaggio); il rate limiting
   vero va configurato lì, è gratuito fino a una soglia generosa.

## Verificare che funzioni

Dopo il deploy puoi testare il Worker da terminale, senza passare dal sito:

```bash
curl -X POST https://realflipping-ai.<tuo-account>.workers.dev \
  -H "Content-Type: application/json" \
  -d '{"message":"qual è il ticket minimo nel crowdfunding?","history":[],"context":{}}'
```

Dovresti ricevere una risposta JSON tipo `{"reply":"...","escalate":false}`.

## Se qualcosa va storto

Il sito non si rompe mai per l'investitore: se il Worker non risponde (non
deployato, chiave mancante, errore, timeout dopo 15 secondi), il Consulente
IA ricade automaticamente sul motore a regole locale — la stessa esperienza
che c'era prima di questo upgrade. Gli errori veri (status del Worker,
messaggio Anthropic) restano solo nella console del browser
(`console.warn`), utili a te in fase di debug ma mai mostrati
all'investitore.

## Costi indicativi

Con un modello economico (il default nel codice, `claude-haiku-4-5` —
verifica comunque il listino aggiornato su
[anthropic.com/pricing](https://www.anthropic.com/pricing) prima di
lanciare) il costo per singola domanda/risposta è tipicamente sotto il
centesimo di euro. Per un MVP con pochi investitori di test l'uscita
mensile resta trascurabile; monitora comunque l'uso da
console.anthropic.com man mano che il traffico cresce.
