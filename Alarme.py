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
    init_bdd()
    insert_sql("INSERT OR REPLACE INTO etat_alarme (id, est_activee, mise_a_jour_le) VALUES (1, ?, CURRENT_TIMESTAMP)", (1 if est_activee else 0,))

    type_evenement = "Armement" if est_activee else "Désarmement"
    etat = "ARMÉ" if est_activee else "DÉSARMÉ"
    insert_sql("INSERT INTO historique_alarme (type_evenement, etat) VALUES (?, ?)", (type_evenement, etat))


class EcranLCD:
    def __init__(self):
        self.bus = smbus.SMBus(1)
        self.adresse_texte = 0x3e
        self.adresse_couleur = 0x62
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

    def changer_couleur(self, r, g, b):
        self.bus.write_byte_data(self.adresse_couleur, 0x04, r)
        self.bus.write_byte_data(self.adresse_couleur, 0x03, g)
        self.bus.write_byte_data(self.adresse_couleur, 0x02, b)

    def ecrire_texte(self, message):
        self.bus.write_byte_data(self.adresse_texte, 0x80, 0x01)
        time.sleep(0.05)
        for lettre in message:
            self.bus.write_byte_data(self.adresse_texte, 0x40, ord(lettre))


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
        self.bouton.on_event = self.action_bouton
        self.led.off()
        self.buzzer.write(0)

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
        if nombre_de_fois == 1:
            etat_alarme_et_historique(True)
        else :
            etat_alarme_et_historique(False)

    def action_bouton(self, pin, value):
        if value == 1:
            self.est_actif = not self.est_actif

            if self.est_actif == True:
                print("Système ACTIVÉ")
                self.led.on()
                self.lcd.ecrire_texte("Alarme Activee")
                self.lcd.changer_couleur(0, 255, 0)
                self.faire_bip(1)
            else:
                print("Système DÉSACTIVÉ")
                self.led.off()
                self.arreter_sonnerie()
                self.lcd.ecrire_texte("Systeme Eteint")
                self.lcd.changer_couleur(50, 50, 50)
                self.faire_bip(2)


    def declencher_sonnerie(self):
        if self.sonne == False:
            print("ALERTE ! Mouvement !")
            self.buzzer.write(1)
            self.lcd.ecrire_texte("INTRUSION !!!")
            self.lcd.changer_couleur(255, 0, 0)
            self.debut_sonnerie = time.time()
            self.sonne = True

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
        self.lcd.ecrire_texte("Systeme Eteint")
        self.lcd.changer_couleur(50, 50, 50)
        print("Programme lancé. En attente...")
        while True:
            if self.est_actif == True and self.capteur.read() == 1:
                self.declencher_sonnerie()
            if self.sonne == True:
                maintenant = time.time()
                if maintenant - self.debut_sonnerie > self.duree_sonnerie:
                    print("Fin du temps de sonnerie.")
                    self.arreter_sonnerie()
                elif maintenant - self.dernier_clignotement > 0.25:
                    if self.etat_clignotement == False:
                        self.lcd.changer_couleur(255, 0, 0)
                        self.etat_clignotement = True
                    else:
                        self.lcd.changer_couleur(0, 0, 0)
                        self.etat_clignotement = False
                    self.dernier_clignotement = maintenant
            time.sleep(0.1)



if __name__ == "__main__":
    mon_alarme = SystemeAlarme()
    mon_alarme.demarrer()
