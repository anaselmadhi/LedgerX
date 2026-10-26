"""Build the French engineering walkthrough as a vector PDF, with local font caches.

Matplotlib is already installed in the analysis environment. This keeps PDF generation
independent from the API and avoids installing a document library in its virtualenv.
"""

import json
import os
import textwrap
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".runtime/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".runtime/cache"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = ROOT / "output/pdf/ledgerx-construction-pas-a-pas.pdf"
INK = "#26362c"
MUTED = "#6c7b6b"
GREEN = "#335b49"
LIME = "#c7e9a3"
PALE = "#f0f5e8"
PAPER = "#fcfcf8"
plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 42})


def page(number, section, title, subtitle=""):
    fig = plt.figure(figsize=(8.27, 11.69), facecolor=PAPER)
    ax = fig.add_axes((0, 0, 1, 1), xlim=(0, 595), ylim=(842, 0))
    ax.set_axis_off()
    ax.text(45, 34, "LEDGERX / CARNET D'INGÉNIERIE", fontsize=8, color=GREEN, weight="bold")
    ax.text(550, 34, section.upper(), fontsize=7, color=MUTED, ha="right")
    ax.plot([45, 550], [48, 48], color="#dfe7d5", lw=0.7)
    ax.text(45, 84, title, fontsize=27, color=INK, weight="normal", va="top")
    if subtitle:
        paragraph(ax, subtitle, 45, 132, width=86, size=9.2, color=MUTED)
    ax.plot([45, 550], [797, 797], color="#dfe7d5", lw=0.7)
    ax.text(
        45, 815, "Portfolio indépendant · Fonds fictifs · 22 octobre 2026", fontsize=7, color=MUTED
    )
    ax.text(550, 815, f"{number:02d}", fontsize=8, color=GREEN, ha="right")
    return fig, ax


def paragraph(ax, text, x, y, width=86, size=10, color=INK, line=15):
    rows = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    for row in rows:
        ax.text(x, y, row, fontsize=size, color=color, va="top")
        y += line
    return y


def box(ax, x, y, w, h, fill=PALE, border=None, radius=10):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle=f"round,pad=0,rounding_size={radius}",
            facecolor=fill,
            edgecolor=border or fill,
            linewidth=0.8,
        )
    )


def arrow(ax, x1, y1, x2, y2, color=GREEN):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12, color=color, linewidth=1.2
        )
    )


def node(ax, x, y, w, h, title, description, dark=False):
    box(ax, x, y, w, h, GREEN if dark else PALE)
    ax.text(
        x + w / 2,
        y + 23,
        title,
        ha="center",
        fontsize=11,
        weight="bold",
        color="white" if dark else INK,
    )
    ax.text(
        x + w / 2, y + 43, description, ha="center", fontsize=8, color="#dae8cf" if dark else MUTED
    )


def step(ax, number, title, action, why, proof, y):
    box(ax, 45, y, 35, 35, GREEN, radius=9)
    ax.text(62.5, y + 23, f"{number:02d}", color=LIME, ha="center", fontsize=13, weight="bold")
    ax.text(92, y + 7, title, color=INK, fontsize=16, va="top", weight="normal")
    y += 45
    for label, text in (("ACTION", action), ("POURQUOI", why), ("PREUVE / LIMITE", proof)):
        ax.text(45, y, label, color=GREEN, fontsize=7, weight="bold", va="top")
        y = paragraph(ax, text, 45, y + 13, width=88, size=9, line=12.8) + 9
    return y


