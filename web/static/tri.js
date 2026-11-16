// Tri des cartes d'une page (À postuler, Écartées) avec un menu « Trier par ».
// Chaque option du menu vaut "champ:asc" ou "champ:desc" ; le champ est un attribut data-<champ> des cartes.
// Une option avec data-nombre trie numériquement. Les valeurs vides vont toujours à la fin.
// Le choix est retenu dans le navigateur (localStorage), pour chaque page.

function comparerCartes(a, b, champ, sens, nombre) {
  const x = (a.dataset[champ] || "").trim(), y = (b.dataset[champ] || "").trim();
  if (!x !== !y) return x ? -1 : 1;                       // vide à la fin, dans les deux sens
  let r = nombre ? (parseFloat(x) || 0) - (parseFloat(y) || 0)
                 : x.localeCompare(y, "fr", { sensitivity: "base", numeric: true });
  if (sens === "desc") r = -r;
  if (!r) r = (a.dataset.entreprise || "").localeCompare(b.dataset.entreprise || "", "fr", { sensitivity: "base" });
  return r;
}

function trierCartes(cartes, valeur, nombre) {
  const [champ, sens] = String(valeur || "").split(":");
  return [...cartes].sort((a, b) => comparerCartes(a, b, champ, sens, nombre));
}

function activerTri(idMenu, idBoite, memoire) {
  const menu = document.getElementById(idMenu), boite = document.getElementById(idBoite);
  if (!menu || !boite) return;
  try {
    const choix = localStorage.getItem(memoire);
    if (choix && [...menu.options].some(o => o.value === choix)) menu.value = choix;
  } catch (e) {}
  const appliquer = () => {
    const cartes = [...boite.children].filter(c => c.classList.contains("carte") && c.dataset.entreprise !== undefined);
    const nombre = menu.selectedOptions[0] && menu.selectedOptions[0].dataset.nombre !== undefined;
    trierCartes(cartes, menu.value, nombre).forEach(c => boite.appendChild(c));
    try { localStorage.setItem(memoire, menu.value); } catch (e) {}
  };
  menu.addEventListener("change", appliquer);
  appliquer();
}

if (typeof module !== "undefined") module.exports = { comparerCartes, trierCartes };
