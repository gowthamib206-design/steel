import logging
import sys
from ui_main import SensorGUI

def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('sensor_app.log')
        ]
    )
    return logging.getLogger(__name__)

def main():
    """Main entry point for the Wireless Sensor application"""
    logger = setup_logging()
    logger.info("Starting Wireless Sensor Data Logger Application")
    
    try:
        app = SensorGUI()
        app.mainloop()
    except Exception as e:
        logger.exception("Application crashed with an unhandled exception")
        sys.exit(1)

if __name__ == "__main__":
    main()
