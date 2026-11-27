// Page Routines : lancement, avancement en direct (relu chaque seconde pendant une routine, toutes les 5 s sinon pour
// voir démarrer une routine programmée), journal, annulation, routines programmées.
let suivi = null, debutRoutine = null, enCours = false, journalChoisi = null;

function duree(depuis) {
  const s = Math.max(0, Math.floor((Date.now() - depuis) / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return (h ? h + " h " : "") + (h || m ? String(m).padStart(h ? 2 : 1, "0") + " min " : "") + String(r).padStart(2, "0") + " s";
}

function jauge(idBarre, idTexte, k, n) {
  const barre = document.getElementById(idBarre), texte = document.getElementById(idTexte);
  const ok = Number.isFinite(k) && Number.isFinite(n) && n > 0;
  barre.parentElement.style.visibility = ok ? "" : "hidden";
  barre.style.width = ok ? Math.min(100, Math.round(100 * k / n)) + "%" : "0";
  texte.textContent = ok ? k + " / " + n : "";
}

function afficherAvancement(r) {
  const a = r.avancement || null, corps = document.getElementById("av-corps");
  enCours = !!r.en_cours;
  document.getElementById("annuler").style.display = r.en_cours ? "" : "none";
  document.getElementById("avancement").classList.toggle("actif", enCours);
  if (!r.nom) return;
  const etat = r.en_cours ? "⏳ en cours" : r.annulee ? "⛔ annulée"
    : (r.code === 0 ? "✅ terminée" : "❌ terminée avec une erreur (code " + r.code + ")");
  document.getElementById("titre-sortie").textContent = r.nom + " — " + etat;
  debutRoutine = r.en_cours && a && a.debut ? new Date(a.debut).getTime() : null;
  if (!debutRoutine) document.getElementById("av-duree").textContent = r.debut ? "lancée à " + r.debut : "";
  corps.style.display = r.en_cours && a ? "" : "none";
  if (!(r.en_cours && a)) return;
  jauge("av-passage-barre", "av-passage", a.passage, a.total);
  document.getElementById("av-etape").textContent = a.etape || "";
  jauge("av-compte-barre", "av-compte", a.k, a.n);
  document.getElementById("av-detail").textContent = a.detail || "";
}

function afficherJournal(texte) {
  const pre = document.getElementById("sortie");
  const suivre = document.getElementById("suivre").checked;
  if (pre.textContent !== texte) {
    pre.textContent = texte;
    if (suivre) pre.scrollTop = pre.scrollHeight;
  }
}

async function actualiser() {
  clearTimeout(suivi);
  let r = {};
  try { r = await (await fetch("/api/routine", { cache: "no-store" })).json(); } catch (e) {}
  afficherAvancement(r);
  if (!journalChoisi) {
    document.getElementById("titre-journal").textContent = "Journal" + (r.nom ? " — " + r.nom : "");
    afficherJournal(r.sortie || "");
  }
  suivi = setTimeout(actualiser, r.en_cours ? 1000 : 5000);
}

async function lancer(nom) {
  const r = await poster("/api/routine/" + nom, {
    essai: document.getElementById("essai").checked,
    fois: parseInt(document.getElementById("fois").value, 10) || 1,
    depuis: document.getElementById("depuis").value,
  });
  if (!r.ok) { annoncer(r.message || "Impossible de lancer", true); return; }
  journalChoisi = null;
  annoncer("Routine lancée."); actualiser();
}

async function annulerRoutine() {
  if (!confirm("Annuler la routine en cours ?\nCe qui est déjà fait (tableau, brouillons, lettres) est gardé ; "
               + "les passages suivants ne seront pas lancés.")) return;
  const bouton = document.getElementById("annuler");
  bouton.disabled = true;
  const r = await poster("/api/annuler_routine");
  bouton.disabled = false;
  annoncer(r.message || (r.ok ? "Routine annulée." : "Erreur"), !r.ok);
  actualiser();
}

async function voir(nom) {      // ancien lancement : son journal (« Journal » revient à la routine en cours)
  const r = await (await fetch("/api/historique/" + encodeURIComponent(nom))).json();
  journalChoisi = nom;
  document.getElementById("titre-journal").innerHTML = "";
  const t = document.createElement("span");
  t.textContent = "Journal — " + nom + " ";
  const retour = document.createElement("button");
  retour.className = "petit";
  retour.textContent = "↩ routine en cours";
  retour.onclick = () => { journalChoisi = null; actualiser(); };
  document.getElementById("titre-journal").append(t, retour);
  afficherJournal(r.sortie || "");
  document.getElementById("sortie").scrollTop = 0;
}

// --- routines programmées (Planificateur de tâches) ---
async function chargerPlanification() {
  const liste = await (await fetch("/api/planification")).json();
  for (const nom of ["relances", "recherche", "tout", "mails", "reponses"]) {
    const e = document.getElementById("etat-" + nom), siennes = liste.filter(t => t.routine === nom);
    e.replaceChildren();
    if (!siennes.length) { e.textContent = "non programmée"; continue; }
    for (const t of siennes) {
      const puce = document.createElement("span");
      puce.className = "puce";
      puce.title = "Prochaine : " + t.prochaine + " (" + t.etat + ")";
      puce.textContent = "⏰ " + t.heure + (t.fois > 1 ? " ×" + t.fois : "");
      const x = document.createElement("button");
      x.textContent = "✕";
      x.title = "Supprimer ce passage programmé";
      x.className = "petit";
      x.onclick = () => supprimerPlanification(t.id, t.heure);
      puce.append(x);
      e.append(puce);
    }
  }
}
async function planifier(nom) {
  const heure = document.getElementById("heure-" + nom).value;
  if (!heure) { annoncer("Choisis une heure.", true); return; }
  const fois = parseInt(document.getElementById("fois-" + nom).value, 10) || 1;
  const r = await poster("/api/planification", {nom, heure, fois});
  annoncer(r.message || (r.ok ? "Enregistré." : "Erreur"), !r.ok);
  chargerPlanification();
}
async function supprimerPlanification(id, heure) {
  if (!confirm("Supprimer le passage programmé de " + heure + " ?")) return;
  const r = await poster("/api/planification", {supprimer: id});
  annoncer(r.message || (r.ok ? "Supprimé." : "Erreur"), !r.ok);
  chargerPlanification();
}

if (typeof document !== "undefined" && document.getElementById("avancement")) {
  chargerPlanification();
  // par défaut : lundi de la semaine en cours (les mails plus anciens ont déjà été lus)
  const d = new Date(); d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  const p = n => String(n).padStart(2, "0");
  document.getElementById("depuis").value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  actualiser();
  setInterval(() => {      // chronomètre : chaque seconde, sans attendre le serveur
    if (debutRoutine && enCours) document.getElementById("av-duree").textContent = "depuis " + duree(debutRoutine);
  }, 1000);
}
if (typeof module !== "undefined") module.exports = { duree };
