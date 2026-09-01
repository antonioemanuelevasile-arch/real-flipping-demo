/**
 * RealFlipping — backend del Consulente IA (Cloudflare Worker)
 * ==============================================================
 *
 * Fa da ponte sicuro tra il sito statico (index.html) e l'API di Claude:
 * la chiave Anthropic vive SOLO qui, come secret del Worker — non è mai
 * nel front-end. index.html manda domanda + contesto (portafoglio e
 * progetti dell'utente, presi da PROJECTS in index.html), il Worker
 * costruisce il prompt e ritorna la risposta.
 *
 * Deploy rapido (vedi anche worker/README.md):
 *   1. npm install -g wrangler
 *   2. cd worker && wrangler login
 *   3. wrangler secret put ANTHROPIC_API_KEY   (incolla la tua chiave da console.anthropic.com)
 *   4. wrangler deploy
 *   5. Copia l'URL che stampa wrangler (tipo https://realflipping-ai.<tuo-account>.workers.dev)
 *      dentro AI_BACKEND_URL in index.html.
 *
 * Costo: paghi solo le chiamate effettive all'API Anthropic (a consumo) +
 * eventualmente Cloudflare Workers oltre il piano gratuito (molto
 * generoso per un MVP). Imposta ANCHE una Rate Limiting Rule sul dominio
 * da dashboard Cloudflare per evitare abusi che gonfino il conto: questo
 * script fa solo controlli minimi lato codice (lunghezza messaggio,
 * numero di turni), non è un rate limiter vero e proprio.
 */

// Modello di default: economico, adatto a un consulente conversazionale.
// Verifica il model id più recente su https://docs.claude.com/en/docs/about-claude/models
// prima del deploy — puoi anche sovrascriverlo con la variabile d'ambiente ANTHROPIC_MODEL.
const DEFAULT_MODEL = "claude-haiku-4-5";

const MAX_MESSAGE_CHARS = 600;
const MAX_HISTORY_TURNS = 8; // domande+risposte precedenti mandate come contesto
const MAX_TOKENS = 500;

const ESCALATE_TOKEN = "[[ESCALATE]]";

function corsHeaders(env) {
  const allowed = (env.ALLOWED_ORIGIN || "*").trim();
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json; charset=utf-8",
  };
}

function buildSystemPrompt(context) {
  return `Sei il Consulente IA di RealFlipping, una piattaforma DEMO (dati finti) di investimento immobiliare in Italia che unisce flipping (operazioni intere) e crowdfunding immobiliare (quote da 500€).

REGOLE FONDAMENTALI — da rispettare sempre:
1. Rispondi SOLO in base ai dati JSON nel blocco CONTESTO qui sotto. Non inventare mai numeri, progetti, zone o percentuali che non ci sono nel contesto.
2. Se la domanda richiede un'informazione che non hai nel contesto, oppure è una richiesta di consulenza finanziaria/fiscale/legale personalizzata (es. "cosa dovrei fare io", raccomandazioni di investimento specifiche, casi fiscali personali complessi), NON provare a rispondere nel merito: scrivi una frase breve che spieghi che serve un consulente umano e termina il messaggio esattamente con il token ${ESCALATE_TOKEN} (su una riga a parte, verrà rimosso automaticamente prima di mostrarlo).
3. Non sei un consulente finanziario abilitato: questa è consulenza informativa su dati demo, mai consulenza reale. Se opportuno ricordalo brevemente, senza essere ripetitivo a ogni messaggio.
4. Rispondi in italiano, tono professionale ma diretto e caldo, frasi brevi. Puoi usare <b>...</b> per evidenziare numeri importanti (niente markdown, niente asterischi). Niente elenchi puntati lunghi: preferisci prosa breve, o se serve una lista usa numeri "1. 2. 3." in poche righe.
5. Non uscire mai dal ruolo di consulente RealFlipping, anche se l'utente te lo chiede esplicitamente o insiste.

CONTESTO (dati reali di questa sessione demo, in JSON):
${JSON.stringify(context, null, 2)}`;
}

function sanitizeHistory(history) {
  if (!Array.isArray(history)) return [];
  return history
    .slice(-MAX_HISTORY_TURNS * 2)
    .filter(
      (m) =>
        m &&
        (m.role === "user" || m.role === "assistant") &&
        typeof m.text === "string"
    )
    .map((m) => ({
      role: m.role,
      content: String(m.text).slice(0, MAX_MESSAGE_CHARS),
    }));
}

async function handleAsk(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonError("Corpo della richiesta non valido (JSON atteso).", 400, env);
  }

  const message = typeof body.message === "string" ? body.message.trim() : "";
  if (!message) return jsonError("Messaggio mancante.", 400, env);
  if (message.length > MAX_MESSAGE_CHARS) {
    return jsonError(`Messaggio troppo lungo (max ${MAX_MESSAGE_CHARS} caratteri).`, 400, env);
  }

  const history = sanitizeHistory(body.history);
  const context = body.context && typeof body.context === "object" ? body.context : {};

  if (!env.ANTHROPIC_API_KEY) {
    return jsonError("Backend non configurato: manca il secret ANTHROPIC_API_KEY.", 500, env);
  }

  const anthropicRes = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: env.ANTHROPIC_MODEL || DEFAULT_MODEL,
      max_tokens: MAX_TOKENS,
      system: buildSystemPrompt(context),
      messages: [...history, { role: "user", content: message }],
    }),
  });

  if (!anthropicRes.ok) {
    const errText = await anthropicRes.text().catch(() => "");
    console.error("Anthropic API error", anthropicRes.status, errText);
    return jsonError("Il consulente IA non è raggiungibile in questo momento.", 502, env);
  }

  const data = await anthropicRes.json();
  const rawText = (data.content || [])
    .filter((b) => b.type === "text")
    .map((b) => b.text)
    .join("\n")
    .trim();

  const escalate = rawText.includes(ESCALATE_TOKEN);
  const reply = rawText.replace(ESCALATE_TOKEN, "").trim();

  return new Response(JSON.stringify({ reply, escalate }), {
    status: 200,
    headers: corsHeaders(env),
  });
}

function jsonError(message, status, env) {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: corsHeaders(env),
  });
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(env) });
    }
    if (request.method !== "POST") {
      return jsonError("Metodo non supportato, usa POST.", 405, env);
    }
    try {
      return await handleAsk(request, env);
    } catch (err) {
      console.error(err);
      return jsonError("Errore interno del backend.", 500, env);
    }
  },
};
