// Remplissage du formulaire « Candidature simplifiée » de La Bonne Alternance, partagé par l'extension LMAgent
// (contenu.js) et par le Chrome piloté de LMAgent (formulaire_lba_chrome.py). Le site est en React : chaque champ
// est rempli comme une saisie au clavier. Ce code ne clique JAMAIS sur « J'envoie ma candidature ».
// lmagentRemplir(d) : ouvre « Candidature simplifiée » puis remplit (fiche ouverte par LMAgent) ;
// lmagentRemplirFormulaire(d, vides) : remplit un formulaire déjà ouvert (vides = ne touche à rien de déjà saisi).
(() => {
  const pause = (ms) => new Promise((r) => setTimeout(r, ms));
  const attendre = async (test, delai) => {
    const fin = Date.now() + delai;
    while (Date.now() < fin) {
      try { const v = test(); if (v) return v; } catch (e) { /* page pas encore prête */ }
      await pause(300);
    }
    return null;
  };
  const saisir = (el, v) => {
    const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype
      : el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, v);
    ["input", "change", "blur"].forEach((t) => el.dispatchEvent(new Event(t, { bubbles: true })));
  };
  const bloc = (libelle) => {
    const l = [...document.querySelectorAll("label")].find((x) => libelle.test(x.innerText));
    return l ? (l.closest(".fr-select-group") || l.parentElement) : null;
  };
  const MOTS = { motivations: ["pourquoi", "rejoindre", "motivation"], missions: ["mission"],
                 experiences: ["expérience", "experience", "stage"] };

  async function debutDeContrat(d, faits, vides) {
    const b = bloc(/Début de contrat/);
    if (!b || !d.debut || !d.debut.length) return;
    const s = b.querySelector("select");
    if (vides && s && [...s.options].some((o) => o.selected && o.value)) return;
    ["mousedown", "mouseup", "click"].forEach((t) => s.dispatchEvent(new MouseEvent(t, { bubbles: true })));
    const liste = await attendre(() => document.querySelector("[role=listbox]"), 3000);
    if (!liste) return;
    const voulus = d.debut.map((v) => v.toLowerCase());
    liste.querySelectorAll("input[type=checkbox]").forEach((c) => {
      const texte = ((c.labels && c.labels[0]) ? c.labels[0].innerText : c.parentElement.innerText).trim().toLowerCase();
      if (voulus.includes(texte) && !c.checked) c.click();
    });
    const ok = [...liste.querySelectorAll("button")].find((x) => /enregistrer/i.test(x.innerText));
    if (ok) ok.click();
    faits.push("debut");
  }

  // Le site confirme un CV accepté par « Pièce jointe <nom> ajoutée » (et retire le champ) ; sinon on réessaie.
  async function joindreCv(cv, faits, vides) {
    if (!cv) return;
    const champ0 = document.getElementById("applicant_attachment_name");
    if (vides && (!champ0 || (champ0.files && champ0.files.length))) return;   // déjà joint (le site retire le champ)
    const octets = Uint8Array.from(atob(cv.contenu), (c) => c.charCodeAt(0));
    const accepte = () => [...document.querySelectorAll("[role=dialog] *")]
      .some((e) => e.children.length === 0 && /pièce jointe/i.test(e.textContent) && e.textContent.includes(cv.nom));
    for (let essai = 0; essai < 3 && !accepte(); essai++) {
      const champ = await attendre(() => document.getElementById("applicant_attachment_name"), 3000);
      if (!champ) break;
      const dt = new DataTransfer();
      dt.items.add(new File([octets], cv.nom, { type: cv.type }));
      champ.files = dt.files;
      champ.dispatchEvent(new Event("change", { bubbles: true }));
      await attendre(accepte, 2000);
    }
    if (accepte()) faits.push("cv");
  }

  // d : données préparées par LMAgent (formulaire_lba.champs) ; renvoie {ok, faits} ou {ok: false, raison}
  async function lmagentRemplir(d) {
    const bouton = await attendre(() => [...document.querySelectorAll("button")]
      .find((x) => /candidature simplifi/i.test(x.innerText)), 25000);
    if (!bouton) {
      const sans = /pas d.(e-?mail|contact) pour cette entreprise/i.test(document.body.innerText);
      return { ok: false, raison: sans ? "sans_contact" : "sans_bouton" };
    }
    bouton.click();
    if (!await attendre(() => document.getElementById("applicant_last_name"), 15000)) {
      return { ok: false, raison: "sans_formulaire" };
    }
    return lmagentRemplirFormulaire(d, false);
  }

  // Formulaire déjà ouvert. vides = true : un champ déjà saisi (par toi, ou un passage précédent) n'est pas touché.
  async function lmagentRemplirFormulaire(d, vides) {
    const faits = [];
    const libre = (el) => el && !(vides && el.value);
    for (const nom of ["applicant_last_name", "applicant_first_name", "applicant_email", "applicant_phone"]) {
      const el = document.getElementById(nom);
      if (libre(el) && d[nom]) { saisir(el, d[nom]); faits.push(nom); }
    }
    const radios = document.querySelectorAll("input[name=applicant_inscription_formation]");
    const coche = [...radios].some((r) => r.checked);
    if (d.situation !== null && d.situation !== undefined && radios[d.situation] && !(vides && coche)) {
      radios[d.situation].click();
      faits.push("situation");
      if (d.situation === 0) await attendre(() => document.getElementById("applicant_formation_description"), 5000);
    }
    for (const nom of ["applicant_formation_description", "applicant_rythm_description", "applicant_message"]) {
      const el = document.getElementById(nom);
      if (libre(el) && d[nom]) { saisir(el, d[nom]); faits.push(nom); }
    }
    const duree = bloc(/Durée du contrat/);
    const choix = duree ? duree.querySelector("select") : null;
    if (libre(choix) && d.duree) { saisir(choix, d.duree); faits.push("duree"); }
    document.querySelectorAll("textarea[id^=custom_question_]").forEach((el) => {
      const t = ((el.labels && el.labels[0]) ? el.labels[0].innerText : "").toLowerCase();
      const cle = Object.keys(MOTS).find((k) => MOTS[k].some((m) => t.includes(m)));
      if (cle && libre(el) && d.reponses && d.reponses[cle]) { saisir(el, d.reponses[cle].slice(0, 2000)); faits.push(cle); }
    });
    await debutDeContrat(d, faits, vides);
    await pause(500);                                   // la liste du début de contrat se referme
    await joindreCv(d.cv, faits, vides);
    return { ok: true, faits };
  }

  globalThis.lmagentRemplir = lmagentRemplir;
  globalThis.lmagentRemplirFormulaire = lmagentRemplirFormulaire;
})();
