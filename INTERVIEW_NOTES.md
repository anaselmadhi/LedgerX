# Présenter LedgerX en entretien

## Présentation en une minute

« LedgerX est un backend de transactions financières en Python, FastAPI et PostgreSQL. Le monolithe
modulaire permet au débit, au crédit, au journal et au résultat d'idempotence de partager un seul
commit. Les montants sont des entiers en centimes. Chaque transfert produit deux écritures immuables,
et des contraintes différées vérifient leur cohérence au commit.

J'ai travaillé avec une assistance IA pour ajouter l'authentification, la propriété des comptes,
les remboursements compensatoires et le rapprochement indépendant. La version 0004 a passé 147 tests
unitaires et PostgreSQL, puis deux tests HTTP, avec 94,12 % de couverture applicative. Les 12 tests
navigateur passent aussi. La projection incrémentale conserve les contrôles au commit sans relire
tout l'historique. La charge à arrivées fixes montre aussi une limite : les objectifs élevés ne sont
pas toujours tenus, même si tous les contrôles comptables passent. »

Le projet est indépendant et n'est pas affilié à Revolut. Ces choix ne décrivent pas l'architecture
interne de Revolut. Comprendre et expliquer le code est plus utile que mémoriser cette présentation.

## Démonstration de cinq à dix minutes

1. Afficher le schéma d'architecture du README et expliquer la frontière transactionnelle.
2. Se connecter, créer deux comptes et créditer le premier via l'administrateur de démonstration.
3. Transférer 15 EUR avec une clé, puis réessayer : même identifiant, aucun second débit.
   Changer le montant avec la même clé produit un conflit 409.
4. Montrer qu'un autre utilisateur ne peut lire le solde ni débiter le compte.
5. Rembourser depuis le destinataire : nouveau transfert opposé, original conservé.
6. Afficher la réconciliation et les résultats PostgreSQL.
7. Ouvrir le notebook et expliquer les graphiques, y compris les limites observées.

Les commandes HTTP sont dans le README. La commande `python -m app.cli create-admin` prépare
l'administrateur interactif. Utiliser des identifiants fictifs et éviter de montrer les tokens.

## Expliquer un transfert

Pydantic valide les données. L'authentification termine sa courte transaction de lecture avant
l'ouverture de la transaction métier. Chaque requête possède sa session SQLAlchemy.

La clé composée contient utilisateur, type d'opération et clé client. Le payload normalisé devient
un JSON canonique puis une empreinte SHA-256. Une insertion concurrente attend le commit ou rollback
du détenteur. Même empreinte : retour du résultat existant. Autre empreinte : refus.

Le service verrouille les deux comptes dans l'ordre des UUID avec `FOR UPDATE`, puis recharge leurs
valeurs grâce à `populate_existing=True`. Il vérifie propriétaire et fonds, prépare le transfert,
les nouveaux soldes et deux écritures opposées. Les services flushent sans committer eux-mêmes.

Au commit, les contraintes différées vérifient les deux écritures attendues et l'égalité entre
soldes et journal. L'idempotence est complétée dans le même commit. Une erreur avant commit annule
tout, y compris la réservation de clé. `flush()` ne signifie pas que l'opération est durable.

## Concurrence : pourquoi cela tient

Avec 100 EUR et deux débits simultanés de 80 EUR, le premier verrouille, lit 100 et termine avec 20.
Le second attend, relit 20 et échoue. Vérifier les fonds avant de verrouiller permettrait aux deux
requêtes de lire 100.

Verrouiller « source puis destination » pour A→B et B→A peut créer un cycle d'attente. L'ordre global
des UUID évite ce cycle entre les chemins actuels. Cela ne prouve pas l'absence de tout deadlock
possible dans de futurs chemins SQL. Les délais de verrouillage et de connexion sont bornés.

Le point subtil est l'identity map : la ligne PostgreSQL verrouillée peut être fraîche alors que
SQLAlchemy conserve une ancienne instance. Un test vérifie que le rechargement explicite empêche
ce solde obsolète d'autoriser une dépense supplémentaire.

Les routes synchrones s'exécutent dans les threads FastAPI. Le pool limite les connexions. Cela
permet des attentes concurrentes de base/réseau, pas un parallélisme illimité des calculs Python.
Ajouter `async` ne supprimerait ni la contention ni le besoin de transactions.

