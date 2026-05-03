"""main.py -- Twin Portal server. Port 5050."""
import logging
logging.basicConfig(level=logging.INFO)
from portal.app import app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
