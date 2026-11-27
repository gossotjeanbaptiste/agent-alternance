// Regroupement des cartes (À postuler, Écartées) en sous-catégories repliables : par ville, type, source…
// Menu « Regrouper par » : chaque option vaut le nom d'un attribut data-<champ> des cartes ("" = pas de groupes).
// Les groupes sont rangés par ordre alphabétique, « (inconnu) » à la fin ; l'ordre des cartes dans un groupe est
// celui du tri (tri.js). Le choix et les groupes repliés sont retenus dans le navigateur, pour chaque page.

function nomGroupe(carte, champ, libelles) {
  const v = (carte.dataset[champ] || "").trim();
  return v ? (libelles && libelles[v]) || v : "";
}

function ordreGroupes(noms, impose) {
  // noms distincts, triés (accents et majuscules ignorés), le groupe sans nom ("") à la fin ;
  // impose : ordre voulu pour certains noms (ex. les types de candidature), placés d'abord dans cet ordre
  const vus = [...new Set(noms)], rang = n => (impose || []).indexOf(n);
  return vus.filter(Boolean).sort((a, b) => {
    const ra = rang(a), rb = rang(b);
    if (ra !== rb && (ra >= 0 || rb >= 0)) return ra < 0 ? 1 : rb < 0 ? -1 : ra - rb;
    return a.localeCompare(b, "fr", { sensitivity: "base", numeric: true });
  }).concat(vus.includes("") ? [""] : []);
}

function cartesDe(boite) {
  return [...boite.querySelectorAll(".carte[data-entreprise]")];
}

function lireReplies(memoire) {
  try { return new Set(JSON.parse(localStorage.getItem(memoire) || "[]")); } catch (e) { return new Set(); }
}

function regrouper(boite, champ, o) {
  // o = {inconnu: {villenom: "Ville inconnue"…}, colonnes: [champs affichés un groupe par colonne], libelles: {valeur: nom affiché}, memoire: clé des groupes repliés}
  o = o || {};
  const cartes = cartesDe(boite);                        // dans l'ordre actuel (celui du tri)
  boite.querySelectorAll(":scope > .groupe").forEach(g => g.remove());
  cartes.forEach(c => boite.appendChild(c));
  boite.classList.toggle("sans-groupes", !champ);   // sans groupes : les cartes en grille directement
  boite.classList.toggle("en-colonnes", !!champ && (o.colonnes || []).includes(champ));   // un groupe par colonne
  if (!champ) return;
  const replies = o.memoire ? lireReplies(o.memoire) : new Set();
  const groupes = new Map();
  for (const nom of ordreGroupes(cartes.map(c => nomGroupe(c, champ, o.libelles)), (o.ordre || {})[champ])) {
    const g = document.createElement("details");
    g.className = "groupe";
    g.open = !replies.has(champ + ":" + nom);
    g.dataset.groupe = nom;
    const titre = document.createElement("summary");
    const t = document.createElement("span");
    t.className = "titre-groupe";
    t.textContent = nom || (o.inconnu && o.inconnu[champ]) || "(inconnu)";
    const n = document.createElement("span");
    n.className = "compte-groupe";
    titre.append(t, n);
    const contenu = document.createElement("div");
    contenu.className = "contenu-groupe";
    g.append(titre, contenu);
    g.addEventListener("toggle", () => {
      if (!o.memoire) return;
      const r = lireReplies(o.memoire), cle = champ + ":" + nom;
      if (g.open) r.delete(cle); else r.add(cle);
      try { localStorage.setItem(o.memoire, JSON.stringify([...r])); } catch (e) {}
    });
    boite.appendChild(g);
    groupes.set(nom, contenu);
  }
  cartes.forEach(c => groupes.get(nomGroupe(c, champ, o.libelles)).appendChild(c));
  majGroupes(boite);
}

function majGroupes(boite) {
  // nombre de cartes visibles de chaque groupe ; groupe caché s'il n'en montre aucune, retiré s'il est vide
  if (!boite) return;
  boite.querySelectorAll(":scope > .groupe").forEach(g => {
    const cartes = cartesDe(g);
    if (!cartes.length) { g.remove(); return; }
    const visibles = cartes.filter(c => c.style.display !== "none").length;
    g.style.display = visibles ? "" : "none";
    g.querySelector(".compte-groupe").textContent = visibles === cartes.length ? cartes.length : visibles + " sur " + cartes.length;
  });
}

function activerGroupes(idMenu, idsBoites, o) {
  // menu « Regrouper par » appliqué à une ou plusieurs listes ; renvoie la fonction qui regroupe à nouveau
  const menu = document.getElementById(idMenu);
  const boites = idsBoites.map(id => document.getElementById(id)).filter(Boolean);
  if (!menu || !boites.length) return () => {};
  const cle = (o && o.memoire) ? o.memoire + "-choix" : null;
  try {
    const choix = cle && localStorage.getItem(cle);
    if (choix !== null && choix !== undefined && [...menu.options].some(x => x.value === choix)) menu.value = choix;
  } catch (e) {}
  const appliquer = () => {
    boites.forEach(b => regrouper(b, menu.value, o));
    try { if (cle) localStorage.setItem(cle, menu.value); } catch (e) {}
    if (o && o.apres) o.apres();
  };
  menu.addEventListener("change", appliquer);
  appliquer();
  return appliquer;
}

function toutDeplier(idsBoites, ouvrir) {
  idsBoites.map(id => document.getElementById(id)).filter(Boolean)
    .forEach(b => b.querySelectorAll(":scope > .groupe").forEach(g => { g.open = ouvrir; }));
}

if (typeof module !== "undefined") module.exports = { nomGroupe, ordreGroupes };
