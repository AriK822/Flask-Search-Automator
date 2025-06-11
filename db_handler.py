import sqlite3
from os import urandom, path, mkdir
from hashlib import sha256
from string import ascii_letters
from time import time, sleep
from os import remove, listdir
from pickle import dumps, loads
from uuid import uuid4
from security import encrypt_code, decrypt_code
from re import sub, DOTALL


sessions_timeout = 7 * (24 * 60 * 60)
pending_timeout = 120
pass_change_timeout = 5 * 60


if not path.exists("data_base"): mkdir("data_base")


def clear_cache():
    files = listdir("cache")
    if len(files) > 2:
        files.sort(key = lambda x: path.getmtime(f"cache/{x}"))
        for file in files[:-2]:
            remove(f"cache/{file}")


def clear_captcha_cache():
    files = listdir("static/captcha")
    if len(files) > 2:
        files.sort(key = lambda x: path.getmtime(f"static/captcha/{x}"))
        for file in files[:-2]:
            remove(f"static/captcha/{file}")


def generate_session_id() -> str:
    return str(uuid4())


def compress(html_string:str):
    # is_script, result = False, ""
    # for i in html_string.split('\n'):
    #     if i.strip() == '': continue
    #     if '<script' in i: is_script = True
    #     if '</script>' in i: is_script = False
    #     if is_script:
    #         i = i.strip()
    #         if i[:2] == '//': continue
    #         if i[-1] in ['{', ';']: result += i
    #         else: result += i + '\n'
    #     else:
    #         i = i.strip()
    #         if i[-1] in ['"', "'"]: i += ''
    #         result += i
    # 
    # return result

    html_string = '\n'.join([i.strip() for i in html_string.split('\n') if i.strip()])
    html_string = sub(r'>\s+<', '><', html_string)

    def minify(match):
        content = match.group(1)
        content = content.replace('\n', '')
        return f"<style>{content}</style>"

    html_string = sub(r'<style[^>]*>(.*?)</style>', minify, html_string, flags=DOTALL)

    return html_string


def get_pfp(username:str):
    cu = username.split('@')[0]
    if path.exists(f"static/users/{cu}.png"): 
        return f"users/{cu}.png"
    return "default_pfp.jpg"


def remove_pfp(username:str):
    cu = username.split('@')[0]
    if path.exists(f"static/users/{cu}.png"):
        remove(f"static/users/{cu}.png")



