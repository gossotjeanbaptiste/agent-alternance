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
  afficher("Arrêt en cours…", "");
  // On vérifie que le serveur ne répond vraiment plus.
  await new Promise(r => setTimeout(r, 1500));
  let repondEncore = false;
  try { await fetch("/api/routine", { cache: "no-store" }); repondEncore = true; } catch (e) {}
  if (repondEncore) {
    afficher("L'interface répond encore",
      "Une autre copie de l'interface tourne sans doute en parallèle. Ferme toutes les fenêtres noires " +
      "« lancer_interface » (ou Ctrl+C dans les terminaux), puis relance-la une seule fois.");
  } else {
    afficher("Interface arrêtée",
      "Tu peux fermer cet onglet. Pour la relancer : double-clic sur <code>lancer_interface.bat</code>.");
    window.close();  // ne marche que si le navigateur l'autorise ; sinon le message reste affiché
  }
}

async function copier(texte, quoi = "Lettre copiée") {
  try { await navigator.clipboard.writeText(texte); annoncer(quoi + " : colle-la avec Ctrl+V."); }
  catch (e) { annoncer("Copie impossible : sélectionne le texte à la main.", true); }
}
