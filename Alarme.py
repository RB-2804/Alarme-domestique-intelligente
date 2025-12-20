import time
import smbus2 as smbus
from grove.gpio import GPIO
from grove.grove_led import GroveLed
from grove.grove_mini_pir_motion_sensor import GroveMiniPIRMotionSensor
from database import init_db, select_sql, insert_sql


# --- Configuration des Ports ---
PIN_PIR = 5       # Le capteur de mouvement (Mini PIR Motion Sensor) sur D5
PIN_BUZZER = 16   # Buzzer sur D16
PIN_BUTTON = 18   # Bouton sur D18
PIN_LED = 22      # LED sur D22

_bdd_initialisee = False

def init_bdd() -> bool:
    global _bdd_initialisee
    if _bdd_initialisee:
        return False
    init_db()
    _bdd_initialisee = True
    return True


def lire_etat_alarme_bdd() -> bool:
    init_bdd()
    lignes = select_sql("SELECT est_activee FROM etat_alarme WHERE id = 1", ())
    if not lignes:
        return False
    return bool(lignes[0][0])


def etat_alarme_et_historique(est_activee: bool):
    """Met à jour l'état et ajoute à l'historique SEULEMENT si ça a changé"""
    init_bdd()
    insert_sql("INSERT OR REPLACE INTO etat_alarme (id, est_activee, mise_a_jour_le) VALUES (1, ?, CURRENT_TIMESTAMP)", (1 if est_activee else 0,))
    nouvel_etat = "ARMÉ" if est_activee else "DÉSARMÉ"
    type_evenement = "Armement" if est_activee else "Désarmement"
    derniere_ligne = select_sql("SELECT etat FROM historique_alarme ORDER BY id DESC LIMIT 1", ())
    if derniere_ligne and derniere_ligne[0][0] == nouvel_etat:
        return
    insert_sql("INSERT INTO historique_alarme (type_evenement, etat) VALUES (?, ?)", (type_evenement, nouvel_etat))

def evenement_declenchement(type_evenement: str, etat: str, description: str):
    init_bdd()
    insert_sql("INSERT INTO historique_alarme (type_evenement, etat, description) VALUES (?, ?, ?)", (type_evenement, etat, description))


class EcranLCD:
    def __init__(self):
        self.bus = smbus.SMBus(1)
        self.adresse_texte = 0x3e
        self.adresse_couleur = 0x62
        try:
            time.sleep(0.05)
            self.bus.write_byte_data(self.adresse_texte, 0x80, 0x28)
            time.sleep(0.05)
            self.bus.write_byte_data(self.adresse_texte, 0x80, 0x0C)
            time.sleep(0.05)
            self.bus.write_byte_data(self.adresse_texte, 0x80, 0x01)
            time.sleep(0.05)
            self.bus.write_byte_data(self.adresse_couleur, 0x00, 0x00)
            self.bus.write_byte_data(self.adresse_couleur, 0x01, 0x05)
            self.bus.write_byte_data(self.adresse_couleur, 0x08, 0xAA)
        except: pass

    def changer_couleur(self, r, g, b):
        try:
            self.bus.write_byte_data(self.adresse_couleur, 0x04, r)
            self.bus.write_byte_data(self.adresse_couleur, 0x03, g)
            self.bus.write_byte_data(self.adresse_couleur, 0x02, b)
        except: pass

    def ecrire_texte(self, message):
        try:
            self.bus.write_byte_data(self.adresse_texte, 0x80, 0x01)
            time.sleep(0.05)
            for lettre in message:
                self.bus.write_byte_data(self.adresse_texte, 0x40, ord(lettre))
        except: pass


