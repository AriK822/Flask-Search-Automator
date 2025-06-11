from flask import Flask, request, render_template, jsonify, session, redirect, send_file, g, Response, stream_with_context
import json
from datetime import timedelta
from time import time
from db_handler import *
from selenium_handler import SeleniumHandler
from csv_handler import DataFethcher, Converter
from security import *



app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * (1024 * 1024)
app.secret_key = FLASK_APP_SECRET_KEY
app.permanent_session_lifetime = timedelta(days=7)


@app.before_request
def perminant_sessions():
    session.permanent = True


@app.before_request
def s_session_handler():
    if request.endpoint == 'static': return None
    if 'id' not in session:
        session_id = Sessions().add()
        session['id'] = session_id
        g.session = {}
    else:
        session_id = session['id']
        info = Sessions().get(session_id)
        if info == False:
            session_id = Sessions().add()
            session['id'] = session_id
            g.session = {}
        else:
            g.session = info


@app.after_request
def e_session_handler(response):
    if request.endpoint == 'static': return response
    Sessions().update(session['id'], g.session)
    return response


@app.before_request
def flood_handler():
    if request.endpoint != 'static':
        if flood(request.remote_addr):
            return render_template("flood.html")
    

@app.before_request
def csrf_handler():
    if request.method in ["POST", "DELETE", "PUT"]:
        if 'token' in request.headers:
            if request.headers["token"] != g.session["token"]:
                return jsonify()
        elif request.get_json()["token"] != g.session["token"]: 
            return jsonify()
        

@app.after_request
def compress_request(response):
    if request.endpoint == 'download_html': return response
    if response.content_type.startswith('text/html'):
        response.set_data(compress(response.get_data(as_text=True)))
    return response



@app.route('/', methods=['GET', 'POST'])
def home_page():
    return render_template("home.html")


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/sources')
def sources():
    return render_template('sources.html')
    

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()

        username = data["username"]
        password = data["password"]

        login_resault = Users().login(username, password)

        if login_resault[0]:
            g.session["username"] = username

        return jsonify({"success": login_resault[0], "msg": login_resault[1]})
    else:
        if "username" in g.session:
            return redirect('/pp')
        
        token = generate_csrf()
        g.session["token"] = token

        return render_template("login.html", token = token)
    

@app.route('/signup', methods=['GET', 'POST'])
def sgin_up():
    if request.method == "POST":
        data = request.get_json()

        if data["captcha"] != decrypt_code(g.session["captcha"]): 
            return jsonify({"success": False, "msg": "Security code invalid!"})
        
        username = data["username"]
        password = data["password"]

        signup_resault = Users().is_valid(username, password)

        if not signup_resault[0]:
            return jsonify({"success": signup_resault[0], "msg": signup_resault[1]})
        
        verification_key = generate_auth()
        if not Pending().add(username, password, verification_key):
            return jsonify({"success": False, "msg": "An email is already sent to this email. Please wait a few minutes."})
        if not EmailSender().send_authentication(username, verification_key):
            Pending().remove(username)
            return jsonify({"success": False, "msg": "Failed to send email."})
   
        g.session["pending"] = username
        g.session.pop("captcha")
        return jsonify({"success": True, "msg": "Verification code sent."})
    
    else:
        if "username" in g.session:
            return redirect('/pp')
        
        token = generate_csrf()
        g.session["token"] = token

        security_code = generate_captcha_image(request.remote_addr)
        g.session["captcha"] = encrypt_code(security_code)

        return render_template("signup.html", token = token, id = request.remote_addr)
    

