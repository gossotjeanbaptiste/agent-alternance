// Barre de recherche et filtres des pages À postuler et Écartées (retenus d'un rechargement à l'autre, comme sur
// la page Suivi, qui utilise retenirChamps / effacerChamps).
// Chaque carte porte data-texte (ce que cherche la barre) et un attribut data-<champ> par filtre.
// Les menus marqués « dynamique » se remplissent avec les valeurs présentes sur la page.

function normaliser(s) {
  return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function carteCorrespond(carte, recherche, filtres) {
  // recherche : texte saisi ; filtres : [{champ, valeur}] (valeur vide = pas de filtre)
  const q = normaliser(recherche).trim();
  if (q && !q.split(/\s+/).every(mot => normaliser(carte.dataset.texte || "").includes(mot))) return false;
  return filtres.every(f => !f.valeur || (carte.dataset[f.champ] || "") === f.valeur);
}

function valeursDistinctes(cartes, champ) {
  const vals = [...new Set(cartes.map(c => (c.dataset[champ] || "").trim()).filter(Boolean))];
  return vals.sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));
}

function valeurGardee(el, v) {
  // une valeur gardée n'est remise que si elle existe encore (option d'un menu)
  return typeof v === "string" && (el.tagName !== "SELECT" || [...el.options].some(o => o.value === v));
}

function retenirChamps(ids, memoire) {
  // Recherche et filtres retenus dans le navigateur (localStorage), pour chaque page : un rechargement ne les
  // efface plus. Les valeurs sont remises tout de suite, puis gardées à chaque saisie.
  let gardes = {};
  try { gardes = JSON.parse(localStorage.getItem(memoire) || "{}") || {}; } catch (e) {}
  if (typeof gardes !== "object" || Array.isArray(gardes)) gardes = {};
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (valeurGardee(el, gardes[id])) el.value = gardes[id];
    el.addEventListener("input", () => {
      gardes[id] = el.value;
      try { localStorage.setItem(memoire, JSON.stringify(gardes)); } catch (e) {}
    });
  }
}

function effacerChamps(ids) {
  // bouton « Effacer les filtres » : tout est vidé (et oublié, par l'événement input)
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) { el.value = ""; el.dispatchEvent(new Event("input")); }
  }
}

function activerFiltres(o) {
  // o = {recherche: id, filtres: [{id, champ, dynamique}], boites: [id…], compte: id, vide: id, memoire: clé}
  const boites = o.boites.map(id => document.getElementById(id)).filter(Boolean);
  if (!boites.length) return;
  const cartes = () => boites.flatMap(b => [...b.children].filter(c => c.classList.contains("carte") && c.dataset.entreprise !== undefined));
  for (const f of o.filtres) {
    const menu = document.getElementById(f.id);
    if (menu && f.dynamique) valeursDistinctes(cartes(), f.champ).forEach(v => menu.add(new Option(v, v)));
  }
  if (o.memoire) retenirChamps([o.recherche, ...o.filtres.map(f => f.id)], o.memoire);
  const champ = document.getElementById(o.recherche);
  const appliquer = () => {
    const filtres = o.filtres.map(f => ({ champ: f.champ, valeur: (document.getElementById(f.id) || {}).value || "" }));
    let n = 0;
    for (const c of cartes()) {
      const ok = carteCorrespond(c, champ ? champ.value : "", filtres);
      c.style.display = ok ? "" : "none";
      if (ok && boites[0].contains(c)) n++;          // compteur : cartes de la liste principale
    }
    const compte = document.getElementById(o.compte), total = cartes().filter(c => boites[0].contains(c)).length;
    if (compte) compte.textContent = "(" + (n === total ? total : n + " sur " + total) + ")";
    const vide = document.getElementById(o.vide);
    if (vide) vide.style.display = total && !n ? "" : "none";
  };
  [o.recherche, ...o.filtres.map(f => f.id)].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", appliquer);
  });
  appliquer();
  return appliquer;      // à rappeler quand une carte est retirée de la page
}

if (typeof module !== "undefined") module.exports = { normaliser, carteCorrespond, valeursDistinctes, valeurGardee, retenirChamps };
