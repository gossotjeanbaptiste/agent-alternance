// Boutons de la page À postuler (Envoyée, Abandonner, Écrire ce qui manque, Postuler par La Bonne Alternance,
// formulaire prérempli, extension Chrome). refiltrer est défini par la page (filtres.js).
function retirer(carte) { carte.remove(); refiltrer(); }   // le groupe vide disparaît aussi (majGroupes)
async function fait(ligne, statut, postule) {
  const carte = document.getElementById("c" + ligne);
  if (await changerStatut(ligne, carte.dataset.entreprise, statut, postule)) retirer(carte);
}
async function envoyeeSansAdresse(ligne) {
  const carte = document.getElementById("c" + ligne);
  const adresse = prompt("À quelle adresse as-tu envoyé la candidature de " + carte.dataset.entreprise + " ?\n"
    + "(elle sert au suivi des réponses et à la relance ; laisse vide si tu ne la connais pas)", "");
  if (adresse === null) return;
  const r = await poster("/api/statut", { ligne, entreprise: carte.dataset.entreprise, statut: "Candidaté (mail)",
                                         postule: true, email: adresse.trim() });
  annoncer(r.message || (r.ok ? "Enregistré." : "Erreur"), !r.ok);
  if (r.ok) retirer(carte);
}
async function ecrireManque(bouton, ligne) {
  const carte = document.getElementById("c" + ligne), texte = bouton.textContent;
  document.querySelectorAll("button[onclick^='ecrireManque']").forEach(b => b.disabled = true);
  bouton.textContent = "✍️ Rédaction en cours… (environ une minute)";
  const r = await poster("/api/ecrire", { ligne, entreprise: carte.dataset.entreprise });
  annoncer(r.message || (r.ok ? "C'est écrit." : "Erreur"), !r.ok);
  if (r.ok) { location.reload(); return; }
  bouton.textContent = texte;
  document.querySelectorAll("button[onclick^='ecrireManque']").forEach(b => b.disabled = false);
}
async function versLba(bouton, ligne, chercher) {
  const carte = document.getElementById("c" + ligne);
  if (!confirm("Postuler chez " + carte.dataset.entreprise + " par le formulaire de La Bonne Alternance ? "
               + (chercher ? "L'entreprise y est d'abord cherchée (SIRET, sinon nom et adresse). " : "")
               + "La lettre est gardée, le brouillon sans adresse va à la corbeille et le modèle écrit les réponses aux questions.")) return;
  document.querySelectorAll("button[onclick^='versLba'], button[onclick^='ecrireManque']").forEach(b => b.disabled = true);
  bouton.textContent = chercher ? "🎓 Recherche sur La Bonne Alternance…" : "🎓 En cours… (environ une minute)";
  const r = await poster("/api/vers_lba", { ligne, entreprise: carte.dataset.entreprise });
  annoncer(r.message || (r.ok ? "C'est fait." : "Erreur"), !r.ok);
  if (r.ok) { location.reload(); return; }
  bouton.textContent = "🎓 Postuler par La Bonne Alternance";
  document.querySelectorAll("button[onclick^='versLba'], button[onclick^='ecrireManque']").forEach(b => b.disabled = false);
}
async function installerExtension() {
  const r = await poster("/api/extension_installer", {});
  if (r.ok && r.dossier) {
    try { await navigator.clipboard.writeText(r.dossier); } catch (e) { /* copie refusée : le chemin reste affiché */ }
  }
  annoncer(r.message || "Erreur", !r.ok);
}
async function ouvrirFormulaire(bouton, ligne, navigateur) {
  const carte = document.getElementById("c" + ligne), texte = bouton.textContent;
  bouton.disabled = true;
  bouton.textContent = "🧾 Ouverture…";
  const r = await poster("/api/formulaire", { ligne, entreprise: carte.dataset.entreprise, navigateur });
  bouton.textContent = texte;
  bouton.disabled = false;
  if (r.navigateurs) return choisirNavigateur(bouton, ligne, r.navigateurs);   // Chrome absent : lequel ?
  if (r.lettre) { try { await navigator.clipboard.writeText(r.lettre); } catch (e) {} }   // à coller à la main
  annoncer(r.message || (r.ok ? "Formulaire prérempli." : "Erreur"), !r.ok);
}
// Chrome absent du PC : choix du navigateur (le dernier choisi est proposé en premier)
function choisirNavigateur(bouton, ligne, liste) {
  const d = document.getElementById("choix-navigateur"), zone = document.getElementById("navigateurs");
  let dernier = null;
  try { dernier = localStorage.getItem("navigateur-lba"); } catch (e) {}
  liste.sort((a, b) => (b.cle === dernier) - (a.cle === dernier));
  zone.replaceChildren(...liste.map(n => {
    const b = document.createElement("button");
    b.textContent = n.nom + (n.prerempli ? " (prérempli)" : " (page seulement, lettre copiée)");
    if (n.cle === dernier) b.className = "principal";
    b.onclick = () => {
      d.close();
      try { localStorage.setItem("navigateur-lba", n.cle); } catch (e) {}
      ouvrirFormulaire(bouton, ligne, n.cle);
    };
    return b;
  }));
  d.showModal();
}
async function abandonnerMail(ligne) {
  const carte = document.getElementById("c" + ligne);
  if (!confirm("Abandonner " + carte.dataset.entreprise + " et mettre son brouillon à la corbeille ?")) return;
  if (await changerStatut(ligne, carte.dataset.entreprise, "Abandonné", false, carte.dataset.email)) retirer(carte);
}
