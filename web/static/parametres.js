// Page Paramètres : menu à gauche (catégorie retenue dans l'adresse, #messagerie…), recherche d'un réglage dans
// toutes les catégories, et enregistrement (signature, profil, contre-prompt, mot de passe, réglages).
// CHAMPS et FICHIER_SIGNATURE sont définis par la page.

const ETIQUETTES = {linkedin: "LinkedIn", portfolio: "Portfolio", github: "GitHub"};
function valeurs() {
  const v = {};
  for (const c of CHAMPS) v[c] = document.getElementById("s-" + c).value.trim();
  return v;
}
function apercu() {  // même mise en forme que postuler.signature()
  const v = valeurs();
  const lignes = ["nom", "titre", "telephone", "email"].map(c => v[c]);
  for (const c of ["linkedin", "portfolio", "github"]) if (v[c]) lignes.push(ETIQUETTES[c] + " : " + v[c]);
  const sig = lignes.filter(Boolean).join("\n");
  const mail = document.getElementById("ajouter").checked
    ? (FICHIER_SIGNATURE ? "(ton fichier de signature)" : sig) : "(pas de signature)";
  document.getElementById("apercu").textContent =
    "Formulaires :\n…fin de la lettre.\n\nCordialement,\n\n" + sig +
    "\n\n──────────\n\nMails :\n…fin du mail.\n\nCordialement,\n\n" + mail;
}
async function enregistrer() {
  const r = await poster("/api/signature", {signature: valeurs(), debut: document.getElementById("debut").value,
                                         ajouter: document.getElementById("ajouter").checked});
  annoncer(r.message || (r.ok ? "Enregistré." : "Erreur"), !r.ok);
}
async function verifierMaj() {
  const r = await poster("/api/mise_a_jour", {});
  annoncer(r.message || "Erreur", !r.ok);
  if (r.redemarrage) attendreRedemarrage(Date.now());
}
async function attendreRedemarrage(debut) {   // la page se recharge quand l'interface relancée répond
  await new Promise(ok => setTimeout(ok, 4000));
  while (Date.now() - debut < 180000) {
    try { if ((await fetch("/parametres", {cache: "no-store"})).ok) { location.reload(); return; } } catch (e) {}
    await new Promise(ok => setTimeout(ok, 1500));
  }
  annoncer("L'interface ne répond pas : relance LMAgent toi-même.", true);
}
async function enregistrerProfil() {
  const r = await poster("/api/profil", {texte: document.getElementById("profil").value});
  annoncer(r.message || (r.ok ? "Enregistré." : "Erreur"), !r.ok);
}
async function changerMotDePasse() {
  const v = id => document.getElementById(id).value;
  const r = await poster("/api/mot_de_passe", {actuel: v("mdp-actuel"), nouveau: v("mdp-nouveau"), confirmation: v("mdp-confirmation")});
  annoncer(r.message || (r.ok ? "Mot de passe changé." : "Erreur"), !r.ok);
  for (const id of ["mdp-actuel", "mdp-nouveau", "mdp-confirmation"]) document.getElementById(id).value = "";
}
async function enregistrerReglages() {
  const valeurs = {};
  for (const el of document.querySelectorAll("[data-cle]")) {
    valeurs[el.dataset.cle] = el.dataset.type === "oui_non" ? el.checked : el.value;
  }
  const r = await poster("/api/reglages", {valeurs});
  annoncer(r.message || (r.ok ? "Enregistré." : "Erreur"), !r.ok);
  if (r.ok) for (const el of document.querySelectorAll('[data-type="secret"]')) el.value = "";
  const theme = document.querySelector('[data-cle$="interface.theme"]');   // thème appliqué tout de suite
  if (r.ok && theme) {
    if (theme.value === "clair" || theme.value === "sombre") document.documentElement.dataset.theme = theme.value;
    else delete document.documentElement.dataset.theme;
  }
}
async function enregistrerInterdits() {
  const r = await poster("/api/interdits", {texte: document.getElementById("interdits").value});
  annoncer(r.message || (r.ok ? "Enregistré." : "Erreur"), !r.ok);
}

function montrer(cat) {
  const panneaux = [...document.querySelectorAll(".panneau")];
  let cible = null;
  if (!panneaux.some(p => p.dataset.cat === cat)) {
    // ancre vers un bloc (#pli-signature…) : on ouvre sa catégorie et on y descend
    cible = cat ? document.getElementById(cat) : null;
    const panneau = cible && cible.closest(".panneau");
    cat = panneau ? panneau.dataset.cat : panneaux[0].dataset.cat;
  }
  if (cible) setTimeout(() => cible.scrollIntoView({ block: "start" }), 0);
  setTimeout(() => document.querySelectorAll("textarea.auto").forEach(ajusterHauteur), 0);
  panneaux.forEach(p => { p.style.display = p.dataset.cat === cat ? "" : "none"; });
  document.querySelectorAll(".menu-param a").forEach(a => a.classList.toggle("actif", a.dataset.cat === cat));
}

function chercher(q) {
  // recherche : toutes les catégories, seulement les réglages (et blocs) qui contiennent le texte
  q = normaliserTexte(q.trim());
  const rien = document.getElementById("rien-trouve");
  if (!q) {
    document.querySelectorAll(".panneau .champ, .groupe-param, .bloc-param, .panneau > .actions").forEach(e => { e.style.display = ""; });
    rien.style.display = "none";
    montrer(location.hash.slice(1));
    return;
  }
  let total = 0;
  document.querySelectorAll(".panneau").forEach(p => {
    let n = 0;
    p.querySelectorAll(".groupe-param").forEach(g => {
      let vus = 0;
      g.querySelectorAll(".champ").forEach(c => {
        const ok = normaliserTexte((c.dataset.texte || c.textContent) + " " + g.querySelector("h3").textContent).includes(q);
        c.style.display = ok ? "" : "none";
        vus += ok;
      });
      g.style.display = vus ? "" : "none";
      n += vus;
    });
    p.querySelectorAll(".bloc-param").forEach(b => {
      const ok = normaliserTexte(b.querySelector("h3").textContent).includes(q);
      b.style.display = ok ? "" : "none";
      n += ok;
    });
    p.querySelectorAll(":scope > .actions").forEach(a => { a.style.display = n ? "" : "none"; });
    p.style.display = n ? "" : "none";
    total += n;
  });
  document.querySelectorAll(".menu-param a").forEach(a => a.classList.remove("actif"));
  rien.style.display = total ? "none" : "";
}

function ajusterHauteur(t) {
  // zone de texte à la hauteur de son contenu (plus de défilement dans un petit cadre)
  if (!t.offsetParent) return;                 // catégorie cachée : ajustée quand elle s'affiche
  t.rows = 1;                                  // sinon la hauteur de départ (rows) compte comme du contenu
  t.style.height = "auto";
  t.style.height = (t.scrollHeight + 2) + "px";
}

function normaliserTexte(s) {
  return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

if (typeof document !== "undefined" && document.querySelector(".panneau")) {
  window.addEventListener("hashchange", () => montrer(location.hash.slice(1)));
  document.getElementById("cherche-reglage").addEventListener("input", e => {
    chercher(e.target.value);
    document.querySelectorAll("textarea.auto").forEach(ajusterHauteur);
  });
  document.querySelectorAll("textarea.auto").forEach(t => t.addEventListener("input", () => ajusterHauteur(t)));
  montrer(location.hash.slice(1));
  apercu();
}
