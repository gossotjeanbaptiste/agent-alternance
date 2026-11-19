// Extension LMAgent : seul endroit qui contacte LMAgent (http://127.0.0.1, sur ce PC), pour le compte de contenu.js.
// Il n'accepte que les messages de sa propre extension venant d'une page de La Bonne Alternance, avec un jeton au
// bon format ; aucun cookie n'est envoyé (credentials: "omit") et rien n'est gardé.
const SITE = "https://labonnealternance.apprentissage.beta.gouv.fr/";
const PORT_LMAGENT = 8765;   // port de l'interface de LMAgent (web/app.py)

// À l'installation et au démarrage de Chrome : signale à LMAgent que l'extension est là (aucune donnée échangée),
// pour que sa page À postuler affiche « installée ». Sans LMAgent ouvert, rien ne se passe.
const signaler = () => fetch(`http://127.0.0.1:${PORT_LMAGENT}/api/extension_presente`,
  { method: "POST", credentials: "omit", cache: "no-store", redirect: "error" }).catch(() => {});
chrome.runtime.onInstalled.addListener(signaler);
chrome.runtime.onStartup.addListener(signaler);

chrome.runtime.onMessage.addListener((m, envoyeur, repondre) => {
  if (envoyeur.id !== chrome.runtime.id || !String(envoyeur.url || "").startsWith(SITE)) return false;
  if (!m || !Number.isInteger(m.port) || m.port < 1024 || m.port > 65535
      || !/^[A-Za-z0-9_-]{40,64}$/.test(String(m.jeton || ""))) return false;
  fetch(`http://127.0.0.1:${m.port}/api/extension/${m.jeton}`,
        { method: "POST", credentials: "omit", cache: "no-store", redirect: "error" })
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => repondre(d && d.ok ? d.donnees : null))
    .catch(() => repondre(null));
  return true;   // réponse asynchrone
});