class SystemeAlarme:
    def __init__(self):
        self.capteur = GroveMiniPIRMotionSensor(PIN_PIR)
        self.buzzer = GPIO(PIN_BUZZER, GPIO.OUT)
        self.bouton = GPIO(PIN_BUTTON, GPIO.IN)
        self.led = GroveLed(PIN_LED)
        self.lcd = EcranLCD()

        self.est_actif = lire_etat_alarme_bdd()
        
        self.sonne = False
        self.duree_sonnerie = 2
        self.debut_sonnerie = 0
        self.dernier_clignotement = 0
        self.etat_clignotement = False
        
        self.led.off()
        self.buzzer.write(0)

        if self.est_actif:
            self.led.on()
            self.lcd.ecrire_texte("Alarme Activee")
            self.lcd.changer_couleur(0, 255, 0)
        else:
            self.lcd.ecrire_texte("Systeme Eteint")
            self.lcd.changer_couleur(50, 50, 50)

    def configurer_duree(self):
        print("--- CONFIGURATION ---")
        print("Combien de temps l'alarme doit sonner ? (en secondes)")
        reponse = input(">> ")
        try:
            self.duree_sonnerie = int(reponse)
        except ValueError:
            print("Erreur de saisie.")
            self.duree_sonnerie = 2
        print("Durée réglée sur", self.duree_sonnerie, "secondes.")
        print("-" * 20)

    def faire_bip(self, nombre_de_fois):
        for i in range(nombre_de_fois):
            self.buzzer.write(1)
            time.sleep(0.1)
            self.buzzer.write(0)
            time.sleep(0.1)
    

    def action_bouton(self):
        self.est_actif = not self.est_actif

        if self.est_actif == True:
            print("Système ACTIVÉ (Physique)")
            self.led.on()
            self.lcd.ecrire_texte("Alarme Activee")
            self.lcd.changer_couleur(0, 255, 0)
            self.faire_bip(1)
        else:
            print("Système DÉSACTIVÉ (Physique)")
            self.led.off()
            self.arreter_sonnerie()
            self.lcd.ecrire_texte("Systeme Eteint")
            self.lcd.changer_couleur(50, 50, 50)
            self.faire_bip(2)
        etat_alarme_et_historique(self.est_actif)
        
    def declencher_sonnerie(self):
        if self.sonne == False:
            print("ALERTE ! Mouvement !")
            self.buzzer.write(1)
            self.lcd.ecrire_texte("ALERTE ! Mouvement !")
            self.lcd.changer_couleur(255, 0, 0)
            self.debut_sonnerie = time.time()
            self.sonne = True
            evenement_declenchement("Déclenchement de l'alarme", "ARMÉ","aucune")

    def arreter_sonnerie(self):
        if self.sonne == True:
            self.buzzer.write(0)
            self.sonne = False
            if self.est_actif:
                self.lcd.ecrire_texte("Alarme Activee")
                self.lcd.changer_couleur(0, 255, 0)
            else:
                self.lcd.ecrire_texte("Systeme Eteint")
                self.lcd.changer_couleur(50, 50, 50)

    def demarrer(self):
        self.configurer_duree()
        print("Programme lancé. En attente...")
        etat_bouton_precedent = 0
        derniere_lecture_bdd = 0
        while True:
            etat_bouton_actuel = self.bouton.read()
            if etat_bouton_actuel == 1 and etat_bouton_precedent == 0:
                self.action_bouton()
                time.sleep(0.25)
            etat_bouton_precedent = etat_bouton_actuel
            maintenant = time.time()
            if maintenant - derniere_lecture_bdd > 1.0:
                etat_distant = lire_etat_alarme_bdd()
                if etat_distant != self.est_actif:
                    self.est_actif = not self.est_actif

                    if self.est_actif == True:
                        print("Système ACTIVÉ (Web)")
                        self.led.on()
                        self.lcd.ecrire_texte("Alarme Activee")
                        self.lcd.changer_couleur(0, 255, 0)
                        self.faire_bip(1)
                    else:
                        print("Système DÉSACTIVÉ (Web)")
                        self.led.off()
                        self.arreter_sonnerie()
                        self.lcd.ecrire_texte("Systeme Eteint")
                        self.lcd.changer_couleur(50, 50, 50)
                        self.faire_bip(2)
                    etat_alarme_et_historique(self.est_actif)
                derniere_lecture_bdd = maintenant
            if self.est_actif == True and self.capteur.read() == 1:
                self.declencher_sonnerie()
            if self.sonne == True:
                maintenant2 = time.time()
                if maintenant2 - self.debut_sonnerie > self.duree_sonnerie:
                    self.arreter_sonnerie()
                elif maintenant2 - self.dernier_clignotement > 0.25:
                    if self.etat_clignotement == False:
                        self.lcd.changer_couleur(255, 0, 0)
                        self.etat_clignotement = True
                    else:
                        self.lcd.changer_couleur(0, 0, 0)
                        self.etat_clignotement = False
                    self.dernier_clignotement = maintenant2
            time.sleep(0.05)

if __name__ == "__main__":
    mon_alarme = SystemeAlarme()
    mon_alarme.demarrer()
