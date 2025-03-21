from flask import Flask, request, jsonify
import auth

app = Flask(__name__)

@app.route('/signup', methods=['POST'])
def sign_up():
    username = request.json.get('username')
    email = request.json.get('email')
    password = request.json.get('password')
    name = request.json.get('name')
    
    ret = auth.sign_up(username, email, password, name)
    if 'error' in ret:
        return jsonify(ret), 400
    else:
        return jsonify(ret), 200
    
@app.route('/confirm_signup', methods=['POST'])
def confirm_signup():
    username = request.json.get('username')
    conf_code = request.json.get('conf_code')
    
    ret = auth.confirm_signup(username, conf_code)
    if 'error' in ret:
        return jsonify(ret), 400
    else:
        return jsonify(ret), 200
    
@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')

    ret = auth.login(username, password)
    if 'error' in ret:
        return jsonify(ret), 400
    else:
        return jsonify(ret), 200
    
@app.route('/logout', methods=['POST'])
def logout():
    access_token = request.json.get('AccessToken')
    if not access_token:
        return jsonify({"error": "Invalid Access Token"}), 400
    ret = auth.logout(access_token)
    if 'error' in ret:
        return jsonify(ret), 400
    else:
        return jsonify(ret), 200

if __name__ == "__main__":
    app.run(debug=True)