## Remboursements et réconciliation

Un remboursement crée un transfert d'exactement le même montant dans l'autre sens. L'original reste
inchangé. Seul son destinataire peut autoriser le nouveau débit ; le payeur ne peut reprendre
arbitrairement l'argent d'un tiers.

Le verrou `FOR NO KEY UPDATE` sur l'original sérialise les remboursements sans bloquer les contrôles
de clé étrangère `KEY SHARE`. L'unicité de `reversal_of` fournit une deuxième défense. Les fonds
sont contrôlés normalement. Les remboursements partiels demanderaient un invariant sur leur somme
cumulée et ne sont pas implémentés.

La réconciliation recalcule depuis le journal sans utiliser le service de posting. Une requête SQL
unique utilise un snapshot MVCC cohérent ; plusieurs lectures séparées pourraient produire un faux
écart pendant un transfert. Le test de corruption injecte 7 centimes dans une base jetable et vérifie
leur détection sans réparation automatique.

## Sécurité et conception objet

Les mots de passe utilisent scrypt avec sel aléatoire ; SHA-256 seul serait trop rapide. Les tokens
sont aléatoires sur 256 bits et seul leur condensat SHA-256 est stocké : leur forte entropie justifie
ce choix différent. Chaque requête vérifie expiration, révocation et utilisateur actif en base.
Une révocation ne stoppe pas une requête déjà authentifiée.

Un UUID n'est pas une autorisation. Les lectures filtrent le propriétaire et les débits contrôlent
la source, même pour un administrateur. Le funding, le rapprochement et les métriques nécessitent
le rôle administrateur. Les logs évitent mots de passe, tokens et paramètres SQL.

Les entités ORM représentent identité et persistance. Les DTO Pydantic définissent la frontière HTTP.
`Session` fournit identity map et unité de travail ; `Principal` est immuable. Les services sans état
utilisent des fonctions composées. Une interface de repository supplémentaire ou une hiérarchie
de classes apporterait ici de l'indirection sans deuxième implémentation utile.

Un dictionnaire associe les UUID aux deux comptes chargés. Les recherches utilisent des B-tree.
L'empreinte est linéaire dans la taille du payload. L'historique utilise l'index composé
`(account_id, created_at, id)` ; le curseur fait un seek, alors que l'offset parcourt les lignes sautées.
L'UUID départage les timestamps identiques. Les pages HTTP ne partagent toutefois pas un snapshot :
un export strictement cohérent nécessiterait un autre mécanisme.

## Présenter les preuves et les chiffres

**149 tests backend sur 149 passent pour 0004** : 147 en 25,75 s, puis deux tests HTTP en 0,94 s.
La couverture **816/867 = 94,12 %** mesure les instructions exécutées, pas une probabilité d'absence
de bug. La CLI interactive reste incluse au dénominateur sans couverture. Les 26 tests frontend et
12 tests navigateur passent ; migrations et déploiement Docker local aussi. La CI distante n'a pas
encore tourné. Preuves : `artifacts/releases/2026-10-22-projection/`.

Les mesures HTTP en boucle fermée couvrent 4 scénarios, 1/8/32 clients et trois répétitions de 200
requêtes : 7 200 requêtes, sans réponse inattendue ni écart comptable. Exemples de médianes des
statistiques de répétition, pas de percentiles agrégés :

| Scénario | Clients | Requêtes/s | Médiane des p95 |
|---|---:|---:|---:|
| Lecture de solde | 8 | 921,9 | 10,83 ms |
| Transferts indépendants | 8 | 459,7 | 20,65 ms |
| Transferts indépendants | 32 | 403,4 | 112,25 ms |
| Source partagée | 8 | 353,6 | 27,00 ms |
| Source partagée | 32 | 304,1 | 136,19 ms |

Le profil de service comprend 100 transferts par profondeur et trois répétitions : 1 200 transferts.
Le p95 médian est de 4,85 ms à profondeur zéro et 5,75 ms à profondeur 10 000 ; le p95 de commit
est respectivement 0,717 et 0,622 ms. Six exécutions SQL applicatives par transfert sont mesurées ;
les instructions internes aux triggers ne figurent pas dans ce compteur. cProfile ajoute du coût.

