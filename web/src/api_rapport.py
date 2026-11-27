"""Actions de la page Rapport : rapport rédigé par le modèle local (lancement, avancement)."""
from flask import Blueprint, jsonify, request

import rapport_ia

api_rapport = Blueprint("api_rapport", __name__, url_prefix="/api/rapport")


@api_rapport.post("/rediger")
def rediger():
    """Lance la rédaction en arrière-plan pour la période {jours} ou {du, au} de la page ; {type} : moi / ecole."""
    d = request.get_json(force=True, silent=True) or {}
    ok, message = rapport_ia.lancer({k: d.get(k) for k in ("jours", "du", "au") if d.get(k)},
                                    type_=str(d.get("type") or "moi"))
    return jsonify(ok=ok, message=message), (200 if ok else 409)


@api_rapport.get("/etat")
def etat():
    return jsonify(rapport_ia.ETAT)
