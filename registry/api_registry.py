from socket import socket
from web3.middleware import geth_poa_middleware
from web3 import Web3
import json
from flask import Flask, request, jsonify
import socket

app = Flask(__name__)
PORT = 5000

# use case data to setup the trusted issuer registry 
issuer_data = open("archipels_data.json", "r").read()
issuer_did = "did:ethr:0x9dff77de48a3314ebeab8e2c3adca62b61018f5d"  

# data to setup the schema registry
schema_data_1= open("schema.json", "r").read()
id_1 = "123"

# this is a signer address and private key with some eth to pay transaction fees
# use local msg sender private key with some eth
address = "0x461B99bCBdaD9697d299FDFe0879eC04De256DA1"
private_key = "4203a13f5b04d83bf35d00982c8d7ed3af7c99ee446300da7a35705b135a4164"

# smart contract address and abi, this comes from remix
registries_abi = open("registry.abi", "r").read()
registries_contract = "0xe14C84119B20f1E5732d9ADF8869546E6d564dC2"

# use an IPCProvider if this program runs on the Geth IPC node, if not you need a rpc node
# ex : w3 = Web3(Web3.IPCProvider("/home/admin/Talaonet/node1/geth.ipc", timeout=20))
w3 = Web3(Web3.HTTPProvider("https://talao.co/rpc"))

# for POA compatibility
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
contract = w3.eth.contract(registries_contract,abi=registries_abi)


# API to get Issuer data
# example https://talao.co/registry/api/v1/issuer?did=did:ethr:0xd6008c16068c40c05a5574525db31053ae8b3ba7
@app.route('/registry/api/v1/issuer', methods=['GET'])
def get_issuer() :
    try :
        did = request.args['did']
        issuer_data = contract.functions.get_issuer_data(did).call()
        if not issuer_data :
            print("DID not found")
            return jsonify("DID not found"), 400
        return jsonify(json.loads(issuer_data))
    except :
        print("Request mal formed")
        return jsonify ("request malformed"), 400


# API to get Schema data
@app.route('/registry/api/v1/schema', methods=['GET'])
def get_schema() :
    try :
        id = request.args['id']
        schema_data = contract.functions.get_schema_data(id).call()
        if not schema_data :
            print("Schema not found")
            return jsonify("Schema not found"), 400
        return jsonify(json.loads(schema_data))
    except :
        print("Request mal formed")
        return jsonify ("request malformed"), 400


# Call this API to init smart contract data. Use once it is enough
@app.route('/registry/api/v1/init', methods=['GET'])
def api_set_issuer() :
    try : 
        set_issuer(issuer_did, issuer_data)
        set_schema(id_1, schema_data_1)
        print("all registries updated")
        return jsonify("all registries updated")
    except :
        print("registries update failed")
        return jsonify("registry update failed"), 500


# this is needed within the schema.json
# https://talao.co/schemas/residentcard/2020/v1
@app.route('/schemas/certificateofemployment/2020/v1', methods=['GET'])
def residentcard() :
    return jsonify(json.load(open("schema.jsonld", "r")))


# send transaction to POA for issuer registry init
def set_issuer(did, json_string) :
    nonce = w3.eth.get_transaction_count(address)
    txn = contract.functions.set_issuer_data(did, json_string).buildTransaction({'chainId': 50000,'gas': 1000000,'gasPrice': w3.toWei("10", 'gwei'),'nonce': nonce,})
    signed_txn = w3.eth.account.sign_transaction(txn,private_key)
    w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    hash = w3.toHex(w3.keccak(signed_txn.rawTransaction))
    receipt = w3.eth.wait_for_transaction_receipt(hash, timeout=2000, poll_latency=1)
    return receipt['status']


# send transaction to POA for schema registry init
def set_schema(did, json_string) :
    nonce = w3.eth.get_transaction_count(address)
    txn = contract.functions.set_schema_data(did, json_string).buildTransaction({'chainId': 50000,'gas': 1000000,'gasPrice': w3.toWei("10", 'gwei'),'nonce': nonce,})
    signed_txn = w3.eth.account.sign_transaction(txn,private_key)
    w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    hash = w3.toHex(w3.keccak(signed_txn.rawTransaction))
    receipt = w3.eth.wait_for_transaction_receipt(hash, timeout=2000, poll_latency=1)
    return receipt['status']


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