class Users:
    def __init__(self):
        self.conn = sqlite3.connect("data_base/users.db")
        self.cursor = self.conn.cursor()

        self.cursor.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            salt TEXT NOT NULL
            );	""")
    
    
    def add(self, username, password):
        salt = urandom(16)
        hashed_password = sha256(salt + password.encode()).hexdigest()
        self.cursor.execute("INSERT INTO users (username, password, salt) VALUES (?, ?, ?)", (username, hashed_password, salt))
        self.conn.commit()

    
    def select_all(self):
        self.cursor.execute("SELECT * FROM users ")
        data = self.cursor.fetchall()
        return data
    

    def delete_all(self):
        self.cursor.execute("DELETE FROM users")
        self.conn.commit()


    def update(self, username, password):
        salt = urandom(16)
        hashed_password = sha256(salt + password.encode()).hexdigest()
        self.cursor.execute("UPDATE users SET password = ?, salt = ? WHERE username = ?", (hashed_password, salt, username))
        self.conn.commit()
    

    def delete_row(self, username):
        self.cursor.execute("DELETE FROM users WHERE username = ?", (username, ))
        self.conn.commit()


    def select_row(self, username):
        self.cursor.execute("SELECT * FROM users WHERE username = ?", (username, ))
        data = self.cursor.fetchone()
        return data


    def login(self, username, password):
        data = self.select_row(username)
        if not data:
            return (False, "Username not found!")
        salt = data[3]
        hashed_password = sha256(salt + password.encode()).hexdigest()
        if data[2] == hashed_password:
            return (True, "Welcome back!")
        else:
            return (False, "Password not correct")
        

    def signup(self, username:str, password:str) -> tuple:
        result = self.is_valid(username, password)
        if result[0]:
            self.add(username, password)
        return result
    

    def pass_valid(self, password):
        if password.strip() == "":
            return (False, "Password cannot be empty!")
        if len(password) < 8:
            return (False, "Password must be atleast 8 characters long!")
        if len(password) > 16:
            return (False, "Password can be at most 20 characters long!")
        if ' ' in password:
            return (False, "Password cannot contain spaces!")
        if all(map(lambda x:x in '0123456789', password)):
            return (False, "Password must contain atleast one character!")
        if all(map(lambda x:x in ascii_letters, password)):
            return (False, "Password must contain atleast one number!")
        return (True, "")
        

    def is_valid(self, username:str, password:str) -> tuple:
        if username.strip() == "":
            return (False, "Username cannot be empty!")
        if password.strip() == "":
            return (False, "Password cannot be empty!")
        if len(username) < 4:
            return (False, "Username must be atleast 4 characters long!")
        if len(password) < 8:
            return (False, "Password must be atleast 8 characters long!")
        if len(username) > 50:
            return (False, "Username can be at most 50 characters long!")
        if len(password) > 16:
            return (False, "Password can be at most 20 characters long!")
        if ' ' in username:
            return (False, "Username cannot contain spaces!")
        if ' ' in password:
            return (False, "Password cannot contain spaces!")
        if all(map(lambda x:x in '0123456789', password)):
            return (False, "Password must contain atleast one character!")
        if all(map(lambda x:x in ascii_letters, password)):
            return (False, "Password must contain atleast one number!")
        if "@gmail.com" not in username:
            return (False, "Email not valid or not supported.")

        data = self.select_row(username)
        if not data:
            return (True, "Account created!")
        else:
            return (False, "Account already exists!")


    def __str__(self):
        return str(self.select_all())
    


class CsvFiles:
    def __init__(self):
        self.conn = sqlite3.connect("data_base/file_locations.db")
        self.cursor = self.conn.cursor()

        self.cursor.execute("""CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT NOT NULL,
            file_name TEXT NOT NULL UNIQUE,
            job TEXT NOT NULL,
            location TEXT NOT NULL
            );	""")
    
    
    def add(self, username, file_name, job, location):
        self.cursor.execute("INSERT INTO files (username, file_name, job, location) VALUES (?, ?, ?, ?)", (username, file_name, job, location))
        self.conn.commit()

    
    def select_all(self):
        self.cursor.execute("SELECT * FROM files ")
        data = self.cursor.fetchall()
        return data
    

    def delete_all(self):
        self.cursor.execute("DELETE FROM files")
        self.conn.commit()
    

    def delete_row(self, filename):
        self.cursor.execute("DELETE FROM files WHERE file_name = ?", (filename, ))
        self.conn.commit()

        if path.exists(f"saved_csv/{filename}.csv"):
            remove(f"saved_csv/{filename}.csv")
            return (True, "Deleted successfully!")
        else:
            return (False, "File does not exist!")


    def delete_user(self, username):
        files = self.fetch(username)
        for file in files:
            remove(f"saved_csv/{file[2]}.csv")
        print(files)
        self.cursor.execute("DELETE FROM files WHERE username = ?", (username,))
        self.conn.commit()


    def select_row(self, job, location):
        self.cursor.execute("SELECT * FROM files WHERE job = ? AND location = ?", (job, location))
        data = self.cursor.fetchall()
        return data
    

    def count(self, username):
        self.cursor.execute("SELECT * FROM files WHERE username = ?", (username, ))
        data = self.cursor.fetchall()
        if data:
            return int(data[-1][2].split()[-1])
        return 0
    
    
    def fetch(self, username):
        self.cursor.execute("SELECT * FROM files WHERE username = ?", (username, ))
        data = self.cursor.fetchall()
        return data


    def __str__(self):
        return str(self.select_all())
    


pending = []

class Pending:
    def __init__(self):
        delete_users = []

        for user in pending:
            if time() - user["sent_time"] > pending_timeout:
                delete_users.append(user)

        for user in delete_users:
            pending.remove(user)

    
    def add(self, username:str, password:str, auth:int):
        for user in pending:
            if user["username"] == username:
                return False
            
        password = encrypt_code(password)
        pending.append({'username':username, 'password':password, 'auth':auth, 'sent_time':time()})
        return True


    def get(self, username:str):
        for user in pending:
            if user["username"] == username:
                decrypted_pass = decrypt_code(user["password"])
                return {
                    'username':  user['username'],
                    'password':  decrypted_pass,
                    'auth':      user['auth'],
                    'sent_time': user['sent_time']
                }
        return None
    

    def remove(self, username:str):
        for user in pending:
            if user["username"] == username:
                pending.remove(user)
                return True
        return False


    def __str__(self):
        return str(pending)
    


class Sessions:
    conut = 0

    def __init__(self):
        self.conn = sqlite3.connect("data_base/sessions.db")
        self.cursor = self.conn.cursor()

        self.cursor.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            session_id TEXT NOT NULL UNIQUE,
            used_time INTIGER NOT NULL,
            info BLOB
            );	""")
        
        Sessions.conut += 1
        if Sessions.conut % 100 == 0:
            self.clean_timeouts()
    
    
    def add(self):
        session_id = generate_session_id()
        self.cursor.execute("INSERT INTO sessions (session_id, used_time, info) VALUES (?, ?, ?)", (session_id, time(), dumps({})))
        self.conn.commit()
        return session_id

    
    def select_all(self):
        self.cursor.execute("SELECT * FROM sessions ")
        data = self.cursor.fetchall()
        return data
    

    def delete_all(self):
        self.cursor.execute("DELETE FROM sessions")
        self.conn.commit()
    

    def delete_row(self, session_id:str):
        self.cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id, ))
        self.conn.commit()
    

    def get(self, session_id):
        self.cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id, ))
        data = self.cursor.fetchone()
        if not data:
            return False
        self.cursor.execute("UPDATE sessions SET used_time = ? WHERE session_id = ?", (time(), session_id))
        self.conn.commit()
        if data[3]:
            return loads(data[3])
    

    def update(self, session_id, info):
        self.cursor.execute("UPDATE sessions SET used_time = ?, info = ? WHERE session_id = ?", (time(), dumps(info), session_id))
        self.conn.commit()


    def clean_timeouts(self):
        data = self.select_all()
        for i in data:
            last_used = i[2]
            if time() - last_used > sessions_timeout:
                self.delete_row(i[1])
        self.conn.commit()
        

    def __str__(self):
        return str(self.select_all())
    


