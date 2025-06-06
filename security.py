from os import getenv, path, mkdir
from dotenv import load_dotenv
from string import ascii_lowercase
from random import randint
from time import time
from smtplib import SMTP_SSL
from email.mime.text import MIMEText
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from cryptography.fernet import Fernet
from db_handler import clear_captcha_cache



load_dotenv()
GMAIL_APP_PASSWORD = getenv('GMAIL_APP_PASSWORD')  
FLASK_APP_SECRET_KEY = getenv('FLASK_APP_SECRET_KEY')

active_ips = set()
ip_tracker = {}
banned_ips = {}


if not path.exists("static/captcha"):
    mkdir("static")
    mkdir("static/captcha")


def generate_csrf(length:int = 16) -> str:
    string = ascii_lowercase + '0123456789'
    return ''.join([string[randint(0, len(string) - 1)] for _ in range(length)])


def generate_auth() -> int:
    return randint(1000, 9999)


def flood(ip, request_count = 5, time_limit = 1, ban_time = 5) -> bool:
    if ip in ip_tracker:
        tracker = ip_tracker[ip]
        tracker:list
        tracker.append(time())
        while len(tracker) > request_count:
            tracker.pop(0)
    else:
        ip_tracker[ip] = [time()]
        tracker = ip_tracker[ip]

    if len(tracker) == request_count and tracker[-1] - tracker[0] < time_limit:
        banned_ips[ip] = time()

    if ip in banned_ips:
        if time() - banned_ips[ip] > ban_time:
            banned_ips.pop(ip)
            return False
        return True
    else: return False



class EmailSender:
    def send(self, to_email:str, authentication_code:int):
        from_email = "kianiarman91@gmail.com"
        password = GMAIL_APP_PASSWORD

        body = f"""
        <html>
        <body>
            <h2 style="color:navy;">Welcome to search automator!</h2>
            <p><b>Hello dear user</b>,</p>
            <p>Thank you for signing up. Use this authentication code to verify your account:</p>
            <p style="text-decoration: underline;"><span style="color: red;"><b>Don't share</span></b> this code with anyone!</p>
            <h4>Your verification code: <h2>{authentication_code}</h2></h4>
            <br>
            <p>If you face any issues, pls contact us at:</p>
            <a>kianiarman91@gmail.com</a>
        </body>
        </html>
        """

        msg = MIMEText(body, "html")
        msg["Subject"] = "Verification - Search automator"
        msg["From"] = from_email
        msg["To"] = to_email

        try:
            with SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(from_email, password) # type: ignore
                server.sendmail(from_email, to_email, msg.as_string())
                return True
            
        except Exception as e:
            print("Error while sending the eamil:", e)
            return False



fernet = Fernet(Fernet.generate_key())

def encrypt_code(text:str) -> str:
    return fernet.encrypt(text.encode()).decode()


def decrypt_code(text:str) -> str:
    return fernet.decrypt(text.encode()).decode()


def generate_captcha_image(id) -> str:
    width, height = 100, 40
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    font = ImageFont.load_default(32)

    text = str(generate_auth())

    t_width = width / (len(text))
    for i, char in enumerate(text):
        x = t_width * (i) + randint(-2, 2)
        y = randint(-7, 7)
        draw.text((x, y), char, font=font, fill=(0, 0, 0))

    for _ in range(50):
        x = randint(0, width)
        y = randint(0, height)
        draw.point((x, y), fill=(0, 0, 0))

    draw.line((0, 0, width, height), (0, 0, 0), width=3)
    draw.line((0, height, width, 0), (0, 0, 0), width=3)

    image = image.filter(ImageFilter.GaussianBlur(1))

    clear_captcha_cache()
    image.save(f"static/captcha/{id}.png")
    return text



if __name__ == "__main__":
    # code = generate_captcha_image("192.168.0.21")
    # print(code)
    # EmailSender().send("armankiani1384@gmail.com", generate_auth())
    pass
