"""
Issuer simplifié
https://github.com/TalaoDAO/talao-wallet/blob/dev-talao/docs/talao_interaction_protocol.md

"""

from flask import Flask, jsonify, request, Response, render_template_string
from flask_qrcode import QRcode
import json
from datetime import timedelta, datetime
import uuid
import sys
import didkit
import redis
import socket

app = Flask(__name__)
qrcode = QRcode(app)
PORT = 3000

# Redis est utilisé pour stocker les données de session
red= redis.Redis(host='localhost', port=6379, db=0)

# On va utiliser did:ethr
# https://github.com/decentralized-identity/ethr-did-resolver/blob/master/doc/did-method-spec.md
issuer_key = json.dumps({"alg":"ES256K-R",
                        "crv":"secp256k1",
                        "d":"7Y_O4Vl4nr_znkq9S-Kb2sh8B-9jYST8kZTYdr9KUhU",
                        "kty":"EC",
                        "x":"Ocenh6RngwFPSNX9YZgif9Kg3stxedjLUq5Iik7WXW8",
                        "y":"cXKzcH2gtOyTBQvnLuyTz6I-qWqnS8MQnFCkhWVzojM"})
issuer_DID = didkit.keyToDID("ethr", issuer_key)
print('issuer DID = ', issuer_DID)

OFFER_DELAY = timedelta(seconds= 10*60)
CREDENTIAL_EXPIRATION_DELAY = timedelta(seconds= 365*24*60*60) # 1 year

# uniquement pour récuperer l'adresse réseau du serveur
def extract_ip():
    st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:       
        st.connect(('10.255.255.255', 1))
        IP = st.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        st.close()
    return IP

# Affichage du QR code
@app.route('/login' , methods=['GET'], defaults={'red' : red}) 
@app.route('/' , methods=['GET'], defaults={'red' : red}) 
def qrcode(red) :
    # utilisation d'un VC au format JSON-LD
    # see https://www.w3.org/TR/vc-data-model/ 
    try :
        credential = json.load(open('CertificateOfEmployment.jsonld', 'r'))
    except :
        print('probleme chargement fichier')
        sys.exit()
    credential["issuer"] = issuer_DID
    # dates au format iso
    credential['expirationDate'] = (datetime.now() +  CREDENTIAL_EXPIRATION_DELAY).replace(microsecond=0).isoformat() + "Z"
    credential['id'] = 'urn:uuid:' + str(uuid.uuid4())
    credential['issuanceDate'] = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    credentialOffer = {
            "type": "CredentialOffer",
            "credentialPreview": credential,
            "expires" : (datetime.now() + OFFER_DELAY).replace(microsecond=0).isoformat() + "Z",
            "shareLink" : "",
            "display" : { "backgroundColor" : "ffffff"}
            }
    # endpoint dynamique
    id = str(uuid.uuid4())
    url = 'http://' + IP + ':' + str(PORT) +  '/endpoint/' + id + '?issuer=' + issuer_DID
    # session data stockée avec Redis
    red.set(id, json.dumps(credentialOffer))
    # html page. le JS est utilisé pour switcher sur la page follow up apres la reception d'un event
    html_string = """  <!DOCTYPE html>
        <html>
        <head></head>
        <body>
        <center>
            <div>  
                <h2>Scan the QR Code bellow with your Talao wallet</h2> 
                <br>  
                <div><img src="{{ qrcode(url) }}" ></div>
            </div>
        </center>
        <script>
            var source = new EventSource('/issuer_stream');
            source.onmessage = function (event) {
                const result = JSON.parse(event.data)
                if (result.check == 'success' & result.id == '{{id}}'){
                    window.location.href="/followup";
                }
            };
        </script>
        </body>
        </html>"""
        
    return render_template_string(html_string,
                                url=url,
                                id=credential['id']
                                )

# Endpoint for wallet call, it is a dynamic endpoint path
@app.route('/endpoint/<id>', methods = ['GET', 'POST'],  defaults={'red' : red})
def credentialOffer_endpoint(id, red):
    try : 
        credentialOffer = red.get(id).decode()
    except :
        return jsonify('Redis server error'), 500

    if request.method == 'GET':
        return Response(json.dumps(credentialOffer, separators=(':', ':')),
                        headers={ "Content-Type" : "application/json"},
                        status=200)
                       
    if request.method == 'POST':
        credential =  json.loads(credentialOffer)['credentialPreview']
        #red.delete(id)
        # wallet DID  (user DID) est transféré par l'argument  "subject_id"
        credential['credentialSubject']['id'] = request.form['subject_id']
        # issuer signe le VC
        # options : https://www.w3.org/TR/did-core/#verification-methods
        didkit_options = {
            "proofPurpose": "assertionMethod",
            "verificationMethod": didkit.keyToVerificationMethod("ethr", issuer_key)
            }
        try :
            signed_credential =  didkit.issueCredential(json.dumps(credential),
                                                     didkit_options.__str__().replace("'", '"'),
                                                     issuer_key )
        except :
            print('JSON LD signature erreur')
            sys.exit()
        # data is pushed to the front end through redis then an event
        data = json.dumps({
                            'id' : id,
                            'check' : 'success',
                            })
        red.publish('issuer', data)
        return Response(json.dumps(signed_credential, separators=(':', ':')),
                        headers={ "Content-Type" : "application/json"},
                        status=200)


# follow up screen
@app.route('/followup', methods = ['GET'])
def credentialOffer_back():
    html_string = """
        <!DOCTYPE html>
        <html>
        <body>
        <center>
            <h2>Verifiable Credential has been signed and transfered to wallet</h2<
            <br><br><br>
            <form action="/" method="GET" >
                    <button  type"submit" >Back</button></form>
        </center>
        </body>
        </html>"""
    return render_template_string(html_string)


# server event push for user agent EventSource / 
# websocket would be another solution  (more complicated !) to synchronize with the front end
@app.route('/issuer_stream', methods = ['GET', 'POST'],  defaults={'red' : red})
def offer_stream(red):
    def event_stream(red):
        pubsub = red.pubsub()
        pubsub.subscribe('issuer')
        for message in pubsub.listen():
            if message['type']=='message':
                yield 'data: %s\n\n' % message['data'].decode()  
    headers = { "Content-Type" : "text/event-stream",
                "Cache-Control" : "no-cache",
                "X-Accel-Buffering" : "no"}
    return Response(event_stream(red), headers=headers)


# MAIN entry point. Flask http server
if __name__ == '__main__':
    # to get the local server IP 
    IP = extract_ip()
    # server start
    app.run(host = IP, port= PORT, debug=True)