@app.route('/verification', methods=['GET', 'POST'])
def verification():
    if request.method == "POST":
        user = Pending().get(g.session["pending"])
        if not user:
            return jsonify({"redirect": True, "msg": "/signin"})
        if not str(user["auth"]) == request.get_json()["auth"]:
            return jsonify({"redirect": False, "msg": "Incorrect code"})
        
        Pending().remove(user["username"])
        g.session.pop("pending")
        g.session["username"] = user["username"]
        Users().add(user["username"], user["password"])
        return jsonify({"redirect": True, "msg": "/pp"})

    else:
        if not "pending" in g.session:
            return redirect('/')
        
        user = Pending().get(g.session["pending"])
        if not user:
            g.session.pop("pending")
            return redirect("/")
        
        token = generate_csrf()
        g.session["token"] = token

        remaining_time = round(user["sent_time"] + pending_timeout - time())

        return render_template("verification.html", username = user["username"], token = token, remaining_time = remaining_time)


@app.route('/passchange', methods=["GET", "POST", "PUT"])
def change_password():
    if request.method == 'PUT':
        data = request.get_json()
        username = data["username"]
        result = PassChanger().add(username)
        if not result[0]:
            return jsonify({"msg": result[1], "success":False,})
        if not EmailSender().send_passchange_link(username, result[1]):
            PassChanger().remove(username)
            return jsonify({"msg": "Failed to send email.", "success":False,})
        
        return jsonify({"msg": "A recovery link was successfully sent to your email.", "success":True,})

    elif request.method == "POST":
        key = request.get_json()["key"]
        user = PassChanger().get(key)

        if not user:
            return jsonify({"redirect": False, "msg": "The link has expired!"})

        username = user["username"]
        password = request.get_json()["newpass"]

        valid = Users().pass_valid(password)
        if not valid[0]:
            return jsonify({"redirect": False, "msg": valid[1]})
        
        Users().update(username, password)
        EmailSender().send_security_alert(username, request.remote_addr) #type: ignore
        PassChanger().remove(username)
        return jsonify({"redirect": True, "msg": "/login"})

    else:
        key = request.args.get("key")
        user = PassChanger().get(key)

        if not user:
            return redirect('/login')
        
        token = generate_csrf()
        g.session["token"] = token

        remaining_time = round(user["sent_time"] + pass_change_timeout - time())
        return render_template("passchange.html", token=token, remaining_time = remaining_time, key = key)


@app.route('/forgotpass', methods=['GET', 'POST'])
def forgot_pass():
    if request.method == 'POST':
        data = request.get_json()

        if data["captcha"] != decrypt_code(g.session["captcha"]): 
            return jsonify({"success": False, "msg": "Security code invalid!"})
        
        username = data["username"]

        result = PassChanger().add(username)
        if not result[0]:
            return jsonify({"success": False, "msg": result[1]})
        if not EmailSender().send_passchange_link(username, result[1]):
            PassChanger().remove(username)
            return jsonify({"success": False, "msg": "Failed to send email."})
        
        return jsonify({"success": True, "msg": "A link for changing your password was successfully sent to your email."})

    else:
        if "username" in g.session:
            return redirect('/pp')
        
        token = generate_csrf()
        g.session["token"] = token

        security_code = generate_captcha_image(request.remote_addr)
        g.session["captcha"] = encrypt_code(security_code)

        return render_template("forgotpass.html", token = token, id = request.remote_addr)


@app.route('/pp', methods=['GET', 'DELETE', 'POST'])
def personal_page():
    if "username" not in g.session:
        return redirect("/login")
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({"msg": "No file part", "success": False}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"msg": "No selected file", "success": False}), 400

        path = validate_filename(g.session["username"], file.filename) # type: ignore
        if not path[0]: 
            return jsonify({"msg": path[1], "success": False}), 400
        
        result = save_image(file, path[1])
        if not result[0]:
            return jsonify({"msg": result[1], "success": False}), 400
        
        return jsonify({"msg": result[1], "success": True, "src": "static/" + get_pfp(g.session["username"])}), 400
    
    elif request.method == 'DELETE':
        CsvFiles().delete_user(g.session["username"])
        Users().delete_row(g.session["username"])
        remove_pfp(g.session["username"])
        g.session.pop("username")
        return jsonify()

    else:
        token = generate_csrf()
        g.session["token"] = token

        pfp = get_pfp(g.session["username"])
        return render_template("pp.html", user = g.session["username"], token = token, pfp=pfp)
    

