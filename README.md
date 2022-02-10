# issuer et verifier pour l'app smartphone Talao wallet

python3 -m venv venv 
. venv/bin/activate

pip install redis  
pip install flask-session  
pip install didkit==0.2.1 
pip install web3 # pour registry seulement

python issuer.py  
ou  
python verifier.py  



Voir test.py pour des exemples de signature et verifications (doc) 

helpers pour des conversions entre ethereum et tezos cle publique/privée et adresses vs JWK  
