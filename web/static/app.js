const JETON = document.querySelector('meta[name="jeton"]').content;

async function poster(url, donnees) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Jeton": JETON },
    body: JSON.stringify(donnees || {}),
  });
  let json = {};
  try { json = await r.json(); } catch (e) { json = { ok: false, message: "Erreur " + r.status }; }
  if (r.status === 401 && json.connexion) {  // session expirée : retour à la page de connexion
    location.href = "/connexion?suite=" + encodeURIComponent(location.pathname);
  }
  return json;
}

async function deconnecter() {
  await poster("/api/deconnexion");
  location.href = "/connexion";
}

function annoncer(texte, erreur) {
  const m = document.getElementById("message");
  m.textContent = texte;
  m.style.background = erreur ? "var(--erreur)" : "";
  m.classList.add("visible");
  clearTimeout(m._t);
  m._t = setTimeout(() => m.classList.remove("visible"), 3500);
}

async function changerStatut(ligne, entreprise, statut, postule, brouillon_a) {
  const r = await poster("/api/statut", { ligne, entreprise, statut, postule: !!postule, brouillon_a: brouillon_a || "" });
  annoncer(r.message || (r.ok ? "Enregistré." : "Erreur"), !r.ok);
  return r.ok;
}

async function quitter() {
  let enCours = false;
  try { enCours = (await (await fetch("/api/routine")).json()).en_cours; } catch (e) {}
  const question = enCours
    ? "Une routine est en cours : elle continuera jusqu'au bout, mais tu ne verras plus son avancement ici.\nArrêter l'interface ?"
    : "Arrêter l'interface ?";
  if (!confirm(question)) return;
  try { await poster("/api/quitter"); } catch (e) {}
  const afficher = (titre, texte) => {
    document.body.innerHTML = '<main><div class="carte" style="margin-top:40px; text-align:center">' +
      "<h1>" + titre + '</h1><p class="doux">' + texte + "</p></div></main>";
  };
  // Journal de la fermeture affiché en direct (LM Studio fermé sur la tour, mise en veille…), jusqu'à ce que
  // l'interface ne réponde plus. Une copie qui répond sans jamais finir : une autre interface tourne en parallèle.
  const echapper = s => String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  let lignes = [], repondEncore = true;
  const montrer = (titre, texte) => afficher(titre, (texte ? texte + "<br><br>" : "") +
    lignes.map(l => '<span style="display:block; text-align:left">' + echapper(l) + "</span>").join(""));
  afficher("Arrêt en cours…", "");
  for (let i = 0; i < 120; i++) {           // 90 s au plus
    await new Promise(r => setTimeout(r, 750));
    let etat;
    try { etat = await (await fetch("/api/arret", { cache: "no-store" })).json(); }
    catch (e) { repondEncore = false; break; }
    lignes = etat.lignes || [];
    montrer("Arrêt en cours…", "");
  }
  if (repondEncore) {
    afficher("L'interface répond encore",
      "Une autre copie de l'interface tourne sans doute en parallèle : quitte-la par son icône près de " +
      "l'horloge (ou Ctrl+C dans le terminal), puis relance LMAgent une seule fois.");
  } else {
    montrer("Interface arrêtée",
      "Tu peux fermer cet onglet. Pour la relancer : raccourci LMAgent (menu Démarrer ou bureau).");
    if (!lignes.length) window.close();  // journal à lire : la page reste ouverte (sinon seulement si autorisé)
  }
}

async function copier(texte, quoi = "Lettre copiée") {
  try { await navigator.clipboard.writeText(texte); annoncer(quoi + " : colle-la avec Ctrl+V."); }
  catch (e) { annoncer("Copie impossible : sélectionne le texte à la main.", true); }
}

// bouton « 🔄 Recharger » (Suivi, À postuler, Écartées) : données relues tout de suite (À postuler : lettres relues
// dans la messagerie, sans attendre la fin du cache) ; recherche et filtres restent (retenus par filtres.js)
function recharger() {
  location.href = location.pathname + "?frais=1";
}
if (new URLSearchParams(location.search).has("frais")) {
  history.replaceState(null, "", location.pathname);   // un F5 ensuite ne relit pas la messagerie pour rien
}

// Listes des barres d'outils : largeur réglée sur le choix affiché (« Plus anciennes d'abord » lisible en entier,
// sans élargir les autres pour rien). Recalculée à chaque changement, filtres remis au chargement compris.
function ajusterListe(sel) {
  const choix = sel.selectedOptions[0];
  if (!choix) return;
  const c = ajusterListe.c || (ajusterListe.c = document.createElement("canvas").getContext("2d"));
  const st = getComputedStyle(sel);
  c.font = st.fontWeight + " " + st.fontSize + " " + st.fontFamily;
  sel.style.width = Math.ceil(c.measureText(choix.textContent).width + 46) + "px";   // texte + marges + flèche
}
function ajusterListes() { document.querySelectorAll(".barre-outils select").forEach(ajusterListe); }
document.addEventListener("change", e => { if (e.target.matches && e.target.matches(".barre-outils select")) ajusterListe(e.target); });
document.addEventListener("input", e => { if (e.target.matches && e.target.matches(".barre-outils select")) ajusterListe(e.target); });
window.addEventListener("load", ajusterListes);
