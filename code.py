#!/usr/bin/env python3

from pathlib import Path
import os.path
import random as rd
import argparse
import subprocess
import sys
import os


#Import des bibliothèques non-standards
#OpenSSL
try:
	from OpenSSL import crypto, SSL
except ImportError:
	subprocess.check_call([sys.executable, "-m", "pip", "install", "openssl-python"])
	print("Erreur avec la libraire OpenSSL. Essayer:\nsudo apt-get install libssl-dev libffi-dev");
	exit(0)

#Cryptodome pour RSA et DSA
try:
	import Crypto.PublicKey
	from Crypto.PublicKey import RSA,DSA
	if int(Crypto.__version__[0])<3:
		subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "pycryptodome"])
except ImportError:
	subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "pycryptodome"])
	print("Erreur avec la libraire PyCryptodome. Essayer:\npip3 uninstall PyCrypto");
	exit(0)


#Pour éviter des erreurs, on s'assure que certaines entrées soient non-vides
def entree_non_vide(texte):
	entree=""
	while entree=="":
		entree=input(texte)
	return entree


#On vérifie que les valeurs soient bien des entiers
def entree_entier(texte,defaut):
	entree=input(texte) or defaut
	try:
		return int(entree)
	except:
		print("Nombre incorrect")
		return entree_entier(texte,defaut)


#On enregistre une clé privée avec une passphrase
def enregistrer_passphrase(cle,passphrase,type_c):
	sortie = open("tmp.txt", "w")
	sortie.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, cle).decode("utf-8"))
	sortie.close()
		
	f = open('tmp.txt','r')
	if type_c in {"r","R"}:
		key = RSA.importKey(f.read())
	else:
		key = DSA.importKey(f.read())
	f.close()
	
	nom=entree_non_vide("Sous quel nom enregistrer la clé privée chiffrée (.pem) ?\n")
	if Path(nom).is_file():
		print("Fichier existant, veuillez choisir un nouveau nom")
		return enregistrer_passphrase(cle,passphrase)
	
	f = open(nom+".pem",'w')
	f.write(key.exportKey('PEM',passphrase=passphrase).decode('ascii'))
	f.close()
	os.remove("tmp.txt")


#Enregistrer paire clés en appelant enregistrer_fichier()
def enregistrer_cle(cle,type_c):
	print("On enregistre la clé privée")
	passphrase=input("Passphrase (optionnel):")
	if passphrase != "":
		enregistrer_passphrase(cle,passphrase,type_c)
	else:
		cle_privee = crypto.dump_privatekey(crypto.FILETYPE_PEM, cle)
		enregistrer_fichier("pem", cle_privee)
	
	print("On enregistre la clé publique")
	cle_publique = crypto.dump_publickey(crypto.FILETYPE_PEM, cle)
	enregistrer_fichier("pem", cle_publique)
	
	
#Enregistrer un fichier sur le disque
def enregistrer_fichier(ftype, objet):
	nom=entree_non_vide("Sous quel nom enregistrer le fichier ."+ftype+" ?\n")
	if Path(nom+"."+ftype).is_file():
		print("Fichier existant, veuillez choisir un nouveau nom")
		return enregistrer_fichier(ftype, objet)
	sortie = open(nom+"."+ftype, "w")
	sortie.write(objet.decode("utf-8") )
	sortie.close()


#Ouvrir un fichier
def ouvrir_fichier(type_fichier):
	
	chemin=input("Chemin pour le fichier "+type_fichier+" :")
		
	if not Path(chemin).is_file():
		print("Fichier non trouvé, veuillez réessayer")
		return ouvrir_fichier(type_fichier)
		
	fichier=open(chemin, 'rt').read()
	try:
		if str(type_fichier)=="csr":
			objet=crypto.load_certificate_request(crypto.FILETYPE_PEM, fichier)
		elif str(type_fichier)=="crt":
			objet=crypto.load_certificate(crypto.FILETYPE_PEM, fichier)
		elif str(type_fichier)=="clé privée":
			try:
				objet=crypto.load_privatekey(crypto.FILETYPE_PEM, fichier)
			except:
				print("Passphrase invalide. On recommence.")
				return ouvrir_fichier(type_fichier)
	except:
		print("Le fichier entré n'est pas du bon type, veuillez vérifier")
		return ouvrir_fichier(type_fichier)
		 
	return objet
	

#Générer une paire de clés
def paire_cle():
	print("CRÉATION DE LA PAIRE DE CLÉS")
	cle=crypto.PKey()
	type_c=input("Chiffrement RSA ou DSA ? [R/D]:")
	bits=entree_entier("Clé de combien de bits ? (2048 par défaut):",2048)

	if type_c in {"r","R"}:
		cle.generate_key(crypto.TYPE_RSA, int(bits))
	elif type_c in {"d","D"}:
		cle.generate_key(crypto.TYPE_DSA, int(bits))
	else:
		print("Choix de chiffrement non valide, veuillez réessayer")
		return paire_cle()
		
	return cle,type_c
		

