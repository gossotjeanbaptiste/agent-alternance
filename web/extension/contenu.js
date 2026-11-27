// Extension LMAgent, sur les pages de La Bonne Alternance seulement. Deux cas :
// - fiche ouverte par LMAgent (adresse terminée par #lmagent=<port>.<jeton>) : le jeton est aussitôt retiré de l'adresse,
//   les données sont demandées à LMAgent une seule fois (jeton à usage unique, valable 2 minutes), puis le formulaire
//   « Candidature simplifiée » est ouvert et rempli ;
// - formulaire ouvert par toi-même (fiche trouvée sur le site) : dès qu'il apparaît, LMAgent (ouvert sur ce PC) donne
//   ce qu'il a pour cette fiche et seuls les champs encore vides sont remplis. Rien n'est demandé tant que le
//   formulaire n'est pas ouvert ; réglage « Préremplir aussi les formulaires ouverts hors de LMAgent ».
// Rien d'autre n'est lu ni envoyé : ni cookies, ni mots de passe, ni autre site. Jamais de clic sur l'envoi.
(() => {
  const annoncer = (texte, erreur) => {
    const boite = document.createElement("div");
    boite.textContent = texte;                       // texte seulement, jamais de HTML
    boite.setAttribute("role", "status");
    boite.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:2147483647;max-width:420px;padding:12px 16px;"
      + "border-radius:10px;font:14px/1.4 system-ui,sans-serif;color:#fff;box-shadow:0 4px 16px rgba(0,0,0,.25);"
      + "background:" + (erreur ? "#b3261e" : "#1f4e78");
    const fermer = document.createElement("button");
    fermer.textContent = "✕";
    fermer.style.cssText = "margin-left:12px;background:none;border:0;color:#fff;cursor:pointer;font-size:14px";
    fermer.onclick = () => boite.remove();
    boite.appendChild(fermer);
    (document.body || document.documentElement).appendChild(boite);
  };
  const pret = () => document.readyState !== "loading" ? Promise.resolve()
    : new Promise((r) => document.addEventListener("DOMContentLoaded", r, { once: true }));
  const bilan = (r) => r.faits.length + " champs"
    + (r.faits.includes("cv") ? ", CV joint" : ", CV à joindre à la main");
  const remplis = new WeakSet();                   // formulaires déjà traités (le site ouvre / ferme sans recharger)

  // --- 1. fiche ouverte par LMAgent ------------------------------------------------------------------------------
  async function parJeton() {
    // le site se recharge parfois juste après l'ouverture : on attend qu'il soit stable avant d'utiliser le jeton
    // (sinon le jeton, à usage unique, serait consommé par une page aussitôt remplacée)
    if (document.readyState !== "complete") await new Promise((r) => addEventListener("load", r, { once: true }));
    await new Promise((r) => setTimeout(r, 1500));
    const m = /^#lmagent=(\d{4,5})\.([A-Za-z0-9_-]{40,64})$/.exec(location.hash);
    if (!m) return;
    history.replaceState(history.state, "", location.pathname + location.search);
    chrome.runtime.sendMessage({ type: "donnees", port: Number(m[1]), jeton: m[2] }, async (donnees) => {
      await pret();
      if (chrome.runtime.lastError || !donnees) {
        annoncer("LMAgent : données introuvables (lien expiré ou déjà utilisé, ou LMAgent fermé). "
          + "Reclique « Ouvrir le formulaire prérempli » dans LMAgent.", true);
        return;
      }
      const r = await globalThis.lmagentRemplir(donnees);
      const champ = document.getElementById("applicant_last_name");
      if (champ) remplis.add(champ.form || champ);
      if (r.ok) {
        annoncer("LMAgent a prérempli le formulaire (" + bilan(r)
          + "). Relis tout, puis clique toi-même « J'envoie ma candidature spontanée ».", false);
      } else {
        annoncer({ sans_contact: "La Bonne Alternance n'a plus de contact pour cette entreprise : pas de formulaire.",
                   sans_bouton: "Bouton « Candidature simplifiée » introuvable : remplis le formulaire à la main.",
                   sans_formulaire: "Le formulaire ne s'est pas ouvert : remplis-le à la main." }[r.raison] || "Remplissage impossible.", true);
      }
    });
  }

  // --- 2. formulaire ouvert par toi-même ---------------------------------------------------------------------------
  function surveiller() {
    let enCours = false;
    const verifier = () => {
      const champ = document.getElementById("applicant_last_name");
      const formulaire = champ && (champ.form || champ);
      if (!formulaire || remplis.has(formulaire) || enCours) return;
      remplis.add(formulaire);
      enCours = true;
      chrome.runtime.sendMessage({ type: "fiche" }, async (donnees) => {
        try {
          if (chrome.runtime.lastError || !donnees) return;   // LMAgent fermé, réglage coupé : on ne gêne pas
          const r = await globalThis.lmagentRemplirFormulaire(donnees, true);
          if (!r.ok || !r.faits.length) return;
          annoncer("LMAgent a rempli les champs vides (" + bilan(r) + ")."
            + (donnees.connue ? "" : " Pas de lettre LMAgent pour cette entreprise : écris ton message.")
            + " Relis tout, puis envoie toi-même.", false);
        } finally {
          enCours = false;
        }
      });
    };
    pret().then(() => {
      new MutationObserver(verifier).observe(document.documentElement, { childList: true, subtree: true });
      verifier();
    });
  }

  if (/^#lmagent=/.test(location.hash)) {
    parJeton();
  } else {
    surveiller();
  }
})();
