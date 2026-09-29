import tempfile
import unittest
from pathlib import Path
from stocks import lire_stock, appliquer_stock


class TestsStocks(unittest.TestCase):
    def test_pourcentages_et_identifiants(self):
        elements = [{'repere': 'P5', 'label': 'carnets bleus'}, {'repere': 'P2', 'label': 'stylos noirs'}]
        legende = [{'label': 'carnets bleus', 'quantite_par_symbole': 10}, {'label': 'stylos noirs', 'quantite_par_symbole': 25}]
        stock = {'N7': {'quantite': 7, 'type_objet': 'carnet bleu'}, 'S3': {'quantite': 1, 'type_objet': 'stylo noir'}}
        appliquer_stock(elements, legende, [{'candidat': 'P2', 'repere': 'S3'}, {'candidat': 'P5', 'repere': 'N7'}], stock)
        self.assertEqual([e['taux_remplissage'] for e in elements], [70, 4])
        self.assertEqual([e['repere'] for e in elements], ['N7', 'S3'])

    def test_zero_et_depassement_non_plafonne(self):
        for quantite, attendu in [(0, 0), (12, 120)]:
            elements = [{'repere': 'P1', 'label': 'carnets bleus'}]
            appliquer_stock(elements, [{'label': 'carnets bleus', 'quantite_par_symbole': 10}],
                            [{'candidat': 'P1', 'repere': 'N1'}], {'N1': {'quantite': quantite, 'type_objet': 'carnet bleu'}})
            self.assertEqual(elements[0]['taux_remplissage'], attendu)

    def test_incertitudes_ne_deviennent_pas_des_chiffres(self):
        for reperes, stock in [([], {}), ([{'candidat': 'P1', 'repere': 'N8'}], {}),
            ([{'candidat': 'P1', 'repere': 'N8'}], {'N8': {'quantite': 8, 'type_objet': 'stylo noir'}}),
            ([{'candidat': 'P1', 'repere': 'N8'}, {'candidat': 'P2', 'repere': 'N8'}], {'N8': {'quantite': 8, 'type_objet': 'carnet bleu'}})]:
            elements = [{'repere': 'P1', 'label': 'carnets bleus'}]
            appliquer_stock(elements, [{'label': 'carnets bleus', 'quantite_par_symbole': 10}], reperes, stock)
            self.assertIsNone(elements[0]['taux_remplissage'])

    def test_csv_valide_et_invalide(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            fichier = dossier / 'stock.csv'
            fichier.write_text('numero,quantite,type_objet\nN7,7,carnet bleu\n', encoding='utf-8-sig')
            self.assertEqual(lire_stock(dossier, 'stock.csv')['N7']['quantite'], 7)
            for texte in ['numero,quantite,type_objet\nN7,-1,carnet bleu\n',
                          'numero,quantite,type_objet\nN7,1,carnet bleu\nN7,2,carnet bleu\n',
                          'numero,quantite\nN7,7\n']:
                fichier.write_text(texte, encoding='utf-8')
                with self.assertRaises(ValueError):
                    lire_stock(dossier, 'stock.csv')
            with self.assertRaises(ValueError):
                lire_stock(dossier, '../stock.csv')


if __name__ == '__main__':
    unittest.main()
