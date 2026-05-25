import tomllib
import smtplib
from email.mime.text import MIMEText

def test_send():
    try:
        with open(".streamlit/secrets.toml", "rb") as f:
            config = tomllib.load(f)["smtp"]
            
        print(f"Connecting to SMTP server at {config['host']}:{config['port']}...")
        
        msg = MIMEText(
            "This is a secure connection test dispatch from your laptop running the BOKU SSM-iCrop Growth Platform!\n\n"
            "If you are reading this email, your real Google SMTP mail server integration is fully functional and ready to activate new users and process password recoveries in real-time!", 
            "plain"
        )
        msg["Subject"] = "🌱 SSM-iCrop SMTP Connection Success!"
        msg["From"] = config["from_email"]
        msg["To"] = config["user"]
        
        with smtplib.SMTP(config["host"], int(config["port"]), timeout=15) as server:
            server.starttls()
            server.login(config["user"], config["password"])
            server.sendmail(config["from_email"], [config["user"]], msg.as_string())
            
        print(f"Success! A test email has been successfully dispatched to: {config['user']}")
        return True
    except Exception as e:
        print(f"Failed to send SMTP test email: {e}")
        return False

if __name__ == "__main__":
    test_send()
