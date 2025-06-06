from flask import Flask, request, render_template, jsonify, session, redirect, send_file, g
from datetime import timedelta
from time import time
from db_handler import Users, CsvFiles, Pending, Sessions
from selenium_handler import SeleniumHandler
from csv_handler import DataFethcher, Converter
from security import (
    generate_csrf, generate_auth, generate_captcha_image,encrypt_code, decrypt_code,
    flood, FLASK_APP_SECRET_KEY, active_ips, EmailSender,
)


app = Flask(__name__)
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
    if request.method in ["POST", "DELETE"]:
        if request.get_json()["token"] != g.session["token"]: 
            return jsonify()



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
        if not EmailSender().send(username, verification_key):
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

        remaining_time = round(user["sent_time"] + 120 - time())

        return render_template("verification.html", username = user["username"], token = token, remaining_time = remaining_time)


@app.route('/pp', methods=['GET', 'POST', 'DELETE'])
def personal_page():
    if "username" not in g.session:
        return redirect("/login")
    
    if request.method == 'POST':
        data = request.get_json()
        job = data["job"].strip()
        location = data["location"].strip()

        if g.session["username"] in active_ips: return jsonify({"success":False, "msg": "Pls wait for the last request to be done!"})
        active_ips.add(g.session["username"])

        job = "Software engineer" if job == "" else job
        location = "United States" if location == "" else location

        selenium_handler = SeleniumHandler(job, location)
        if selenium_handler.extract():
            csv_handler = CsvFiles()
            count = csv_handler.count(g.session["username"]) + 1

            selenium_handler.save_csv(g.session["username"], count)
            csv_handler.add(g.session["username"], f"{g.session["username"]} {count}", job, location)

            active_ips.remove(g.session["username"])
            return jsonify({"success":True, "msg": f"pp/{g.session["username"]} {count}"})

        else:
            active_ips.remove(g.session["username"])
            return jsonify({"success":False, "msg": f"Error: Could not fetch results from linkedin.com."})
    
    elif request.method == 'DELETE':
        CsvFiles().delete_user(g.session["username"])
        Users().delete_row(g.session["username"])
        g.session.pop("username")
        return jsonify()

    else:
        token = generate_csrf()
        g.session["token"] = token
        return render_template("pp.html", user = g.session["username"], token = token)
    

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
    app.run(host="0.0.0.0", port=5000, debug=True)