def footer_note(ax, title, body, y=712):
    box(ax, 45, y, 505, 64)
    ax.text(60, y + 19, title, fontsize=8, color=GREEN, weight="bold")
    paragraph(ax, body, 60, y + 30, width=91, size=8, line=12)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(
        OUT,
        metadata={
            "Title": "LedgerX - Construction pas à pas",
            "Author": "LedgerX - dossier rédigé avec assistance IA",
            "Subject": "Architecture, backend financier et interface React",
        },
    ) as pdf:
        fig, ax = page(1, "Le parcours", "De l'invariant\nà l'interface.")
        ax.text(
            45, 184, "Construire et expliquer LedgerX, étape par étape", fontsize=12, color=GREEN
        )
        paragraph(
            ax,
            (
                "Un carnet de construction pour comprendre les décisions, relier le "
                "code aux preuves et préparer une démonstration technique crédible."
            ),
            45,
            216,
            width=72,
            size=11,
            line=17,
        )
        box(ax, 45, 295, 505, 183, GREEN)
        ax.text(67, 326, "LE FIL CONDUCTEUR", fontsize=8, color=LIME, weight="bold")
        ax.text(
            67,
            354,
            "Un mouvement d'argent ne doit\njamais exister à moitié.",
            fontsize=23,
            color="white",
            va="top",
            linespacing=1.25,
        )
        paragraph(
            ax,
            (
                "Transactions atomiques, double entrée, verrous en base, idempotence et"
                " journal immuable forment le socle. L'interface vient rendre ce socle "
                "utilisable."
            ),
            67,
            425,
            width=80,
            size=9,
            color="#dbe8d4",
            line=14,
        )
        for y, label, text in [
            (520, "01 / COMPRENDRE", "Audit de l'existant, périmètre et invariants."),
            (567, "02 / CONSTRUIRE", "Transactions, sécurité, remboursements et contrôles."),
            (614, "03 / PROUVER", "PostgreSQL réel, concurrence, mesures et limites."),
            (661, "04 / RENDRE UTILISABLE", "React, montants exacts, parcours et documentation."),
        ]:
            ax.text(45, y, label, fontsize=8, color=GREEN, weight="bold")
            ax.text(45, y + 20, text, fontsize=10, color=INK)
        footer_note(
            ax,
            "NOTE DE MÉTHODE",
            (
                "Le projet existait à la reprise. Ce document reconstruit l'ordre "
                "logique des travaux ; il ne prétend pas être un journal Git horodaté "
                "ni un travail sans assistance IA."
            ),
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            2,
            "Cadrage",
            "Comprendre avant d'étendre.",
            "Étapes 01 et 02 · Partir du dépôt existant et préserver ses garanties financières.",
        )
        y = step(
            ax,
            1,
            "Inspecter le projet existant",
            (
                "Lecture du README, des routes FastAPI, services, modèles SQLAlchemy, "
                "migrations Alembic, scripts et tests. Repérage des limites de "
                "l'environnement et conservation du monolithe modulaire."
            ),
            (
                "Réécrire le dépôt aurait rendu plus difficile la préservation des "
                "invariants. Il fallait d'abord identifier qui ouvre la transaction, "
                "qui verrouille les comptes et qui fait respecter la comptabilité."
            ),
            (
                "Repères : app/api, app/services, app/db, alembic/versions et tests. Le"
                " dépôt n'avait pas d'historique Git disponible pour attribuer chaque "
                "ligne antérieure."
            ),
            183,
        )
        step(
            ax,
            2,
            "Fixer les invariants de l'argent",
            (
                "Montants en centimes entiers ; un transfert produit deux écritures "
                "opposées ; les comptes clients ne peuvent pas devenir négatifs ; le "
                "journal ne peut être ni modifié ni supprimé."
            ),
            (
                "Le solde est une vue matérialisée du journal. Les deux doivent rester "
                "cohérents. La base vérifie les contraintes financières même si une "
                "nouvelle route ou un autre client oublie un contrôle."
            ),
            (
                "Compte système réservé au financement fictif. EUR uniquement. Plafond "
                "de 9 × 10^18 centimes. Contraintes, déclencheurs différés et tests "
                "d'intégrité dans PostgreSQL."
            ),
            y + 19,
        )
        footer_note(
            ax,
            "À SAVOIR EXPLIQUER",
            (
                "Pourquoi un float n'est pas adapté à l'argent ; pourquoi une "
                "validation Python seule ne protège pas tous les chemins d'écriture."
            ),
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            3,
            "Architecture",
            "Un monolithe, des frontières.",
            "Étapes 03 et 04 · Responsabilités séparées, transaction financière unique.",
        )
        node(ax, 45, 183, 145, 65, "React + TypeScript", "Écrans et intentions")
        node(ax, 225, 183, 145, 65, "FastAPI", "HTTP, validation, identité")
        node(ax, 405, 183, 145, 65, "Services", "Règles métier", True)
        arrow(ax, 191, 215, 224, 215)
        arrow(ax, 371, 215, 404, 215)
        node(ax, 405, 282, 145, 65, "PostgreSQL", "Écritures et contraintes")
        arrow(ax, 477, 249, 477, 281)
        paragraph(
            ax,
            (
                "JSON/HTTP, même origine. SQLAlchemy + Psycopg dialoguent avec "
                "PostgreSQL. Aucun Kafka, microservice ou serveur Node n'est nécessaire"
                " à l'exécution du build final."
            ),
            45,
            287,
            width=57,
            size=9,
            line=14,
        )
        y = step(
            ax,
            3,
            "Conserver une séparation simple",
            (
                "Les schémas Pydantic portent les contrats ; les routes gèrent HTTP et "
                "les transactions ; les services exécutent le métier ; les modèles et "
                "migrations définissent la persistance."
            ),
            (
                "L'OOP sert aux entités, sessions et contrats. Les services restent des"
                " fonctions explicites : aucune hiérarchie de classes artificielle "
                "n'est nécessaire pour déplacer de l'argent."
            ),
            (
                "Repères : app/schemas, app/api, app/services et app/db. Le frontend "
                "appelle les mêmes routes documentées dans /docs."
            ),
            380,
        )
        box(ax, 45, y + 4, 505, 89, PALE)
        ax.text(60, y + 24, "04 / UNE FRONTIÈRE ATOMIQUE", fontsize=11, color=GREEN, weight="bold")
        paragraph(
            ax,
            (
                "La route ouvre session.begin(). Le service réserve la clé, verrouille "
                "les comptes, vérifie les fonds, inscrit le transfert et ses deux "
                "écritures. Un seul commit rend tout visible ; toute exception annule "
                "l'ensemble."
            ),
            60,
            y + 40,
            width=87,
            size=9,
            line=14,
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            4,
            "Concurrence",
            "Deux clients. Un même solde.",
            "Étapes 05 et 06 · Traiter les courses avec les garanties de PostgreSQL.",
        )
        ax.text(
            45,
            183,
            "EXEMPLE : A DISPOSE DE 100 € ; DEUX DEMANDES VEULENT DÉBITER 80 €",
            fontsize=8,
            color=GREEN,
            weight="bold",
        )
        node(ax, 45, 210, 225, 64, "Requête 1", "Verrouille A, vérifie, débite 80 €", True)
        node(ax, 325, 210, 225, 64, "Requête 2", "Attend le verrou sur A")
        arrow(ax, 157, 275, 157, 307)
        arrow(ax, 437, 275, 437, 307)
        node(ax, 45, 310, 225, 64, "COMMIT", "A = 20 € ; verrou libéré")
        node(ax, 325, 310, 225, 64, "RELECTURE + REFUS", "20 € < 80 € ; aucun débit")
        arrow(ax, 272, 342, 323, 342)
        y = step(
            ax,
            5,
            "Verrouiller dans un ordre stable",
            (
                "Les deux comptes sont verrouillés par UUID croissant avec SELECT FOR "
                "UPDATE. Tous les chemins financiers suivent le même ordre pour les "
                "comptes."
            ),
            (
                "Cela sérialise les dépenses sur une même source et réduit les risques "
                "d'interblocage entre virements opposés. Un mutex Python ne "
                "coordonnerait pas plusieurs processus API."
            ),
            (
                "Tests de concurrence avec plusieurs connexions PostgreSQL. La sûreté "
                "n'élimine pas la contention : les virements partageant une source "
                "ralentissent sous forte concurrence."
            ),
            412,
        )
        box(ax, 45, y + 7, 505, 87)
        ax.text(
            60,
            y + 27,
            "06 / RAFRAÎCHIR AUSSI L'IDENTITY MAP",
            fontsize=10,
            color=GREEN,
            weight="bold",
        )
        paragraph(
            ax,
            (
                "Un verrou SQL ne remplace pas automatiquement un objet déjà présent "
                "dans la Session SQLAlchemy. populate_existing=True recharge le solde "
                "verrouillé ; un test de régression protège ce cas subtil."
            ),
            60,
            y + 44,
            width=88,
            size=9,
            line=14,
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            5,
            "Reprise et sécurité",
            "Une intention, un effet.",
            "Étapes 07 et 08 · Répétition réseau, nouvelle opération et propriétaire.",
        )
        y = step(
            ax,
            7,
            "Rendre les répétitions sûres",
            (
                "La clé d'idempotence est indexée par utilisateur et type d'opération. "
                "Une empreinte SHA-256 du contenu détecte les réutilisations "
                "incompatibles. La réponse d'un transfert terminé est retrouvée en "
                "base."
            ),
            (
                "Une réponse HTTP perdue ne signifie pas un paiement annulé. Le client "
                "peut réémettre la même intention, avec le même contenu et la même clé,"
                " sans effectuer un second débit."
            ),
            (
                "Optimisation introduite : INSERT ... RETURNING récupère directement "
                "une nouvelle réservation ; le chemin de conflit conserve sa lecture "
                "verrouillée. Ne pas attribuer les anciennes mesures à cette version "
                "sans la remesurer."
            ),
            183,
        )
        step(
            ax,
            8,
            "Ajouter identité et propriété",
            (
                "Mots de passe dérivés avec scrypt et sel aléatoire ; tokens opaques "
                "aléatoires dont seul le condensat est conservé en base ; expiration et"
                " révocation. Chaque compte appartient à un utilisateur."
            ),
            (
                "L'authentification identifie ; l'autorisation décide. Connaître un "
                "UUID ou une clé d'idempotence ne doit pas permettre d'accéder aux "
                "comptes d'un autre utilisateur, même avec un rôle administrateur."
            ),
            (
                "Tests d'absence de token, de tokens expirés et révoqués, de rôles et "
                "d'accès croisés. Le financement reste administratif et soumis à un "
                "flag explicite. Aucun MFA ni mécanisme de récupération de compte à ce "
                "stade."
            ),
            y + 19,
        )
        footer_note(
            ax,
            "LE POINT D'ENTRETIEN",
            (
                "Les tokens du navigateur restent en mémoire. Un rechargement "
                "déconnecte ; aucun bearer token n'est persisté dans localStorage."
            ),
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            6,
            "Comptabilité",
            "Corriger sans effacer.",
            "Étapes 09 et 10 · Compensation et contrôle indépendant du journal.",
        )
        node(
            ax,
            45,
            185,
            220,
            67,
            "Transfert original : 25 €",
            "A : -2 500 c.       B : +2 500 c.",
            True,
        )
        node(ax, 330, 185, 220, 67, "Remboursement : 25 €", "B : -2 500 c.       A : +2 500 c.")
        arrow(ax, 267, 218, 328, 218)
        ax.text(
            297,
            272,
            "Lien reversal_of · les anciennes écritures restent intactes",
            fontsize=8,
            color=MUTED,
            ha="center",
        )
        y = step(
            ax,
            9,
            "Créer un transfert compensatoire",
            (
                "Le destinataire d'origine peut retourner l'intégralité du paiement. La"
                " ligne d'origine est verrouillée pour sérialiser les demandes ; une "
                "contrainte unique interdit une seconde compensation."
            ),
            (
                "Une annulation destructive détruirait l'audit. Une nouvelle écriture "
                "conserve la cause et l'effet, vérifie les fonds disponibles et "
                "respecte encore la double entrée. Le verrou NO KEY UPDATE évite un "
                "conflit inutile avec les verrous de clés étrangères."
            ),
            (
                "Remboursements complets uniquement, idempotents ; financement et "
                "remboursement d'un remboursement interdits. Tests de tentatives "
                "simultanées, de propriétaire et de solde insuffisant."
            ),
            310,
        )
        step(
            ax,
            10,
            "Recalculer indépendamment",
            (
                "Le moteur de réconciliation somme les écritures de chaque compte et "
                "compare le résultat au solde stocké. Il vérifie aussi la structure des"
                " transferts et les totaux du journal dans un même instantané SQL."
            ),
            (
                "Le contrôle ne doit pas simplement réutiliser le résultat du service "
                "de virement : il confronte deux représentations indépendantes des "
                "montants."
            ),
            (
                "Endpoint administratif ; rapport structuré ; aucune réparation "
                "silencieuse. Une corruption volontaire et isolée de sept centimes "
                "vérifie que l'écart est détecté."
            ),
            y + 12,
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            7,
            "Vérification",
            "Chercher les pannes utiles.",
            "Étapes 11 et 12 · Observer sans divulguer, puis tester les garanties réelles.",
        )
        y = step(
            ax,
            11,
            "Instrumenter les opérations",
            (
                "Ajout de logs JSON avec identifiants de requête et de corrélation, "
                "métriques Prometheus et mesures de latence. Les erreurs SQL sont "
                "converties en réponses expurgées sans paramètres sensibles."
            ),
            (
                "On doit suivre un incident sans exposer mots de passe, tokens ou "
                "données financières dans les logs. Les labels de métriques sont bornés"
                " : pas d'identifiant de compte par série."
            ),
            (
                "Injection de panne après modification en mémoire et après flush ; "
                "validation du rollback. Tests de lock timeout et de filtrage des "
                "exceptions inattendues. Timeouts de connexion, pool, verrou et requête"
                " explicités."
            ),
            183,
        )
        step(
            ax,
            12,
            "Tester sur PostgreSQL réel",
            (
                "Tests unitaires, intégration avec plusieurs connexions, tests HTTP, "
                "migrations upgrade/downgrade lorsque réversibles et vérification de "
                "dérive ORM. Bases destructibles protégées par des suffixes dédiés."
            ),
            (
                "SQLite ne reproduit pas les verrous ni les déclencheurs PostgreSQL. "
                "Les tests financiers doivent vérifier aussi l'état final : soldes, "
                "écritures, comptes et idempotence après un échec."
            ),
            (
                "Version 0004 validée : 147 tests unitaires/intégration et 2 E2E HTTP, "
                "94,12 % de couverture. Rapports archivés dans artifacts/releases. "
                "La CI distante reste à exécuter ; le déploiement Docker local réussit."
            ),
            y + 19,
        )
        footer_note(
            ax,
            "RÈGLE DE PRÉSENTATION",
            (
                "Un test écrit n'est pas un test exécuté. Une couverture élevée n'est "
                "pas une preuve d'absence de bugs ; elle complète les assertions "
                "métier."
            ),
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            8,
            "Performance",
            "Mesurer avant de promettre.",
            "Étapes 13 et 14 · Référence du 20 octobre ; résultats de la version 0004 en page 14.",
        )
        y = step(
            ax,
            13,
            "Construire une matrice de charge",
            (
                "Dix scénarios HTTP, 1, 8 et 32 clients en concurrence, trois "
                "répétitions : 90 cas et 18 000 requêtes chronométrées. Les scénarios "
                "distinguent lectures, virements indépendants, source partagée, "
                "répétitions et remboursements."
            ),
            (
                "Une moyenne globale masquerait l'attente des verrous et les queues de "
                "latence. On conserve les données brutes, les percentiles et les "
                "contrôles de cohérence après chaque scénario."
            ),
            (
                "Référence locale : tous les cas avaient les réponses attendues et une "
                "réconciliation cohérente. Les réponses d'insuffisance de fonds "
                "attendues sont des succès du scénario de test, pas des virements "
                "réussis."
            ),
            183,
        )
        headers = ["Scénario / 8 clients", "Requêtes/s", "p95"]
        rows = [
            ["Lecture du solde", "926,5", "10,44 ms"],
            ["Virements indépendants", "443,1", "21,44 ms"],
            ["Source partagée", "365,5", "56,52 ms"],
        ]
        table = ax.table(
            cellText=rows,
            colLabels=headers,
            colWidths=[0.55, 0.23, 0.22],
            bbox=(45 / 595, 1 - (y + 112) / 842, 505 / 595, 105 / 842),
            cellLoc="left",
            colLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        for (row, _), cell in table.get_celld().items():
            cell.set_edgecolor("#e2e9d9")
            cell.set_linewidth(0.5)
            cell.set_facecolor(GREEN if row == 0 else PALE if row % 2 else "white")
            cell.get_text().set_color("white" if row == 0 else INK)
        ax.text(
            45,
            y + 130,
            "Médianes des 3 répétitions, y compris médiane des p95 ; pas un p95 agrégé.",
            fontsize=7.5,
            color=MUTED,
        )
        step(
            ax,
            14,
            "Profiler et conserver la référence",
            (
                "cProfile, comptage SQL, EXPLAIN ANALYZE et notebook avec courbes. La "
                "référence est archivée avant l'optimisation de la réservation "
                "d'idempotence, qui vise à supprimer une lecture SQL redondante."
            ),
            (
                "La profondeur du journal, la pagination et le niveau de concurrence "
                "n'ont pas les mêmes coûts. Un plan SQL plus rapide ne prouve pas "
                "automatiquement une amélioration HTTP de bout en bout."
            ),
            (
                "Référence : 7 appels SQL par transfert ; 6 observés sur la version "
                "0004. Ces comptes excluent les instructions internes aux triggers. "
                "32 clients testés ne donnent pas une capacité commerciale "
                "garantie."
            ),
            y + 140,
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            9,
            "Interface",
            "Rendre le système utilisable.",
            "Étapes 15 et 16 · Construire une interface originale sur les contrats existants.",
        )
        y = step(
            ax,
            15,
            "Ajouter React sans refaire l'API",
            (
                "React et TypeScript construisent les écrans ; Vite produit un bundle "
                "statique servi par FastAPI. Deux lectures protégées sont ajoutées : "
                "/auth/me et la liste paginée /accounts, filtrée par propriétaire."
            ),
            (
                "Le dashboard utilise les comptes réels et leurs écritures. Les "
                "graphiques indiquent leur fenêtre et leur périmètre chargé ; aucune "
                "fausse dépense ou banque externe n'est injectée dans le produit."
            ),
            (
                "Connexion, création de compte, réception par UUID, virement avec "
                "confirmation, historique, détail, remboursement et réconciliation "
                "admin. CSS responsive original, dialogue natif, navigation clavier et "
                "réduction des animations."
            ),
            183,
        )
        step(
            ax,
            16,
            "Préserver la précision et l'intention",
            (
                "Les centimes restent des BigInt dans le navigateur. lossless-json "
                "préserve les entiers au passage JSON. Une intention de paiement fige "
                "la charge utile et la clé d'idempotence pour les nouvelles tentatives."
            ),
            (
                "JSON.parse avec Number peut arrondir un grand entier avant même son "
                "affichage. Une panne réseau peut survenir après le commit : le bouton "
                "Réessayer doit réutiliser l'intention au lieu d'en créer une autre."
            ),
            (
                "26 tests frontend exécutés à cette étape couvrent conversions, bornes "
                "et reprises. La compilation TypeScript + Vite réussit. Les tests "
                "navigateur sont distingués entre API simulée et parcours sur "
                "PostgreSQL réel."
            ),
            y + 19,
        )
        footer_note(
            ax,
            "LIMITES ASSUMÉES",
            (
                "La session et la clé en attente restent en mémoire. Après rechargement"
                " ou expiration, vérifier l'historique avant de créer un nouveau "
                "paiement."
            ),
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            10,
            "Livraison",
            "Pouvoir le refaire. Et l'expliquer.",
            "Étapes 17 et 18 · Reproductibilité locale et présentation honnête des résultats.",
        )
        y = step(
            ax,
            17,
            "Rendre l'installation reproductible",
            (
                "Scripts dédiés pour Node local, npm, compilation, tests navigateur et "
                "vérification backend. uv.lock et package-lock.json enregistrent les "
                "dépendances. Caches et téléchargements restent dans le projet."
            ),
            (
                "Un reviewer doit pouvoir suivre quelques commandes, sans compte cloud,"
                " et comprendre ce qui démarre. FastAPI sert le frontend compilé ; Node"
                " n'est nécessaire qu'au build et au développement frontend."
            ),
            (
                "scripts/verify_local.sh utilise _test et _bench ; "
                "scripts/verify_web.sh utilise _bench. Le README précise chaque "
                "commande. Ne pas commettre node_modules, .venv, .runtime ni les "
                "secrets."
            ),
            183,
        )
        step(
            ax,
            18,
            "Préparer une démo vérifiable",
            (
                "Démontrer deux comptes, un financement fictif administrateur, un "
                "virement, un remboursement et une réconciliation. Relier chaque écran "
                "aux services et à un test pertinent, puis présenter les mesures "
                "archivées."
            ),
            (
                "Le projet est convaincant lorsqu'on sait expliquer un compromis, "
                "reproduire un résultat et reconnaître une limite. Ajouter des "
                "infrastructures ou des features décoratives ne remplace pas cette "
                "maîtrise."
            ),
            (
                "Aucun argent réel, aucune conformité bancaire revendiquée. TLS public,"
                " sauvegarde/restauration, quotas, protection distribuée, surveillance "
                "et charge longue restent à traiter avant une ouverture à de vrais "
                "utilisateurs."
            ),
            y + 19,
        )
        footer_note(
            ax,
            "PROVENANCE ET NOM",
            (
                "Travail accompagné par IA ; revue et compréhension personnelles "
                "nécessaires. LedgerX est un nom de travail déjà utilisé ailleurs ; le "
                "projet est indépendant et non affilié à Revolut ou à Ledger."
            ),
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            11,
            "Carte de lecture",
            "Du récit aux preuves.",
            "Les fichiers à consulter pour vérifier les explications et reproduire les parcours.",
        )
        items = [
            ("Architecture et décisions", "README.md · docs/ENGINEERING_REPORT.md"),
            ("Invariants et schéma", "app/db/models.py · alembic/versions/"),
            ("Transactions et verrous", "app/services/transfer_service.py"),
            ("Idempotence et identité", "app/services/idempotency_service.py · auth_service.py"),
            ("Réconciliation", "app/services/reconciliation_service.py"),
            ("Preuves PostgreSQL", "tests/ · artifacts/integration.xml · artifacts/e2e.xml"),
            ("Mesures et référence", "artifacts/latency/ · artifacts/baseline/"),
            ("Analyse visuelle", "analysis/ledgerx_performance.ipynb"),
            ("Interface et contrats", "frontend/src/ · frontend/tests/ · frontend/e2e/"),
            ("Résultats navigateur", "artifacts/frontend-browser-results.json"),
            ("Guide de démonstration", "docs/DEMO.md"),
        ]
        for i, (title, path) in enumerate(items):
            y = 190 + i * 43
            ax.text(45, y, f"{i + 1:02d}", fontsize=9, color="#8ca375", weight="bold")
            ax.text(76, y, title, fontsize=10, color=INK)
            ax.text(76, y + 16, path, fontsize=7.8, color=MUTED)
        report = ROOT / "artifacts/releases/2026-10-22-projection/frontend-browser-results.json"
        summary = "Rapport navigateur non disponible au moment de la génération."
        if report.exists():
            stats = json.loads(report.read_text()).get("stats", {})
            summary = (
                f"Version 0004 vérifiée : {stats.get('expected', 0)} réussis, "
                f"{stats.get('unexpected', 0)} en échec, {stats.get('skipped', 0)} ignorés. "
                "Deux parcours réels dans Docker ; déploiement local terminé le 22 octobre."
            )
        footer_note(ax, "ÉTAT DU RAPPORT AU MOMENT DE LA GÉNÉRATION", summary, y=712)
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            12,
            "Préparer l'ouverture",
            "De la démo locale au web.",
            "Étapes 19 et 20 · Docker validé sur 0004 ; partage HTTPS à tester.",
        )
        node(ax, 45, 183, 145, 65, "Navigateur", "Session en mémoire")
        node(ax, 225, 183, 145, 65, "Docker / API", "Mac ou hébergeur", True)
        node(ax, 405, 183, 145, 65, "PostgreSQL", "Données persistantes")
        arrow(ax, 191, 215, 224, 215)
        arrow(ax, 371, 215, 404, 215)
        ax.text(
            45,
            270,
            "Accès public futur : tunnel HTTPS ou hébergement distant.",
            fontsize=8,
            color=MUTED,
        )
        y = step(
            ax,
            19,
            "Borner le coût de l'authentification",
            "Connexions et inscriptions partagent une fenêtre glissante et deux places simultanées."
            " Une deque, des compteurs et un verrou protègent les réservations en mémoire.",
            "Le hachage scrypt coûte du CPU et de la mémoire. Une requête refusée reçoit HTTP 429"
            " et Retry-After avant la vérification du mot de passe.",
            "Six tests dédiés passent. Limites locales au processus, remises à zéro "
            "au redémarrage ;"
            " plusieurs visiteurs derrière un proxy peuvent partager le même quota.",
            299,
        )
        step(
            ax,
            20,
            "Préparer et vérifier le conteneur public",
            "Dépendances Python verrouillées, PORT fourni par l'hébergeur, arrêt si "
            "migration en échec."
            " La dernière étape Docker produit l'application, pas l'image de tests.",
            "La préparation distingue la base locale de la base distante. Le scénario Docker isolé"
            " transfère puis rembourse entre deux vrais profils clients.",
            "Version 0004 : 149 tests backend, 26 frontend et 12 navigateur passent. "
            "Sauvegarde créée et app locale migrée. Restauration non encore testée.",
            y + 12,
        )
        footer_note(
            ax,
            "HISTORIQUE GITHUB",
            "Importer honnêtement le travail local, puis créer des PR pour les évolutions réelles."
            " Les résultats et dates correspondent aux vérifications exécutées.",
            y=722,
        )
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            13,
            "Optimiser avec preuves",
            "Retirer le coût de l'historique.",
            "Étapes 21 et 22 · Projection incrémentale et charge à arrivées fixes.",
        )
        node(ax, 45, 180, 145, 65, "Nouvelles écritures", "Deux lignes par virement")
        node(ax, 225, 180, 145, 65, "Projection", "Delta exact par compte", True)
        node(ax, 405, 180, 145, 65, "Commit", "Comparaison différée")
        arrow(ax, 191, 212, 224, 212)
        arrow(ax, 371, 212, 404, 212)
        y = step(
            ax,
            21,
            "Maintenir le total du journal à chaque insertion",
            "Le trigger additionne les nouvelles écritures au lieu de relire tout "
            "l'historique. Il protège la projection ; les contraintes de double entrée restent.",
            "Le coût de validation ne doit pas augmenter avec l'âge du compte. "
            "La réconciliation recalcule encore le journal complet indépendamment.",
            "Dix tests PostgreSQL ajoutés : falsification, lots, concurrence, rollback "
            "et migration avec fonds. Tous passent dans la suite PostgreSQL sur le Mac.",
            274,
        )
        step(
            ax,
            22,
            "Mesurer la latence sans masquer la saturation",
            "Arrivées programmées à débit fixé, tâches simultanées bornées. "
            "Chaque perte est comptée ; le délai de programmation entre dans la latence.",
            "En boucle fermée, un serveur lent ralentit aussi le générateur. "
            "La nouvelle mesure distingue débit offert, réponses, pertes, p95 et p99.",
            "18 cas mesurés : comptabilité cohérente, objectifs de charge élevés non tenus. "
            "Les graphiques exposent les abandons du générateur, sans les masquer.",
            y + 12,
        )
        footer_note(
            ax,
            "MESURE ET COMPROMIS",
            "Projection : mises à jour et WAL supplémentaires. Verrous toujours nécessaires. "
            "Les anciens chiffres restent une référence archivée, pas une preuve de gain.",
            y=722,
        )
        pdf.savefig(fig)
        plt.close(fig)
        fig, ax = page(
            14,
            "Livraison mesurée",
            "Les preuves du 22 octobre.",
            "Étapes 23 et 24 · Mesures réelles, limites explicites et app disponible sur le Mac.",
        )
        for x, value, label in [
            (45, "149", "tests backend"),
            (220, "26", "tests frontend"),
            (395, "12", "tests navigateur"),
        ]:
            box(ax, x, 177, 155, 74)
            ax.text(x + 15, 209, value, fontsize=25, color=GREEN)
            ax.text(x + 15, 232, label, fontsize=8, color=MUTED)
        profile = json.loads((ROOT / "artifacts/latency/profiling.json").read_text())
        depths = sorted({r["prepared_transfer_history"] for r in profile["runs"]})
        chart = fig.add_axes((0.13, 0.48, 0.77, 0.17), facecolor=PAPER)
        for key, label, color in [
            ("service_including_commit_ms", "Service, commit inclus", GREEN),
            ("commit_ms", "Commit seul", "#b3652f"),
        ]:
            values = [
                median(
                    r[key]["p95"]
                    for r in profile["runs"]
                    if r["prepared_transfer_history"] == depth
                )
                for depth in depths
            ]
            chart.plot(range(len(depths)), values, marker="o", color=color, label=label)
        chart.set_xticks(range(len(depths)), [f"{d:,}".replace(",", " ") for d in depths])
        chart.set_ylabel("p95 médian (ms)", fontsize=8)
        chart.set_xlabel("Historique préparé : nombre de transferts", fontsize=8)
        chart.tick_params(labelsize=8)
        chart.set_ylim(0, 7)
        chart.spines[["top", "right"]].set_visible(False)
        chart.grid(alpha=0.15)
        chart.legend(fontsize=7, loc="upper left")
        ax.text(
            45,
            279,
            "PROFILAGE : 3 RÉPÉTITIONS DE 100 TRANSFERTS PAR PROFONDEUR",
            fontsize=8,
            color=GREEN,
            weight="bold",
        )
        paragraph(
            ax,
            "cProfile inclus. Mesure de service distincte de la latence HTTP. "
            "Source : artifacts/latency/profiling.json.",
            45,
            465,
            size=8,
            line=12,
        )
        y = 507
        for title, body in [
            (
                "23 / CONSERVER LES LIMITES DE CHARGE",
                "30 000 arrivées proposées : 18 439 envoyées, "
                "11 561 abandonnées par le générateur. "
                "Aucune réponse inattendue ; rapprochements cohérents. Les six essais courts à "
                "100 req/s passent, mais seulement deux sur six à 300 et aucun à 600. "
                "Aucun SLO garanti.",
            ),
            (
                "24 / LIVRER ET PARTAGER",
                "Image Docker construite, base personnelle sauvegardée, migration 0004 "
                "et contrôles "
                "de disponibilité réussis. Utilisation : http://127.0.0.1:8000. Le tunnel HTTPS "
                "temporaire permet à un ami de s'inscrire pendant que le Mac reste allumé ; "
                "pas besoin de compte Cloudflare.",
            ),
        ]:
            ax.text(45, y, title, fontsize=8, color=GREEN, weight="bold")
            y = paragraph(ax, body, 45, y + 17, size=9, width=88, line=13) + 21
        footer_note(
            ax,
            "CE QUI RESTE À VÉRIFIER",
            "Parcours navigateur externe à terminer, CI GitHub à lancer, restauration sur base "
            "séparée et test de charge longue à faire. La sauvegarde est créée, sa restauration "
            "n'a pas encore été vérifiée.",
            y=722,
        )
        pdf.savefig(fig)
        plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
