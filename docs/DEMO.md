# Démontrer LedgerX en cinq minutes

Le produit manipule exclusivement des fonds fictifs. Le frontend est une interface React originale,
servie par FastAPI sur la même adresse. Il ne contient aucun jeu de données de démonstration caché.
Les captures des tests navigateur utilisent des fixtures synthétiques, distinctes du produit.

## 1. Démarrer le projet

Depuis le dossier LedgerX, après l'installation Python et PostgreSQL décrite dans le README :

```bash
docker compose up -d db

# À faire une première fois ; Node et ses caches restent dans le projet.
bash scripts/setup_frontend.sh
bash scripts/frontend.sh install
bash scripts/frontend.sh build

# Créer un administrateur local, en saisissant son mot de passe dans le terminal.
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli create-admin

# Démarrer l'application ; Ctrl+C l'arrête.
ENABLE_DEV_FUNDING=true bash scripts/run_local.sh
```

Ouvrir **http://127.0.0.1:8000**. L'API reste accessible sur `/docs`.
Le flag ne donne pas de droits supplémentaires aux utilisateurs ordinaires : le financement exige
aussi un administrateur. Ne pas utiliser les identifiants du benchmark pour la base principale :
ce sont des bases indépendantes.

Après une modification frontend, recompiler avec `bash scripts/frontend.sh build`, puis recharger.
Pour le rechargement automatique pendant le développement, laisser FastAPI tourner sur 8000 et
lancer `bash scripts/frontend.sh dev` dans un deuxième terminal ; ouvrir http://127.0.0.1:5173.
Vite transmet les requêtes API à FastAPI. Le build final n'a pas besoin d'un serveur Node.

## 2. Le parcours à montrer

1. Se connecter avec l'administrateur local. Ouvrir deux comptes EUR depuis **Open an account**.
2. Dans **My accounts**, sélectionner le premier et cliquer **Add demo funds**. Ajouter 100,00 EUR.
   La transaction de financement produit également deux écritures : le compte système est la
   contrepartie. Rien n'est ajouté silencieusement à la connexion.
3. Cliquer **Send money**, sélectionner le second compte, saisir 12,34 EUR, puis **Review transfer**
   et **Confirm transfer**. Montrer les soldes : 87,66 EUR et 12,34 EUR.
4. Sélectionner le second compte et ouvrir **Activity**. Ouvrir le paiement reçu, puis
   **Return this payment**. Donner une raison et confirmer le remboursement complet.
5. Montrer les soldes revenus à 100,00 EUR et 0,00 EUR. Les anciennes écritures sont toujours là ;
   le remboursement apparaît comme une nouvelle opération.
6. Ouvrir **Operations**, lancer **Run reconciliation** et expliquer le recalcul indépendant.

Pour démontrer les permissions, créer ensuite un profil normal : il n'a ni financement ni écran
administratif. Ses comptes sont privés. Un administrateur peut financer un compte client via
`POST /dev/funding` dans Swagger avec son UUID ; le bouton de financement du dashboard cible
uniquement le compte actuellement sélectionné de l'administrateur.

## 3. Les explications qui accompagnent les écrans

| À l'écran | Ce qui se passe derrière |
|---|---|
| Saisie de 12,34 EUR | Conversion exacte en 1 234 centimes avec BigInt ; JSON sans perte |
| Confirmation du virement | Une intention fige le montant, la destination et la clé d'idempotence |
| Traitement | Une transaction PostgreSQL ; deux comptes verrouillés dans un ordre stable |
| Résultat | Transfert, débit, crédit, soldes et référence idempotente validés ensemble |
| Remboursement | Nouveau transfert opposé, lié à l'original ; ancien journal inchangé |
| Réconciliation | Somme indépendante du journal et comparaison avec les soldes stockés |
| Graphique | Activité réelle chargée, fenêtre de sept jours indiquée ; aucune prévision |

Les montants positifs/négatifs de l'historique sont les écritures du compte sélectionné. Un
remboursement est également une écriture : ouvrir le détail pour consulter son type et son lien.

## 4. Vérifier les preuves

```bash
bash scripts/verify_local.sh
bash scripts/frontend.sh browsers  # installation initiale de Chromium dans .runtime
bash scripts/verify_web.sh
```

La première commande réinitialise uniquement la base `_test` ; la seconde vérification ajoute des
fixtures à `_bench`. Ne pas exécuter plusieurs pipelines de test simultanément. Les rapports sont
dans `artifacts/`. Les tests navigateur distinguent les scénarios avec réponses contrôlées et le
parcours réel navigateur → FastAPI → PostgreSQL.

Les scripts de vérification arrêtent leur serveur temporaire à la fin. Ils ne remplacent donc pas
`run_local.sh` pour visiter l'application après les tests.

## 5. Points à annoncer clairement

- Recharger la page efface la session du navigateur : se reconnecter. Un token actif côté serveur
  reste valable jusqu'à son expiration ou une déconnexion explicite.
- En cas de réponse perdue, garder le dialogue ouvert et utiliser **Retry same request**. Ne pas
  changer le montant, la destination ou la clé. Après fermeture ou rechargement, vérifier l'activité.
- Le bouton **Refresh** relit les données ; les pages n'utilisent ni WebSocket ni actualisation
  permanente. Le solde affiché peut changer avant la validation : la base décide avec son verrou.
- La pagination ne constitue pas un instantané de toute la session. Les totaux affichés portent
  sur les écritures chargées, pas nécessairement tout l'historique.
- Ouvrir une URL `localhost` ou HTTPS : certaines API de navigateur exigent un contexte sécurisé.
  Une adresse HTTP du réseau local n'est pas un mode de partage pris en charge.
- Aucun taux de disponibilité, nombre maximal d'utilisateurs ou niveau bancaire n'est promis.
  Les mesures locales du README sont des observations avec leur protocole et leurs limites.

Lire aussi le [carnet de construction PDF](../output/pdf/ledgerx-construction-pas-a-pas.pdf),
le [rapport d'ingénierie](ENGINEERING_REPORT.md) et les [notes d'entretien](../INTERVIEW_NOTES.md).