#Signature d'une CSR pour créer un certificat
def signature_cert():
	csr=ouvrir_fichier("csr")
	
	print("Certificat de la CA:")
	ca = ouvrir_fichier("crt")
	print("Il faut la clé privé de la CA")
	ca_cle = ouvrir_fichier("clé privée")
	
	serialnb=rd.getrandbits(64)

	cert = crypto.X509()
	cert.set_issuer(ca.get_subject())
	cert.set_subject(csr.get_subject())
	cert.set_pubkey(csr.get_pubkey())
	
	cert.gmtime_adj_notBefore(0)
	cert.gmtime_adj_notAfter(365*24*60*60)
	
	cert.set_serial_number(serialnb)
	
	cert.sign(ca_cle, "sha256")
	
	crt_sortie = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
	
	print("On enregistre le nouveau certificat créé")
	enregistrer_fichier("crt",crt_sortie)
	

#Création de la CA
def creation_ca():
	cle,type_c=paire_cle()
	ca = crypto.X509()
	ca.set_version(3)
	ca.set_serial_number(1)
	sujet=entree_non_vide("Sujet de la CA (ex: localhost): ")
	ca.get_subject().CN = sujet
	ca.gmtime_adj_notBefore(0)
	ca.gmtime_adj_notAfter(365*24*60*60)
	ca.set_issuer(ca.get_subject())
	ca.set_pubkey(cle)
	ca.add_extensions([crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE, pathlen:0"),crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"), crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=ca),])
	ca.sign(cle, "sha256")
	
	ca_sortie = crypto.dump_certificate(crypto.FILETYPE_PEM, ca)
	
	print("On enregistre la CA")
	enregistrer_fichier("crt",ca_sortie)

	enregistrer_cle(cle,type_c)
	
	
#Création d'une CSR
def requete_csr():
	print("CRÉATION DE LA REQUÊTE CSR\n");
	cle,type_c=paire_cle()
	pays=""
	liste=list()

	csr = crypto.X509Req()
	csr.get_subject().CN = entree_non_vide("Nom du certificat: ")
	
	while len(pays)!=2 : pays=input("Pays (2 car.):");
	csr.get_subject().countryName = pays
	csr.get_subject().stateOrProvinceName = entree_non_vide("Région: ")
	csr.get_subject().localityName = entree_non_vide("Ville: ")
	csr.get_subject().organizationName = entree_non_vide("Organisation: ")
	csr.get_subject().organizationalUnitName = entree_non_vide("Unité: ")
	csr.get_subject().emailAddress = entree_non_vide("Adresse mail: ")
	
	nb_san=entree_entier("Nombre de noms de domaine alternatifs (0 par défaut):",0)
	
	csr.get_subject().subjectAltName = str(nb_san)

	for i in range(0, int(csr.get_subject().subjectAltName)):
		liste.append('DNS:'+input("Nom DNS "+str(i+1)+' :'))

	if int(csr.get_subject().subjectAltName) > 0:
		csr.add_extensions([crypto.X509Extension(b'subjectAltName', False,','.join(liste).encode())])
	
	csr.set_pubkey(cle)
	csr.sign(cle, "sha256")

	enregistrer_cle(cle,type_c)
	
	csr_sortie = crypto.dump_certificate_request(crypto.FILETYPE_PEM, csr)
	print("On enregistre la requête")
	enregistrer_fichier("csr",csr_sortie)


#Vérification de la signature d'un certificat à partir de la CA + de l'association clé privée/certificat
def verif():
	choix=input("Vérifier:\n1: La clé privée du certificat\n2: L'émetteur du certificat\nVotre choix:")
	
	print("On ouvre le certificat à vérifier")
	client_cert=ouvrir_fichier("crt")
	if str(choix) =="1":
		ctx = SSL.Context(SSL.TLSv1_METHOD)
		ctx.use_certificate(client_cert)
		ctx.use_privatekey(ouvrir_fichier("clé privée"))

		try:
			ctx.check_privatekey()
		except SSL.Error:
			print("\nIl n'y a pas de correspondance entre la clé privée et le certificat\n")
		else:
			print("\nLa clé privée correspond au certificat\n")

	elif str(choix)=="2":
		print("Certificat de la CA:")
		serveur_cert=ouvrir_fichier("crt")		
		
		try:
			store = crypto.X509Store()
			store.add_cert(serveur_cert)

			store_ctx = crypto.X509StoreContext(store, client_cert)
			store_ctx.verify_certificate()
			print("\nCertificat bien signé par la CA\n")

		except Exception as e:
			print("\nLes certificats ne correspondent pas\n")
			print(e)
	else:
		print("Choix incorrect, veuillez recommencer")
		verif()

	
#Parseur d'arguments
parser = argparse.ArgumentParser(description='Création automatique de CSR, CA, signature de certificat et vérification de la signature et de la clé d\'un certificat. Choix dans le chiffrement des clés. Fonction de hashage: SHA256')
parser.add_argument('--csr', help='Génération d\'une CSR',action='store_true')
parser.add_argument('--ca', help='Création d\'une CA',action='store_true')
parser.add_argument('--sign', help='Création d\'un certificat à partir de la CA',action='store_true')
parser.add_argument('--verif', help='Vérifications de la clé et signature d\'un certificat',action='store_true')

args = parser.parse_args()
if args.csr:
	requete_csr()
elif args.ca:
	creation_ca()
elif args.sign:
	signature_cert()
elif args.verif:
	verif()
else:
	parser.print_help()
