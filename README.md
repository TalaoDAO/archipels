# Installation d'un issuer et verifier pour l'app smartphone Talao wallet

python3 -m venv venv 
. venv/bin/activate

pip install redis  
pip install flask-session  
pip install didkit==0.2.1 

python issuer.py  
ou  
python verifier.py  



