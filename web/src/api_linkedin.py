"""Actions de la page LinkedIn : import de l'export (Connections.csv ou archive .zip) et ajout d'une relation."""
from flask import Blueprint, jsonify, request

import relations

api_linkedin = Blueprint("api_linkedin", __name__, url_prefix="/api/linkedin")


@api_linkedin.post("/importer")
def importer():
    ok, message = relations.importer(request.files.get("fichier"))
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api_linkedin.post("/ajouter")
def ajouter():
    ok, message = relations.ajouter(request.get_json(force=True, silent=True) or {})
    return jsonify(ok=ok, message=message), (200 if ok else 400)
