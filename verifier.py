""" le protocole utilisé ici est décrit 
https://github.com/TalaoDAO/talao-wallet/blob/dev-talao/docs/talao_interaction_protocol.md
https://github.com/TalaoDAO/talao-wallet/blob/dev-talao/docs/verifier_flow.pdf

basé sur 
https://w3c-ccg.github.io/vp-request-spec/#query-by-example


"""

from flask import Flask, render_template_string, jsonify, request, Response
from flask_qrcode import QRcode
from datetime import timedelta
import didkit
import redis
import socket
import uuid
import json
import sys

app = Flask(__name__)
qrcode = QRcode(app)
PORT = 3000

# Redis pour stocker les datas de session
red= redis.Redis(host='localhost', port=6379, db=0)
OFFER_DELAY = timedelta(seconds= 10*60)
did_verifier = 'did:tz:tz2NQkPq3FFA3zGAyG8kLcWatGbeXpHMu7yk'
# pattern pour https://w3c-ccg.github.io/vp-request-spec/#query-by-example
pattern = {"type": "VerifiablePresentationRequest",
            "query": [
                {
                    "type": "QueryByExample",
                    "credentialQuery": []
                }]
            }


# appel de l'affichage du QR code
# l'argument "issuer" permet de faire un controle sur l identité de l'issuer au travers d'un registre de confiance
# Attention on ne verifie pas que l issuer dispose de la clé privéee associé à son DID
@app.route('/' , methods=['GET'], defaults={'red' : red}) 
def qrcode(red):
    id = str(uuid.uuid1())
    pattern['challenge'] = str(uuid.uuid1()) # nonce
    pattern['domain'] = 'http://' + IP
    # l'idee ici est de créer un endpoint dynamique
    red.set(id,  json.dumps(pattern))
    url = 'http://' + IP + ':' + str(PORT) +  '/endpoint/' + id +'?issuer=' + did_verifier
    html_string = """  <!DOCTYPE html>
        <html>
        <head></head>
        <body>
        <center>
            <div>  
                <h2>Scan the QR Code bellow with your smartphone wallet</h2> 
                <br>  
                <div><img src="{{ qrcode(url) }}" ></div>
            </div>
        </center>
        <script>
            var source = new EventSource('/verifier_stream');
            source.onmessage = function (event) {
                const result = JSON.parse(event.data);
                console.log(result.message);
                if (result.check == 'ok' & result.id == '{{id}}'){
                    window.location.href="/followup?id={{id}}";
                }
                else { 
                    window.alert(result.message);
                    window.location.href="/";
                }
            };
        </script>
        </body>
        </html>"""
    return render_template_string(html_string, url=url, id=id)


# Endpoint pour le call du wallet
@app.route('/endpoint/<id>', methods = ['GET', 'POST'],  defaults={'red' : red})
def presentation_endpoint(id, red):
    try :
        my_pattern = json.loads(red.get(id).decode())
    except :
        event_data = json.dumps({"id" : id,
                                 "message" : "redis decode failed",
                                 "check" : "ko"})
        red.publish('verifier', event_data)
        return jsonify("server error"), 500
    
    if request.method == 'GET':
        return jsonify(my_pattern)
    
    if request.method == 'POST' :
        #red.delete(id)
        try : 
            result = json.loads(didkit.verifyPresentation(request.form['presentation'], '{}'))['errors']
        except:
            event_data = json.dumps({"id" : id,
                                    "check" : "ko",
                                    "message" : "presentation is not correct"})
            red.publish('verifier', event_data)
            return jsonify("presentation is not correct"), 403
        if result :
            event_data = json.dumps({"id" : id,
                                    "check" : "ko",
                                    "message" : result})
            red.publish('verifier', event_data)
            return jsonify(result), 403
        # mettre les tests pour verifier la cohérence entre issuer, holder et credentialSubject.id 
        # 
        red.set(id,  request.form['presentation'])
        event_data = json.dumps({"id" : id,
                                "message" : "presentation is verified",
                                "check" : "ok"})           
        red.publish('verifier', event_data)
        return jsonify("ok"), 200


# server event push, peut etre remplacé par websocket
@app.route('/verifier_stream', methods = ['GET'],  defaults={'red' : red})
def presentation_stream(red):
    def event_stream(red):
        pubsub = red.pubsub()
        pubsub.subscribe('verifier')
        for message in pubsub.listen():
            if message['type']=='message':
                yield 'data: %s\n\n' % message['data'].decode()
    headers = { "Content-Type" : "text/event-stream",
                "Cache-Control" : "no-cache",
                "X-Accel-Buffering" : "no"}
    return Response(event_stream(red), headers=headers)


# uniquement pour l affichage du VP/VC, inutile sinon
@app.route('/followup', methods = ['GET', 'POST'],  defaults={'red' : red})
def followup(red):  
    try :  
        presentation = json.loads(red.get(request.args['id']).decode())
    except :
        print('redis problem')
        sys.exit()
    red.delete(request.args['id'])
    holder = presentation['holder']
    # pour prendre en compte une selection multiple ou unique
    if isinstance(presentation['verifiableCredential'], dict) :
        nb_credentials = "1"
        issuers = presentation['verifiableCredential']['issuer']
        types = presentation['verifiableCredential']['type'][1]
        credential = json.dumps(presentation['verifiableCredential'], indent=4, ensure_ascii=False)
    else :
        nb_credentials = str(len(presentation['verifiableCredential']))
        issuer_list = type_list = list()
        for credential in presentation['verifiableCredential'] :
            if credential['issuer'] not in issuer_list :
                issuer_list.append(credential['issuer'])
            if credential['type'][1] not in type_list :
                type_list.append(credential['type'][1])
        issuers = ", ".join(issuer_list)
        types = ", ".join(type_list)
        # on ne presente que le premier
        credential = json.dumps(presentation['verifiableCredential'][0], indent=4, ensure_ascii=False)
    presentation = json.dumps(presentation, indent=4, ensure_ascii=False)
    html_string = """
        <!DOCTYPE html>
        <html>
        <body class="h-screen w-screen flex">
        <br>Number of credentials : """ + nb_credentials + """<br>
        <br>Holder (wallet DID)  : """ + holder + """<br>
        <br>Issuers : """ + issuers + """<br>
        <br>Credential types : """ + types + """
        <br><br>
        <form action="/" method="GET" >
                    <button  type"submit" >Verifier test</button>
        </form>
        <br>---------------------------------------------------<br>
        <h2> Verifiable Credential </h2>
        <pre class="whitespace-pre-wrap m-auto">""" + credential + """</pre>
        <h2> Verifiable Presentation </h2>
        <pre class="whitespace-pre-wrap m-auto">""" + presentation + """</pre>
        </body>
        </html>"""
    return render_template_string(html_string)


# Pour obtenir l'adresse du serveur sur le reseau
# inutile si adresse serveur connue
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


# MAIN entry point. Flask http server
if __name__ == '__main__':
    # to get the local server IP 
    IP = extract_ip()
    # server start
    app.run(host = IP, port= PORT, debug=True)