La boucle ouverte propose 30 000 arrivées : 18 439 sont envoyées, 11 561 abandonnées par le
générateur (retard ou limite de requêtes simultanées). Aucun résultat envoyé n'est inattendu ou
incertain ; toutes les réconciliations passent. Les six essais à 100 requêtes/s tiennent leur
objectif pendant cinq secondes chacun. À 300, deux sur six le tiennent ; à 600, aucun. Ce ne sont
ni des pertes d'argent ni un SLO garanti à 100 requêtes/s. Générateur et serveur partagent le Mac.

Le notebook et les graphiques lisent les JSON ; ils ne déclenchent pas de transactions. Les anciens
résultats du 20 octobre restent archivés. Comparer deux révisions dans des conditions différentes
ne démontre pas un gain causal de bout en bout. Voir `docs/LATENCY_RESULTS.md`.

## Compromis et évolutions défendables

La version 0003 recalculait le total du journal à chaque validation de solde : le coût dépendait
de l'historique. La migration 0004 ajoute une projection maintenue par les nouvelles écritures,
puis conserve la comparaison différée au commit. La réconciliation recalcule toujours le journal
indépendamment et vérifie les deux représentations. Expliquer la preuve par induction, le verrou,
le rollback et la protection contre les modifications directes plutôt que promettre un gain.

Le générateur en boucle ouverte a mesuré les arrivées prévues, les abandons et le délai de
programmation. Ses 18 cas montrent la saturation ; les résultats historiques restent séparés. Le timer de commit inclut les contraintes différées et le
profilage ajoute son propre coût. Voir `docs/LATENCY.md` pour les conditions de comparaison.

Pour des notifications externes, une outbox transactionnelle éviterait de publier les effets d'une
transaction annulée. Cette extension n'est pas implémentée.

Après un commit, une réponse réseau perdue laisse le client incertain. Il doit réessayer le même
payload avec la même clé. Un effet validé par clé ne signifie pas une livraison réseau « exactement
une fois ». Le serveur n'effectue pas de retry monétaire aveugle.

La formulation exacte est : « backend de portfolio dont les invariants ont été vérifiés sur
PostgreSQL, avec des mesures locales et des limites documentées ». Une exploitation réelle exige
encore TLS déployé et vérifié, limitation distribuée des abus, contrôles de comptes,
sauvegardes/restaurations, supervision opérationnelle
et preuves de reprise après incident. Les fonctionnalités de banque/settlement ne sont pas présentes.

La préparation publique ajoute une limite locale aux connexions et inscriptions : fenêtre glissante,
compteurs bornés et verrou Python pour réserver deux places de vérification simultanées. Ce verrou
protège l'état en mémoire ; les transactions financières restent protégées par PostgreSQL. Les
nouveaux tests isolés passent, mais le nouveau conteneur et la suite complète doivent être relancés.
Le guide est dans [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).


## Montrer le frontend sans perdre le fil backend

Le frontend React/TypeScript sert à rendre les garanties observables. Il n'ajoute pas de règles
financières concurrentes : la validation du solde et la propriété restent vérifiées en base/API.
Le parcours de présentation est dans [docs/DEMO.md](docs/DEMO.md).

À expliquer : JavaScript Number ne représente pas exactement tous les montants autorisés ; les
centimes sont donc des BigInt, et lossless-json préserve ces entiers dans les requêtes et réponses.
Une intention confirmée fige aussi une clé d'idempotence et une charge utile. Réessayer après une
réponse perdue réutilise les deux. Un rechargement perd cette intention en mémoire : on avertit
l'utilisateur et on lui demande de consulter l'historique avant un nouveau paiement.

Le build est statique et servi par FastAPI. Node et Vite servent à construire le frontend ; aucun
serveur Node n'est requis pour la démonstration compilée. Les captures automatisées contiennent des
fixtures explicitement synthétiques ; une vraie inscription démarre avec zéro compte.

Le [carnet PDF](output/pdf/ledgerx-construction-pas-a-pas.pdf) récapitule les étapes, les choix et
les preuves. Il décrit un travail assisté par IA et l'évolution d'un dépôt existant, sans inventer
une histoire de développement entièrement manuelle.
