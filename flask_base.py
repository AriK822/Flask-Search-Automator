from flask import Flask, request, render_template, jsonify, session, redirect, send_file
from datetime import timedelta
from time import time
from db_handler import Users, CsvFiles, Pending
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
    if 'username' in session:
        session.permanent = True
    else:
        session.permanent = False



@app.route('/', methods=['GET', 'POST'])
def home_page():
    if flood(request.remote_addr):
        return render_template("flood.html")
        
    return render_template("home.html")


@app.route('/about')
def about():
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    return render_template('about.html')


@app.route('/sources')
def sources():
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    return render_template('sources.html')
    

@app.route('/login', methods=['GET', 'POST'])
def login():
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if request.method == 'POST':
        data = request.get_json()

        if data["token"] != session["token"]: return jsonify()

        username = data["username"]
        password = data["password"]

        login_resault = Users().login(username, password)

        if login_resault[0]:
            session["username"] = username

        return jsonify({"success": login_resault[0], "msg": login_resault[1]})
    else:
        if "username" in session:
            return redirect('/pp')
        
        token = generate_csrf()
        session["token"] = token

        return render_template("login.html", token = token)
    

@app.route('/signup', methods=['GET', 'POST'])
def sgin_up():
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if request.method == "POST":
        data = request.get_json()

        if data["token"] != session["token"]: return jsonify()
        if data["captcha"] != decrypt_code(session["captcha"]): 
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
   
        session["pending"] = username
        session.pop("captcha")
        return jsonify({"success": True, "msg": "Verification code sent."})
    
    else:
        if "username" in session:
            return redirect('/pp')
        
        token = generate_csrf()
        session["token"] = token

        security_code = generate_captcha_image(request.remote_addr)
        session["captcha"] = encrypt_code(security_code)

        return render_template("signup.html", token = token, id = request.remote_addr)
    

@app.route('/verification', methods=['GET', 'POST'])
def verification():
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if request.method == "POST":
        if session["token"] != request.get_json()["token"]: return jsonify()

        user = Pending().get(session["pending"])
        if not user:
            return jsonify({"redirect": True, "msg": "/signin"})
        if not str(user["auth"]) == request.get_json()["auth"]:
            return jsonify({"redirect": False, "msg": "Incorrect code"})
        
        Pending().remove(user["username"])
        session.pop("pending")
        session["username"] = user["username"]
        Users().add(user["username"], user["password"])
        return jsonify({"redirect": True, "msg": "/pp"})

    else:
        if not "pending" in session:
            return redirect('/')
        
        user = Pending().get(session["pending"])
        if not user:
            session.pop("pending")
            return redirect("/")
        
        token = generate_csrf()
        session["token"] = token

        remaining_time = round(user["sent_time"] + 120 - time())

        return render_template("verification.html", username = user["username"], token = token, remaining_time = remaining_time)


@app.route('/pp', methods=['GET', 'POST', 'DELETE'])
def personal_page():
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if "username" not in session:
        return redirect("/login")
    
    if request.method == 'POST':
        data = request.get_json()
        job = data["job"].strip()
        location = data["location"].strip()
        token = data["token"]

        if token != session["token"]: return jsonify()

        if session["username"] in active_ips: return jsonify({"success":False, "msg": "Pls wait for the last request to be done!"})
        active_ips.add(session["username"])

        job = "Software engineer" if job == "" else job
        location = "United States" if location == "" else location

        selenium_handler = SeleniumHandler(job, location)
        if selenium_handler.extract():
            csv_handler = CsvFiles()
            count = csv_handler.count(session["username"]) + 1

            selenium_handler.save_csv(session["username"], count)
            csv_handler.add(session["username"], f"{session["username"]} {count}", job, location)

            active_ips.remove(session["username"])
            return jsonify({"success":True, "msg": f"pp/{session["username"]} {count}"})

        else:
            active_ips.remove(session["username"])
            return jsonify({"success":False, "msg": f"Error: Could not fetch results from linkedin.com."})
    
    elif request.method == 'DELETE':
        if request.get_json()["token"] != session["token"]: return jsonify()
        CsvFiles().delete_user(session["username"])
        Users().delete_row(session["username"])
        session.pop("username")
        return jsonify()

    else:
        token = generate_csrf()
        session["token"] = token
        return render_template("pp.html", user = session["username"], token = token)
    

@app.route('/load_files', methods=['POST'])
def load_files():
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if not request.get_json()["token"] == session["token"]: return jsonify()
    
    data = CsvFiles().fetch(session["username"])[::-1]
    return jsonify({"data" : data})


@app.route('/logout', methods=['POST'])
def logout():
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if not request.get_json()["token"] == session["token"]: return jsonify()
    
    session.pop("username")

    return jsonify({"success":True})


@app.route('/pp/<filename>')
def load_result(filename):
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if "username" not in session:
        return redirect("/")
    
    try:
        data = DataFethcher(filename).fetch()
    except FileNotFoundError:
        return render_template("filenotfound.html")
    
    return render_template("result.html", user=session["username"], data = data, filename=filename)


@app.route('/download/csv/<filename>')
def download_csv(filename):
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if "username" not in session:
        return redirect('/')
    
    return send_file(f"saved_csv/{filename}.csv")


@app.route('/download/excel/<filename>')
def download_excel(filename):
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if "username" not in session:
        return redirect('/')
    
    Converter(filename).to_excel()
    return send_file(f"cache/{filename}.xlsx")


@app.route('/download/html/<filename>')
def download_html(filename):
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if "username" not in session:
        return redirect('/')
    
    Converter(filename).to_html()
    return send_file(f"cache/{filename}.html")


@app.route('/download/json/<filename>')
def download_json(filename):
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    if "username" not in session:
        return redirect('/')
    
    Converter(filename).to_json()
    return send_file(f"cache/{filename}.json")
    

@app.errorhandler(404)
def page_not_found(e):
    if flood(request.remote_addr):
        return render_template("flood.html")
    
    return render_template("404.html"), 404
    

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)