pass_change_list = []

class PassChanger:
    def __init__(self):
        self.clear_timeout()


    def clear_timeout(self):
        delete_list = []
        for user in pass_change_list:
            if time() - user["sent_time"] > pass_change_timeout:
                delete_list.append(user)

        for user in delete_list:
            pass_change_list.remove(user)


    def add(self, username):
        if not Users().select_row(username):
            return (False, "User does not exist")
        for user in pass_change_list:
            if user["username"] == username:
                return (False, "Email is already sent to this username. Please check tour email or wait a few minutes.")

        key = generate_session_id()

        pass_change_list.append({
            'username': username,
            'key' : encrypt_code(key),
            'sent_time' : time(),
        })
        return (True, key)
    

    def get(self, key):
        for user in pass_change_list:
            user_key = decrypt_code(user["key"])
            if user_key == key:
                return {
                    'username': user["username"],
                    'key' : user_key,
                    'sent_time' : user["sent_time"],
                }
        return None
    

    def remove(self, username):
        for user in pass_change_list:
            if user["username"] == username:
                pass_change_list.remove(user)
                return True
            
        return False
    



if __name__ == "__main__":
    # handler = Users()
    # handler.delete_all()
    # handler.add("Arik", "12315")
    # handler.update("Arik", "1")
    # print(handler.login("Arik", "1"))
    # handler.delete_all()
    # print(handler)
    pass


if __name__ == "__main__":
    # handler = CsvFiles()
    # handler.add("Ari", "assss", "jj", "bb")
    # handler.delete_row("jj", "bb")
    # print(handler.select_row("jj", "bb"))
    # print(handler)
    # print(handler.count("Ari"))
    # count = handler.count("Arik-808") + 1
    # print(count)
    # print(handler.fetch("AriK_808"))
    pass


if __name__ == "__main__":
    # Pending().add("Arik", "123", 123)
    # print(Pending())
    # sleep(1)
    # print(Pending(2))
    # sleep(1.1)
    # print(Pending(2))
    # clear_captcha_cache()
    pass


if __name__ == "__main__":
    # handler = Sessions()
    # handler.add()
    # print(handler.get("234ew"))
    # Pending().add("adadf", "ADFA", 123)
    # a = Pending().get("adadf")
    # a = Pending().get("adadf")
    pass


if __name__ == "__main__":
    # handler = CsvFiles()
    # print(handler.fetch("armankiani1384@gmail.com"))
    # key = PassChanger().add("armankiani1384@gmail.com")[1]
    # print(key)
    # print(PassChanger().get(key))
    # CsvFiles().delete_row("3")
    print(CsvFiles().count("Ari_phone"))
    pass
