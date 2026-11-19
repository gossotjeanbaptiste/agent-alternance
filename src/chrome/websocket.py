"""Client WebSocket minimal (bibliothèque standard seulement) : juste ce qu'il faut pour parler à Chrome
(messages texte, trames masquées côté client, réponses non fragmentées ou fragmentées)."""
import base64
import os
import socket
import struct
from urllib.parse import urlparse


class WebSocket:
    def __init__(self, url, timeout=30):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        cle = base64.b64encode(os.urandom(16)).decode()
        chemin = u.path + (f"?{u.query}" if u.query else "")
        demande = (f"GET {chemin} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {cle}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(demande.encode())
        reponse = b""
        while b"\r\n\r\n" not in reponse:
            morceau = self.sock.recv(4096)
            if not morceau:
                raise ConnectionError("connexion fermée pendant l'ouverture du WebSocket")
            reponse += morceau
        entete, self._reste = reponse.split(b"\r\n\r\n", 1)
        if b" 101 " not in entete.split(b"\r\n", 1)[0]:
            raise ConnectionError(f"WebSocket refusé : {entete.splitlines()[0].decode(errors='replace')}")

    def _lire(self, n):
        while len(self._reste) < n:
            morceau = self.sock.recv(65536)
            if not morceau:
                raise ConnectionError("connexion fermée par Chrome")
            self._reste += morceau
        donnees, self._reste = self._reste[:n], self._reste[n:]
        return donnees

    def envoyer(self, texte):
        charge = texte.encode("utf-8")
        n = len(charge)
        entete = bytes([0x81])                                   # FIN + message texte
        if n < 126:
            entete += bytes([0x80 | n])
        elif n < 65536:
            entete += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            entete += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masque = os.urandom(4)
        self.sock.sendall(entete + masque + bytes(b ^ masque[i % 4] for i, b in enumerate(charge)))

    def recevoir(self):
        """Prochain message texte (les pings reçoivent leur pong, les fragments sont recollés)."""
        message = b""
        while True:
            b1, b2 = self._lire(2)
            code, fin, n = b1 & 0x0F, b1 & 0x80, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._lire(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._lire(8))[0]
            masque = self._lire(4) if b2 & 0x80 else None
            charge = self._lire(n)
            if masque:
                charge = bytes(b ^ masque[i % 4] for i, b in enumerate(charge))
            if code == 0x8:
                raise ConnectionError("WebSocket fermé par Chrome")
            if code == 0x9:                                       # ping -> pong
                self.sock.sendall(bytes([0x8A, 0x80 | len(charge)]) + b"\0\0\0\0" + charge)
                continue
            if code in (0x1, 0x0):
                message += charge
                if fin:
                    return message.decode("utf-8", errors="replace")

    def fermer(self):
        try:
            self.sock.sendall(bytes([0x88, 0x80]) + b"\0\0\0\0")
            self.sock.close()
        except OSError:
            pass
