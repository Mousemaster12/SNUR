import sys
from config import Config, parse_args
from service import LocalizationService
from web import start_web

def main():
    print("🎤 Starting Snur - Sound Localization (Raspberry Pi 5)")
    
    args = parse_args()
    config = Config().load(args.config)
    
    print(f"Mode: {'🟢 Simulation' if config.simulate else '🔴 Hardware'}")
    print(f"Web UI will run on http://{config.ui_bind_host}:{config.ui_bind_port}")
    
    # Start the localization service
    service = LocalizationService(config)
    service.start()
    
    try:
        # Start the web server
        start_web(service, 
                 host=config.ui_bind_host, 
                 port=config.ui_bind_port)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down Snur...")
        service.stop()
    except Exception as e:
        print(f"❌ Error: {e}")
        service.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()