@app.route('/pp/delrow', methods=['DELETE'])
def delete_row():
    filename = request.get_json()["filename"]
    result = CsvFiles().delete_row(filename)
    return jsonify({"msg": result[1], "success": result[0]})
    

@app.route('/pp/fetch', methods=['GET'])
def fetch_results():
    token = request.args.get("token")
    job = request.args.get("job").strip() # type: ignore
    location = request.args.get("location").strip() # type: ignore

    job = "Software engineer" if job == "" else job
    location = "United States" if location == "" else location

    if 'token' not in g.session:
        return jsonify()
    
    if token != g.session["token"]:
        return jsonify()
    
    g_session = g.session
    
    def stream_results():
        try:
            if g_session["username"] in active_ips: 
                yield f"data: {json.dumps({"success":False, "continue": False, "msg": "Pls wait for the last request to be done!", "end":False})}\n\n"
                return
            
            active_ips.add(g_session["username"])
            yield f"data: {json.dumps({"success":True, "continue": True, "msg": "Started processing..."})}\n\n"

            selenium_handler = SeleniumHandler(job, location)

            gen = selenium_handler.extract()
            while True:
                result = next(gen)
                if result in ["True", "False"]:
                    break
                yield result

            if result == "True":
                yield f"data: {json.dumps({"success":True, "continue": True, "msg": "Saving data..."})}\n\n"

                csv_handler = CsvFiles()
                count = csv_handler.count(g_session["username"]) + 1

                selenium_handler.save_csv(g_session["username"], count)
                csv_handler.add(g_session["username"], f"{g_session["username"]} {count}", job, location)

                active_ips.remove(g_session["username"])
                yield f"data: {json.dumps({"success":True, "continue": False, "msg": f"pp/{g_session["username"]} {count}"})}\n\n"
                return

            else:
                active_ips.remove(g_session["username"])
                yield f"data: {json.dumps({"success":False, "continue": False, "msg": f"Error: Could not fetch results from linkedin.com.", "end":True})}\n\n"
                return
        except Exception as e:
            print(f"\n\n\nCought it!!!{e}\n\n\n")
        
    
    return Response(stream_with_context(stream_results()), mimetype="text/event-stream") #type: ignore
    

@app.route('/load_files', methods=['POST'])
def load_files():
    data = CsvFiles().fetch(g.session["username"])[::-1]
    return jsonify({"data" : data})


@app.route('/logout', methods=['POST'])
def logout():
    g.session.pop("username")
    return jsonify({"success":True})


@app.route('/pp/<filename>')
def load_result(filename):
    if "username" not in g.session:
        return redirect("/")
    
    try:
        data = DataFethcher(filename).fetch()
    except FileNotFoundError:
        CsvFiles().delete_row(filename)
        return render_template("filenotfound.html")
    
    return render_template("result.html", user=g.session["username"], data = data, filename=filename)


@app.route('/download/csv/<filename>')
def download_csv(filename):
    if "username" not in g.session:
        return redirect('/')
    
    return send_file(f"saved_csv/{filename}.csv")


@app.route('/download/excel/<filename>')
def download_excel(filename):
    if "username" not in g.session:
        return redirect('/')
    
    Converter(filename).to_excel()
    return send_file(f"cache/{filename}.xlsx")


@app.route('/download/html/<filename>')
def download_html(filename):
    if "username" not in g.session:
        return redirect('/')
    
    Converter(filename).to_html()
    return send_file(f"cache/{filename}.html")


@app.route('/download/json/<filename>')
def download_json(filename):
    if "username" not in g.session:
        return redirect('/')
    
    Converter(filename).to_json()
    return send_file(f"cache/{filename}.json")
    

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404
    

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=6969, debug=True)
